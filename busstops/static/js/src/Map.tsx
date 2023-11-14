import React from "react";
import { captureException } from "@sentry/react";

import Map, {
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";
import type { Map as MapType } from "maplibre-gl";

import stopMarker from "data-url:../../stop-marker.png";
import routeStopMarker from "data-url:../../route-stop-marker.png";
import arrow from "data-url:../../arrow.png";

const images: { [imageName: string]: string } = {
  "stop-marker": stopMarker,
  "route-stop-marker": routeStopMarker,
  arrow: arrow
};

export default function BusTimesMap(props: any) {
  const mapRef = React.useCallback(
    (map: MapType) => {
      if (map && props.images) {
        for (let imageName of props.images) {
          const image = new Image();
          image.src = images[imageName];
          image.onload = function () {
            map.addImage(imageName, image, {
              pixelRatio: 2,
            });
          };
        }
      }
    },
    [props.images],
  );

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
