import React from "react";

import { createRoot } from "react-dom/client";
import MapRouter from "./MapRouter";

const rootElement = document.getElementById("hugemap") as Element;
const root = createRoot(rootElement);
root.render(
  <React.StrictMode>
    <MapRouter />
  </React.StrictMode>,
);
