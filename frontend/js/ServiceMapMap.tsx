import React from "react";

import {
  Layer,
  type LayerProps,
  type MapGeoJSONFeature,
  type MapLayerMouseEvent,
  Source,
} from "react-map-gl/maplibre";

import BusTimesMap, { ThemeContext } from "./Map";
import StopPopup, { type Stop } from "./StopPopup";
import VehicleMarker, {
  type Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

declare global {
  interface Window {
    EXTENT: [number, number, number, number];
  }
}

export type ServiceMapMapProps = {
  vehicles?: Vehicle[];
  serviceIds: Set<number>;
  stopsAndGeometry: {
    [serviceId: number]: {
      stops?: {
        type: "FeatureCollection";
        features: MapGeoJSONFeature[];
      };
      geometry?: MapGeoJSONFeature;
    };
  };
};

function Geometry({ geometry }: { geometry: MapGeoJSONFeature }) {
  const theme = React.useContext(ThemeContext);
  const darkMode = theme.endsWith("dark") || theme === "alidade_satellite";

  const routeStyle: LayerProps = {
    type: "line",
    paint: {
      "line-color": darkMode ? "#ccc" : "#666",
      "line-width": 3,
    },
  };

  return (
    <Source type="geojson" data={geometry}>
      <Layer {...routeStyle} />
    </Source>
  );
}

function Stops({
  stops,
}: {
  stops: { type: "FeatureCollection"; features: MapGeoJSONFeature[] };
}) {
  const theme = React.useContext(ThemeContext);
  const darkMode = theme.endsWith("_dark") || theme === "alidade_satellite";

  const stopsStyle: LayerProps = {
    id: "stops",
    type: "symbol",
    layout: {
      "icon-rotate": ["+", 45, ["get", "bearing"]],
      "icon-image": [
        "case",
        ["==", ["get", "bearing"], ["literal", null]],
        darkMode ? "route-stop-marker-dark-circle" : "route-stop-marker-circle",
        darkMode ? "route-stop-marker-dark" : "route-stop-marker",
      ],
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  };

  if (stops) {
    return (
      <Source type="geojson" data={stops}>
        <Layer {...stopsStyle} />
      </Source>
    );
  }
}

export default function ServiceMapMap({
  vehicles,
  stopsAndGeometry,
  serviceIds,
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
  >(() => {
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
            if (typeof stop.properties.services === "string") {
              stop.properties.services = JSON.parse(stop.properties.services);
            }
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
  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  const stops = React.useMemo(() => {
    return {
      type: "FeatureCollection" as const,
      features: Array.from(serviceIds).flatMap((serviceId) => {
        return stopsAndGeometry[serviceId]?.stops?.features || [];
      }),
    };
  }, [stopsAndGeometry, serviceIds]);

  return (
    <BusTimesMap
      initialViewState={{
        bounds: window.EXTENT,
        fitBoundsOptions: {
          padding: { top: 20, bottom: 120, left: 20, right: 20 },
        },
      }}
      cursor={cursor}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={handleMapClick}
      // onLoad={handleMapLoad}
      interactiveLayerIds={["stops"]}
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

      {Array.from(serviceIds).map((serviceId) => {
        if (stopsAndGeometry[serviceId]?.geometry) {
          return (
            <Geometry
              key={serviceId}
              geometry={stopsAndGeometry[serviceId].geometry}
            />
          );
        }
      })}

      {stops && stopsAndGeometry ? <Stops stops={stops} /> : null}
    </BusTimesMap>
  );
}
