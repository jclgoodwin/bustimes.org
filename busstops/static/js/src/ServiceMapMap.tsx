import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  LayerProps,
  MapEvent,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";

import StopPopup, { Stop } from "./StopPopup";
import VehicleMarker, { Vehicle } from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

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
  geometry: any;
  stops: any;
  // closeButton: ReactElement;
};

export default function ServiceMapMap({
  vehicles,
  geometry,
  stops,
}: ServiceMapMapProps) {
  const darkMode = false;

  const [cursor, setCursor] = React.useState<string | null>(null);

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
  }, []);

  const vehiclesById = React.useMemo(() => {
    if (vehicles) {
      return Object.assign(
        {},
        ...vehicles.map((item) => ({ [item.id]: item })),
      );
    }
  }, [vehicles]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState<number>(function () {
      if (vehicles && vehicles.length === 1) {
        return vehicles[0].id;
      }
    });

  const [clickedStop, setClickedStop] = React.useState<Stop>();

  const handleMapClick = React.useCallback(
    (e: MapLayerMouseEvent) => {
      const target = e.originalEvent.target;
      if (target instanceof HTMLElement || target instanceof SVGElement) {
        let vehicleId = target.dataset.vehicleId;
        if (!vehicleId) {
          vehicleId = target.parentElement.dataset.vehicleId;
        }
        if (vehicleId) {
          setClickedVehicleMarker(parseInt(vehicleId, 10));
          setClickedStop(undefined);
          return;
        }
      }

      if (e.features.length) {
        for (const stop of e.features) {
          if (stop.properties.url !== clickedStop?.properties.url) {
            setClickedStop(stop as any as Stop);
          }
        }
      } else {
        setClickedStop(undefined);
      }
      setClickedVehicleMarker(null);
    },
    [clickedStop],
  );

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    map.loadImage("/static/route-stop-marker.png", (error, image) => {
      if (error) throw error;
      map.addImage("stop", image, {
        pixelRatio: 2,
      });
    });
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  const stopsStyle: LayerProps = {
    id: "stops",
    type: "symbol",
    layout: {
      "icon-rotate": ["+", 45, ["get", "bearing"]],
      "icon-image": "stop",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  };

  return (
    <Map
      dragRotate={false}
      touchPitch={false}
      pitchWithRotate={false}
      maxZoom={18}
      initialViewState={{
        bounds: window.EXTENT,
        fitBoundsOptions: {
          padding: 20,
        },
      }}
      cursor={cursor}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      mapStyle={
        darkMode
          ? "https://tiles.stadiamaps.com/styles/alidade_smooth_dark.json"
          : "https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      }
      RTLTextPlugin={null}
      onClick={handleMapClick}
      onLoad={handleMapLoad}
      interactiveLayerIds={["stops"]}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

      {vehicles ? (
        vehicles.map((item) => {
          return (
            <VehicleMarker
              key={item.id}
              selected={item === clickedVehicle}
              vehicle={item}
            />
          );
        })
      ) : (
        <div className="maplibregl-ctrl">Loading</div>
      )}

      {clickedVehicle ? (
        <VehiclePopup
          item={clickedVehicle}
          onClose={() => {
            setClickedVehicleMarker(null);
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
    </Map>
  );
}
