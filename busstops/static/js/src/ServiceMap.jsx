import React, { lazy, Suspense } from "react";

const ServiceMapMap = lazy(() => import("./ServiceMapMap"));

import loadjs from "loadjs";

const apiRoot = process.env.API_ROOT;

let hasHistory = false;
let hasCss = false;

export default function OperatorMap() {
  const [isOpen, setOpen] = React.useState(
    window.location.hash.indexOf("#map") === 0,
  );

  const openMap = React.useCallback((e) => {
    hasHistory = true;
    window.location.hash = "#map";
    e.preventDefault();
  }, []);

  const closeMap = React.useCallback(() => {
    if (isOpen) {
      if (hasHistory) {
        history.back();
      } else {
        window.location.hash = "";
      }
    }
  }, [isOpen]);

  const [vehicles, setVehicles] = React.useState(null);

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

  let timeout;

  React.useEffect(() => {
    if (isOpen) {
      document.body.classList.add("has-overlay");
      if (!hasCss) {
        loadjs(window.LIVERIES_CSS_URL, function () {
          hasCss = true;
        });
      }
    } else {
      document.body.classList.remove("has-overlay");
    }

    // service map data
    fetch(`/services/${window.SERVICE_ID}.json`).then((response) => {
      response.json().then((data) => {
        setGeometry(data.geometry);
        setStops(data.stops);
      });
    });

    const loadVehicles = () => {
      let url = apiRoot + "vehicles.json?service=" + window.SERVICE_ID;
      fetch(url).then((response) => {
        response.json().then((items) => {
          setVehicles(
            Object.assign({}, ...items.map((item) => ({ [item.id]: item }))),
          );
          clearTimeout(timeout);
          timeout = setTimeout(loadVehicles, 10000); // 10 seconds
        });
      });
    };

    loadVehicles();
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
  }, [isOpen]);

  const vehiclesList = vehicles ? Object.values(vehicles) : null;

  let count = vehiclesList && vehiclesList.length;

  if (count) {
    if (count === 1) {
      count = `${count} bus`;
    } else {
      count = `${count} buses`;
    }
  }

  const button = (
    <a className="button" href="#map" onClick={openMap}>
      Map
      {count ? ` (tracking ${count})` : null}
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
            vehiclesList={vehiclesList}
            geometry={geometry}
            stops={stops}
            count={count}
          />
        </Suspense>
      </div>
    </React.Fragment>
  );
}
