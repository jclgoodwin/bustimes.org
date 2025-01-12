import React, { memo, useEffect, createContext } from "react";
import { createRoot } from "react-dom/client";
// import { captureException } from "@sentry/react";

import MapGL, {
  NavigationControl,
  GeolocateControl,
  AttributionControl,
  type MapProps,
  useControl,
  useMap,
  Popup,
  type LngLat,
  type MapLayerMouseEvent,
  type PopupEvent,
} from "react-map-gl/maplibre";

import arrow from "data-url:../history-arrow.png";
import routeStopMarkerCircle from "data-url:../route-stop-marker-circle.png";
import routeStopMarkerDarkCircle from "data-url:../route-stop-marker-dark-circle.png";
import routeStopMarkerDark from "data-url:../route-stop-marker-dark.png";
import routeStopMarker from "data-url:../route-stop-marker.png";
import stopMarkerCircle from "data-url:../stop-marker-circle.png";
import stopMarker from "data-url:../stop-marker.png";
import type {
  Map as MapLibreMap,
  MapStyleImageMissingEvent,
} from "maplibre-gl";

const imagesByName: { [imageName: string]: string } = {
  "stop-marker": stopMarker,
  "stop-marker-circle": stopMarkerCircle,
  "route-stop-marker": routeStopMarker,
  "route-stop-marker-circle": routeStopMarkerCircle,
  "route-stop-marker-dark": routeStopMarkerDark,
  "route-stop-marker-dark-circle": routeStopMarkerDarkCircle,
  arrow: arrow,
};

const mapStyles: { [key: string]: string } = {
  alidade_smooth: "Light",
  alidade_smooth_dark: "Dark",
  alidade_satellite: "Satellite",
  osm_bright: "Bright",
};

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
        {Object.entries(mapStyles).map(([key, value]) => (
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
        ))}
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

export const ThemeContext = createContext("");

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

      const onStyleImageMissing = (e: MapStyleImageMissingEvent) => {
        if (e.id in imagesByName) {
          const image = new Image();
          image.src = imagesByName[e.id];
          image.onload = () => {
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
  const darkModeQuery = window.matchMedia("(prefers-color-scheme: dark)");

  const [mapStyle, setMapStyle] = React.useState(() => {
    try {
      const style = localStorage.getItem("map-style");
      if (style && style in mapStyles) {
        return style;
      }
    } catch {
      // ignore
    }

    return darkModeQuery.matches ? "alidade_smooth_dark" : "alidade_smooth";
  });

  useEffect(() => {
    const handleChange = (e: MediaQueryListEvent) => {
      setMapStyle(e.matches ? "alidade_smooth_dark" : "alidade_smooth");
    };

    if (darkModeQuery.addEventListener) {
      darkModeQuery.addEventListener("change", handleChange);

      return () => {
        darkModeQuery.removeEventListener("change", handleChange);
      };
    }
  }, [darkModeQuery]);

  const handleMapStyleChange = React.useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const style = e.target.value;
      const defaultStyle = darkModeQuery.matches
        ? "alidade_smooth_dark"
        : "alidade_smooth";
      setMapStyle(style);
      try {
        if (style === defaultStyle) {
          localStorage.removeItem("map-style");
        } else {
          localStorage.setItem("map-style", style);
        }
      } catch {
        // ignore
      }
    },
    [darkModeQuery.matches],
  );

  const [contextMenu, setContextMenu] = React.useState<LngLat>();

  const onContextMenu = (e: MapLayerMouseEvent | PopupEvent) => {
    if ("lngLat" in e) {
      setContextMenu(e.lngLat);
    } else {
      setContextMenu(undefined);
    }
  };

  useEffect(() => {
    document.body.classList.toggle("dark-mode", mapStyle.endsWith("_dark"));
  }, [mapStyle]);

  return (
    <ThemeContext.Provider value={mapStyle}>
      <MapGL
        {...props}
        reuseMaps
        touchPitch={false}
        pitchWithRotate={false}
        dragRotate={false}
        minZoom={2}
        maxZoom={18}
        mapStyle={`https://tiles.stadiamaps.com/styles/${mapStyle}.json`}
        RTLTextPlugin={""}
        attributionControl={false}
        // onError={(e) => captureException(e.error)}
        onContextMenu={onContextMenu}
        // workaround for wrong react-map-gl type definitions?
        transformRequest={undefined}
        maxTileCacheSize={undefined}
      >
        <NavigationControl showCompass={false} />
        <GeolocateControl trackUserLocation />
        <StyleSwitcherControl
          style={mapStyle}
          onChange={handleMapStyleChange}
        />
        <AttributionControl />
        <MapChild onInit={props.onMapInit} />

        {props.children}
        {contextMenu ? (
          <Popup
            longitude={contextMenu.lng}
            latitude={contextMenu.lat}
            onClose={onContextMenu}
          >
            <a
              href={`https://www.openstreetmap.org/#map=15/${contextMenu.lat}/${contextMenu.lng}`}
              rel="noopener noreferrer"
            >
              OpenStreetMap
            </a>
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${contextMenu.lat},${contextMenu.lng}`}
              rel="noopener noreferrer"
            >
              Google Maps
            </a>
          </Popup>
        ) : null}
      </MapGL>
    </ThemeContext.Provider>
  );
}
