import React from "react";

import TripTimetable, { Trip } from "./TripTimetable";

const apiRoot = process.env.API_ROOT;

export default function TripLayer({ tripId }: { tripId: number }) {
  const [trip, setTrip] = React.useState<Trip>();

  React.useEffect(() => {
    fetch(`${apiRoot}api/trips/${tripId}/`).then((response) => {
      if (response.ok) {
        response.json().then(setTrip);
      }
    });
  }, [tripId]);

  if (!trip || trip.id !== tripId) {
    return (
      <div className="trip-timetable">
        <div className="sorry">Loading trip #{tripId}…</div>
      </div>
    );
  }

  return <TripTimetable trip={trip} />;
}
