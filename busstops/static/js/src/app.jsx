import React from "react";
import ReactDOM from "react-dom/client";

import OperatorMap from "./OperatorMap";
import BigMap from "./BigMap";

let root = document.getElementById("hugemap");
if (root) {
  root = ReactDOM.createRoot(root);
  root.render(
    <React.StrictMode>
      <BigMap />
    </React.StrictMode>
  );
} else if (window.location.href.indexOf("/operators/") !== -1) {
  const root = ReactDOM.createRoot(document.getElementById("map"));
  root.render(
    <React.StrictMode>
      <OperatorMap />
    </React.StrictMode>
  );
}
