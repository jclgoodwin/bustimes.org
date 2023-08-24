import React from "react";
import { Popup } from "react-map-gl/maplibre";

export default function StopPopup({ item, onClose }) {
  let name = item.properties.name;

  if (item.properties.url) {
    name = (
      <a href={item.properties.url} className="link-with-smalls">
        <div className="description">{name}</div>
        {item.properties.services ? (
          <div className="smalls">
            {item.properties.services.join("\u00A0 ")}
          </div>
        ) : null}
      </a>
    );
  } else {
    name = <div>{name}</div>;
  }

  return (
    <Popup
      offset={2}
      latitude={item.geometry.coordinates[1]}
      longitude={item.geometry.coordinates[0]}
      closeOnClick={false}
      onClose={onClose}
      focusAfterOpen={false}
    >
      {name}
    </Popup>
  );
}
