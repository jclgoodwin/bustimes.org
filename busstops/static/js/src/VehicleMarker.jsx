import React, { memo } from "react";
import { Marker } from "react-map-gl/maplibre";

function VehicleMarker({ vehicle, selected, onClick }) {
  let className = "vehicle-marker";

  let rotation = vehicle.heading;

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += " right";
    } else {
      rotation -= 270;
    }
  }

  if (vehicle.vehicle.livery) {
    className += " livery-" + vehicle.vehicle.livery;
  }

  if (selected) {
    className += " selected";
  }

  let css = vehicle.vehicle.css;
  if (css) {
    css = {
      background: css,
    };
    if (vehicle.vehicle.text_colour) {
      className += " white-text";
    }
  }

  let marker = vehicle.service?.line_name;

  if (vehicle.vehicle.livery && vehicle.vehicle.livery != 262) {
    marker = (
      <svg className={className} style={css}>
        <text x="12" y="12">
          {marker}
        </text>
      </svg>
    );
  } else {
    marker = (
      <div className={className} style={css}>
        {marker}
      </div>
    );
  }

  return (
    <Marker
      latitude={vehicle.coordinates[1]}
      longitude={vehicle.coordinates[0]}
      rotation={rotation}
      style={selected ? { zIndex: 1 } : { zIndex: null }}
      onClick={(event) => onClick(event, vehicle.id)}
    >
      {marker}
      {rotation == null ? null : <div className="arrow" />}
    </Marker>
  );
}

function propsAreEqual(prev, props) {
  return (
    prev.selected === props.selected &&
    prev.vehicle.datetime === props.vehicle.datetime
  );
}

export default memo(VehicleMarker, propsAreEqual);
