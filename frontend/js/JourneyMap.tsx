import React from "react";

import {
  Source,
  Layer,
  LayerProps,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";

import BusTimesMap, { ThemeContext } from "./Map";

import { LngLatBounds, Map } from "maplibre-gl";
import TripTimetable, { TripTime } from "./TripTimetable";
import StopPopup from "./StopPopup";
import VehicleMarker, {
  Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";

type VehicleJourneyLocation = {
  id: number;
  coordinates: [number, number];
  delta: number | null;
  direction?: number | null;
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
  vehicle?: string;
  current: boolean;
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
    // "symbol-sort-key": ["get", "priority"],
    "icon-rotate": ["+", 45, ["get", "heading"]],
    "icon-image": "route-stop-marker",
    // "icon-padding": 0,
    "icon-allow-overlap": true,
    "icon-ignore-placement": true,
  },
};

const Locations = React.memo(function Locations({
  locations,
}: {
  locations: VehicleJourneyLocation[];
}) {
  const theme = React.useContext(ThemeContext);
  const darkMode = theme === "alidade_dark";
  const font =
    theme === "ordnance_survey"
      ? ["Source Sans Pro Regular"]
      : ["Stadia Regular"];

  const routeStyle: LayerProps = {
    type: "line",
    paint: {
      "line-color": darkMode ? "#eee" : "#666",
      "line-width": 2,
      "line-dasharray": [2, 2],
    },
  };

  const locationsStyle: LayerProps = {
    id: "locations",
    type: "symbol",
    layout: {
      "text-field": ["get", "time"],
      "text-size": 11,
      "text-font": font,

      "icon-rotate": ["+", 45, ["get", "heading"]],
      "icon-image": "arrow",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
      "icon-anchor": "top-left",

      "text-allow-overlap": true,
    },
    paint: {
      "text-opacity": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
        1,
        0,
      ],
      "text-color": darkMode ? "#fff" : "#333",
      "text-halo-color": darkMode ? "#333" : "#fff",
      "text-halo-width": 3,
    },
  };

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
        id="locations"
        data={{
          type: "FeatureCollection",
          features: locations.map((l) => {
            return {
              type: "Feature",
              id: l.id,
              geometry: {
                type: "Point",
                coordinates: l.coordinates,
              },
              properties: {
                // delta: l.delta,
                heading: l.direction,
                // datetime: l.datetime,
                time: new Date(l.datetime).toTimeString().slice(0, 8),
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
                // minor: s.minor,
                heading: s.heading,
                aimed_arrival_time: s.aimed_arrival_time,
                aimed_departure_time: s.aimed_departure_time,
                // priority: s.minor ? 0 : 1, // symbol-sort-key lower number - "higher" priority
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

  let text = today;
  let reg = null;
  if (journey.vehicle) {
    reg = journey.vehicle;
    if (journey.vehicle.includes(" ")) {
      if (journey.vehicle.includes(" - ")) {
        const parts = journey.vehicle.split(" - ", 2);
        text += " " + parts[0];
        reg = <span className="reg">{parts[1]}</span>;
      }
    }
  } else {
    text += " " + journey.route_name;
    if (journey.destination) {
      text += " to " + journey.destination;
    }
  }

  return (
    <div className={className}>
      <div className="navigation">
        {previousLink}
        {nextLink}
      </div>
      <p>
        {text} {reg}
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

function JourneyVehicle({
  // journey,
  onVehicleMove,
  clickedVehicleMarker,
  setClickedVehicleMarker,
}: {
  // journey: VehicleJourney;
  onVehicleMove: (v: Vehicle) => void;
  clickedVehicleMarker: boolean;
  setClickedVehicleMarker: (b: boolean) => void;
}) {
  const vehicleId = window.VEHICLE_ID;

  const [vehicle, setVehicle] = React.useState<Vehicle>();

  // const timeout = React.useRef<number>();

  const handleVehicle = React.useCallback(
    (v: Vehicle) => {
      if (v.datetime !== vehicle?.datetime) {
        setVehicle(v);
        onVehicleMove(v);
      }
    },
    [vehicle?.datetime, onVehicleMove],
  );

  React.useEffect(() => {
    if (!vehicleId) {
      return;
    }

    let timeout: number;

    const loadVehicle = () => {
      fetch(`/vehicles.json?id=${vehicleId}`).then((response) => {
        response.json().then((data: Vehicle[]) => {
          if (data && data.length) {
            handleVehicle(data[0]);
            timeout = window.setTimeout(loadVehicle, 12000); // 12 seconds
          }
        });
      });
    };

    loadVehicle();

    return () => {
      clearTimeout(timeout);
    };
  }, [vehicleId, handleVehicle]);

  if (!vehicle) {
    return null;
  }

  return (
    <React.Fragment>
      <VehicleMarker selected={clickedVehicleMarker} vehicle={vehicle} />
      {clickedVehicleMarker ? (
        <VehiclePopup
          item={vehicle}
          onClose={() => setClickedVehicleMarker(false)}
        />
      ) : null}
    </React.Fragment>
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

  const hoveredLocation = React.useRef<number>();

  const onMouseEnter = React.useCallback((e: MapLayerMouseEvent) => {
    const vehicleId = getClickedVehicleMarkerId(e);
    if (vehicleId) {
      return;
    }

    if (e.features?.length) {
      setCursor("pointer");

      for (const feature of e.features) {
        if (feature.layer.id === "locations") {
          if (hoveredLocation.current) {
            e.target.setFeatureState(
              { source: "locations", id: hoveredLocation.current },
              { hover: false },
            );
          }
          e.target.setFeatureState(
            { source: "locations", id: feature.id },
            { hover: true },
          );
          hoveredLocation.current = feature.id as number;
          return;
        }
      }
    }
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor(undefined);
    // setClickedLocation(undefined);
  }, []);

  const [clickedStop, setClickedStop] = React.useState<Stop>();

  const [clickedVehicleMarker, setClickedVehicleMarker] =
    React.useState<boolean>(true);

  const [locations, setLocations] = React.useState<VehicleJourneyLocation[]>(
    [],
  );

  const handleVehicleMove = React.useCallback(
    (vehicle: Vehicle) => {
      setLocations(
        locations.concat([
          {
            id: new Date(vehicle.datetime).getTime(),
            coordinates: vehicle.coordinates,
            delta: null,
            datetime: vehicle.datetime,
            direction: vehicle.heading,
          },
        ]),
      );
    },
    [locations],
  );

  const handleMapClick = React.useCallback((e: MapLayerMouseEvent) => {
    const vehicleId = getClickedVehicleMarkerId(e);
    if (vehicleId) {
      setClickedVehicleMarker(true);
      setClickedStop(undefined);
      return;
    }

    setClickedVehicleMarker(false);

    if (e.features?.length) {
      for (const feature of e.features) {
        if (feature.layer.id === "stops") {
          setClickedStop(feature as unknown as Stop);
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

  const mapRef = React.useRef<Map>();

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

  const onMapInit = React.useCallback((map: Map) => {
    // debugger;
    mapRef.current = map;

    // if (bounds) {
    //   map.fitBounds(bounds, {
    //     padding: 50,
    //   });
    // }
  }, []);

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
            onMapInit={onMapInit}
            interactiveLayerIds={["stops", "locations"]}
          >
            {journey.stops ? <Stops stops={journey.stops} /> : null}

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

            {journey.locations ? (
              <Locations
                locations={
                  journey.current
                    ? journey.locations.concat(locations)
                    : journey.locations
                }
              />
            ) : null}
            {journey.locations && journey.current ? (
              <JourneyVehicle
                // journey={journey}
                onVehicleMove={handleVehicleMove}
                clickedVehicleMarker={clickedVehicleMarker}
                setClickedVehicleMarker={setClickedVehicleMarker}
              />
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
