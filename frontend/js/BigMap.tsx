import React, { ReactElement, memo } from "react";

import {
  Source,
  Layer,
  MapProps,
  useMap,
  ViewStateChangeEvent,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";
import { LngLatBounds, Map, Hash } from "maplibre-gl";
import { Link } from "wouter";

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
    INITIAL_VIEW_STATE: MapProps["initialViewState"];
  }
}

const updateLocalStorage = debounce(function (zoom: number, latLng) {
  try {
    localStorage.setItem("vehicleMap", `${zoom}/${latLng.lat}/${latLng.lng}`);
  } catch (e) {
    // never mind
  }
}, 2000);

if (window.INITIAL_VIEW_STATE && !window.location.hash) {
  try {
    if (localStorage.vehicleMap) {
      const parts = localStorage.vehicleMap.split("/");
      if (parts.length === 3) {
        window.INITIAL_VIEW_STATE = {
          zoom: parts[0],
          latitude: parts[1],
          longitude: parts[2],
        };
      }
    }
  } catch (e) {
    // never mind
  }
}

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
  stops?: {
    features: Stop[];
  };
  trip?: Trip;
  clickedStopUrl?: string;
  setClickedStop: (stop?: string) => void;
};

function SlippyMapHash() {
  const mapRef = useMap();

  React.useEffect(() => {
    if (mapRef.current) {
      const map = mapRef.current.getMap();
      let hash: Hash;
      if (!map._hash) {
        hash = new Hash();
        hash.addTo(map);
      }
      return () => {
        if (hash) {
          hash.remove();
        }
      };
    }
  }, [mapRef]);

  return null;
}

function Stops({ stops, trip, clickedStopUrl, setClickedStop }: StopsProps) {
  const stopsById = React.useMemo<{ [url: string]: Stop } | undefined>(() => {
    if (stops) {
      return Object.assign(
        {},
        ...stops.features.map((stop) => ({ [stop.properties.url]: stop })),
      );
    }
    if (trip) {
      return Object.assign(
        {},
        ...trip.times.map((time) => {
          const url = "/stops/" + time.stop.atco_code;
          return {
            [url]: {
              properties: { url, name: time.stop.name },
              geometry: { coordinates: time.stop.location },
            },
          };
        }),
      );
    }
  }, [stops, trip]);

  const clickedStop = stopsById && clickedStopUrl && stopsById[clickedStopUrl];

  return (
    <React.Fragment>
      {stops ? (
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
      ) : null}
      {clickedStop ? (
        <StopPopup
          item={clickedStop}
          onClose={() => setClickedStop(undefined)}
        />
      ) : null}
    </React.Fragment>
  );
}

