import React from "react";

import { MapEvent, MapLayerMouseEvent } from "react-map-gl/maplibre";

import VehicleMarker, {
  Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

import { LngLatBounds } from "maplibre-gl";
import BusTimesMap from "./Map";

const apiRoot = process.env.API_ROOT;

type OperatorMapProps = {
  noc: string;
};

function getBounds(items: Vehicle[]) {
  const bounds = new LngLatBounds();
  for (const item of items) {
    bounds.extend(item.coordinates);
  }

  return bounds;
}

export default function OperatorMap({ noc }: OperatorMapProps) {
  const [vehiclesList, setVehicles] = React.useState<Vehicle[]>();

  const vehiclesById = React.useMemo<{ [id: string]: Vehicle }>(() => {
    if (vehiclesList) {
      return Object.assign(
        {},
        ...vehiclesList.map((item) => ({ [item.id]: item })),
      );
    }
  }, [vehiclesList]);

  const [bounds, setBounds] = React.useState<LngLatBounds>();

  React.useEffect(() => {
    let timeout: number;

    const loadVehicles = (first = false) => {
      if (document.hidden && !first) {
        return;
      }

      const url = apiRoot + "vehicles.json?operator=" + noc;
      fetch(url).then((response) => {
        response.json().then((items) => {
          if (first) {
            setBounds(getBounds(items));
          }

          setVehicles(items);
          clearTimeout(timeout);
          if (!document.hidden) {
            timeout = window.setTimeout(loadVehicles, 10000); // 10 seconds
          }
        });
      });
    };

    loadVehicles(true);

    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearTimeout(timeout);
      } else {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimeout(timeout);
    };
  }, [noc]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState<number>();

  const handleMapClick = React.useCallback((e: MapLayerMouseEvent) => {
    // handle click on VehicleMarker element
    const vehicleId = getClickedVehicleMarkerId(e);
    if (vehicleId) {
      setClickedVehicleMarker(vehicleId);
      return;
    }
    setClickedVehicleMarker(undefined);
  }, []);

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  if (!vehiclesList) {
    return <div className="sorry">Loading…</div>;
  }

  if (!vehiclesList.length) {
    return (
      <div className="sorry">Sorry, no buses are tracking at the moment</div>
    );
  }

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  return (
    <div className="operator-map">
      <BusTimesMap
        initialViewState={{
          bounds: bounds,
          fitBoundsOptions: {
            maxZoom: 15,
            padding: 50,
          },
        }}
        onClick={handleMapClick}
        onLoad={handleMapLoad}
      >
        {vehiclesList.map((item) => {
          return (
            <VehicleMarker
              key={item.id}
              selected={item === clickedVehicle}
              vehicle={item}
            />
          );
        })}

        {clickedVehicle && (
          <VehiclePopup
            snazzyTripLink
            item={clickedVehicle}
            onClose={() => setClickedVehicleMarker(undefined)}
          />
        )}
      </BusTimesMap>
    </div>
  );
}
