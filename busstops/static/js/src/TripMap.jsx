import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";

import "maplibre-gl/dist/maplibre-gl.css";

const apiRoot = "https://bustimes.org/";

export default function TripMap() {
  const stops = window.STOPS;


  return (
    <table>
      <thead>
        <th></th>
        <th>Timetable</th>
        <th></th>
        <th></th>
      </thead>
      <tbody>
        {stops.times.map(stop => (
          <tr key={stop.id}>
            <td>{stop.stop.name}</td>
            <td></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
