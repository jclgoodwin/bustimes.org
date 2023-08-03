import React from "react";
import { Popup } from "react-map-gl/maplibre";

export default function StopPopup({ item, onClose, anchor }) {
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
        {item.properties.services ? (
          <div className="smalls">
            {item.properties.services.join("\u00A0 ")}
          </div>
        ) : null}
      </a>
    </Popup>
  );
}
