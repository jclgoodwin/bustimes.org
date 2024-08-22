import React, { memo, useEffect, createContext } from "react";
import { createRoot } from "react-dom/client";
// import { captureException } from "@sentry/react";

import Map, {
  NavigationControl,
  GeolocateControl,
  AttributionControl,
  MapProps,
  useControl,
  useMap,
} from "react-map-gl/maplibre";

import stopMarker from "data-url:../stop-marker.png";
import routeStopMarker from "data-url:../route-stop-marker.png";
import arrow from "data-url:../history-arrow.png";
import type {
  Map as MapLibreMap,
  MapStyleImageMissingEvent,
} from "maplibre-gl";

const imagesByName: { [imageName: string]: string } = {
  "stop-marker": stopMarker,
  "route-stop-marker": routeStopMarker,
  arrow: arrow,
};

const mapStyles = [
  ["alidade_smooth", "Default"],
  ["alidade_smooth_dark", "Dark (experimental)"],
  ["osm_bright", "Bright"],
  ["outdoors", "Outdoors"],
  // ["alidade_satellite", "Satellite"],
];

type StyleSwitcherProps = {
  style: string;
  onChange: React.ChangeEventHandler<HTMLInputElement>;
};

class StyleSwitcher {
  style: string;
  handleChange: React.ChangeEventHandler<HTMLInputElement>;
  _container?: HTMLElement;

  constructor(props: StyleSwitcherProps) {
    this.style = props.style;
    this.handleChange = props.onChange;
  }

  onAdd() {
    this._container = document.createElement("div");

    const root = createRoot(this._container);
    root.render(
      <details className="maplibregl-ctrl maplibregl-ctrl-group map-style-switcher">
        <summary>Map style</summary>
        {mapStyles.map((style) => {
          const [key, value] = style;
          return (
            <label key={key}>
              <input
                type="radio"
                value={key}
                name="map-style"
                defaultChecked={key === this.style}
                onChange={this.handleChange}
              />
              {value}
            </label>
          );
        })}
      </details>,
    );
    return this._container;
  }

  onRemove() {
    this._container?.parentNode?.removeChild(this._container);
  }
}

const StyleSwitcherControl = memo(function StyleSwitcherControl(
  props: StyleSwitcherProps,
) {
  useControl(() => new StyleSwitcher(props));

  return null;
});

export const ThemeContext = createContext(false);

function MapChild({ onInit }: { onInit?: (map: MapLibreMap) => void }) {
  const { current: map } = useMap();

  useEffect(() => {
    if (map) {
      const _map = map.getMap();
      _map.keyboard.disableRotation();
      _map.touchZoomRotate.disableRotation();

      if (onInit) {
        onInit(_map);
      }

      const onStyleImageMissing = function (e: MapStyleImageMissingEvent) {
        if (e.id in imagesByName) {
          const image = new Image();
          image.src = imagesByName[e.id];
          image.onload = function () {
            if (!map.hasImage(e.id)) {
              map.addImage(e.id, image, {
                pixelRatio: 2,
              });
            }
          };
        }
      };

      map.on("styleimagemissing", onStyleImageMissing);

      return () => {
        map.off("styleimagemissing", onStyleImageMissing);
      };
    }
  });

  return null;
}

export default function BusTimesMap(
  props: MapProps & {
    onMapInit?: (map: MapLibreMap) => void;
    // workaround for wrong react-map-gl type definitions?
    minPitch?: number;
    maxPitch?: number;
    scrollZoom?: boolean;
    touchZoomRotate?: boolean;
    localIdeographFontFamily?: string;
    pitchWithRotate?: boolean;
  },
) {
  const [mapStyle, setMapStyle] = React.useState(() => {
    try {
      const style = localStorage.getItem("map-style");
      if (style) {
        return style;
      }
    } catch {
      // ignore
    }
    return "alidade_smooth";
  });

  const handleMapStyleChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const style = e.target.value;
      setMapStyle(style);
      try {
        localStorage.setItem("map-style", style);
      } catch {
        // ignore
      }
    },
    [],
  );

  useEffect(() => {
    document.body.classList.toggle("dark-mode", mapStyle.endsWith("_dark"));
  }, [mapStyle]);

  return (
    <ThemeContext.Provider value={mapStyle.endsWith("_dark")}>
      <Map
        {...props}
        reuseMaps
        touchPitch={false}
        pitchWithRotate={false}
        dragRotate={false}
        minZoom={5}
        maxZoom={18}
        mapStyle={`https://tiles.stadiamaps.com/styles/${mapStyle}.json`}
        RTLTextPlugin={""}
        attributionControl={false}
        // onError={(e) => captureException(e.error)}

        // workaround for wrong react-map-gl type definitions?
        transformRequest={undefined}
        maxTileCacheSize={undefined}
      >
        <NavigationControl showCompass={false} />
        <GeolocateControl />
        <StyleSwitcherControl
          style={mapStyle}
          onChange={handleMapStyleChange}
        />
        <AttributionControl />

        <MapChild onInit={props.onMapInit} />

        {props.children}
      </Map>
    </ThemeContext.Provider>
  );
}
