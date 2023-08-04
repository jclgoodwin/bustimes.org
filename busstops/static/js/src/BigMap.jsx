import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";
import StopPopup from "./StopPopup";

import { useDarkMode } from "./utils";

const apiRoot = process.env.API_ROOT;

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
  return zoom >= 10;
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
              "icon-padding": 0,
              "icon-allow-overlap": true,
              "icon-ignore-placement": true,
              "text-ignore-placement": true,
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

  return fetch(url).then((response) => {
    if (response.ok) {
      return response.json();
    }
  });
}

export default function BigMap() {
  const darkMode = useDarkMode();

  // const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [zoom, setZoom] = React.useState(null);

  const [clickedStop, setClickedStop] = React.useState(null);

  const [bounds, setBounds] = React.useState(null);

  const [stopsHighWaterMark, setStopsHighWaterMark] = React.useState(null);

  const [vehiclesHighWaterMark, setVehiclesHighWaterMark] =
    React.useState(null);

  const loadStops = React.useCallback((bounds) => {
    fetchJson("stops", bounds).then((items) => {
      setStopsHighWaterMark(bounds);
      setStops(items);
    });
  }, []);

  const handleMoveEnd = React.useCallback(
    (evt) => {
      const map = evt.target;

      const bounds = map.getBounds();
      const zoom = map.getZoom();

      setZoom(zoom);
      setBounds(bounds);

      if (
        shouldShowStops(zoom) &&
        !containsBounds(stopsHighWaterMark, bounds)
      ) {
        loadStops(bounds);
      }
    },
    [stopsHighWaterMark],
  );

  React.useEffect(() => {
    if (!(bounds && zoom)) {
      return;
    }

    let timeout;
    let controller = new AbortController();

    const loadVehicles = () => {
      if (!shouldShowVehicles(zoom)) {
        return;
      }

      const url = apiRoot + "vehicles.json" + getBoundsQueryString(bounds);

      fetch(url, {
        signal: controller.signal,
      }).then((response) => {
        response.json().then((items) => {
          setVehiclesHighWaterMark(bounds);
          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item }))),
          );
        });

        timeout = setTimeout(loadVehicles, 12000);
      });
    };

    if (shouldShowVehicles(zoom)) {
      if (!containsBounds(vehiclesHighWaterMark, bounds)) {
        loadVehicles();
      } else {
        timeout = setTimeout(loadVehicles, 12000);
      }
    }

    const handleVisibilityChange = (event) => {
      if (shouldShowVehicles(zoom)) {
        if (event.target.hidden) {
          clearTimeout(timeout);
          controller.abort();
        } else {
          loadVehicles();
        }
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
      controller.abort();
    };
  }, [zoom, bounds, vehiclesHighWaterMark]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleVehicleMarkerClick = React.useCallback((event, id) => {
    event.originalEvent.preventDefault();
    setClickedStop(null);
    setClickedVehicleMarker(id);
  }, []);

  const handleMapClick = React.useCallback(
    (e) => {
      if (!e.originalEvent.defaultPrevented) {
        if (e.features.length) {
          for (const stop of e.features) {
            if (stop.properties.url !== clickedStop) {
              setClickedStop(stop.properties.url);
            }
          }
        } else {
          setClickedStop(null);
        }
        setClickedVehicleMarker(null);
      }
    },
    [clickedStop],
  );

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    const zoom = map.getZoom();
    const bounds = map.getBounds();

    setZoom(zoom);
    setBounds(bounds);

    if (shouldShowStops(zoom)) {
      loadStops(bounds);
    }

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

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  let vehiclesList = vehicles ? Object.values(vehicles) : [];

  // const otherVehicles = vehiclesList.filter((i) => {
  //   return i.vehicle.livery === 262 || i.id === clickedVehicleMarkerId;
  // });
  // if (otherVehicles.length) {
  //   vehiclesList = vehiclesList.filter((i) => {
  //     return i.vehicle.livery != 262;
  //   });
  // }
  // const otherVehicles = vehiclesList;
  // vehiclesList = [];

  const showStops = shouldShowStops(zoom);
  const showBuses = shouldShowVehicles(zoom);

  return (
    <Map
      initialViewState={window.INITIAL_VIEW_STATE}
      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
      showCollisionBoxes={true}
      pitchWithRotate={false}
      onMoveEnd={handleMoveEnd}
      minZoom={6}
      maxZoom={16}
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
      interactiveLayerIds={["stops"]}
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

      {showBuses
        ? vehiclesList.map((item) => {
            return (
              <VehicleMarker
                key={item.id}
                selected={item.id === clickedVehicleMarkerId}
                vehicle={item}
                onClick={handleVehicleMarkerClick}
              />
            );
          })
        : null}

      {/*otherVehicles ? (
        <Source
          type="geojson"
          data={{
            type: "FeatureCollection",
            features: otherVehicles.map((item) => {
              return {
                type: "Feature",
                id: item.id,
                geometry: {
                  type: "Point",
                  coordinates: item.coordinates,
                },
                properties: {
                  heading: item.heading,
                },
              };
            }),
          }}
        >
          <Layer {...redBusesStyle} />
        </Source>
      ) : null*/}

      {zoom && !showStops ? (
        <div className="maplibregl-ctrl map-status-bar">
          Zoom in to see stops
          {!showBuses ? <div>Zoom in to see buses</div> : null}
        </div>
      ) : null}

      {clickedVehicle && (
        <VehiclePopup
          item={clickedVehicle}
          onClose={() => setClickedVehicleMarker(null)}
        />
      )}
    </Map>
  );
}
[];
