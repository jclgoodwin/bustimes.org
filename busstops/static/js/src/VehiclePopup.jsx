import React, { memo } from "react";
import { Popup } from "react-map-gl/maplibre";
import ReactTimeAgo from "react-time-ago";

import TimeAgo from "javascript-time-ago";

import en from "javascript-time-ago/locale/en.json";
TimeAgo.addDefaultLocale(en);

function getTimeDelta(seconds) {
  const minutes = Math.round(seconds / 60);
  if (minutes === 1) {
    return "1 minute";
  }
  return minutes + " minutes";
}

function Delay({ item }) {
  let delay = item.delay;
  if (typeof delay !== "undefined") {
    if (-60 < delay && delay < 60) {
      delay = "On time";
    } else {
      if (delay < 0) {
        delay *= -1;
      }
      delay = getTimeDelta(delay);
      if (item.delay < 0) {
        delay += " early";
      } else {
        delay += " late";
      }
    }
    return <div>{delay}</div>;
  }
}

export default function VehiclePopup({
  item,
  onClose,
  closeButton = true,
  onTripClick = null,
}) {
  const handleTripClick = React.useCallback(
    (e) => {
      if (onTripClick) {
        e.preventDefault();
        onTripClick(item);
      }
    },
    [item],
  );

  let line_name = item.service?.line_name;
  if (item.destination) {
    if (line_name) {
      line_name += " to ";
    }
    line_name += item.destination;
  }

  if (item.tfl_code) {
    line_name = <a href={`/vehicles/tfl/${item.tfl_code}`}>{line_name}</a>;
  } else if (item.trip_id) {
    if (item.trip_id != window.TRIP_ID) {
      line_name = (
        <a href={`/trips/${item.trip_id}`} onClick={handleTripClick}>
          {line_name}
        </a>
      );
    }
  } else if (item.service?.url) {
    if (item.service.url != window.location.pathname) {
      line_name = <a href={item.service.url}>{line_name}</a>;
    }
  }

  let vehicle = item.vehicle.name;
  if (item.vehicle.url) {
    vehicle = <a href={`${item.vehicle.url}`}>{vehicle}</a>;
  }

  const date = new Date(item.datetime);

  return (
    <Popup
      offset={8}
      latitude={item.coordinates[1]}
      longitude={item.coordinates[0]}
      closeOnClick={false}
      onClose={onClose}
      closeButton={closeButton}
    >
      <div>{line_name}</div>
      {vehicle}
      {item.vehicle.features && (
        <div>{item.vehicle.features.replace("<br>", ", ")}</div>
      )}
      {item.seats && (
        <div>
          <img alt="" src="/static/svg/seat.svg" width="14" height="14" />{" "}
          {item.seats}
        </div>
      )}
      {item.wheelchair && (
        <div>
          <img
            alt="wheelchair"
            src="/static/svg/wheelchair.svg"
            width="14"
            height="14"
          />{" "}
          {item.wheelchair}
        </div>
      )}
      <Delay item={item} />
      <div>
        <ReactTimeAgo
          date={date}
          locale="en-GB"
          tooltip={true}
          timeStyle="round"
        />
      </div>
    </Popup>
  );
}
