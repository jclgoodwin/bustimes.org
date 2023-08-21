import React, { ReactElement, memo } from "react";
import { LngLatLike, Marker } from "react-map-gl/maplibre";

export type Vehicle = {
  id: number;
  coordinates: LngLatLike;
  heading?: number;
  datetime: string;
  destination: string;
  delay?: number;
  block?: string;
  tfl_code?: string;
  trip_id?: number;
  service_id?: number;
  service: {
    url?: string;
    line_name: string;
  };
  vehicle: {
    url: string;
    name: string;
    features?: string;
    livery?: number;
    colour?: string;
    colours?: string;
    text_colour?: string;
    css?: string;
    right_css?: string;
  };
};

type VehicleMarkerProps = {
  vehicle: Vehicle;
  selected: boolean;
};

function VehicleMarker({ vehicle, selected }: VehicleMarkerProps) {
  let className = "vehicle-marker";

  let rotation = vehicle.heading;

  let background: string | null;
  if (vehicle.vehicle.css) {
    background = vehicle.vehicle.css;
  }

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += " right";
      if (vehicle.vehicle.right_css) {
        background = vehicle.vehicle.right_css;
      }
    } else {
      rotation -= 270;
    }
  }

  if (vehicle.vehicle.livery) {
    className += " livery-" + vehicle.vehicle.livery;
  } else if (background && vehicle.vehicle.text_colour) {
    className += " white-text";
  }

  if (selected) {
    className += " selected";
  }

  let marker: string | ReactElement = vehicle.service?.line_name;

  if (vehicle.vehicle.livery && vehicle.vehicle.livery !== 262) {
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
      <div
        data-vehicle-id={vehicle.id}
        className={className}
        style={background && { background: background }}
      >
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
      data-vehicle-id={vehicle.id}
    >
      {marker}
      {rotation == null ? null : (
        <div className="arrow" data-vehicle-id={vehicle.id} />
      )}
    </Marker>
  );
}

function propsAreEqual(prev: VehicleMarkerProps, props: VehicleMarkerProps) {
  return (
    prev.selected === props.selected &&
    prev.vehicle.datetime === props.vehicle.datetime
  );
}

export default memo(VehicleMarker, propsAreEqual);
