import React from "react";
import { captureException } from "@sentry/react";


import Map, {
  NavigationControl,
  GeolocateControl
} from "react-map-gl/maplibre";
import type { Map as MapType } from "maplibre-gl";

export default function BusTimesMap(props: any) {
  const mapRef = React.useCallback((map: MapType) => {
    if (map) {
      for (let src of props.images) {
        const image = new Image();
        image.src = src;
        image.onload = function () {
          map.addImage("stop", image, {
            pixelRatio: 2,
          });
        };
      }
    }
  }, [props.images]);

  return (
    <Map
      {...props}
      ref={mapRef}
      touchPitch={false}
      pitchWithRotate={false}
      dragRotate={false}
      minZoom={5}
      maxZoom={18}
      mapStyle="https://tiles.stadiamaps.com/styles/alidade_smooth.json"
      RTLTextPlugin={""}
      onError={(e) => captureException(e.error)}
    >
      <NavigationControl showCompass={false} />
      <GeolocateControl />
      {props.children}
    </Map>
  );
}
