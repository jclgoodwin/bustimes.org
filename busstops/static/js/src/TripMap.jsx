import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

import { useDarkMode } from "./utils";
import { LngLatBounds } from "maplibre-gl";

import TripTimetable from "./TripTimetable";
import StopPopup from "./StopPopup";
import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "/";

const stopsStyle = {
  id: "stops",
  type: "circle",
  paint: {
    "circle-color": "#fff",
    "circle-radius": 3,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#666",
  },
};

const routeStyle = {
  type: "line",
  paint: {
    "line-color": "#777",
    "line-width": 3,
  },
};

export default function TripMap() {
  const [trip, setTrip] = React.useState(window.STOPS);

  const bounds = React.useMemo(() => {
    console.log("getBounds");
    let bounds = new LngLatBounds();
    for (let item of trip.times) {
      if (item.stop.location) {
        bounds.extend(item.stop.location);
      }
    }
    return bounds;
  }, [trip])

  const loadTrip = function(tripId) {
    window.TRIP_ID = tripId;
    fetch(`${apiRoot}api/trips/${tripId}/`).then((response) => {
      response.json().then(setTrip);
    });
  };

  const darkMode = useDarkMode();

  const [cursor, setCursor] = React.useState();

  const onMouseEnter = React.useCallback((e) => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
  }, []);

  const [clickedStop, setClickedStop] = React.useState(null);

  const handleMapClick = React.useCallback((e) => {
    if (!e.originalEvent.defaultPrevented) {
      if (e.features.length) {
        setClickedStop(e.features[0]);
      } else {
        setClickedStop(null);
      }
      setClickedVehicleMarker(null);
    }
  }, []);

  const handleMouseEnter = React.useCallback((stop) => {
    setClickedStop({
      geometry: {
        coordinates: stop.stop.location,
      },
      properties: {
        name: stop.stop.name,
        url: `/stops/${stop.stop.atco_code}`,
      },
    });
  }, []);

  const [tripVehicle, setTripVehicle] = React.useState(null);
  const [vehicles, setVehicles] = React.useState(null);

  let timeout;

  const loadVehicles = () => {
    const url = `${apiRoot}vehicles.json?service=${window.SERVICE}&trip=${trip.id}`;
    fetch(url).then((response) => {
      response.json().then((items) => {
        setVehicles(
          Object.assign(
            {},
            ...items.map((item) => {
              if (item.trip_id === window.TRIP_ID) {
                if (!vehicles) {
                  setClickedVehicleMarker(item.id);
                }
                setTripVehicle(item);
              }
              return { [item.id]: item };
            }),
          ),
        );
        clearTimeout(timeout);
        timeout = setTimeout(loadVehicles, 10000); // 10 seconds
      });
    });
  };

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleVehicleMarkerClick = React.useCallback((event, id) => {
    event.originalEvent.preventDefault();
    setClickedStop(null);
    setClickedVehicleMarker(id);
  }, []);

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    loadVehicles();
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  const vehiclesList = vehicles ? Object.values(vehicles) : [];

  return (
    <React.Fragment>
      <div className="trip-map">
        <Map
          dragRotate={false}
          touchPitch={false}
          touchRotate={false}
          pitchWithRotate={false}
          maxZoom={16}
          bounds={bounds}
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            left: 0,
          }}
          fitBoundsOptions={{
            padding: 50,
          }}
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

          <Source
            type="geojson"
            data={{
              type: "FeatureCollection",
              features: trip.times
                .filter((stop) => stop.track)
                .map((stop) => {
                  return {
                    type: "Feature",
                    geometry: {
                      type: "LineString",
                      coordinates: stop.track,
                    },
                  };
                }),
            }}
          >
            <Layer {...routeStyle} />
          </Source>
          <Source
            type="geojson"
            data={{
              type: "FeatureCollection",
              features: trip.times
                .filter((stop) => stop.stop.location)
                .map((stop) => {
                  return {
                    type: "Feature",
                    geometry: {
                      type: "Point",
                      coordinates: stop.stop.location,
                    },
                    properties: {
                      url: `/stops/${stop.stop.atco_code}`,
                      name: stop.stop.name,
                    },
                  };
                }),
            }}
          >
            <Layer {...stopsStyle} />
          </Source>

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

          {clickedVehicle ? (
            <VehiclePopup
              item={clickedVehicle}
              onTripClick={loadTrip}
              onClose={() => {
                setClickedVehicleMarker(null);
              }}
            />
          ) : null}

          {clickedStop ? (
            <StopPopup
              item={clickedStop}
              onClose={() => setClickedStop(null)}
            />
          ) : null}
        </Map>
      </div>
      <TripTimetable
        trip={trip}
        vehicle={tripVehicle}
        onMouseEnter={handleMouseEnter}
      />
    </React.Fragment>
  );
}
