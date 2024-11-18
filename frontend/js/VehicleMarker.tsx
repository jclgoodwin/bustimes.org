import React, { ReactElement, memo } from "react";
import { Marker, MapLayerMouseEvent } from "react-map-gl/maplibre";

export function getClickedVehicleMarkerId(
  e: MapLayerMouseEvent,
): number | undefined {
  // handle click on VehicleMarker element
  const target = e.originalEvent.target;
  if (target instanceof HTMLElement || target instanceof SVGElement) {
    let vehicleId = target.dataset.vehicleId;
    if (!vehicleId && target.parentElement) {
      vehicleId = target.parentElement.dataset.vehicleId;
    }
    if (
      !vehicleId &&
      (target.firstChild instanceof HTMLElement ||
        target.firstChild instanceof SVGElement)
    ) {
      vehicleId = target.firstChild.dataset.vehicleId;
    }
    if (vehicleId) {
      return parseInt(vehicleId, 10);
    }
  }
}

export type Vehicle = {
  id: number;
  journey_id?: number;
  coordinates: [number, number];
  heading?: number;
  datetime: string;
  destination: string;
  block?: string;
  tfl_code?: string;
  trip_id?: number;
  service_id?: number;
  service?: {
    url?: string;
    line_name: string;
  };
  vehicle?: {
    url: string;
    name: string;
    features?: string;
    livery?: number;
    colour?: string;
    text_colour?: string;
    css?: string;
    right_css?: string;
  };
  progress?: {
    id: number;
    sequence: number;
    prev_stop: string;
    next_stop: string;
    progress: number;
  };
  delay?: number;
  seats?: string;
  wheelchair?: string;
};

type VehicleMarkerProps = {
  vehicle: Vehicle;
  selected: boolean;
};

function VehicleMarker({ vehicle, selected }: VehicleMarkerProps) {
  let className = "vehicle-marker";

  let rotation = vehicle.heading;

  let background = "";
  if (vehicle.vehicle?.css) {
    background = vehicle.vehicle.css;
  }

  if (rotation != null) {
    if (rotation < 180) {
      rotation -= 90;
      className += " right";
      if (vehicle.vehicle?.right_css) {
        background = vehicle.vehicle.right_css;
      }
    } else {
      rotation -= 270;
    }
  }

  if (vehicle.vehicle?.livery) {
    className += " livery-" + vehicle.vehicle.livery;
  } else if (background && vehicle.vehicle?.text_colour) {
    className += " white-text";
  }

  if (selected) {
    className += " selected";
  }

  let marker: string | ReactElement = vehicle.service?.line_name || "";

  if (vehicle.vehicle?.livery && vehicle.vehicle.livery !== 262) {
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
        style={background ? { background: background } : undefined}
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
      style={{ zIndex: selected ? 1 : 0 }}
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
