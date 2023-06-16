import React from "react";
import ReactDOM from "react-dom/client";

import Map, {
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";
import { LngLatBounds } from "maplibre-gl";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function getBounds(items) {
  let bounds = new LngLatBounds();
  for (let item of items) {
    bounds.extend(item.coordinates);
  }
  return bounds;
}

function OperatorMap() {
  // dark mode:

  const [darkMode, setDarkMode] = React.useState(false);

  React.useEffect(() => {
    if (window.matchMedia) {
      let query = window.matchMedia("(prefers-color-scheme: dark)");
      if (query.matches) {
        setDarkMode(true);
      }

      const handleChange = (e) => {
        setDarkMode(e.matches);
      };

      query.addEventListener("change", handleChange);

      return () => {
        query.removeEventListener("change", handleChange);
      };
    }
  }, []);

  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [bounds, setBounds] = React.useState(null);

  let timeout;

  React.useEffect(() => {
    const loadVehicles = () => {
      let url = apiRoot + "vehicles.json?operator=" + window.OPERATOR_ID;
      fetch(url).then((response) => {
        response.json().then((items) => {
          setBounds(getBounds(items));

          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item })))
          );
          setLoading(false);
          clearTimeout(timeout);
          timeout = setTimeout(loadVehicles, 10000); // 10 seconds
        });
      });
    };

    loadVehicles();

    const handleVisibilityChange = (event) => {
      if (event.target.hidden) {
        clearTimeout(timeout);
      } else {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
    };
  }, []);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleVehicleMarkerClick = React.useCallback((event, id) => {
    event.originalEvent.preventDefault();
    setClickedVehicleMarker(id);
  }, []);

  const handleMapClick = React.useCallback((e) => {
    if (!e.originalEvent.defaultPrevented) {
      setClickedVehicleMarker(null);
    }
  }, []);

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  if (loading) {
    return <div className="sorry">Loading…</div>;
  }

  const vehiclesList = Object.values(vehicles);

  if (!vehiclesList.length) {
    return (
      <div className="sorry">Sorry, no buses are tracking at the moment</div>
    );
  }

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  return (
    <Map
      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
      pitchWithRotate={false}
      minZoom={6}
      maxZoom={16}
      bounds={bounds}
      mapStyle={
        darkMode
          ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
          : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      }
      RTLTextPlugin={null}
      onClick={handleMapClick}
      onLoad={handleMapLoad}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

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

      {clickedVehicle && (
        <VehiclePopup
          item={clickedVehicle}
          onClose={() => setClickedVehicleMarker(null)}
        />
      )}
    </Map>
  );
}

const root = ReactDOM.createRoot(document.getElementById("map"));
root.render(
  <React.StrictMode>
    <OperatorMap />
  </React.StrictMode>
);
