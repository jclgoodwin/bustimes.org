import React from "react";

import TripTimetable from "./TripTimetable";

const apiRoot = process.env.API_ROOT;

export default function TripLayer({ tripId }) {
  const [trip, setTrip] = React.useState(null);

  React.useEffect(() => {
    setTrip(null);
    fetch(`${apiRoot}api/trips/${tripId}/`).then((response) => {
      if (response.ok) {
        response.json().then(setTrip);
      }
    });
  }, [tripId]);

  if (!trip) {
    return (
      <div className="trip-timetable">
        <div className="sorry">Loading trip #{tripId}…</div>
      </div>
    );
  }


  debugger;
  return <TripTimetable trip={trip} />;
}
