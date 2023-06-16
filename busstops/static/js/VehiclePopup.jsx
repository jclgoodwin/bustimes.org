import React from "react";
import { Popup } from "react-map-gl/maplibre";

function VehiclePopup({ item, onClose }) {
  let line_name = item.service?.line_name;
  if (item.destination) {
    if (line_name) {
      line_name += ' to ';
    }
    line_name += item.destination;
  }

  let vehicle = item.vehicle.name;
  if (item.vehicle.url) {
    vehicle = (
      <a href={`https://bustimes.org${item.vehicle.url}`}>
        {vehicle}
      </a>
    );
  }

  const date = new Date(item.datetime);

  return (
    <Popup
      offset={8}
      latitude={item.coordinates[1]}
      longitude={item.coordinates[0]}
      closeOnClick={false}
      onClose={onClose}
    >
      <div>
        {line_name}
      </div>
      {vehicle}
      { item.features && <div>{item.vehicle.features}</div> }
      <div>{ date.toTimeString().slice(0, 8) }</div>
    </Popup>
  );
}

export default VehiclePopup;
