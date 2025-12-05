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
    allowUrls: [/https:\/\/bustimes\.org\/static\//],
    ignoreErrors: [
      "Failed to fetch dynamically imported module",
      "Load failed",
      "AbortError: The user aborted a request.",
    ],
    integrations: [
      Sentry.globalHandlersIntegration({
        onerror: false,
        onunhandledrejection: false,
      }),
    ],
    release: process.env.KAMAL_CONTAINER_NAME,
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

function error(error: { error?: unknown }) {
  return (
    <LoadingSorry
      text={error.error?.toString() || "Sorry, something has gone wrong"}
    />
  );
}

const createRootOptions = {
  // Callback called when an error is thrown and not caught by an ErrorBoundary.
  onUncaughtError: Sentry.reactErrorHandler((error, errorInfo) => {
    console.warn("Uncaught error", error, errorInfo.componentStack);
  }),
  // Callback called when React catches an error in an ErrorBoundary.
  onCaughtError: Sentry.reactErrorHandler(),
  // Callback called when React automatically recovers from errors.
  onRecoverableError: Sentry.reactErrorHandler(),
};

let rootElement: HTMLElement | null;
if ((rootElement = document.getElementById("history"))) {
  // vehicle journey history
  const root = createRoot(rootElement, createRootOptions);
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
  const root = createRoot(rootElement, createRootOptions);
  root.render(
    <React.StrictMode>
      <Sentry.ErrorBoundary fallback={error}>
        <ServiceMap
          serviceId={window.SERVICE_ID}
          buttonText={rootElement.innerText}
        />
      </Sentry.ErrorBoundary>
    </React.StrictMode>,
  );
} else if ((rootElement = document.getElementById("hugemap"))) {
  const root = createRoot(rootElement, createRootOptions);
  root.render(
    <React.StrictMode>
      <Sentry.ErrorBoundary fallback={error}>
        <MapRouter />
      </Sentry.ErrorBoundary>
    </React.StrictMode>,
  );
}
