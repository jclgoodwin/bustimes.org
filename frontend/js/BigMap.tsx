import React, { ReactElement, memo } from "react";

import {
  Source,
  Layer,
  ViewState,
  useMap,
  ViewStateChangeEvent,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import { LngLatBounds, Map, Hash, MapLibreEvent } from "maplibre-gl";

import debounce from "lodash/debounce";

import VehicleMarker, {
  Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";

import VehiclePopup from "./VehiclePopup";
import StopPopup, { Stop } from "./StopPopup";
import BusTimesMap from "./Map";
import { Route } from "./TripMap";
import TripTimetable, { Trip } from "./TripTimetable";

const apiRoot = process.env.API_ROOT;

declare global {
  interface Window {
    INITIAL_VIEW_STATE: Partial<ViewState> & {
      zoom: number;
      latitude: number;
      longitude: number;
    };
  }
}

const updateLocalStorage = debounce(function (zoom: number, latLng) {
  try {
    localStorage.setItem("vehicleMap", `${zoom}/${latLng.lat}/${latLng.lng}`);
  } catch (e) {
    // never mind
  }
}, 2000);

function getBoundsQueryString(bounds: LngLatBounds): string {
  return `?ymax=${bounds.getNorth()}&xmax=${bounds.getEast()}&ymin=${bounds.getSouth()}&xmin=${bounds.getWest()}`;
}

function containsBounds(
  a: LngLatBounds | undefined,
  b: LngLatBounds,
): boolean | undefined {
  return a && a.contains(b.getNorthWest()) && a.contains(b.getSouthEast());
}

function shouldShowStops(zoom?: number) {
  return zoom && zoom >= 14;
}

function shouldShowVehicles(zoom?: number) {
  return zoom && zoom >= 6;
}

export enum MapMode {
  Slippy,
  Operator,
  Trip,
}

type StopsProps = {
  stops: {
    features: Stop[];
  };
  clickedStopUrl?: string;
  setClickedStop: (stop?: string) => void;
};

function SlippyMapHash() {
  const mapRef = useMap();

  React.useEffect(() => {
    if (mapRef.current) {
      const map = mapRef.current.getMap();
      const hash = map._hash || new Hash();
      hash.addTo(map);
      return () => {
        hash.remove();
      };
    }
  }, [mapRef]);

  return null;
}

function Stops({ stops, clickedStopUrl, setClickedStop }: StopsProps) {
  const stopsById = React.useMemo<{ [url: string]: Stop }>(() => {
    return Object.assign(
      {},
      ...stops.features.map((stop) => ({ [stop.properties.url]: stop })),
    );
  }, [stops]);

  const clickedStop = clickedStopUrl && stopsById[clickedStopUrl];

  return (
    <React.Fragment>
      <Source type="geojson" data={stops}>
        <Layer
          {...{
            id: "stops",
            type: "symbol",
            minzoom: 14,
            layout: {
              "text-field": ["get", "icon"],
              "text-font": ["Stadia Regular"],
              "text-allow-overlap": true,
              "text-size": 10,
              "icon-rotate": ["+", 45, ["get", "bearing"]],
              "icon-image": "stop-marker",
              "icon-allow-overlap": true,
              "icon-ignore-placement": true,
              "text-ignore-placement": true,
              "icon-padding": [3],
            },
            paint: {
              "text-color": "#ffffff",
            },
          }}
        />
      </Source>
      {clickedStop ? (
        <StopPopup
          item={clickedStop}
          onClose={() => setClickedStop(undefined)}
        />
      ) : null}
    </React.Fragment>
  );
}

function fetchJson(what: string, bounds: LngLatBounds) {
  const url = apiRoot + what + ".json" + getBoundsQueryString(bounds);

  return fetch(url).then(
    (response) => {
      if (response.ok) {
        return response.json();
      }
    },
    () => {
      // never mind
    },
  );
}

type VehiclesProps = {
  vehicles: Vehicle[];
  clickedVehicleMarkerId?: number;
  setClickedVehicleMarker: (vehicleId?: number) => void;
};

const Vehicles = memo(function Vehicles({
  vehicles,
  clickedVehicleMarkerId,
  setClickedVehicleMarker,
}: VehiclesProps) {
  const vehiclesById = React.useMemo<{ [id: string]: Vehicle }>(() => {
    return Object.assign({}, ...vehicles.map((item) => ({ [item.id]: item })));
  }, [vehicles]);

  const vehiclesGeoJson = React.useMemo(() => {
    if (vehicles.length < 1000) {
      return null;
    }
    return {
      type: "FeatureCollection",
      features: vehicles
        ? vehicles.map((vehicle) => {
            return {
              type: "Feature",
              id: vehicle.id,
              geometry: {
                type: "Point",
                coordinates: vehicle.coordinates,
              },
              properties: {
                url: vehicle.vehicle?.url,
                colour:
                  vehicle.vehicle?.colour ||
                  (vehicle.vehicle?.css?.length === 7
                    ? vehicle.vehicle.css
                    : "#fff"),
              },
            };
          })
        : [],
    };
  }, [vehicles]);

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  let markers: ReactElement[] | ReactElement;

  if (!vehiclesGeoJson) {
    markers = vehicles.map((item) => {
      return (
        <VehicleMarker
          key={item.id}
          selected={item === clickedVehicle}
          vehicle={item}
        />
      );
    });
  } else {
    markers = (
      <Source type="geojson" data={vehiclesGeoJson}>
        <Layer
          {...{
            id: "vehicles",
            type: "circle",
            paint: {
              "circle-color": ["get", "colour"],
            },
          }}
        />
      </Source>
    );
  }

  return (
    <React.Fragment>
      {markers}
      {clickedVehicle && (
        <VehiclePopup
          item={clickedVehicle}
          onClose={() => setClickedVehicleMarker()}
          snazzyTripLink
        />
      )}
      {clickedVehicle && vehiclesGeoJson && (
        <VehicleMarker selected={true} vehicle={clickedVehicle} />
      )}
    </React.Fragment>
  );
});

export default function BigMap(props: {
  mode: MapMode;
  noc?: string;
  trip?: Trip;
  tripId?: string;
}) {
  const mapRef = React.useRef<Map>();

  const [vehicles, setVehicles] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [zoom, setZoom] = React.useState<number>();

  const [clickedStop, setClickedStop] = React.useState(() => {
    if (document.referrer) {
      const referrer = new URL(document.referrer).pathname;
      if (referrer.indexOf("/stops/") === 0) {
        return referrer;
      }
    }
  });

  const timeout = React.useRef<number>();
  const boundsRef = React.useRef<LngLatBounds>();
  const stopsHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesAbortController = React.useRef<AbortController>();
  const vehiclesLength = React.useRef<number>(0);

  // trip mode
  const [trip, setTrip] = React.useState<Trip | undefined>(props.trip);

  React.useEffect(() => {
    if (trip?.id?.toString() === props.tripId) {
      return;
    }
    fetch(`${apiRoot}api/trips/${props.tripId}/`).then((response) => {
      if (response.ok) {
        response.json().then(setTrip);
      }
    });
  }, [props.tripId, trip]);

  const bounds = React.useMemo((): LngLatBounds | undefined => {
    if (trip) {
      const _bounds = new LngLatBounds();
      for (const item of trip.times) {
        if (item.stop.location) {
          _bounds.extend(item.stop.location);
        }
      }
      return _bounds;
    }
  }, [trip]);

  React.useEffect(() => {
    if (bounds && mapRef.current) {
      mapRef.current.fitBounds(bounds, {
        padding: 50,
      });
    }
  }, [bounds]);

  const loadStops = React.useCallback(() => {
    const _bounds = boundsRef.current as LngLatBounds;
    setLoadingStops(true);
    fetchJson("stops", _bounds).then((items) => {
      stopsHighWaterMark.current = _bounds;
      setLoadingStops(false);
      setStops(items);
    });
  }, []);

  const [loadingStops, setLoadingStops] = React.useState(false);
  const [loadingBuses, setLoadingBuses] = React.useState(true);

  const loadVehicles = React.useCallback(() => {
    if (document.hidden) {
      return;
    }
    clearTimeout(timeout.current);

    if (vehiclesAbortController.current) {
      vehiclesAbortController.current.abort();
    }
    vehiclesAbortController.current = new AbortController() as AbortController;

    let _bounds: LngLatBounds;
    let url: string;
    if (props.mode === MapMode.Slippy) {
      _bounds = boundsRef.current as LngLatBounds;
      url = apiRoot + "vehicles.json" + getBoundsQueryString(_bounds);
    } else if (props.noc) {
      url = apiRoot + "vehicles.json?operator=" + props.noc;
    } else if (trip?.service?.id) {
      url =
        apiRoot +
        "vehicles.json?service=" +
        trip.service.id +
        "&trip=" +
        trip.id;
    } else {
      return;
    }

    setLoadingBuses(true);

    fetch(url, {
      signal: vehiclesAbortController.current.signal,
    })
      .then(
        (response) => {
          if (response.ok) {
            response.json().then((items) => {
              vehiclesHighWaterMark.current = _bounds;
              vehiclesLength.current = items.length;
              setVehicles(items);
            });
          }
          setLoadingBuses(false);
          if (!document.hidden) {
            timeout.current = window.setTimeout(loadVehicles, 12000); // 12 seconds
          }
        },
        () => {
          // never mind
          setLoadingBuses(false);
        },
      )
      .catch(() => {
        // never mind
        setLoadingBuses(false);
      });
  }, [props.mode, props.noc, trip]);

  const handleMoveEnd = debounce(
    React.useCallback(
      (evt: ViewStateChangeEvent) => {
        const map = evt.target;
        boundsRef.current = map.getBounds() as LngLatBounds;
        const zoom = map.getZoom() as number;

        if (shouldShowVehicles(zoom)) {
          if (
            !containsBounds(vehiclesHighWaterMark.current, boundsRef.current) ||
            vehiclesLength.current >= 1000
          ) {
            loadVehicles();
          }

          if (
            shouldShowStops(zoom) &&
            !containsBounds(stopsHighWaterMark.current, boundsRef.current)
          ) {
            loadStops();
          }
        }

        setZoom(zoom);
        updateLocalStorage(zoom, map.getCenter());
      },
      [loadStops, loadVehicles],
    ),
    400,
    {
      leading: true,
    },
  );

  React.useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && zoom && shouldShowVehicles(zoom)) {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [zoom, loadVehicles]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState<number>();

  const handleMapClick = React.useCallback(
    (e: MapLayerMouseEvent) => {
      // handle click on VehicleMarker element
      const vehicleId = getClickedVehicleMarkerId(e);
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        setClickedStop(undefined);
        return;
      }

      // handle click on maplibre rendered feature
      if (e.features?.length) {
        for (const feature of e.features) {
          if (feature.layer.id === "vehicles" && feature.id) {
            setClickedVehicleMarker(feature.id as number);
            return;
          }
          if (feature.properties.url !== clickedStop) {
            setClickedStop(feature.properties.url);
            break;
          }
        }
      } else {
        setClickedStop(undefined);
      }
      setClickedVehicleMarker(undefined);
    },
    [clickedStop],
  );

  const handleMapLoad = function (event: MapLibreEvent) {
    const map = event.target;
    mapRef.current = map;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
    // map.showPadding = true;
    // map.showCollisionBoxes = true;
    // map.showTileBoundaries = true;

    boundsRef.current = map.getBounds();
    const zoom = map.getZoom();

    if (shouldShowVehicles(zoom)) {
      loadVehicles();

      if (props.mode === MapMode.Slippy) {
        if (shouldShowStops(zoom)) {
          loadStops();
        }
      }
    } else {
      setLoadingBuses(false);
    }
    setZoom(zoom);
  };

  const [cursor, setCursor] = React.useState("");

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor("");
  }, []);

  const showStops = shouldShowStops(zoom);
  const showBuses = props.mode != MapMode.Slippy || shouldShowVehicles(zoom);

  const initialViewState = React.useMemo(() => {
    if (props.mode === MapMode.Slippy) {
      try {
        if (localStorage.vehicleMap && !window.location.hash) {
          const parts = localStorage.vehicleMap.split("/");
          if (parts.length === 3) {
            return {
              zoom: +parts[0],
              latitude: +parts[1],
              longitude: +parts[2],
            };
          }
        }
      } catch (e) {
        // ok
      }
      return window.INITIAL_VIEW_STATE;
    } else if (props.mode === MapMode.Trip) {
      return {
        bounds: bounds,
        fitBoundsOptions: {
          padding: 50,
        },
      };
    } else {
      return {
        bounds: bounds,
        fitBoundsOptions: {
          maxZoom: 15,
          padding: 50,
        },
      };
    }
  }, [bounds, props.mode]);

  return (
    <React.Fragment>
      <BusTimesMap
        initialViewState={initialViewState}
        onMoveEnd={props.mode === MapMode.Slippy ? handleMoveEnd : undefined}
        hash={props.mode === MapMode.Slippy}
        onClick={handleMapClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        cursor={cursor}
        onLoad={handleMapLoad}
        images={["stop-marker"]}
        interactiveLayerIds={["stops", "vehicles"]}
      >
        {props.mode === MapMode.Trip && trip ? (
          <Route times={trip.times} />
        ) : null}

        {props.mode === MapMode.Slippy ? <SlippyMapHash /> : null}

        {props.mode === MapMode.Slippy && stops && showStops ? (
          <Stops
            stops={stops}
            setClickedStop={setClickedStop}
            clickedStopUrl={clickedStop}
          />
        ) : null}

        {vehicles && showBuses ? (
          <Vehicles
            vehicles={vehicles}
            clickedVehicleMarkerId={clickedVehicleMarkerId}
            setClickedVehicleMarker={setClickedVehicleMarker}
          />
        ) : null}

        {zoom && (!showStops || loadingBuses || loadingStops) ? (
          <div className="maplibregl-ctrl map-status-bar">
            {props.mode === MapMode.Slippy && !showStops
              ? "zoooom in to see stops"
              : null}
            {!showBuses ? <div>Zooerofdgxoooom in to see buses</div> : null}
            {loadingBuses || loadingStops ? <div>Loading…</div> : null}
          </div>
        ) : null}
      </BusTimesMap>

      {props.mode === MapMode.Trip ? (
        <div className="trip-timetable map-sidebar">
          {trip ? <TripTimetable trip={trip} /> : null}
        </div>
      ) : null}
    </React.Fragment>
  );
}
