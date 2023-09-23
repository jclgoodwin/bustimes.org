import React, { ReactElement } from "react";
import { Vehicle } from "./VehicleMarker";

export type TripTime = {
  id: number;
  stop: {
    name: string;
    atco_code?: string;
    location?: [number, number];
    icon?: string | null;
    bearing?: number | null;
  };
  track?: [number, number][] | null;
  aimed_arrival_time: string | null;
  aimed_departure_time: string | null;
  expected_arrival_time?: string | null;
  expected_departure_time?: string | null;
  actual_departure_time?: string;
  // actual_arrival_time: string;
  timing_status: string;
  pick_up?: boolean;
  set_down?: boolean;
};

type Note = {
  code: string;
  text: string;
};

export type Trip = {
  id?: number;
  vehicle_journey_code?: string;
  ticket_machine_code?: string;
  block?: string;
  service?: { id: number; line_name: string; mode: string };
  operator?: { noc: string; name: string; vehicle_mode: string };
  times: TripTime[];
  notes?: Note[];
};

function Row({ stop, onMouseEnter, vehicle, aimedColumn, highlightedStop}: {
  stop: TripTime;
  onMouseEnter?: (stop: TripTime) => void;
  vehicle?: Vehicle;
  aimedColumn?: boolean;
  highlightedStop?: string
}) {
  const handleMouseEnter = React.useCallback(() => {
    if (onMouseEnter) {
      if (stop.stop.location) {
        onMouseEnter(stop);
      }
    }
  }, [stop, onMouseEnter]);

  let className;

  let stopName: string | ReactElement = stop.stop.name;
  if (stop.stop.icon) {
    stopName = `${stopName} (${stop.stop.icon})`;
  }
  if (stop.stop.atco_code) {
    let url = `/stops/${stop.stop.atco_code}`;
    if (url === highlightedStop) {
      className = "is-highlighted";
    }
    stopName = <a href={url}>{stopName}</a>;
  }

  if (stop.timing_status && stop.timing_status !== "PTP") {
    className = className ? className + " minor" : "minor";
  }


  let rowSpan;
  if (
    aimedColumn &&
    stop.aimed_arrival_time &&
    stop.aimed_departure_time &&
    stop.aimed_arrival_time !== stop.aimed_departure_time
  ) {
    rowSpan = 2;
  }

  let actual,
    actualRowSpan = rowSpan;

  actual = stop.expected_departure_time || stop.expected_arrival_time; // Irish live departures

  if (!actual) {
    if (
      vehicle?.progress &&
      vehicle.progress.prev_stop === stop.stop.atco_code
    ) {
      actual = vehicle.datetime;
      if (vehicle.progress.progress > 0.1) {
        actualRowSpan = 2;
      }
    } else {
      actual = stop.actual_departure_time; // vehicle history
    }
    if (actual) {
      actual = new Date(actual).toTimeString().slice(0, 8);
    }
  }
  if (actual) {
    actual = <td rowSpan={actualRowSpan}>{actual}</td>;
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
  highlightedStop
}: {
  trip: Trip;
  onMouseEnter?: (stop: TripTime) => void;
  vehicle?: Vehicle;
  loading?: boolean | null;
  highlightedStop?: string;
}) {
  const aimedColumn = trip.times?.some(
    (item: TripTime) => item.aimed_arrival_time || item.aimed_departure_time,
  );

  return (
    <React.Fragment>
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
              onMouseEnter={onMouseEnter}
              vehicle={vehicle}
              highlightedStop={highlightedStop}
            />
          ))}
        </tbody>
      </table>
      {trip.notes?.map((note) => <p key={note.code}>{note.text}</p>)}
    </React.Fragment>
  );
});

export default TripTimetable;
