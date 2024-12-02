import React from "react";
import { createRoot } from "react-dom/client";

import ServiceMap from "./ServiceMap";

declare global {
  interface Window {
    SERVICE_ID?: number;
    globalThis: Window;
  }
}

if (typeof window.globalThis === "undefined") {
  window.globalThis = window;
}

if (window.SERVICE_ID) {
  const rootElement = document.getElementById("map-link");
  if (rootElement) {
    const root = createRoot(rootElement);
    root.render(
      <React.StrictMode>
        <ServiceMap serviceId={window.SERVICE_ID} />
      </React.StrictMode>,
    );
  }
}