function fetchJson(url: string) {
  return fetch(apiRoot + url).then(
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
  tripId?: string;
  clickedVehicleMarkerId?: number;
  setClickedVehicleMarker: (vehicleId?: number) => void;
};

const Vehicles = memo(function Vehicles({
  vehicles,
  tripId,
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
          selected={
            item === clickedVehicle ||
            (tripId && item.trip_id?.toString() === tripId) ||
            false
          }
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
          activeLink={
            tripId ? clickedVehicle.trip_id?.toString() === tripId : false
          }
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

function Sidebar(props: {
  trip?: Trip;
  tripId?: string;
  vehicle?: Vehicle;
  highlightedStop?: string;
}) {
  let className = "trip-timetable map-sidebar";

  const trip = props.trip;

  if (!trip) {
    return <div className={className}></div>;
  }

  if (trip.id && props.tripId !== trip.id?.toString()) {
    className += " loading";
  }

  let operator, service;
  if (trip.operator) {
    operator = (
      <li>
        <a href={`/operators/${trip.operator.slug}`}>{trip.operator.name}</a>
      </li>
    );
  }

  if (props.vehicle?.service) {
    service = (
      <li>
        <a href={props.vehicle.service.url}>
          {props.vehicle.service.line_name}
        </a>
      </li>
    );
  } else if (trip.service?.slug) {
    service = (
      <li>
        <a href={`/services/${trip.service.slug}`}>{trip.service.line_name}</a>
      </li>
    );
  }

  return (
    <div className={className}>
      {operator || service ? (
        <ul className="breadcrumb">
          {operator}
          {service}
        </ul>
      ) : null}
      <TripTimetable
        trip={trip}
        vehicle={props.vehicle}
        highlightedStop={props.highlightedStop}
      />
    </div>
  );
}

export default function BigMap(props: {
  mode: MapMode;
  noc?: string;
  trip?: Trip;
  tripId?: string;
  vehicleId?: number;
  // } & ({
  //   noc: string;
  // } | {
  //   trip: Trip;
  //   tripId: string;
  // } | {
  //   vehicleId: number;
}) {
  const mapRef = React.useRef<Map>();

  const [trip, setTrip] = React.useState<Trip | undefined>(props.trip);

  const [vehicles, setVehicles] = React.useState<Vehicle[]>();

  const [stops, setStops] = React.useState();

  const [zoom, setZoom] = React.useState<number>();

  const [clickedStopUrl, setClickedStopURL] = React.useState(() => {
    if (document.referrer) {
      const referrer = new URL(document.referrer).pathname;
      if (referrer.indexOf("/stops/") === 0) {
        return referrer;
      }
    }
  });

  const [tripVehicle, setTripVehicle] = React.useState<Vehicle>();

  const tripBounds = React.useMemo(
    function () {
      if (trip) {
        const bounds = new LngLatBounds();
        for (const item of trip.times) {
          if (item.stop.location) {
            bounds.extend(item.stop.location);
          }
        }
        if (!bounds.isEmpty()) {
          return bounds;
        }
      }
    },
    [trip],
  );

  React.useEffect(() => {
    if (mapRef.current && tripBounds) {
      mapRef.current.fitBounds(tripBounds, {
        padding: 50,
      });
    }
  }, [tripBounds]);

  const [initialViewState, setInitialViewState] = React.useState(function () {
    if (tripBounds) {
      return {
        bounds: tripBounds,
        fitBoundsOptions: {
          padding: 50,
        },
      };
    }
    return window.INITIAL_VIEW_STATE;
  });

  const timeout = React.useRef<number>();
  const boundsRef = React.useRef<LngLatBounds>();
  const stopsHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesHighWaterMark = React.useRef<LngLatBounds>();
  const vehiclesAbortController = React.useRef<AbortController>();
  const vehiclesLength = React.useRef<number>(0);

  const loadStops = React.useCallback(() => {
    const _bounds = boundsRef.current as LngLatBounds;
    setLoadingStops(true);
    fetchJson("stops.json" + getBoundsQueryString(_bounds)).then((items) => {
      stopsHighWaterMark.current = _bounds;
      setLoadingStops(false);
      setStops(items);
    });
  }, []);

  const [loadingStops, setLoadingStops] = React.useState(false);
  const [loadingBuses, setLoadingBuses] = React.useState(true);

  const loadVehicles = React.useCallback(
    (first = false) => {
      if (!first && document.hidden) {
        return;
      }
      clearTimeout(timeout.current);

      if (vehiclesAbortController.current) {
        vehiclesAbortController.current.abort();
      }
      vehiclesAbortController.current =
        new AbortController() as AbortController;

      let _bounds: LngLatBounds;
      let url: string;
      if (props.mode === MapMode.Slippy) {
        _bounds = boundsRef.current as LngLatBounds;
        if (!_bounds) {
          return;
        }
        url = getBoundsQueryString(_bounds);
      } else if (props.noc) {
        url = "?operator=" + props.noc;
      } else if (trip?.service?.id) {
        url = "?service=" + trip.service.id + "&trip=" + trip.id;
      } else if (props.vehicleId) {
        url = "?id=" + props.vehicleId;
      } else {
        return;
      }

      setLoadingBuses(true);

      return fetch(apiRoot + "vehicles.json" + url, {
        signal: vehiclesAbortController.current.signal,
      })
        .then(
          (response) => {
            if (response.ok) {
              response.json().then((items: Vehicle[]) => {
                vehiclesHighWaterMark.current = _bounds;

                if (first && !initialViewState) {
                  const bounds = new LngLatBounds();
                  for (const item of items) {
                    bounds.extend(item.coordinates);
                  }
                  setInitialViewState({
                    bounds,
                    fitBoundsOptions: {
                      padding: { top: 50, bottom: 150, left: 50, right: 50 },
                    },
                  });
                }

                if (trip && trip.id) {
                  for (const item of items) {
                    if (trip.id === item.trip_id) {
                      if (first) setClickedVehicleMarker(item.id);
                      setTripVehicle(item);
                      break;
                    }
                  }
                }

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
            // setLoadingBuses(false);
          },
        )
        .catch(() => {
          // never mind
          // setLoadingBuses(false);
        });
    },
    [props.mode, props.noc, trip, props.vehicleId, initialViewState],
  );

  React.useEffect(() => {
    // trip mode:
    if (props.tripId) {
      if (trip?.id?.toString() === props.tripId) {
        loadVehicles(true);
        document.title = `${trip.service?.line_name} \u2013 ${trip.operator?.name} \u2013 bustimes.org`;
      } else {
        fetch(`${apiRoot}api/trips/${props.tripId}/`).then((response) => {
          if (response.ok) {
            response.json().then(setTrip);
          }
        });
      }
      // operator mode:
    } else if (props.noc) {
      if (props.noc === trip?.operator?.noc) {
        document.title =
          "Bus tracker map \u2013 " +
          trip.operator.name +
          " \u2013 bustimes.org";
      }
      loadVehicles(true);
    } else if (!props.vehicleId) {
      document.title = "Map \u2013 bustimes.org";
    } else {
      loadVehicles();
    }
  }, [props.tripId, trip, props.noc, props.vehicleId, loadVehicles]);

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
    { leading: true },
  );

  React.useEffect(() => {
    const handleVisibilityChange = () => {
      if (
        !document.hidden &&
        (props.mode !== MapMode.Slippy || (zoom && shouldShowVehicles(zoom)))
      ) {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [zoom, loadVehicles, props.mode]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] = React.useState<
    number | undefined
  >(props.vehicleId);

  const handleMapClick = React.useCallback(
    (e: MapLayerMouseEvent) => {
      // handle click on VehicleMarker element
      const vehicleId = getClickedVehicleMarkerId(e);
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        setClickedStopURL(undefined);
        return;
      }

      // handle click on maplibre rendered feature
      if (e.features?.length) {
        for (const feature of e.features) {
          if (feature.layer.id === "vehicles" && feature.id) {
            setClickedVehicleMarker(feature.id as number);
            return;
          }
          if (feature.properties.url !== clickedStopUrl) {
            setClickedStopURL(feature.properties.url);
            break;
          }
        }
      } else {
        setClickedStopURL(undefined);
      }
      setClickedVehicleMarker(undefined);
    },
    [clickedStopUrl],
  );

  const handleMapInit = function (map: Map) {
    mapRef.current = map;

    if (props.mode === MapMode.Slippy) {
      const bounds = map.getBounds();
      const zoom = map.getZoom();

      if (!boundsRef.current) {
        // first load
        boundsRef.current = bounds;

        if (shouldShowVehicles(zoom)) {
          loadVehicles();

          if (shouldShowStops(zoom)) {
            loadStops();
          }
        } else {
          boundsRef.current = bounds;
        }
      } else {
        setLoadingBuses(false);
      }
      setZoom(zoom);
    }
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

  if (props.mode === MapMode.Operator) {
    if (!vehicles) {
      return <div className="sorry">Loading…</div>;
    }
    if (!vehiclesLength.current) {
      return (
        <div className="sorry">Sorry, no buses are tracking at the moment</div>
      );
    }
  }

  let className = "big-map";
  if (props.mode === MapMode.Trip) {
    className += " has-sidebar";
  }

  return (
    <React.Fragment>
      {props.mode === MapMode.Slippy ? null : (
        <Link className="map-link" href="/map">
          Map
        </Link>
      )}
      <div className={className}>
        <BusTimesMap
          initialViewState={initialViewState}
          onMoveEnd={props.mode === MapMode.Slippy ? handleMoveEnd : undefined}
          hash={props.mode === MapMode.Slippy}
          onClick={handleMapClick}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          cursor={cursor}
          onMapInit={handleMapInit}
          interactiveLayerIds={["stops", "vehicles"]}
        >
          {props.mode === MapMode.Trip && trip ? (
            <Route times={trip.times} />
          ) : null}

          {props.mode === MapMode.Slippy ? <SlippyMapHash /> : null}

          {trip || (stops && showStops) ? (
            <Stops
              stops={props.mode === MapMode.Slippy ? stops : undefined}
              trip={props.mode === MapMode.Trip ? trip : undefined}
              setClickedStop={setClickedStopURL}
              clickedStopUrl={clickedStopUrl}
            />
          ) : null}

          {vehicles && showBuses ? (
            <Vehicles
              vehicles={vehicles}
              tripId={props.tripId}
              clickedVehicleMarkerId={clickedVehicleMarkerId}
              setClickedVehicleMarker={setClickedVehicleMarker}
            />
          ) : null}

          {zoom &&
          ((props.mode === MapMode.Slippy && !showStops) ||
            loadingBuses ||
            loadingStops) ? (
            <div className="maplibregl-ctrl map-status-bar">
              {props.mode === MapMode.Slippy && !showStops
                ? "Zoom in to see stops"
                : null}
              {!showBuses ? <div>Zoom in to see buses</div> : null}
              {loadingBuses || loadingStops ? <div>Loading…</div> : null}
            </div>
          ) : null}
        </BusTimesMap>
      </div>

      {props.mode === MapMode.Trip ? (
        <Sidebar
          trip={trip}
          tripId={props.tripId}
          vehicle={tripVehicle}
          highlightedStop={clickedStopUrl}
        />
      ) : null}
    </React.Fragment>
  );
}
