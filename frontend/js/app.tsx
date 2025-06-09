import React, { lazy } from "react";
import { createRoot } from "react-dom/client";

import "./maps.css";
import "maplibre-gl/dist/maplibre-gl.css";

import LoadingSorry from "./LoadingSorry";
import ServiceMap from "./ServiceMap";
const History = lazy(() => import("./History"));
const MapRouter = lazy(() => import("./MapRouter"));

declare global {
  interface Window {
    SERVICE_ID?: number;
    OPERATOR_ID?: string;
    VEHICLE_ID: number;
    globalThis: Window;
  }
}

if (typeof window.globalThis === "undefined") {
  window.globalThis = window;
}

let rootElement: HTMLElement | null;
if ((rootElement = document.getElementById("history"))) {
  // vehicle journey history
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <History />
    </React.StrictMode>,
  );
} else if (
  window.SERVICE_ID &&
  (rootElement = document.getElementById("map-link"))
) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <ServiceMap serviceId={window.SERVICE_ID} />
    </React.StrictMode>,
  );
} else if ((rootElement = document.getElementById("hugemap"))) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <MapRouter />
    </React.StrictMode>,
  );
}
