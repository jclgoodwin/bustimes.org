import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

import VehicleMarker from "./VehicleMarker";
// import StopMarker from "./StopMarker";
import VehiclePopup from "./VehiclePopup";
import StopPopup from "./StopPopup";

import { useDarkMode } from "./utils";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function getBoundsQueryString(bounds) {
  return `?ymax=${bounds.getNorth()}&xmax=${bounds.getEast()}&ymin=${bounds.getSouth()}&xmin=${bounds.getWest()}`;
}

function containsBounds(a, b) {
  return a?.contains(b.getNorthWest()) && a.contains(b.getSouthEast());
}

// const stopsLayerStyle = {
//   id: "stops",

//   minzoom: 12,
//   maxzoom: 15,

//   // type: "circle",
//   // paint: {
//   //   "circle-color": "#333",
//   //   "circle-opacity": 0.5,
//   //   "circle-radius": 3,
//   // },

//   type: "symbol",
//   layout: {
//     // "text-field": ["get", "icon"],
//     // "text-font": ["Stadia Regular"],
//     // "text-allow-overlap": true,
//     // "text-size": 10,
//     "icon-rotate": ["get", "bearing"],
//     "icon-image": "rail",
//     "icon-size": 0.5,
//     "icon-allow-overlap": true,
//   }
// };

// const redBusesStyle = {
//   id: "vehicles",
//   type: "symbol",
//   layout: {
//     "icon-rotate": ["to-number", ["get", "heading"]],
//     "icon-image": "vehicle",
//     "icon-size": 0.5,
//     "icon-allow-overlap": true,
//     "icon-offset": [0, -6],
//   },
// };

function shouldShowStops(zoom) {
  return zoom >= 14;
}

function shouldShowVehicles(zoom) {
  return zoom >= 10;
}

export default function BigMap() {
  const darkMode = useDarkMode();

  // const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [zoom, setZoom] = React.useState(null);

  const [clickedStopId, setClickedStopId] = React.useState(null);

  const [stopsHighWaterMark, setStopsHighWaterMark] = React.useState(null);

  const [vehiclesHighWaterMark, setVehiclesHighWaterMark] =
    React.useState(null);

  const loadStops = React.useCallback((bounds) => {
    const url = "/stops.json" + getBoundsQueryString(bounds);

    fetch(url).then((response) => {
      response.json().then((items) => {
        setStops(items);
        setStopsHighWaterMark(bounds);
      });
    });
  }, []);

  const loadVehicles = React.useCallback((bounds) => {
    const url = apiRoot + "vehicles.json" + getBoundsQueryString(bounds);

    fetch(url).then((response) => {
      response.json().then((items) => {
        setVehicles(
          Object.assign({}, ...items.map((item) => ({ [item.id]: item }))),
        );
        setVehiclesHighWaterMark(bounds);
      });
    });
  }, []);

  const handleMoveEnd = (evt) => {
    const map = evt.target;
    const zoom = map.getZoom();

    setZoom(zoom);

    if (shouldShowVehicles(zoom)) {
      const bounds = map.getBounds();

      if (!containsBounds(vehiclesHighWaterMark, bounds)) {
        loadVehicles(bounds);
      }

      if (
        shouldShowStops(zoom) &&
        !containsBounds(stopsHighWaterMark, bounds)
      ) {
        loadStops(bounds);
      }
    }
  };

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleVehicleMarkerClick = React.useCallback((event, id) => {
    event.originalEvent.preventDefault();
    setClickedVehicleMarker(id);
  }, []);

  const handleMapClick = React.useCallback((e) => {
    if (e.features?.length) {
      if (e.features[0].layer.id === "stops") {
        setClickedStopId(e.features[0]);
      } else {
        setClickedVehicleMarker(e.features[0].id);
      }
    } else if (!e.originalEvent.defaultPrevented) {
      setClickedStopId(null);
      setClickedVehicleMarker(null);
    }
  }, []);

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    const zoom = map.getZoom();

    setZoom(zoom);

    if (shouldShowStops(zoom)) {
      let bounds = map.getBounds();
      loadStops(bounds);
      loadVehicles(bounds);
    } else if (shouldShowVehicles(zoom)) {
      let bounds = map.getBounds();
      loadVehicles(bounds);
    }

    map.loadImage("/static/root/stop-marker.png", (error, image) => {
      if (error) throw error;
      map.addImage("stop", image, {
        pixelRatio: 2,
        width: 16,
        height: 16,
      });
    });

    // map.loadImage("/static/svg/bus.png", function (error, image) {
    //   if (error) {
    //     throw error;
    //   } else {
    //     map.addImage("vehiclle", image);
    //   }
    // });
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

      {/*showStops &&
        stops?.features.map((item) => {
          return (
            <StopMarker
              key={item.properties.url}
              stop={item}
              onClick={setClickedStopId}
            />
          );
        })*/}

      {showStops ? (
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

      {clickedStopId && (
        <StopPopup
          item={clickedStopId}
          onClose={() => setClickedStopId(null)}
        />
      )}
    </Map>
  );
}
[];
