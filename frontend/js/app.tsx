import * as Sentry from "@sentry/react";
import React, { lazy } from "react";
import { createRoot } from "react-dom/client";

import "./maps.css";
import "maplibre-gl/dist/maplibre-gl.css";

import LoadingSorry from "./LoadingSorry";
import ServiceMap from "./ServiceMap";
const History = lazy(() => import("./History"));
const MapRouter = lazy(() => import("./MapRouter"));

if (process.env.NODE_ENV === "production") {
  Sentry.init({
    dsn: "https://0d628b6fff45463bb803d045b99aa542@o55224.ingest.sentry.io/1379883",
    allowUrls: [/bustimes\.org\/static\/js/, /bustimes\.org\/static\/dist\/js/],
    ignoreErrors: [
      // ignore errors in third-party advert code
      "Load failed",
      "Failed to fetch",
      "AbortError: The user aborted a request",
      "AbortError: Fetch is aborted",
      "NetworkError when attempting to fetch resource",
      "Non-Error promise rejection captured with value: undefined",
      "from accessing a cross-origin frame. Protocols, domains, and ports must",
      "Event `Event` (type=error) captured as promise rejection",
      "this.kdmw is not a function",
      "WKWebView API client did not respond to this postMessage",
      "Origin https://bustimes.org is not allowed by Access-Control-Allow-Origin.",
      "Failed to execute 'send' on 'XMLHttpRequest': Failed to load 'https://t.richaudience.com/",
      "undefined is not an object (evaluating 'navigator.connection.effectiveType')",
    ],
    integrations: [
      Sentry.globalHandlersIntegration({
        onerror: true,
        onunhandledrejection: false,
      }),
    ],
  });
}

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

const error = <LoadingSorry text="Sorry, something has gone wrong" />;

let rootElement: HTMLElement | null;
if ((rootElement = document.getElementById("history"))) {
  // vehicle journey history
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <Sentry.ErrorBoundary fallback={error}>
        <History />
      </Sentry.ErrorBoundary>
    </React.StrictMode>,
  );
} else if (
  window.SERVICE_ID &&
  (rootElement = document.getElementById("map-link"))
) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <Sentry.ErrorBoundary fallback={error}>
        <ServiceMap serviceId={window.SERVICE_ID} />
      </Sentry.ErrorBoundary>
    </React.StrictMode>,
  );
} else if ((rootElement = document.getElementById("hugemap"))) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <Sentry.ErrorBoundary fallback={error}>
        <MapRouter />
      </Sentry.ErrorBoundary>
    </React.StrictMode>,
  );
}
