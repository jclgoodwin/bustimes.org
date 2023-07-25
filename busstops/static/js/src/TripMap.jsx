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

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function getBounds(stops) {
  console.log('getBounds!!!!!!');
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

function Row({ stop }) {
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
      <tr className={className} id={`stop-time-${stop.id}`}>
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

function TripTimetable({ trip }) {
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
          {trip.times.map((stop) => (
            <Row key={stop.id} stop={stop} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TripMap() {
  const trip = window.STOPS;

  const bounds = getBounds(trip.times);

  const darkMode = useDarkMode();

  const [cursor, setCursor] = React.useState();

  // const [clickedLocation, setClickedLocation] = React.useState(null);

  const onMouseEnter = React.useCallback((e) => {
    setCursor("pointer");

    // if (e.features.length && e.features[0].layer.id == "stops") {
    //   setClickedStop(e.features[0]);
    // }
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
    // setClickedLocation(null);
  }, []);

  return (
    <React.Fragment>
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
        // onClick={handleMapClick}
        // onLoad={handleMapLoad}
        interactiveLayerIds={["stops"]}
      >
        <NavigationControl showCompass={false} />
        <GeolocateControl />

        <Source type="geojson" data={{
          type: "FeatureCollection",
          features: trip.times.filter(stop => stop.stop.location).map(stop => {
            return {
              type: "Feature",
              geometry: {
                type: "Point",
                coordinates: stop.stop.location,
              },
              // properties: {
              //   delta: l.delta,
              //   direction: l.direction,
              //   datetime: l.datetime
              // }
            };
          })
        }}>
          <Layer {...stopsStyle} />
        </Source>

      </Map>
      <TripTimetable trip={trip} />
    </React.Fragment>
  );
}
