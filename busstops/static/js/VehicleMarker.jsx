import React from "react";
import { Marker } from "react-map-gl/maplibre";

import "./vehiclemarker.css";


export default function VehicleMarker(props) {
  let className = 'vehicle-marker';

  let rotation = props.vehicle.heading;

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += ' right';
    } else {
      rotation -= 270;
    }
  }

  if (props.vehicle.vehicle.livery) {
    className += ' livery-' + props.vehicle.vehicle.livery;
  }

  let css = props.vehicle.vehicle.css;
  if (css) {
    css = {
      background: css
    };
    if (props.vehicle.vehicle.text_colour) {
        className += ' white-text';
      }
  }

  return (
    <Marker
      latitude={props.vehicle.coordinates[1]}
      longitude={props.vehicle.coordinates[0]}
      rotation={rotation}
      onClick={() => props.onClick(props.vehicle.id)}
    >
      <div
        className={className}
        style={css}
      >
        <div className="text">{props.vehicle.service?.line_name}</div>
        { rotation == null ? null : <div className='arrow' /> }
      </div>
    </Marker>
  );
}

// export default VehicleMarker;
