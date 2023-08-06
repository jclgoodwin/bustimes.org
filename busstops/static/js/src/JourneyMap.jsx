import React from "react";

import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  Popup,
} from "react-map-gl/maplibre";

import { LngLatBounds } from "maplibre-gl";

import { useDarkMode } from "./utils";

import TripTimetable from "./TripTimetable";
import StopPopup from "./StopPopup";

const stopsStyle = {
  id: "stops",
  type: "symbol",
  layout: {
    "icon-rotate": ["+", 45, ["get", "heading"]],
    "icon-image": "stop",
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
    "icon-padding": 0,
  },
};

const locationsStyle = {
  id: "locations",
  type: "symbol",
  layout: {
    "icon-rotate": ["+", 45, ["get", "heading"]],
    "icon-image": "arrow",
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
    "icon-padding": 0,
    "icon-anchor": "top-left",
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

function LocationPopup({ location }) {
  const when = new Date(location.properties.datetime);
  return (
    <Popup
      latitude={location.geometry.coordinates[1]}
      longitude={location.geometry.coordinates[0]}
      closeButton={false}
      closeOnClick={false}
      focusAfterOpen={false}
    >
      {when.toTimeString().slice(0, 8)}
    </Popup>
  );
}

export default function JourneyMap({ journey }) {
  const darkMode = useDarkMode();

  const [cursor, setCursor] = React.useState();

  const [clickedLocation, setClickedLocation] = React.useState(null);

  const onMouseEnter = React.useCallback((e) => {
    if (e.features.length) {
      setCursor("pointer");
    }

    for (const feature of e.features) {
      if (feature.layer.id === "locations") {
        setClickedLocation(feature);
        break;
      }
    }
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(null);
    setClickedLocation(null);
  }, []);

  const [clickedStop, setClickedStop] = React.useState(null);

  const handleMapClick = React.useCallback((e) => {
    if (e.features.length) {
      for (const feature of e.features) {
        if (feature.layer.id == "stops") {
          setClickedStop(feature);
          break;
        }
      }
    } else {
      setClickedStop(null);
    }
  }, []);

  const handleMapLoad = React.useCallback((event) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    map.loadImage("/static/route-stop-marker.png", (error, image) => {
      if (error) throw error;
      map.addImage("stop", image, {
        pixelRatio: 2,
      });
    });

    map.loadImage("/static/arrow.png", (error, image) => {
      if (error) throw error;
      map.addImage("arrow", image, {
        pixelRatio: 2,
      });
    });
  }, []);

  const bounds = React.useMemo(() => {
    if (journey) {
      const bounds = new LngLatBounds();
      if (journey.locations) {
        for (const item of journey.locations) {
          bounds.extend(item.coordinates);
        }
      }
      if (journey.stops) {
        for (const item of journey.stops) {
          bounds.extend(item.coordinates);
        }
      }
      return bounds;
    }
  }, [journey]);

  if (!journey) {
    return <div className="sorry">Loading…</div>;
  }

  let className = "journey-map";
  if (journey.stops) {
    className += " has-sidebar";
  }

  return (
    <React.Fragment>
      <div className={className}>
        <Map
          dragRotate={false}
          touchPitch={false}
          touchRotate={false}
          pitchWithRotate={false}
          maxZoom={18}
          bounds={bounds}
          fitBoundsOptions={{
            padding: 50,
          }}
          cursor={cursor}
          onMouseEnter={onMouseEnter}
          onMouseMove={onMouseEnter}
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

          {journey.locations ? (
            <React.Fragment>
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
                        heading: l.direction,
                        datetime: l.datetime,
                      },
                    };
                  }),
                }}
              >
                <Layer {...locationsStyle} />
              </Source>
            </React.Fragment>
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
            <LocationPopup location={clickedLocation} />
          ) : null}
        </Map>
      </div>

      {journey.stops ? (
        <TripTimetable
          trip={{
            times: journey.stops.map((stop, i) => {
              return {
                id: i,
                stop: {
                  atco_code: stop.atco_code,
                  name: stop.name,
                  location: stop.coordinates,
                },
                timing_status: stop.minor ? "OTH" : "PTP",
                aimed_arrival_time: stop.aimed_arrival_time,
                aimed_departure_time: stop.aimed_departure_time,
                actual_departure_time: stop.actual_departure_time,
              };
            }),
            notes: [],
          }}
        />
      ) : null}
    </React.Fragment>
  );
}
