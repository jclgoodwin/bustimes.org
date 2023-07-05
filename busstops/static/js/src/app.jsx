import React, { lazy } from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";

const BigMap = lazy(() => import("./BigMap"));
const OperatorMap = lazy(() => import("./OperatorMap"));
const ServiceMap = lazy(() => import("./ServiceMap"));

Sentry.init({
  dsn: "https://0d628b6fff45463bb803d045b99aa542@o55224.ingest.sentry.io/1379883",
  // allowUrls: [/bustimes\.org\/static\//],
});

let root = document.getElementById("hugemap");
if (root) {
  root = ReactDOM.createRoot(root);
  root.render(
    <React.StrictMode>
      <BigMap />
    </React.StrictMode>
  );
} else if (window.location.href.indexOf("/operators/") !== -1) {
  root = ReactDOM.createRoot(document.getElementById("map"));
  root.render(
    <React.StrictMode>
      <OperatorMap />
    </React.StrictMode>
  );
} else if (window.SERVICE_ID) {
  root = ReactDOM.createRoot(document.getElementById("map"));
  root.render(
    <React.StrictMode>
      <ServiceMap />
    </React.StrictMode>
  );
}
