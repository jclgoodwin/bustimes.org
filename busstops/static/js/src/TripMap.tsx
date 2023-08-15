import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  MapEvent,
  LayerProps,
} from "react-map-gl/maplibre";

import { useRoute } from "wouter";
import { navigate } from "wouter/use-location";

import { useDarkMode } from "./utils";
import { LngLatBounds, LngLatBoundsLike } from "maplibre-gl";

import TripTimetable from "./TripTimetable";
import StopPopup from "./StopPopup";
import VehicleMarker from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

declare global {
  interface Window {
    SERVICE: number;
    TRIP_ID: number;
    VEHICLE_ID: number;
    STOPS: object;
  }
}

const apiRoot = process.env.API_ROOT;

const stopsStyle: LayerProps = {
  id: "stops",
  type: "symbol",
  layout: {
    "icon-rotate": ["+", 45, ["get", "bearing"]],
    "icon-image": "stop",
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
  },
};

const routeStyle: LayerProps = {
  type: "line",
  paint: {
    "line-color": "#666",
    "line-width": 3,
  },
};

const lineStyle: LayerProps = {
  type: "line",
  paint: {
    "line-color": "#666",
    "line-width": 3,
    "line-dasharray": [2, 2],
  },
};

const Route = React.memo(function Route({ times }) {
  const lines = [];
  const lineStrings = [];
  let prevLocation,
    prevTime,
    i = null;

  for (const time of times) {
    if (time.track) {
      lineStrings.push(time.track);
    } else if (prevLocation && time.stop.location) {
      if (prevTime.track || i === null) {
        lines.push([prevLocation, time.stop.location]);
        i = lines.length - 1;
      } else {
        lines[i].push(time.stop.location);
      }
    }

    prevTime = time;
    prevLocation = time.stop.location;
  }

  return (
    <React.Fragment>
      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: lineStrings.map((lineString) => {
            return {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: lineString,
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
          features: lines.map((line) => {
            return {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: line,
              },
            };
          }),
        }}
      >
        <Layer {...lineStyle} />
      </Source>

      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: times
            .filter((stop) => stop.stop.location)
            .map((stop) => {
              return {
                type: "Feature",
                geometry: {
                  type: "Point",
                  coordinates: stop.stop.location,
                },
                properties: {
                  url: stop.stop.atco_code
                    ? `/stops/${stop.stop.atco_code}`
                    : null,
                  name: stop.stop.name,
                  bearing: stop.stop.bearing,
                },
              };
            }),
        }}
      >
        <Layer {...stopsStyle} />
      </Source>
    </React.Fragment>
  );
});

export default function TripMap() {
  const [, params] = useRoute("/trips/:id");

  const [trip, setTrip] = React.useState(window.STOPS);

  const bounds = React.useMemo(() => {
    let bounds: LngLatBoundsLike = new LngLatBounds();
    for (let item of trip.times) {
      if (item.stop.location) {
        bounds.extend(item.stop.location);
      }
    }
    return bounds;
  }, [trip]);

  const navigateToTrip = React.useCallback((item) => {
    navigate("/trips/" + item.trip_id);
  }, []);

  const darkMode = useDarkMode();

  const [cursor, setCursor] = React.useState();

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
  }, []);

  const [clickedStop, setClickedStop] = React.useState(null);

  const handleMapClick = React.useCallback(
    (e) => {
      const srcElement = e.originalEvent.srcElement;
      const vehicleId =
        srcElement.dataset.vehicleId || srcElement.parentNode.dataset.vehicleId;
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        setClickedStop(null);
        return;
      }

      if (e.features.length) {
        for (const stop of e.features) {
          if (
            !stop.properties.url ||
            stop.properties.url !== clickedStop?.properties.url
          ) {
            setClickedStop(stop);
          }
        }
      } else {
        setClickedStop(null);
      }
      setClickedVehicleMarker(null);
    },
    [clickedStop],
  );

  const [tripVehicle, setTripVehicle] = React.useState(null);
  const [vehicles, setVehicles] = React.useState(null);

  const timeout = React.useRef(null);
  const vehiclesAbortController = React.useRef(null);

  React.useEffect(() => {
    const loadVehicles = (first = false) => {
      if (document.hidden) {
        return;
      }

      let url = `${apiRoot}vehicles.json`;
      if (window.VEHICLE_ID) {
        url = `${url}?id=${window.VEHICLE_ID}`;
      } else if (!window.SERVICE) {
        return;
      } else {
        url = `${url}?service=${window.SERVICE}&trip=${params.id}`;
      }

      if (vehiclesAbortController.current) {
        vehiclesAbortController.current.abort();
      }
      vehiclesAbortController.current = new AbortController();

      clearTimeout(timeout.current);

      fetch(url, {
        signal: vehiclesAbortController.current.signal,
      }).then(
        (response) => {
          if (!response.ok) {
            return;
          }
          response.json().then((items) => {
            setVehicles(
              Object.assign(
                {},
                ...items.map((item) => {
                  if (
                    (params && item.trip_id == params.id) ||
                    (window.VEHICLE_ID && item.id === window.VEHICLE_ID)
                  ) {
                    if (first) {
                      setClickedVehicleMarker(item.id);
                    }
                    setTripVehicle(item);
                  }
                  return { [item.id]: item };
                }),
              ),
            );
          });
          if (!document.hidden) {
            timeout.current = setTimeout(loadVehicles, 12000); // 12 seconds
          }
        },
        (reason) => {
          // never mind
        },
      );
    };

    const loadTrip = () => {
      if (params) {
        if (trip && trip.id && params.id == trip.id.toString()) {
          return;
        }
        setTripVehicle(null);
        fetch(`${apiRoot}api/trips/${params.id}/`).then((response) => {
          if (response.ok) {
            response.json().then(setTrip);
          }
        });
      }
    };

    loadTrip();
    loadVehicles(true);

    const handleVisibilityChange = (event) => {
      clearTimeout(timeout.current);
      if (!event.target.hidden) {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [params?.id]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState(null);

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    map.loadImage("/static/route-stop-marker.png", (error, image) => {
      if (error) throw error;
      map.addImage("stop", image, {
        pixelRatio: 2,
        // width: 16,
        // height: 16
      });
    });
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehicles[clickedVehicleMarkerId];

  const vehiclesList = vehicles ? Object.values(vehicles) : [];

  return (
    <React.Fragment>
      <div className="trip-map has-sidebar">
        <Map
          dragRotate={false}
          touchPitch={false}
          pitchWithRotate={false}
          maxZoom={18}
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

          <Route times={trip.times} />

          {vehiclesList.map((item) => {
            return (
              <VehicleMarker
                key={item.id || item.stop.atco_code}
                selected={item.id === clickedVehicleMarkerId}
                vehicle={item}
              />
            );
          })}

          {clickedVehicle ? (
            <VehiclePopup
              item={clickedVehicle}
              activeLink={clickedVehicle?.trip_id == params?.id}
              onTripClick={navigateToTrip}
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
        // onMouseEnter={handleMouseEnter}
      />
    </React.Fragment>
  );
}
