import React, { memo } from "react";
import { Marker } from "react-map-gl/maplibre";

import "./vehiclemarker.css";

function VehicleMarker(props) {
  let className = "vehicle-marker";

  let rotation = props.vehicle.heading;

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += " right";
    } else {
      rotation -= 270;
    }
  }

  if (props.vehicle.vehicle.livery) {
    className += " livery-" + props.vehicle.vehicle.livery;
  }

  if (props.selected) {
    className += " selected";
  }

  let css = props.vehicle.vehicle.css;
  if (css) {
    css = {
      background: css,
    };
    if (props.vehicle.vehicle.text_colour) {
      className += " white-text";
    }
  }

  return (
    <Marker
      latitude={props.vehicle.coordinates[1]}
      longitude={props.vehicle.coordinates[0]}
      rotation={rotation}
      style={props.selected ? {zIndex: 1} : {zIndex: null}}
      onClick={(event) => props.onClick(event, props.vehicle.id)}
    >
      <div className={className} style={css}>
        <div className="text">{props.vehicle.service?.line_name}</div>
        {rotation == null ? null : <div className="arrow" />}
      </div>
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
