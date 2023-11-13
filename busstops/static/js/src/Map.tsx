import React from "react";
import { captureException } from "@sentry/react";

import Map, {
  NavigationControl,
  GeolocateControl,
} from "react-map-gl/maplibre";

export default function BusTimesMap(props: any) {
  return (
    <Map
      {...props}
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
