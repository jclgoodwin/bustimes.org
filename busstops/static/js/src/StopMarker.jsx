import React, { memo } from "react";
import { Marker } from "react-map-gl/maplibre";

function StopMarker(props) {
  let className = "stop";

  let rotation = props.stop.properties.bearing;

  if (rotation === null) {
    className += " no-direction"
  } else {
    rotation += 45;
  }

  if (props.stop.properties.icon) {
    if (props.stop.properties.icon.length === 1) {
      className += " stop-1";
    }
  } else {
    className += " stop-0";
  }

  return (
    <Marker
      latitude={props.stop.geometry.coordinates[1]}
      longitude={props.stop.geometry.coordinates[0]}
      onClick={(event) => {
        event.originalEvent.preventDefault();
        props.onClick(props.stop);
      }}
    >
      <div className={className}>
        {props.stop.properties.icon}
        <div
          className="stop-arrow"
          style={{ transform: `rotate(${rotation}deg)` }}
        />
      </div>
    </Marker>
  );
}

function propsAreEqual(prev, props) {
  return true;
}

export default memo(StopMarker, propsAreEqual);
