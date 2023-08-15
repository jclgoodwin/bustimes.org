import React, { lazy, Suspense } from "react";

const JourneyMap = lazy(() => import("./JourneyMap"));

const apiRoot = process.env.API_ROOT;
let hasHistory = 0;

export default function History() {
  const [journeyId, setJourneyId] = React.useState(() => {
    if (window.location.hash.indexOf("#journeys/") === 0) {
      return window.location.hash.slice(1);
    }
  });

  const [loading, setLoading] = React.useState(true);

  const closeMap = React.useCallback(() => {
    if (journeyId) {
      if (hasHistory === 1) {
        window.history.back();
        hasHistory -= 1;
      } else {
        window.location.hash = "";
        hasHistory = 0;
      }
    }
  }, [journeyId]);

  const [journey, setJourney] = React.useState(null);

  React.useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash.indexOf("#journeys/") === 0) {
        setJourneyId(window.location.hash.slice(1));
        hasHistory += 1;
      } else {
        setJourneyId(null);
      }
    };

    const handleKeyDown = (event) => {
      // ESC
      if (journeyId && event.keyCode === 27) {
        closeMap();
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("hashchange", handleHashChange);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [journeyId, closeMap]);

  // let timeout;

  React.useEffect(() => {
    if (journeyId) {
      document.body.classList.add("has-overlay");

      setLoading(true);

      fetch(`${apiRoot}${journeyId}.json`).then((response) => {
        if (response.ok) {
          response.json().then((data) => {
            data.id = journeyId;
            setLoading(false);
            setJourney(data);
          });
        }
      });
    } else {
      document.body.classList.remove("has-overlay");
    }
  }, [journeyId]);

  if (!journeyId) {
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
          <JourneyMap journey={journey} loading={loading} />
        </Suspense>
      </div>
    </React.Fragment>
  );
}
