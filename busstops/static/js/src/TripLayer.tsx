import React from "react";

import TripTimetable from "./TripTimetable";

const apiRoot = process.env.API_ROOT;

export default function TripLayer({ tripId }) {
  const [trip, setTrip] = React.useState(null);

  React.useEffect(() => {
    fetch(`${apiRoot}api/trips/${tripId}/`).then((response) => {
      if (response.ok) {
        response.json().then(setTrip);
      }
    });
  }, [tripId]);

  if (!trip || trip.id != tripId) {
    return (
      <div className="trip-timetable">
        <div className="sorry">Loading trip #{tripId}…</div>
      </div>
    );
  }

  return <TripTimetable trip={trip} />;
}
