import React, { lazy, MouseEvent, Suspense } from "react";

import loadjs from "loadjs";
import { Vehicle } from "./VehicleMarker";

const ServiceMapMap = lazy(() => import("./ServiceMapMap"));

const apiRoot = process.env.API_ROOT;

let hasHistory = false;
let hasCss = false;

declare global {
  interface Window {
    LIVERIES_CSS_URL: string;
  }
}

type ServiceMapProps = {
  serviceId: number;
};

export default function ServiceMap({ serviceId }: ServiceMapProps) {
  const [isOpen, setOpen] = React.useState(() => {
    return window.location.hash.indexOf("#map") === 0;
  });

  const openMap = React.useCallback((e: MouseEvent) => {
    hasHistory = true;
    window.location.hash = "#map";
    e.preventDefault();
  }, []);

  const closeMap = React.useCallback(() => {
    if (isOpen) {
      if (hasHistory) {
        window.history.back();
      } else {
        window.location.hash = "";
      }
    }
  }, [isOpen]);

  const [vehicles, setVehicles] = React.useState<Vehicle[]>();

  const [stops, setStops] = React.useState(null);

  const [geometry, setGeometry] = React.useState(null);

  React.useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash.indexOf("#map") === 0) {
        setOpen(true);
      } else {
        setOpen(false);
      }
    };

    const handleKeyDown = (event) => {
      // ESC
      if (isOpen && event.keyCode === 27) {
        closeMap();
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      window.removeEventListener("keydown", handleKeyDown);
    };
  });

  const first = React.useRef(true);

  React.useEffect(() => {
    let timeout: number;

    if (isOpen) {
      document.body.classList.add("has-overlay");
      if (!hasCss) {
        loadjs(window.LIVERIES_CSS_URL, function () {
          hasCss = true;
        });
      }

      // service map data
      // TODO: linked services
      fetch(`/services/${serviceId}.json`).then(
        (response) => {
          if (response.ok) {
            response.json().then((data) => {
              setGeometry(data.geometry);
              setStops(data.stops);
            });
          }
        },
        (reason) => {
          // never mind
        },
      );
    } else {
      document.body.classList.remove("has-overlay");
    }

    const loadVehicles = () => {
      if (document.hidden) {
        return;
      }

      let url = apiRoot + "vehicles.json?service=" + window.SERVICE_ID;
      fetch(url).then(
        (response) => {
          if (response.ok) {
            response.json().then((items) => {
              setVehicles(items);
              clearTimeout(timeout);
              if (isOpen && items.length && !document.hidden) {
                timeout = window.setTimeout(loadVehicles, 10000); // 10 seconds
              }
            });
          }
        },
        (reason) => {
          // never mind
        },
      );
    };

    if (isOpen || first.current) {
      loadVehicles();
    }
    first.current = false;

    const handleVisibilityChange = (event) => {
      if (event.target.hidden) {
        clearTimeout(timeout);
      } else {
        loadVehicles();
      }
    };

    if (isOpen) {
      window.addEventListener("visibilitychange", handleVisibilityChange);
    }

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
    };
  }, [isOpen, serviceId]);

  let count = vehicles && vehicles.length,
    countString: string | undefined;

  if (count) {
    if (count === 1) {
      countString = `${count} bus`;
    } else {
      countString = `${count} buses`;
    }
  }

  const button = (
    <a className="button" href="#map" onClick={openMap}>
      Map
      {countString ? ` (tracking ${countString})` : null}
    </a>
  );

  if (!isOpen) {
    return button;
  }

  const closeButton = (
    <button onClick={closeMap} className="map-button">
      Close map
    </button>
  );

  return (
    <React.Fragment>
      {button}
      <div className="service-map">
        {closeButton}
        <Suspense fallback={<div className="sorry">Loading…</div>}>
          <ServiceMapMap
            vehicles={vehicles}
            geometry={geometry}
            stops={stops}
          />
        </Suspense>
      </div>
    </React.Fragment>
  );
}
