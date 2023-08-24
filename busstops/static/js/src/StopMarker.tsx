import React, { memo } from "react";
import { Marker } from "react-map-gl/maplibre";

function StopMarker({ stop, onClick }) {
  let className = "stop";

  let rotation = stop.properties.bearing;

  if (rotation === null) {
    className += " no-direction";
  } else {
    rotation += 45;
  }

  if (stop.properties.icon) {
    if (stop.properties.icon.length === 1) {
      className += " stop-1";
    }
  } else {
    className += " stop-0";
  }

  return (
    <Marker
      latitude={stop.geometry.coordinates[1]}
      longitude={stop.geometry.coordinates[0]}
      onClick={(event) => {
        event.originalEvent.preventDefault();
        onClick(stop);
      }}
    >
      <div className={className}>
        {stop.properties.icon}
        <div
          className="stop-arrow"
          style={{ transform: `rotate(${rotation}deg)` }}
        />
      </div>
    </Marker>
  );
}

function propsAreEqual() {
  return true;
}

export default memo(StopMarker, propsAreEqual);
