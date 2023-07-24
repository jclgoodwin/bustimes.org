import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  Popup
} from "react-map-gl/maplibre";

import { useDarkMode, getBounds } from "./utils";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

function Row({ stop }) {
  let stopName = stop.stop.name;
  if (stop.stop.atco_code) {
    stopName = <a href={`/stops/${stop.stop.atco_code}`}>{stopName}</a>;
  }

  const className = stop.timing_status == "OTH" ? "minor" : null;

  const rowSpan = (stop.aimed_arrival_time && stop.aimed_departure_time && stop.aimed_arrival_time !== stop.stop.aimed_departure_time) ? 2 : null;

  return (
    <React.Fragment>
      <tr className={className} id={`stop-time-${stop.id}`}>
        <td className="stop-name" rowSpan={rowSpan}>{stopName}</td>
        <td>{stop.aimed_arrival_time || stop.aimed_departure_time}</td>
        <td></td>
      </tr>
      {rowSpan ?
        <tr className={className}>
          <td>{stop.aimed_departure_time}</td>
          <td></td>
        </tr>
        : null
      }
    </React.Fragment>
  );
}

function TripTimetable({ trip }) {
  return (
    <table className="trip-timetable">
      <thead>
        <tr>
          <th></th>
          <th>Timetable</th>
          <th>Actual</th>
        </tr>
      </thead>
      <tbody>
        {trip.times.map(stop => <Row key={stop.id} stop={stop} />)}
      </tbody>
    </table>
  );
}

export default function TripMap() {
  const trip = window.STOPS;

  const bounds = getBounds(trip.times.map(item => item.stop.location));

  const darkMode = useDarkMode();

  return (
    <div>
      <TripTimetable trip={trip} />

      <Map
        dragRotate={false}
        touchPitch={false}
        touchRotate={false}
        pitchWithRotate={false}
        minZoom={8}
        maxZoom={16}
        bounds={bounds}
        // fitBoundsOptions={{
        //   padding: 50,
        // }}
        // cursor={cursor}
        // onMouseEnter={onMouseEnter}
        // onMouseLeave={onMouseLeave}
        mapStyle={
          darkMode
            ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
            : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
        }
        RTLTextPlugin={null}
        // onClick={handleMapClick}
        // onLoad={handleMapLoad}
        // interactiveLayerIds={["stops", "locations"]}
      >
        <NavigationControl showCompass={false} />
        <GeolocateControl />

{/*      <Source type="geojson" data={{
        type: "LineString",
        coordinates: journey.locations.map(l => l.coordinates)
      }}>
        <Layer {...routeStyle} />
      </Source>

      <Source type="geojson" data={{
        type: "FeatureCollection",
        features: journey.locations.map(l => {
          return {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: l.coordinates,
            },
            properties: {
              delta: l.delta,
              direction: l.direction,
              datetime: l.datetime
            }
          };
        })
      }}>
        <Layer {...locationsStyle} />
      </Source>

      { journey.stops ? <Source type="geojson" data={{
        type: "FeatureCollection",
        features: journey.stops.map(s => {
          return {
            type: "Feature",
            geometry: {
              type: "Point",
              coordinates: s.coordinates,
            },
            properties: {
              atco_code: s.atco_code,
              name: s.name,
              minor: s.minor,
              heading: s.heading,
              aimed_arrival_time: s.aimed_arrival_time,
              aimed_departure_time: s.aimed_departure_time,
            }
          };
        })
      }}>
        <Layer {...stopsStyle} />
      </Source> : null }

      {clickedStop ? <StopPopup item={{
        properties: {
          url: `/stops/{clickedStop.properties.atco_code}`,
          name: clickedStop.properties.name,
        },
        geometry: clickedStop.geometry,
      }} onClose={() => setClickedStop(null)} /> : null}

      {clickedLocation ?
        <Popup
          latitude={clickedLocation.geometry.coordinates[1]}
          longitude={clickedLocation.geometry.coordinates[0]}
          closeButton={false}
          closeOnClick={false}
        >
          {clickedLocation.properties.datetime}

        </Popup>
        : null
      }*/}

      </Map>
    </div>
  );
}
