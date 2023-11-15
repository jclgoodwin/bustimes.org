import React, { lazy } from "react";
import { createRoot } from "react-dom/client";
import * as Sentry from "@sentry/react";

import "./maps.css";
import "maplibre-gl/dist/maplibre-gl.css";
import { Trip } from "./TripTimetable";

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
    "TypeError: Load failed",
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
  ],
  integrations: [
    new Sentry.Integrations.GlobalHandlers({
      onerror: true,
      onunhandledrejection: false,
    }),
  ],
});

declare global {
  interface Window {
    SERVICE_ID: number;
    STOPS: Trip;
    OPERATOR_ID: string;
  }
}

const error = <div className="sorry">Sorry, something has gone wrong</div>;

let rootElement = document.getElementById("hugemap");
if (rootElement) {
  let root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <Sentry.ErrorBoundary fallback={error}>
        <BigMap />
      </Sentry.ErrorBoundary>
    </React.StrictMode>,
  );
} else {
  rootElement = document.getElementById("map");
  if (rootElement) {
    if (window.location.href.indexOf("/operators/") !== -1) {
      let root = createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <Sentry.ErrorBoundary fallback={error}>
            <OperatorMap noc={window.OPERATOR_ID} />
          </Sentry.ErrorBoundary>
        </React.StrictMode>,
      );
    } else if (window.SERVICE_ID) {
      let root = createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <Sentry.ErrorBoundary fallback={error}>
            <ServiceMap serviceId={window.SERVICE_ID} />
          </Sentry.ErrorBoundary>
        </React.StrictMode>,
      );
    } else if (window.STOPS) {
      let root = createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <Sentry.ErrorBoundary fallback={error}>
            <TripMap />
          </Sentry.ErrorBoundary>
        </React.StrictMode>,
      );
    }
  } else {
    let rootElement = document.getElementById("history");
    if (rootElement) {
      let root = createRoot(rootElement);
      root.render(
        <React.StrictMode>
          <Sentry.ErrorBoundary fallback={error}>
            <History />
          </Sentry.ErrorBoundary>
        </React.StrictMode>,
      );
    }
  }
}
