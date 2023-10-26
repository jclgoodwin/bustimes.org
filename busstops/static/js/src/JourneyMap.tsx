import React from "react";

import {
  Source,
  Layer,
  Popup,
  MapEvent,
  LayerProps,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";

import BusTimesMap from "./Map";

import routeStopMarker from "data-url:../../route-stop-marker.png";
import arrow from "data-url:../../arrow.png";

import { LngLatBounds } from "maplibre-gl";
import TripTimetable, { TripTime } from "./TripTimetable";
import StopPopup from "./StopPopup";

type VehicleJourneyLocation = {
  coordinates: [number, number];
  delta: number;
  direction: number;
  datetime: string;
};

type Stop = {
  properties: {
    name: string;
    atco_code: string;
  };
  geometry: {
    coordinates: [number, number];
  };
};

type StopTime = {
  atco_code: string;
  name: string;
  aimed_arrival_time: string;
  aimed_departure_time: string | null;
  minor: boolean;
  heading: number;
  coordinates?: [number, number] | null;
  actual_departure_time: string;
};

export type VehicleJourney = {
  datetime: string;
  route_name?: string;
  code: string;
  destination: string;
  direction: string;
  stops: StopTime[];
  locations: VehicleJourneyLocation[];
  next: {
    id: number;
    datetime: string;
  };
  previous: {
    id: number;
    datetime: string;
  };
};

const stopsStyle: LayerProps = {
  id: "stops",
  type: "symbol",
  layout: {
    "icon-rotate": ["+", 45, ["get", "heading"]],
    "icon-image": "stop",
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
  },
};

const locationsStyle: LayerProps = {
  id: "locations",
  type: "symbol",
  layout: {
    "icon-rotate": ["+", 45, ["get", "heading"]],
    "icon-image": "arrow",
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
    "icon-anchor": "top-left",
  },
};

const routeStyle: LayerProps = {
  type: "line",
  paint: {
    "line-color": "#000",
    "line-opacity": 0.5,
    "line-width": 3,
    "line-dasharray": [2, 2],
  },
};

type LocationPopupProps = {
  location: {
    properties: {
      datetime: string;
    };
    geometry: {
      coordinates: [number, number];
    };
  };
};

function LocationPopup({ location }: LocationPopupProps) {
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

const Locations = React.memo(function Locations({
  locations,
}: {
  locations: VehicleJourneyLocation[];
}) {
  return (
    <React.Fragment>
      <Source
        type="geojson"
        data={{
          type: "LineString",
          coordinates: locations.map((l) => l.coordinates),
        }}
      >
        <Layer {...routeStyle} />
      </Source>

      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: locations.map((l) => {
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
  );
});

const Stops = React.memo(function Stops({ stops }: { stops: StopTime[] }) {
  return (
    <Source
      type="geojson"
      data={{
        type: "FeatureCollection",
        features: stops
          .filter((s) => s.coordinates)
          .map((s) => {
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
  );
});

function nextOrPreviousLink(
  today: string,
  nextOrPrevious: VehicleJourney["next"],
): string {
  const nextOrPreviousDate = new Date(nextOrPrevious.datetime);
  const string = nextOrPreviousDate.toLocaleDateString();
  const timeString = nextOrPreviousDate.toTimeString().slice(0, 5);

  if (string === today) {
    return timeString;
  }

  return string + " " + timeString;
}

function Sidebar({
  journey,
  loading,
  onMouseEnter,
}: {
  journey: VehicleJourney;
  loading: boolean;
  onMouseEnter: (t: TripTime) => void;
}) {
  let className = "trip-timetable map-sidebar";
  if (loading) {
    className += " loading";
  }

  const today = new Date(journey.datetime).toLocaleDateString();

  let previousLink, nextLink;
  if (journey) {
    if (journey.previous) {
      previousLink = nextOrPreviousLink(today, journey.previous);
      previousLink = (
        <p className="previous">
          <a href={`#journeys/${journey.previous.id}`}>&larr; {previousLink}</a>
        </p>
      );
    }
    if (journey.next) {
      nextLink = nextOrPreviousLink(today, journey.next);
      nextLink = (
        <p className="next">
          <a href={`#journeys/${journey.next.id}`}>{nextLink} &rarr;</a>
        </p>
      );
    }
  }

  return (
    <div className={className}>
      <div className="navigation">
        {previousLink}
        {nextLink}
      </div>
      <p>
        {today} {journey.route_name}{" "}
        {journey.destination ? " to " + journey.destination : null}
      </p>
      {journey.stops ? (
        <TripTimetable
          onMouseEnter={onMouseEnter}
          trip={{
            times: journey.stops.map((stop, i: number) => {
              return {
                id: i,
                stop: {
                  atco_code: stop.atco_code,
                  name: stop.name,
                  location: stop.coordinates || undefined,
                },
                timing_status: stop.minor ? "OTH" : "PTP",
                aimed_arrival_time: stop.aimed_arrival_time,
                aimed_departure_time: stop.aimed_departure_time,
                actual_departure_time: stop.actual_departure_time,
              };
            }),
          }}
        />
      ) : (
        <p>{journey.code}</p>
      )}
    </div>
  );
}

export default function JourneyMap({
  journey,
  loading = false,
}: {
  journey?: VehicleJourney;
  loading: boolean;
}) {
  const [cursor, setCursor] = React.useState<string>();

  const [clickedLocation, setClickedLocation] =
    React.useState<LocationPopupProps["location"]>();

  const onMouseEnter = React.useCallback((e: MapLayerMouseEvent) => {
    if (e.features?.length) {
      setCursor("pointer");

      for (const feature of e.features) {
        if (feature.layer.id === "locations") {
          setClickedLocation(feature as any as LocationPopupProps["location"]);
          break;
        }
      }
    }
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(undefined);
    setClickedLocation(undefined);
  }, []);

  const [clickedStop, setClickedStop] = React.useState<Stop>();

  const handleMapClick = React.useCallback((e: MapLayerMouseEvent) => {
    if (e.features?.length) {
      for (const feature of e.features) {
        if (feature.layer.id === "stops") {
          setClickedStop(feature as any as Stop);
          break;
        }
      }
    } else {
      setClickedStop(undefined);
    }
  }, []);

  const handleRowHover = React.useCallback((a: TripTime) => {
    if (a.stop.location && a.stop.atco_code) {
      setClickedStop({
        properties: {
          atco_code: a.stop.atco_code,
          name: a.stop.name,
        },
        geometry: {
          coordinates: a.stop.location,
        },
      });
    }
  }, []);

  const mapRef = React.useRef<any>();

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    mapRef.current = map;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();

    const image = new Image();
    image.src = routeStopMarker;
    image.onload = function () {
      map.addImage("stop", image, {
        pixelRatio: 2,
      });
    };

    const arrowImage = new Image();
    arrowImage.src = arrow;
    arrowImage.onload = function () {
      map.addImage("arrow", arrowImage, {
        pixelRatio: 2,
      });
    };
  }, []);

  const bounds = React.useMemo((): LngLatBounds | null => {
    if (journey) {
      const _bounds = new LngLatBounds();
      if (journey.locations) {
        for (const item of journey.locations) {
          _bounds.extend(item.coordinates);
        }
      }
      if (journey.stops) {
        for (const item of journey.stops) {
          if (item.coordinates) {
            _bounds.extend(item.coordinates);
          }
        }
      }
      if (!_bounds.isEmpty()) {
        return _bounds;
      }
    }
    return null;
  }, [journey]);

  React.useEffect(() => {
    if (bounds && mapRef.current) {
      mapRef.current.fitBounds(bounds, {
        padding: 50,
      });
    }
  }, [bounds]);

  if (!journey) {
    return <div className="sorry">Loading…</div>;
  }

  return (
    <React.Fragment>
      <div className="journey-map has-sidebar">
        {bounds ? (
          <BusTimesMap
            initialViewState={{
              bounds: bounds,
              fitBoundsOptions: {
                padding: 50,
              },
            }}
            cursor={cursor}
            onMouseEnter={onMouseEnter}
            onMouseMove={onMouseEnter}
            onMouseLeave={onMouseLeave}
            onClick={handleMapClick}
            onLoad={handleMapLoad}
            interactiveLayerIds={["stops", "locations"]}
          >
            {journey.stops ? <Stops stops={journey.stops} /> : null}

            {journey.locations ? (
              <Locations locations={journey.locations} />
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
                onClose={() => setClickedStop(undefined)}
              />
            ) : null}

            {clickedLocation ? (
              <LocationPopup location={clickedLocation} />
            ) : null}
          </BusTimesMap>
        ) : null}
      </div>
      <Sidebar
        loading={loading}
        journey={journey}
        onMouseEnter={handleRowHover}
      />
    </React.Fragment>
  );
}
