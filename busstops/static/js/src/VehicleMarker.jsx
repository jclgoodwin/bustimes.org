import React, { memo } from "react";
import { Marker } from "react-map-gl/maplibre";

function VehicleMarker({ vehicle, selected }) {
  let className = "vehicle-marker";

  let rotation = vehicle.heading;

  let css = vehicle.vehicle.css;

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += " right";
      if (vehicle.vehicle.right_css) {
        css = vehicle.vehicle.right_css;
      }
    } else {
      rotation -= 270;
    }
  }

  if (vehicle.vehicle.livery) {
    className += " livery-" + vehicle.vehicle.livery;
  } else if (css) {
    css = {
      background: css,
    };
    if (vehicle.vehicle.text_colour) {
      className += " white-text";
    }
  }

  if (selected) {
    className += " selected";
  }

  let marker = vehicle.service?.line_name;

  if (vehicle.vehicle.livery && vehicle.vehicle.livery != 262) {
    marker = (
      <svg
        width="24"
        height="16"
        data-vehicle-id={vehicle.id}
        className={className}
      >
        <text x="12" y="12">
          {marker}
        </text>
      </svg>
    );
  } else {
    marker = (
      <div data-vehicle-id={vehicle.id} className={className} style={css}>
        {marker}
      </div>
    );
  }

  return (
    <Marker
      id={vehicle.id}
      latitude={vehicle.coordinates[1]}
      longitude={vehicle.coordinates[0]}
      rotation={rotation}
      style={selected ? { zIndex: 1 } : { zIndex: null }}
      data-vehicle-id={vehicle.id}
    >
      {marker}
      {rotation == null ? null : (
        <div className="arrow" data-vehicle-id={vehicle.id} />
      )}
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
