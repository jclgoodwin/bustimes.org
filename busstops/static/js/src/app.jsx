import React, { lazy } from "react";
import ReactDOM from "react-dom/client";

const BigMap = lazy(() => import("./BigMap"));
const OperatorMap = lazy(() => import("./OperatorMap"));
const ServiceMap = lazy(() => import("./ServiceMap"));

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
