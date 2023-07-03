import React from "react";
import ReactDOM from "react-dom/client";

import BigMap from "./BigMap";
import OperatorMap from "./OperatorMap";
import ServiceMap from "./ServiceMap";

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
