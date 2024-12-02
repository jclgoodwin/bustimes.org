import React from "react";
import { createRoot } from "react-dom/client";

import History from "./History";

const rootElement = document.getElementById("history") as Element;
// vehicle journey history
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
        <History />
    </React.StrictMode>,
  );
