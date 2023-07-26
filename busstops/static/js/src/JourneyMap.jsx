import React from "react";
import ReactDOM from "react-dom/client";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  Popup,
} from "react-map-gl/maplibre";

import { useDarkMode, getBounds } from "./utils";

import StopPopup from "./StopPopup";

import "maplibre-gl/dist/maplibre-gl.css";

const stopsStyle = {
  id: "stops",
  type: "circle",
  paint: {
    "circle-color": "#fff",
    "circle-radius": 3,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#666",
  },
};

const locationsStyle = {
  id: "locations",
  type: "circle",
  paint: {
    "circle-color": "#666",
    "circle-radius": 5,
  },
};

const routeStyle = {
  type: "line",
  paint: {
    "line-color": "#000",
    "line-opacity": 0.5,
    "line-width": 2,
    "line-dasharray": [2, 2],
  },
};

export default function JourneyMap({ journey }) {
  const darkMode = useDarkMode();

  const [cursor, setCursor] = React.useState();

  const [clickedLocation, setClickedLocation] = React.useState(null);

  const onMouseEnter = React.useCallback((e) => {
    setCursor("pointer");

    if (e.features.length && e.features[0].layer.id == "locations") {
      setClickedLocation(e.features[0]);
    }
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
    setClickedLocation(null);
  }, []);

  const [clickedStop, setClickedStop] = React.useState(null);

  const handleMapClick = React.useCallback((e) => {
    if (e.features.length) {
      if (e.features[0].layer.id == "stops") {
        setClickedStop(e.features[0]);
      }
    } else {
      setClickedStop(null);
    }
  }, []);

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  if (!journey) {
    return <div className="sorry">Loading…</div>;
  }

  return (
    <Map
      dragRotate={false}
      touchPitch={false}
      touchRotate={false}
      pitchWithRotate={false}
      minZoom={8}
      maxZoom={16}
      bounds={getBounds(journey.locations)}
      fitBoundsOptions={{
        padding: 50,
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
      interactiveLayerIds={["stops", "locations"]}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />

      <Source
        type="geojson"
        data={{
          type: "LineString",
          coordinates: journey.locations.map((l) => l.coordinates),
        }}
      >
        <Layer {...routeStyle} />
      </Source>

      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: journey.locations.map((l) => {
            return {
              type: "Feature",
              geometry: {
                type: "Point",
                coordinates: l.coordinates,
              },
              properties: {
                delta: l.delta,
                direction: l.direction,
                datetime: l.datetime,
              },
            };
          }),
        }}
      >
        <Layer {...locationsStyle} />
      </Source>

      {journey.stops ? (
        <Source
          type="geojson"
          data={{
            type: "FeatureCollection",
            features: journey.stops.map((s) => {
              return {
                type: "Feature",
                geometry: {
                  type: "Point",
                  coordinates: s.coordinates,
                },
                properties: {
                  atco_code: s.atco_code,
                  name: s.name,
                  minor: s.minor,
                  heading: s.heading,
                  aimed_arrival_time: s.aimed_arrival_time,
                  aimed_departure_time: s.aimed_departure_time,
                },
              };
            }),
          }}
        >
          <Layer {...stopsStyle} />
        </Source>
      ) : null}

      {clickedStop ? (
        <StopPopup
          item={{
            properties: {
              url: `/stops/${clickedStop.properties.atco_code}`,
              name: clickedStop.properties.name,
            },
            geometry: clickedStop.geometry,
          }}
          onClose={() => setClickedStop(null)}
        />
      ) : null}

      {clickedLocation ? (
        <Popup
          latitude={clickedLocation.geometry.coordinates[1]}
          longitude={clickedLocation.geometry.coordinates[0]}
          closeButton={false}
          closeOnClick={false}
        >
          {clickedLocation.properties.datetime}
        </Popup>
      ) : null}
    </Map>
  );
}
