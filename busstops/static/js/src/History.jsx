import React, { lazy, Suspense } from "react";

const JourneyMap = lazy(() => import("./JourneyMap"));

const apiRoot = "https://bustimes.org/";
let hasHistory = 0;

export default function History() {
  const [isOpen, setOpen] = React.useState(
    window.location.hash.indexOf("#journeys/") === 0,
  );

  const closeMap = React.useCallback(() => {
    if (isOpen) {
      if (hasHistory) {
        history.back();
        hasHistory -= 1;
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
        hasHistory += 1;
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

      const journeyId = window.location.hash.slice(1);

      if (journey) {
        if (journeyId !== journey.id) {
          setJourney(null);
        }
      }

      // fetch(`/static/js/cookies.json`).then((response) => {
      fetch(`${apiRoot}${journeyId}.json`).then((response) => {
        if (response.ok) {
          response.json().then((data) => {
            data.id = journeyId;
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
          <JourneyMap journey={journey} />
        </Suspense>
      </div>
    </React.Fragment>
  );
}
