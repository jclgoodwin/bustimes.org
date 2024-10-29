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
import stopMarkerCircle from "data-url:../stop-marker-circle.png";
import routeStopMarker from "data-url:../route-stop-marker.png";
import routeStopMarkerCircle from "data-url:../route-stop-marker-circle.png";
import routeStopMarkerDark from "data-url:../route-stop-marker-dark.png";
import routeStopMarkerDarkCircle from "data-url:../route-stop-marker-dark-circle.png";
import arrow from "data-url:../history-arrow.png";
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
  osm_bright: "Bright",
  // outdoors: "Outdoors",
  // alidade_satellite: "Satellite",
  // ordnance_survey: "Ordnance Survey",
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

  useEffect(() => {
    document.body.classList.toggle("dark-mode", mapStyle.endsWith("_dark"));
  }, [mapStyle]);

  let mapStyleUrl;
  if (mapStyle === "ordnance_survey") {
    mapStyleUrl =
      "https://api.os.uk/maps/vector/v1/vts/resources/styles?key=b45dBXyI0RA7DGx5hcftaqVk5GFBUCEY&srs=3857";
  } else {
    mapStyleUrl = `https://tiles.stadiamaps.com/styles/${mapStyle}.json`;
  }
  return (
    <ThemeContext.Provider value={mapStyle}>
      <Map
        {...props}
        reuseMaps
        touchPitch={false}
        pitchWithRotate={false}
        dragRotate={false}
        minZoom={2}
        maxZoom={18}
        mapStyle={mapStyleUrl}
        RTLTextPlugin={""}
        attributionControl={false}
        // onError={(e) => captureException(e.error)}

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

        {mapStyle === "ordnance_survey" ? (
          <AttributionControl customAttribution="© Ordnance Survey" />
        ) : (
          <AttributionControl />
        )}

        <MapChild onInit={props.onMapInit} />

        {props.children}
      </Map>
    </ThemeContext.Provider>
  );
}
