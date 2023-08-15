import React, { memo } from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";
import debounce from "lodash/debounce";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";
import StopPopup from "./StopPopup";

import { useDarkMode } from "./utils";

const apiRoot = process.env.API_ROOT;

try {
  if (localStorage.vehicleMap) {
    var parts = localStorage.vehicleMap.split("/");
    if (parts.length === 3) {
      window.INITIAL_VIEW_STATE = {
        zoom: +parts[0],
        latitude: +parts[1],
        longitude: +parts[2],
      };
    }
  }
} catch (e) {
  // ok
}

const updateLocalStorage = debounce(function (zoom, latLng) {
  localStorage.setItem("vehicleMap", `${zoom}/${latLng.lat}/${latLng.lng}`);
}, 2000);

function getBoundsQueryString(bounds) {
  return `?ymax=${bounds.getNorth()}&xmax=${bounds.getEast()}&ymin=${bounds.getSouth()}&xmin=${bounds.getWest()}`;
}

function containsBounds(a, b) {
  return a?.contains(b.getNorthWest()) && a.contains(b.getSouthEast());
}

function shouldShowStops(zoom) {
  return zoom >= 14;
}

function shouldShowVehicles(zoom) {
  return zoom >= 6;
}

function Stops({ stops, clickedStopUrl, setClickedStop }) {
  const stopsById = React.useMemo(() => {
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
              "icon-image": "stop",
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
        <StopPopup item={clickedStop} onClose={() => setClickedStop(null)} />
      ) : null}
    </React.Fragment>
  );
}

function fetchJson(what, bounds) {
  const url = "/" + what + ".json" + getBoundsQueryString(bounds);

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

const Vehicles = memo(function Vehicles({
  vehicles,
  clickedVehicleMarkerId,
  setClickedVehicleMarker,
}) {
  const vehiclesById = React.useMemo(() => {
    return Object.assign({}, ...vehicles.map((item) => ({ [item.id]: item })));
  }, [vehicles]);

  const vehiclesGeoJson = React.useMemo(() => {
    if (vehicles.length < 1000) {
      return;
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
                url: vehicle.vehicle.url,
                colour:
                  vehicle.vehicle.colour ||
                  (vehicle.vehicle.colours?.length === 7
                    ? vehicle.vehicle.colours
                    : "#fff"),
              },
            };
          })
        : [],
    };
  }, [vehicles]);

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  let markers;

  if (!vehiclesGeoJson) {
    markers = vehicles.map((item) => {
      return (
        <VehicleMarker
          key={item.id}
          selected={item.id === clickedVehicleMarkerId}
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
          onClose={() => setClickedVehicleMarker(null)}
        />
      )}
      {clickedVehicle && vehiclesGeoJson && (
        <VehicleMarker selected={true} vehicle={clickedVehicle} />
      )}
    </React.Fragment>
  );
});

export default function BigMap() {
  const darkMode = useDarkMode();

  const [vehicles, setVehicles] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [zoom, setZoom] = React.useState(null);

  const [clickedStop, setClickedStop] = React.useState(() => {
    if (document.referrer) {
      const referrer = new URL(document.referrer).pathname;
      if (referrer.indexOf("/stops/") === 0) {
        return referrer;
      }
    }
  });

  const timeout = React.useRef(null);
  const bounds = React.useRef(null);
  const stopsHighWaterMark = React.useRef(null);
  const vehiclesHighWaterMark = React.useRef(null);
  const vehiclesAbortController = React.useRef(null);
  const vehiclesLength = React.useRef(null);

  const loadStops = React.useCallback(() => {
    const _bounds = bounds.current;
    fetchJson("stops", _bounds).then((items) => {
      stopsHighWaterMark.current = _bounds;
      setStops(items);
    });
  }, []);

  const loadVehicles = React.useCallback(() => {
    if (document.hidden) {
      return;
    }

    if (vehiclesAbortController.current) {
      vehiclesAbortController.current.abort();
    }
    vehiclesAbortController.current = new AbortController();

    clearTimeout(timeout.current);

    let _bounds = bounds.current;

    const url = apiRoot + "vehicles.json" + getBoundsQueryString(_bounds);

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
          if (!document.hidden) {
            timeout.current = setTimeout(loadVehicles, 12000); // 12 seconds
          }
        },
        () => {
          // never mind
        },
      )
      .catch(() => {
        // never mind
      });
  }, []);

  const handleMoveEnd = React.useCallback(
    debounce(
      (evt) => {
        const map = evt.target;
        bounds.current = map.getBounds();
        const zoom = map.getZoom();

        if (shouldShowVehicles(zoom)) {
          if (
            !containsBounds(vehiclesHighWaterMark.current, bounds.current) ||
            vehiclesLength.current >= 1000
          ) {
            loadVehicles();
          }

          if (
            shouldShowStops(zoom) &&
            !containsBounds(stopsHighWaterMark.current, bounds.current)
          ) {
            loadStops();
          }
        }

        setZoom(zoom);
        updateLocalStorage(zoom, map.getCenter());
      },
      400,
      {
        leading: true,
      },
    ),
    [],
  );

  React.useEffect(() => {
    const handleVisibilityChange = (event) => {
      if (!event.target.hidden && shouldShowVehicles(zoom)) {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [zoom]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleMapClick = React.useCallback(
    (e) => {
      const srcElement = e.originalEvent.srcElement;
      const vehicleId =
        srcElement.dataset.vehicleId || srcElement.parentNode.dataset.vehicleId;
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        return;
      }

      if (e.features.length) {
        for (const feature of e.features) {
          if (feature.layer.id === "vehicles") {
            setClickedVehicleMarker(feature.id);
            return;
          }
          if (feature.properties.url !== clickedStop) {
            setClickedStop(feature.properties.url);
            break;
          }
        }
      } else {
        setClickedStop(null);
      }
      setClickedVehicleMarker(null);
    },
    [clickedStop],
  );

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
    // map.showPadding = true;
    // map.showCollisionBoxes = true;
    // map.showTileBoundaries = true;

    bounds.current = map.getBounds();
    const zoom = map.getZoom();

    if (shouldShowVehicles(zoom)) {
      loadVehicles();
      if (shouldShowStops(zoom)) {
        loadStops();
      }
    }
    setZoom(zoom);

    map.loadImage("/static/stop-marker.png", (error, image) => {
      if (error) throw error;
      map.addImage("stop", image, {
        pixelRatio: 2,
        width: 16,
        height: 16,
      });
    });
  }, []);

  const [cursor, setCursor] = React.useState(null);

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
  }, []);

  const showStops = shouldShowStops(zoom);
  const showBuses = shouldShowVehicles(zoom);

  return (
    <Map
      padding={0}
      initialViewState={window.INITIAL_VIEW_STATE}
      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
      pitchWithRotate={false}
      onMoveEnd={handleMoveEnd}
      minZoom={5}
      maxZoom={18}
      mapStyle={
        darkMode
          ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
          : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      }
      hash={true}
      RTLTextPlugin={null}
      onClick={handleMapClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      cursor={cursor}
      onLoad={handleMapLoad}
      interactiveLayerIds={["stops", "vehicles"]}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

      {stops && showStops ? (
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

      {zoom && !showStops ? (
        <div className="maplibregl-ctrl map-status-bar">
          Zoom in to see stops
          {!showBuses ? <div>Zoom in to see buses</div> : null}
        </div>
      ) : null}
    </Map>
  );
}
[];
