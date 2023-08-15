import React, { lazy } from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";

import "./maps.css";
import "maplibre-gl/dist/maplibre-gl.css";

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

declare global {
  interface Window {
    SERVICE_ID: number;
    STOPS: object;
    OPERATOR_ID: string;
  }
}

let rootElement = document.getElementById("hugemap");
if (rootElement) {
  let root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <BigMap />
    </React.StrictMode>,
  );
} else {
  rootElement = document.getElementById("map");
  if (rootElement) {
    if (window.location.href.indexOf("/operators/") !== -1) {
      let root = ReactDOM.createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <OperatorMap noc={window.OPERATOR_ID} />
        </React.StrictMode>,
      );
    } else if (window.SERVICE_ID) {
      let root = ReactDOM.createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <ServiceMap serviceId={window.SERVICE_ID} />
        </React.StrictMode>,
      );
    } else if (window.STOPS) {
      let root = ReactDOM.createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <TripMap />
        </React.StrictMode>,
      );
    }
  } else {
    let rootElement = document.getElementById("history");
    if (rootElement) {
      let root = ReactDOM.createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <History />
        </React.StrictMode>,
      );
    }
  }
}
