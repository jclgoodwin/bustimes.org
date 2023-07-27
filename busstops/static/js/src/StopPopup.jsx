import React from "react";
import { Popup } from "react-map-gl/maplibre";

export default function StopPopup({ item, onClose, anchor }) {
  let services = item.properties.services;
  if (services?.join) {
    services = services.join(" ");
  }
  return (
    <Popup
      offset={2}
      latitude={item.geometry.coordinates[1]}
      longitude={item.geometry.coordinates[0]}
      closeOnClick={false}
      onClose={onClose}
      anchor={anchor}
    >
      <a href={item.properties.url} className="link-with-smalls">
        <div className="description">{item.properties.name}</div>
        <div className="smalls">{item.properties.services}</div>
      </a>
    </Popup>
  );
}
