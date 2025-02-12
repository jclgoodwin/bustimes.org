import React, { type ReactElement } from "react";
import { Popup } from "react-map-gl/maplibre";

export type Stop = {
  type: "Feature";
  properties: {
    name: string;
    url: string;
    services?: string[];
  };
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
};

type StopPopupProps = {
  item: Stop;
  onClose: () => void;
};

export default function StopPopup({ item, onClose }: StopPopupProps) {
  let name: ReactElement;

  if (item.properties.url) {
    name = (
      <a href={item.properties.url} className="link-with-smalls">
        <div className="description">{item.properties.name}</div>
        {item.properties.services ? (
          <div className="smalls">
            {item.properties.services.join("\u00A0 ")}
          </div>
        ) : null}
      </a>
    );
  } else {
    name = <div>{item.properties.name}</div>;
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
