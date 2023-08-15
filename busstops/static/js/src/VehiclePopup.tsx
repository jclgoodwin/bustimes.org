import React from "react";
import { Popup } from "react-map-gl/maplibre";
import ReactTimeAgo from "react-time-ago";

import TimeAgo from "javascript-time-ago";

import en from "javascript-time-ago/locale/en.json";
TimeAgo.addDefaultLocale(en);

function getTimeDelta(seconds: number) {
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
  activeLink = false,
}) {
  const handleTripClick = React.useCallback(
    (e) => {
      if (onTripClick) {
        e.preventDefault();
        onTripClick(item);
      }
    },
    [item, onTripClick],
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
    if (!activeLink) {
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
      focusAfterOpen={false}
    >
      <div>{line_name}</div>
      {vehicle}
      {item.vehicle.features && (
        <div>{item.vehicle.features.replace("<br>", ", ")}</div>
      )}
      {item.seats && (
        <div>
          <svg
            role="img"
            width="14"
            height="14"
            viewBox="0 0 118 177"
            xmlns="http://www.w3.org/2000/svg"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeMiterlimit="1.5"
          >
            <title>Seats</title>
            <path
              d="M108 9l-19 99-80-1 48 1v59"
              fill="none"
              stroke="currentColor"
              strokeWidth="18"
            />
          </svg>{" "}
          {item.seats}
        </div>
      )}
      {item.wheelchair && (
        <div>
          <svg
            role="img"
            width="14"
            height="14"
            viewBox="0 0 506 647"
            xmlns="http://www.w3.org/2000/svg"
            strokeLinejoin="round"
            strokeMiterlimit="2"
          >
            <title>Wheelchair space</title>
            <path
              fill="currentColor"
              d="M494.28 293.25a38.5 38.5 0 00-29.66-11.55l-133.98 7.46 73.74-83.97a45.03 45.03 0 009.44-42.16 38.26 38.26 0 00-17.14-24.32c-.28-.2-176.25-102.43-176.25-102.43a38.42 38.42 0 00-44.87 4.56L89.6 117.5a38.43 38.43 0 1051.16 57.35l65.17-58.13 53.87 31.29-95.1 108.3a195.94 195.94 0 00-102.76 50.8l49.66 49.66a125.86 125.86 0 0184.92-32.87c69.66 0 126.34 56.68 126.34 126.35 0 32.66-12.46 62.47-32.87 84.92l49.66 49.65a195.76 195.76 0 0053.38-134.57c0-31.04-7.2-60.39-20.01-86.48l51.86-2.9-12.62 154.76a38.43 38.43 0 0076.6 6.24l16.2-198.68a38.42 38.42 0 00-10.78-29.95zM423.1 128.65A64.32 64.32 0 10423.1 0a64.32 64.32 0 000 128.65zM196.52 576.6c-69.67 0-126.35-56.67-126.35-126.34 0-26.26 8.06-50.66 21.82-70.89l-50.2-50.2A195.62 195.62 0 000 450.27c0 108.53 87.98 196.51 196.52 196.51 45.69 0 87.7-15.63 121.08-41.79l-50.2-50.19a125.64 125.64 0 01-70.88 21.82z"
            />
          </svg>{" "}
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
