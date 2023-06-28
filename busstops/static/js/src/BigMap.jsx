import React from "react";
import ReactDOM from "react-dom/client";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

import VehicleMarker from "./VehicleMarker";
import StopMarker from "./StopMarker";
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

export default function BigMap() {
  const darkMode = useDarkMode();

  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [zoom, setZoom] = React.useState(null);

  const [clickedStopId, setClickedStopId] = React.useState(null);

  const [stopsHighWaterMark, setStopsHighWaterMark] = React.useState(null);

  const [vehiclesHighWaterMark, setVehiclesHighWaterMark] = React.useState(null);

  const loadStops = React.useCallback((bounds) => {
    const url = apiRoot + "stops.json" + getBoundsQueryString(bounds);

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
          Object.assign({}, ...items.map((item) => ({ [item.id]: item })))
        );
        setVehiclesHighWaterMark(bounds);
      });
    });
  }, []);


  const handleMoveEnd = (evt) => {
    const map = evt.target;
    const zoom = map.getZoom();

    setZoom(zoom);

    if (zoom > 8) {
      const bounds = map.getBounds();

      if (!containsBounds(vehiclesHighWaterMark, bounds)) {
        loadVehicles(bounds);
      }

      if (zoom >= 12 && !containsBounds(stopsHighWaterMark, bounds)) {
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
      setClickedStopId(e.features[0]);
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

    if (zoom >= 12) {
      let bounds = map.getBounds();
      loadStops(bounds);
      loadVehicles(bounds);
    }

    // map.loadImage("/static/svg/pointy.png", function (error, image) {
    //   debugger;
    //   if (error) {
    //     throw error;
    //   } else {
    //     map.addImage("rail", image);
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

  const vehiclesList = vehicles ? Object.values(vehicles) : [];


  const showStops = zoom >= 12;

  return (
    <Map
      initialViewState={window.INITIAL_VIEW_STATE}

      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
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
      // interactiveLayerIds={["stops"]}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

      {showStops && stops?.features.map((item) => {
        return (
          <StopMarker
            key={item.properties.url}
            stop={item}
            onClick={setClickedStopId}
          />
        );
      })}

      {vehiclesList.map((item) => {
        return (
          <VehicleMarker
            key={item.id}
            selected={item.id === clickedVehicleMarkerId}
            vehicle={item}
            onClick={handleVehicleMarkerClick}
          />
        );
      })}

      {zoom && !showStops ? (
        <div className="maplibregl-ctrl">
          <div>Zoom in to see stops</div>
          {zoom < 8 ? (
            <div>Zoom in to see buses</div>
          ) : null}
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
