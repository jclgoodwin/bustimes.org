import React from "react";
import ReactDOM from "react-dom/client";

import loadjs from "loadjs";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";
import { LngLatBounds } from "maplibre-gl";

import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import { useDarkMode } from "./utils";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

let hasHistory = false;
let hasCss = false;

const stopsStyle = {
  id: "stops",
  type: "circle",
  paint: {
    "circle-color": "#fff",
    "circle-radius": 3,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#666",
    // "circle-stroke-opacity": 0.,
  },
};

const routeStyle = {
  type: "line",
  paint: {
    "line-color": "#000",
    "line-opacity": 0.5,
    "line-width": 3,
  },
};

export default function OperatorMap() {
  const darkMode = useDarkMode();

  const [isOpen, setOpen] = React.useState(
    window.location.hash.indexOf("#map") === 0
  );

  const openMap = React.useCallback((e) => {
    hasHistory = true;
    window.location.hash = "#map";
    e.preventDefault();
  }, []);

  const closeMap = React.useCallback(() => {
    if (hasHistory) {
      history.back();
    } else {
      window.location.hash = "";
    }
  }, []);

  const [loading, setLoading] = React.useState(true);

  const [vehicles, setVehicles] = React.useState(null);

  const [stops, setStops] = React.useState(null);

  const [geometry, setGeometry] = React.useState(null);

  React.useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash.indexOf("#map") === 0) {
        setOpen(true);
      } else {
        setOpen(false);
      }
    };

    const handleKeyDown = () => {
      // ESC
      if (event.keyCode === 27) {
        closeMap();
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      window.removeEventListener("keydown", handleKeyDown);
    };
  });

  let timeout;

  React.useEffect(() => {
    // (overflow css)
    if (isOpen) {
      document.body.classList.add("has-overlay");
      if (!hasCss) {
        loadjs(window.LIVERIES_CSS_URL, function () {
          hasCss = true;
        });
      }
    } else {
      document.body.classList.remove("has-overlay");
    }

    // service map data
    fetch(`/services/${window.SERVICE_ID}.json`).then((response) => {
      response.json().then((data) => {
        setGeometry(data.geometry);
        setStops(data.stops);
      });
    });

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

  [cursor, setCursor] = React.useState();

  const onMouseEnter = React.useCallback((e) => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
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

  const vehiclesList = vehicles ? Object.values(vehicles) : null;

  let count = vehiclesList && vehiclesList.length;

  if (count) {
    if (count === 1) {
      count = `${count} bus`;
    } else {
      count = `${count} buses`;
    }
  }

  const button = (
    <a className="button" href="#map" onClick={openMap}>
      Map
      {count ? ` (tracking ${count})` : null}
    </a>
  );

  if (!isOpen) {
    return button;
  }

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
          minZoom={8}
          maxZoom={16}
          bounds={window.EXTENT}
          cursor={cursor}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          mapStyle={
            darkMode
              ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
              : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
          }
          RTLTextPlugin={null}
          onClick={handleMapClick}
          onLoad={handleMapLoad}
          interactiveLayerIds={["stops"]}
        >
          <NavigationControl showCompass={false} />
          <GeolocateControl />

          <div className="maplibregl-ctrl">
            <button onClick={closeMap}>Close map</button>
            {count ? ` Tracking ${count}` : null}
          </div>

          {vehiclesList ? (
            vehiclesList.map((item) => {
              return (
                <VehicleMarker
                  key={item.id}
                  selected={item.id === clickedVehicleMarkerId}
                  vehicle={item}
                  onClick={handleVehicleMarkerClick}
                />
              );
            })
          ) : (
            <div className="maplibregl-ctrl">Loading</div>
          )}

          {clickedVehicle && (
            <VehiclePopup
              item={clickedVehicle}
              onClose={() => setClickedVehicleMarker(null)}
            />
          )}

          {geometry && (
            <Source type="geojson" data={geometry}>
              <Layer {...routeStyle} />
            </Source>
          )}

          {stops && (
            <Source type="geojson" data={stops}>
              <Layer {...stopsStyle} />
            </Source>
          )}
        </Map>
      </div>
    </React.Fragment>
  );
}
