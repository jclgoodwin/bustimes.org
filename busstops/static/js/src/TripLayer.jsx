import React from "react";

import TripTimetable from "./TripTimetable";

const apiRoot = "https://bustimes.org";

export default function TripLayer({ tripId }) {
  const [trip, setTrip] = React.useState(null);

  React.useEffect(() => {
    fetch(`${apiRoot}/api/trips/${tripId}/`).then((response) => {
      response.json().then(setTrip);
    });
  }, []);

  if (!trip) {
    return null;
  }

  return <TripTimetable trip={ trip } />;
}
