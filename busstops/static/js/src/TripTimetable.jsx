import React from "react";

function Row({ stop, onMouseEnter }) {
  const handleMouseEnter = React.useCallback(() => {
    if (stop.stop.location) {
      onMouseEnter(stop);
    }
  }, []);

  let stopName = stop.stop.name;
  if (stop.stop.atco_code) {
    stopName = <a href={`/stops/${stop.stop.atco_code}`}>{stopName}</a>;
  }

  const className = stop.timing_status == "OTH" ? "minor" : null;

  const rowSpan =
    stop.aimed_arrival_time &&
    stop.aimed_departure_time &&
    stop.aimed_arrival_time !== stop.stop.aimed_departure_time
      ? 2
      : null;

  return (
    <React.Fragment>
      <tr
        className={className}
        id={`stop-time-${stop.id}`}
        onMouseEnter={handleMouseEnter}
      >
        <td className="stop-name" rowSpan={rowSpan}>
          {stopName}
        </td>
        <td>{stop.aimed_arrival_time || stop.aimed_departure_time}</td>
        <td></td>
      </tr>
      {rowSpan ? (
        <tr className={className}>
          <td>{stop.aimed_departure_time}</td>
          <td></td>
        </tr>
      ) : null}
    </React.Fragment>
  );
}

export default function TripTimetable({ trip, onMouseEnter }) {
  const last = trip.times.length - 1;

  return (
    <div className="trip-timetable">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Timetable</th>
            <th>Actual</th>
          </tr>
        </thead>
        <tbody>
          {trip.times.map((stop, i) => (
            <Row
              key={stop.id}
              stop={stop}
              first={i === 0}
              last={i === last}
              onMouseEnter={onMouseEnter}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
