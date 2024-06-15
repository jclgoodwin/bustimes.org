import React from "react";

import {
  Source,
  Layer,
  LayerProps,
  MapEvent,
  MapLayerMouseEvent,
  MapGeoJSONFeature,
} from "react-map-gl/maplibre";

import StopPopup, { Stop } from "./StopPopup";
import VehicleMarker, {
  Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";
import BusTimesMap from "./Map";

declare global {
  interface Window {
    EXTENT: [number, number, number, number];
  }
}

const routeStyle: LayerProps = {
  type: "line",
  paint: {
    "line-color": "#777",
    "line-width": 3,
  },
};

type ServiceMapMapProps = {
  vehicles?: Vehicle[];
  geometry?: MapGeoJSONFeature;
  stops?: MapGeoJSONFeature[];
};

export default function ServiceMapMap({
  vehicles,
  geometry,
  stops,
}: ServiceMapMapProps) {
  const [cursor, setCursor] = React.useState<string>();

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor("");
  }, []);

  const vehiclesById = React.useMemo<{ [id: string]: Vehicle }>(() => {
    if (vehicles) {
      return Object.assign(
        {},
        ...vehicles.map((item) => ({ [item.id]: item })),
      );
    }
  }, [vehicles]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] = React.useState<
    number | undefined
  >(function () {
    if (vehicles && vehicles.length === 1) {
      return vehicles[0].id;
    }
  });

  const [clickedStop, setClickedStop] = React.useState<Stop>();

  const handleMapClick = React.useCallback(
    (e: MapLayerMouseEvent) => {
      const vehicleId = getClickedVehicleMarkerId(e);
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        setClickedStop(undefined);
        return;
      }

      if (e.features?.length) {
        for (const stop of e.features) {
          if (stop.properties.url !== clickedStop?.properties.url) {
            setClickedStop(stop as unknown as Stop);
          }
        }
      } else {
        setClickedStop(undefined);
      }
      setClickedVehicleMarker(undefined);
    },
    [clickedStop],
  );

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  const stopsStyle: LayerProps = {
    id: "stops",
    type: "symbol",
    layout: {
      "icon-rotate": ["+", 45, ["get", "bearing"]],
      "icon-image": "route-stop-marker",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  };

  return (
    <BusTimesMap
      initialViewState={{
        bounds: window.EXTENT,
        fitBoundsOptions: {
          padding: 20,
        },
      }}
      cursor={cursor}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={handleMapClick}
      onLoad={handleMapLoad}
      interactiveLayerIds={["stops"]}
      images={["route-stop-marker"]}
    >
      {vehicles
        ? vehicles.map((item) => {
            return (
              <VehicleMarker
                key={item.id}
                selected={item === clickedVehicle}
                vehicle={item}
              />
            );
          })
        : null}

      {clickedVehicle ? (
        <VehiclePopup
          item={clickedVehicle}
          onClose={() => {
            setClickedVehicleMarker(undefined);
          }}
        />
      ) : null}

      {clickedStop ? (
        <StopPopup
          item={clickedStop}
          onClose={() => setClickedStop(undefined)}
        />
      ) : null}

      {geometry && (
        <Source type="geojson" data={geometry}>
          <Layer {...routeStyle} />
        </Source>
      )}

      {stops && (
        <Source type="geojson" data={stops}>
          <Layer {...stopsStyle} />
        </Source>
      )}
    </BusTimesMap>
  );
}
