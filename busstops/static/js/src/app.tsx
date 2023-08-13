import React, { lazy } from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";

const BigMap = lazy(() => import("./BigMap"));
const TripMap = lazy(() => import("./TripMap"));
const OperatorMap = lazy(() => import("./OperatorMap"));
const ServiceMap = lazy(() => import("./ServiceMap"));
const History = lazy(() => import("./History"));

Sentry.init({
  dsn: "https://0d628b6fff45463bb803d045b99aa542@o55224.ingest.sentry.io/1379883",
  allowUrls: [/bustimes\.org\/static\//],
  ignoreErrors: [
    "TypeError: Failed to fetch",
    "AbortError: The user aborted a request",
    "AbortError: Fetch is aborted",
    "NetworkError when attempting to fetch resource",
  ],
});

import "./maps.css";
import "maplibre-gl/dist/maplibre-gl.css";

let root = document.getElementById("hugemap");
if (root) {
  root = ReactDOM.createRoot(root);
  root.render(
    <React.StrictMode>
      <BigMap />
    </React.StrictMode>,
  );
} else {
  root = document.getElementById("map");
  if (root) {
    if (window.location.href.indexOf("/operators/") !== -1) {
      root = ReactDOM.createRoot(root);
      root.render(
        <React.StrictMode>
          <OperatorMap />
        </React.StrictMode>,
      );
    } else if (window.SERVICE_ID) {
      root = ReactDOM.createRoot(root);
      root.render(
        <React.StrictMode>
          <ServiceMap />
        </React.StrictMode>,
      );
    } else if (window.STOPS) {
      root = ReactDOM.createRoot(root);
      root.render(
        <React.StrictMode>
          <TripMap />
        </React.StrictMode>,
      );
    }
  } else {
    root = document.getElementById("history");
    if (root) {
      root = ReactDOM.createRoot(root);
      root.render(
        <React.StrictMode>
          <History />
        </React.StrictMode>,
      );
    }
  }
}
