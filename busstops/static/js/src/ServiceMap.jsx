import React from "react";
import ReactDOM from "react-dom/client";

import Map, {
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";
import { LngLatBounds } from "maplibre-gl";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import { useDarkMode } from "./utils";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";


export default function OperatorMap() {
  const darkMode = useDarkMode();

  const [isOpen, setOpen] = React.useState(window.location.hash.indexOf('#map') === 0);

  const openMap = React.useCallback(() => {
    setOpen(true);
  }, []);

  const closeMap = React.useCallback(() => {
    setOpen(false);
  }, []);

  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  let timeout;

  React.useEffect(() => {
    if (isOpen) {
      // document.getElementById("map").classList.add('expanded');
      document.body.classList.add('has-overlay');
    } else {
      // document.getElementById("map").classList.remove('expanded');
      document.body.classList.remove('has-overlay');
    }

    const loadVehicles = () => {
      let url = apiRoot + "vehicles.json?service=" + window.SERVICE_ID;
      fetch(url).then((response) => {
        response.json().then((items) => {
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

    if (isOpen) {
      window.addEventListener("visibilitychange", handleVisibilityChange);
    }

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
    };
  }, [isOpen]);

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


  const button = <a className="button" href="#map" onClick={openMap}>Map</a>;

  if (!isOpen) {
    return button;
  }

  const vehiclesList = vehicles ? Object.values(vehicles) : null;

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  return (
    <React.Fragment>
    {button}
    <div className="service-map">
      <Map
        dragRotate={false}
        touchPitch={false}
        touchRotate={false}
        pitchWithRotate={false}
        minZoom={6}
        maxZoom={16}
        bounds={window.EXTENT}
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


        <div className="maplibregl-ctrl">
          <button onClick={closeMap}>Close map</button>
        </div>

        {vehiclesList ? vehiclesList.map((item) => {
          return (
            <VehicleMarker
              key={item.id}
              selected={item.id === clickedVehicleMarkerId}
              vehicle={item}
              onClick={handleVehicleMarkerClick}
            />
          );
        }) : <div className="maplibregl-ctrl">Loading</div> }

        {clickedVehicle && (
          <VehiclePopup
            item={clickedVehicle}
            onClose={() => setClickedVehicleMarker(null)}
          />
        )}

      </Map>
    </div>
    </React.Fragment>
  );
}
