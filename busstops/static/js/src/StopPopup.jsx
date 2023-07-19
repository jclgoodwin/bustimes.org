import React from "react";
import { Popup } from "react-map-gl/maplibre";

export default function StopPopup({ item, onClose }) {
  return (
    <Popup
      offset={2}
      latitude={item.geometry.coordinates[1]}
      longitude={item.geometry.coordinates[0]}
      closeOnClick={false}
      onClose={onClose}
    >
      <a href={item.properties.url} className="link-with-smalls">
        <div className="description">{item.properties.name}</div>
        <div className="smalls">{item.properties.services?.join(" ")}</div>
      </a>
    </Popup>
  );
}
