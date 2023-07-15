import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";

const JourneyMap = lazy(() => import("./JourneyMap"));

const apiRoot = "https://bustimes.org/";

let hasHistory = false;
let hasCss = false;

export default function History() {
  const [isOpen, setOpen] = React.useState(
    window.location.hash.indexOf("#journeys/") === 0,
  );

  const closeMap = React.useCallback(() => {
    if (isOpen) {
      if (hasHistory) {
        history.back();
      } else {
        window.location.hash = "";
      }
    }
  }, [isOpen]);

  const [journey, setJourney] = React.useState(null);

  React.useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash.indexOf("#journeys/") === 0) {
        setOpen(true);
      } else {
        setOpen(false);
      }
    };

    const handleKeyDown = () => {
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

  // let timeout;

  React.useEffect(() => {
    if (isOpen) {
      document.body.classList.add("has-overlay");

      let journey = window.location.hash.slice(1);

      // fetch(`/static/js/cookies.json`).then((response) => {
      fetch(`/${journey}.json`).then((response) => {
        if (response.ok) {
          response.json().then((data) => {
            setJourney(data);
          });
        }
      });

    } else {
      document.body.classList.remove("has-overlay");
    }


  }, [isOpen]);

  if (!isOpen) {
    return;
  }

  const closeButton = (
    <button onClick={closeMap} className="map-button">
       Close map
     </button>
  );

  return (
    <React.Fragment>
      <div className="service-map">
        {closeButton}
        <Suspense fallback={<div className="sorry">Loading…</div>}>
          <JourneyMap
            journey={journey}
          />
        </Suspense>
      </div>
    </React.Fragment>
  );
}
