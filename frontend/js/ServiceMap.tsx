import React, { lazy, Suspense } from "react";
import { createPortal } from "react-dom";

import loadjs from "loadjs";
import LoadingSorry from "./LoadingSorry";
import type { Vehicle } from "./VehicleMarker";

const ServiceMapMap = lazy(() => import("./ServiceMapMap"));

const apiRoot = process.env.API_ROOT;

let hasCss = false;

declare global {
  interface Window {
    LIVERIES_CSS_URL: string;
    SERVICES?: {
      id: number;
      line_names: string[];
    }[];
  }
}

type ServiceMapProps = {
  serviceId: number;
};

const mapContainer = document.getElementById("map");

export default function ServiceMap({ serviceId }: ServiceMapProps) {
  const [isOpen, setOpen] = React.useState(() => {
    return window.location.hash === "#map";
  });

  const closeMap = React.useCallback(() => {
    if (isOpen) {
      if (window.history.state?.hasHistory) {
        window.history.back();
      } else {
        window.location.hash = "";
      }
    }
  }, [isOpen]);

  const [vehicles, setVehicles] = React.useState<Vehicle[]>();

  const [stops, setStops] = React.useState();

  const [geometry, setGeometry] = React.useState();

  React.useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === "#map") {
        setOpen(true);
        window.history.replaceState({ hasHistory: true }, "");
      } else {
        setOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      // ESC
      if (isOpen && event.key === "Escape") {
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

  const [selectedServices, setSelectedServices] = React.useState(
    new Set<number>([serviceId]),
  );

  const handleSelectService = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const serviceId = Number.parseInt(event.target.value, 10);
      if (event.target.checked) {
        selectedServices.add(serviceId);
      } else {
        selectedServices.delete(serviceId);
      }
      setSelectedServices(new Set(selectedServices));
    },
    [selectedServices],
  );

  const first = React.useRef(true);

  React.useEffect(() => {
    let timeout: number;

    if (isOpen) {
      document.body.classList.add("has-overlay");
      if (!hasCss) {
        loadjs(window.LIVERIES_CSS_URL, () => {
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
        () => {
          // never mind
        },
      );
    } else {
      document.body.classList.remove("has-overlay");
    }

    const loadVehicles = () => {
      if ((document.hidden && !first.current) || !selectedServices.size) {
        return;
      }

      const url = `${apiRoot}vehicles.json?service=${Array.from(selectedServices).join(",")}`;
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
        () => {
          // never mind
        },
      );
    };

    if (isOpen || first.current) {
      loadVehicles();
    }
    first.current = false;

    const handleVisibilityChange = () => {
      if (document.hidden) {
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
  }, [isOpen, serviceId, selectedServices]);

  const count = vehicles?.length;
  let countString: string | undefined;

  if (count) {
    if (count === 1) {
      countString = `${count} bus`;
    } else {
      countString = `${count} buses`;
    }
  }

  const button = (
    <a href="#map">
      Map
      {countString ? ` (tracking ${countString})` : null}
    </a>
  );

  if (!isOpen || !mapContainer) {
    return button;
  }

  const closeButton = (
    <button type="button" onClick={closeMap} className="map-button">
      Close map
    </button>
  );

  return (
    <React.Fragment>
      {button}
      {createPortal(
        <div className="service-map">
          {closeButton}
          {window.SERVICES ? (
            <div className="map-select-services">
              {window.SERVICES.map((service) => (
                <label key={service.id}>
                  <input
                    type="checkbox"
                    value={service.id}
                    checked={selectedServices.has(service.id)}
                    onChange={handleSelectService}
                  />{" "}
                  {service.line_names.join(", ")}
                </label>
              ))}
            </div>
          ) : null}
          <Suspense fallback={<LoadingSorry />}>
            <ServiceMapMap
              vehicles={vehicles}
              geometry={geometry}
              stops={stops}
            />
          </Suspense>
        </div>,
        mapContainer,
      )}
    </React.Fragment>
  );
}
