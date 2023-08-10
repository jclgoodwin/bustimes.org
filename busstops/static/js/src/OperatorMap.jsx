import React from "react";

import Map, {
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

// import TripLayer from "./TripLayer";
import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import { useDarkMode, getBounds } from "./utils";

const apiRoot = process.env.API_ROOT;

export default function OperatorMap() {
  // dark mode:

  const darkMode = useDarkMode();

  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [bounds, setBounds] = React.useState(null);

  React.useEffect(() => {
    let timeout;

    const loadVehicles = () => {
      if (document.hidden) {
        return;
      }

      let url = apiRoot + "vehicles.json?operator=" + window.OPERATOR_ID;
      fetch(url).then((response) => {
        response.json().then((items) => {
          if (!bounds) {
            setBounds(getBounds(items));
          }

          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item }))),
          );
          setLoading(false);
          clearTimeout(timeout);
          if (!document.hidden) {
            timeout = setTimeout(loadVehicles, 10000); // 10 seconds
          }
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

  // const clickedTripId = clickedVehicle?.trip_id;

  return (
    <React.Fragment>
      <div className="operator-map">
        <Map
          dragRotate={false}
          touchPitch={false}
          touchRotate={false}
          pitchWithRotate={false}
          maxZoom={18}
          bounds={bounds}
          fitBoundsOptions={{
            padding: 50,
          }}
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
      </div>
      {/*{clickedTripId ? <TripLayer tripId={clickedTripId} /> : null}*/}
    </React.Fragment>
  );
}
