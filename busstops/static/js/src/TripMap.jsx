import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  Popup,
} from "react-map-gl/maplibre";

import { useDarkMode } from "./utils";
import { LngLatBounds } from "maplibre-gl";

import StopPopup from "./StopPopup";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function getBounds(stops) {
  let bounds = new LngLatBounds();
  for (let item of stops) {
    if (item.stop.location) {
      bounds.extend(item.stop.location);
    }
  }
  return bounds;
}

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

function Row({ stop, onMouseEnter }) {
  const handleMouseEnter = React.useCallback(() => {
    if (stop.stop.location) {
      onMouseEnter(stop);
    }
  }, []);

  let stopName = stop.stop.name;
  if (stop.stop.atco_code) {
    stopName = <a href={`/stops/${stop.stop.atco_code}`}>{stopName}</a>;
  }

  const className = stop.timing_status == "OTH" ? "minor" : null;

  const rowSpan =
    stop.aimed_arrival_time &&
    stop.aimed_departure_time &&
    stop.aimed_arrival_time !== stop.stop.aimed_departure_time
      ? 2
      : null;

  return (
    <React.Fragment>
      <tr
        className={className}
        id={`stop-time-${stop.id}`}
        onMouseEnter={handleMouseEnter}
      >
        <td className="stop-name" rowSpan={rowSpan}>
          {stopName}
        </td>
        <td>{stop.aimed_arrival_time || stop.aimed_departure_time}</td>
        <td></td>
      </tr>
      {rowSpan ? (
        <tr className={className}>
          <td>{stop.aimed_departure_time}</td>
          <td></td>
        </tr>
      ) : null}
    </React.Fragment>
  );
}

function TripTimetable({ trip, onMouseEnter }) {
  const last = trip.times.length - 1;

  return (
    <div className="trip-timetable">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Timetable</th>
            <th>Actual</th>
          </tr>
        </thead>
        <tbody>
          {trip.times.map((stop, i) => (
            <Row
              key={stop.id}
              stop={stop}
              first={i === 0}
              last={i === last}
              onMouseEnter={onMouseEnter}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

const trip = window.STOPS;
const bounds = getBounds(trip.times);

export default function TripMap() {
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
    if (e.features.length) {
      if (e.features[0].layer.id == "stops") {
        setClickedStop(e.features[0]);
      }
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

  return (
    <React.Fragment>
      <div className="trip-map">
        <Map
          dragRotate={false}
          touchPitch={false}
          touchRotate={false}
          pitchWithRotate={false}
          minZoom={8}
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
          // onLoad={handleMapLoad}
          interactiveLayerIds={["stops"]}
        >
          <NavigationControl showCompass={false} />
          <GeolocateControl />

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

          {clickedStop ? (
            <StopPopup
              item={clickedStop}
              onClose={() => setClickedStop(null)}
            />
          ) : null}
        </Map>
      </div>
      <TripTimetable trip={trip} onMouseEnter={handleMouseEnter} />
    </React.Fragment>
  );
}
