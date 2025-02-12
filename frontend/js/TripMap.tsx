import React from "react";

import { Layer, type LayerProps, Source } from "react-map-gl/maplibre";

import { ThemeContext } from "./Map";
import type { TripTime } from "./TripTimetable";

type RouteProps = {
  times: TripTime[];
};

export const Route = React.memo(function Route({ times }: RouteProps) {
  const theme = React.useContext(ThemeContext);
  const darkMode =
    theme === "alidade_smooth_dark" || theme === "alidade_satellite";

  const stopsStyle: LayerProps = {
    id: "stops",
    type: "symbol",
    layout: {
      "symbol-sort-key": ["get", "priority"],
      "text-field": ["get", "time"],
      "text-size": 11,
      "text-font": ["Stadia Regular"],
    },
    paint: {
      "text-color": darkMode ? "#fff" : "#333",
      "text-halo-color": darkMode ? "#333" : "#fff",
      "text-halo-width": 2,
    },
  };

  const routeStyle: LayerProps = {
    type: "line",
    paint: {
      "line-color": darkMode ? "#ddd" : "#666",
      "line-width": 3,
    },
  };

  const lineStyle: LayerProps = {
    type: "line",
    paint: {
      "line-color": darkMode ? "#eee" : "#666",
      "line-width": 2,
      "line-dasharray": [2, 2],
    },
  };

  const lines = [];
  const lineStrings = [];
  let prevTime: TripTime | undefined;
  let prevLocation: [number, number] | undefined;
  let i = null;

  for (const time of times) {
    if (time.track) {
      lineStrings.push(time.track);
    } else if (prevTime && prevLocation && time.stop.location) {
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
              properties: null,
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
              properties: null,
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
                  coordinates: stop.stop.location as [number, number],
                },
                properties: {
                  url: stop.stop.atco_code
                    ? `/stops/${stop.stop.atco_code}`
                    : null,
                  name: stop.stop.name,
                  bearing: stop.stop.bearing,
                  time:
                    stop.aimed_arrival_time ||
                    stop.aimed_departure_time ||
                    stop.expected_arrival_time,
                  priority: stop.timing_status === "PTP" ? 0 : 1, // symbol-sort-key lower number - "higher" priority
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
