import React from "react";
import ReactDOM from "react-dom/client";

import Map, {
  NavigationControl, GeolocateControl
} from "react-map-gl/maplibre";
import { LngLatBounds } from "maplibre-gl";;

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
      let query = window.matchMedia('(prefers-color-scheme: dark)');
      if (query.matches) {
        setDarkMode(true);
      }

      const handleChange = (e) => {
        setDarkMode(e.matches);
      }

      query.addEventListener("change", handleChange);

      return () => {
        query.removeEventListener("change", handleChange)
      };
    }
  }, []);


  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);


  const [bounds, setBounds] = React.useState(null);


  React.useEffect(() => {
    let url = apiRoot + "vehicles.json?operator=" + window.OPERATOR_ID;
    fetch(url).then((response) => {
      response.json().then((items) => {

        setBounds(getBounds(items));

        setVehicles(
          Object.assign({}, ...items.map((item) => ({[item.id]: item})))
        );
        setLoading(false);
      });
    });
  }, []);


  const [clickedVehicleMarkerId, handleVehicleMarkerClick] = React.useState(null);

  if (loading) {
    return <div className="sorry">Loading…</div>;
  }

  if (!vehicles.length) {
    return <div className="sorry">Sorry, no buses are tracking at the moment</div>;
  }

  const clickedVehicle = clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  return (
    <Map

    dragRotate={false}
    touchPitch={false}
    touchRotate={false}
    pitchWithRotate={false}

    // onLoad={loadVehicles}

    minZoom={6}
    maxZoom={16}

    bounds={bounds}

    mapStyle={
        darkMode ?
        "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json" :
        "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      // )
    }

    // hash={true}

    RTLTextPlugin={null}
    // mapLib={maplibregl}

    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />


      { Object.values(vehicles).map((item) => {
        return (
          <VehicleMarker
          key={item.id}
          vehicle={item}
          onClick={handleVehicleMarkerClick}
          />
        );
      }) }

      {clickedVehicle && (
          <VehiclePopup
            item={clickedVehicle}
            onClose={() => handleVehicleMarkerClick(null)}
          />
        )}


    </Map>
  );
}


const root = ReactDOM.createRoot(document.getElementById("map"));
root.render(
  <React.StrictMode>
    <OperatorMap/>
  </React.StrictMode>
);
