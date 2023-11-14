import React from "react";
import { captureException } from "@sentry/react";

import Map, {
  NavigationControl,
  GeolocateControl,
  MapEvent
} from "react-map-gl/maplibre";

import stopMarker from "data-url:../../stop-marker.png";
import routeStopMarker from "data-url:../../route-stop-marker.png";
import arrow from "data-url:../../arrow.png";

const images: { [imageName: string]: string } = {
  "stop-marker": stopMarker,
  "route-stop-marker": routeStopMarker,
  arrow: arrow
};

export default function BusTimesMap(props: any) {
  const imageNames = props.images;
  const onLoad = props.onLoad;

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    if (imageNames) {
      const map = event.target;

      for (let imageName of imageNames) {
        const image = new Image();
        image.src = images[imageName];
        image.onload = function () {
          map.addImage(imageName, image, {
            pixelRatio: 2,
          });
        };
      }
    }

    if (onLoad) {
      onLoad(event);
    }
  }, [imageNames, onLoad]);

  return (
    <Map
      {...props}
      onLoad={handleMapLoad}
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
