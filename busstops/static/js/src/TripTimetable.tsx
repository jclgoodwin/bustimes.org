import React from "react";

function Row({ stop, onMouseEnter, vehicle, aimedColumn }) {
  const handleMouseEnter = React.useCallback(() => {
    if (onMouseEnter) {
      if (stop.stop.location) {
        onMouseEnter(stop);
      }
    }
  }, [stop, onMouseEnter]);

  let stopName = stop.stop.name;
  if (stop.stop.icon) {
    stopName = `${stopName} (${stop.stop.icon})`;
  }
  if (stop.stop.atco_code) {
    stopName = <a href={`/stops/${stop.stop.atco_code}`}>{stopName}</a>;
  }

  const className = stop.timing_status === "OTH" ? "minor" : null;

  const rowSpan =
    aimedColumn &&
    stop.aimed_arrival_time &&
    stop.aimed_departure_time &&
    stop.aimed_arrival_time !== stop.stop.aimed_departure_time
      ? 2
      : null;

  let actual;
  if (vehicle?.progress && vehicle.progress.prev_stop === stop.stop.atco_code) {
    actual = vehicle.datetime;
  } else {
    actual = stop.actual_departure_time;
  }
  if (actual) {
    actual = new Date(actual).toTimeString().slice(0, 8);
  } else {
    actual = stop.expected_departure_time || stop.expected_arrival_time;
  }
  if (actual) {
    actual = <td>{actual}</td>;
  }

  return (
    <React.Fragment>
      <tr className={className} onMouseEnter={handleMouseEnter}>
        <td className="stop-name" rowSpan={rowSpan}>
          {stopName}
        </td>
        {aimedColumn ? (
          <td>{stop.aimed_arrival_time || stop.aimed_departure_time}</td>
        ) : null}
        {actual}
      </tr>
      {rowSpan ? (
        <tr className={className}>
          <td>{stop.aimed_departure_time}</td>
        </tr>
      ) : null}
    </React.Fragment>
  );
}

const TripTimetable = React.memo(function TripTimetable({
  trip,
  onMouseEnter,
  vehicle,
  journey,
  loading = false,
}) {
  const last = trip.times?.length - 1;

  const aimedColumn = trip.times?.some(
    (item) => item.aimed_arrival_time || item.aimed_departure_time,
  );

  if (journey) {
    if (journey.previous) {
      let previous = new Date(journey.previous.datetime)
        .toTimeString()
        .slice(0, 5);
      var previousLink = (
        <p className="previous">
          <a href={`#journeys/${journey.previous.id}`}>&larr; {previous}</a>
        </p>
      );
    }
    if (journey.next) {
      let nextDate = new Date(journey.next.datetime).toTimeString().slice(0, 5);
      var nextLink = (
        <p className="next">
          <a href={`#journeys/${journey.next.id}`}>{nextDate} &rarr;</a>
        </p>
      );
    }
  }

  let className = "trip-timetable map-sidebar";
  if (loading) {
    className += " loading";
  }

  return (
    <div className={className}>
      {previousLink}
      {nextLink}
      {trip.times ? (
        <table>
          <thead>
            <tr>
              <th></th>
              {aimedColumn ? <th>Timetable</th> : null}
              <th>Actual</th>
            </tr>
          </thead>
          <tbody>
            {trip.times.map((stop, i) => (
              <Row
                key={stop.id || i}
                aimedColumn={aimedColumn}
                stop={stop}
                first={i === 0}
                last={i === last}
                onMouseEnter={onMouseEnter}
                vehicle={vehicle}
              />
            ))}
          </tbody>
        </table>
      ) : null}
      {trip.notes?.map((note) => <p key={note.code}>{note.text}</p>)}
    </div>
  );
});

export default TripTimetable;
