import React from "react";

import {
  Layer,
  type LayerProps,
  type MapLayerMouseEvent,
  Source,
} from "react-map-gl/maplibre";

import BusTimesMap, { ThemeContext } from "./Map";

import type { Map as MapGL } from "maplibre-gl";
import LoadingSorry from "./LoadingSorry";
import StopPopup, { type Stop } from "./StopPopup";
import TripTimetable, { type TripTime, tripFromJourney } from "./TripTimetable";
import VehicleMarker, {
  type Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";
import { getBounds } from "./utils";

type VehicleJourneyLocation = {
  id: number;
  coordinates: [number, number];
  // delta: number | null;
  direction?: number | null;
  datetime: string | number;
};

export type StopTime = {
  id: number;
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
  id?: string;
  vehicle_id?: number;
  service_id?: number;
  trip_id?: number;
  datetime: string;
  route_name?: string;
  code: string;
  destination: string;
  direction: string;
  stops?: StopTime[];
  locations?: VehicleJourneyLocation[];
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

export const Locations = React.memo(function Locations({
  locations,
}: {
  locations: VehicleJourneyLocation[];
}) {
  const theme = React.useContext(ThemeContext);
  const darkMode =
    theme === "alidade_smooth_dark" || theme === "alidade_satellite";

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
      "text-size": 12,
      "text-font": ["Stadia Regular"],

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

export const JourneyStops = React.memo(function Stops({
  stops,
  clickedStopUrl,
  setClickedStop,
}: {
  stops: StopTime[];
  clickedStopUrl: string | undefined;
  setClickedStop: (s: string | undefined) => void;
}) {
  const theme = React.useContext(ThemeContext);
  const darkMode =
    theme === "alidade_smooth_dark" || theme === "alidade_satellite";

  const features = React.useMemo(() => {
    return stops
      .filter((s) => s.coordinates)
      .map((s) => {
        return {
          type: "Feature" as const,
          geometry: {
            type: "Point" as const,
            coordinates: s.coordinates as [number, number],
          },
          properties: {
            url: `/stops/${s.atco_code}`,
            name: s.name,
            heading: s.heading,
          },
        };
      });
  }, [stops]);

  const featuresByUrl = React.useMemo<
    { [url: string]: Stop } | undefined
  >(() => {
    return Object.assign(
      {},
      ...features.map((stop) => ({ [stop.properties.url]: stop })),
    );
  }, [features]);

  const clickedStop =
    featuresByUrl && clickedStopUrl && featuresByUrl[clickedStopUrl];

  return (
    <React.Fragment>
      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: features,
        }}
      >
        <Layer
          {...{
            id: "stops",
            type: "symbol",
            layout: {
              // "symbol-sort-key": ["get", "priority"],
              "icon-rotate": ["+", 45, ["get", "heading"]],
              "icon-image": [
                "case",
                ["==", ["get", "heading"], ["literal", null]],
                darkMode
                  ? "route-stop-marker-dark-circle"
                  : "route-stop-marker-circle",
                darkMode ? "route-stop-marker-dark" : "route-stop-marker",
              ],
              // "icon-padding": 0,
              "icon-allow-overlap": true,
              "icon-ignore-placement": true,
            },
          }}
        />
      </Source>
      {clickedStop && (
        <StopPopup
          item={clickedStop}
          onClose={() => setClickedStop(undefined)}
        />
      )}
    </React.Fragment>
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

  return `${string} ${timeString}`;
}

function Sidebar({
  journey,
  loading,
  onMouseEnter,
  vehicle,
}: {
  journey: VehicleJourney;
  loading: boolean;
  onMouseEnter: (t: TripTime) => void;
  vehicle?: Vehicle;
}) {
  let className = "trip-timetable map-sidebar";
  if (loading) {
    className += " loading";
  }

  const trip = React.useMemo(() => {
    return tripFromJourney(journey);
  }, [journey]);

  const today = new Date(journey.datetime).toLocaleDateString();

  let previousLink: React.ReactElement | string | undefined;
  let nextLink: React.ReactElement | string | undefined;
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
        text += ` ${parts[0]}`;
        reg = <span className="reg">{parts[1]}</span>;
      }
    }
  } else {
    text += ` ${journey.route_name}`;
    if (journey.destination) {
      text += ` to ${journey.destination}`;
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
      {trip ? (
        <TripTimetable
          onMouseEnter={onMouseEnter}
          trip={trip}
          vehicle={vehicle}
        />
      ) : (
        <p>{journey.code}</p>
      )}
    </div>
  );
}

function JourneyVehicle({
  vehicleId,
  // journey,
  onVehicleMove,
  clickedVehicleMarker,
  setClickedVehicleMarker,
}: {
  vehicleId: number;
  // journey: VehicleJourney;
  onVehicleMove: (v: Vehicle) => void;
  clickedVehicleMarker: boolean;
  setClickedVehicleMarker: (b: boolean) => void;
}) {
  const [vehicle, setVehicle] = React.useState<Vehicle>();

  React.useEffect(() => {
    if (vehicle) {
      onVehicleMove(vehicle);
    }
  }, [vehicle, onVehicleMove]);

  React.useEffect(() => {
    if (!vehicleId) {
      return;
    }

    let timeout: number;
    let current = true;

    const loadVehicle = () => {
      fetch(`/vehicles.json?id=${vehicleId}`).then((response) => {
        response.json().then((data: Vehicle[]) => {
          if (current && data && data.length) {
            setVehicle(data[0]);
            timeout = window.setTimeout(loadVehicle, 12000); // 12 seconds
          }
        });
      });
    };

    loadVehicle();

    return () => {
      current = false;
      clearTimeout(timeout);
    };
  }, [vehicleId]);

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

  const hoveredLocation = React.useRef<number | null>(null);

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

  const [clickedStopUrl, setClickedStop] = React.useState<string>();

  const [clickedVehicleMarker, setClickedVehicleMarker] =
    React.useState<boolean>(true);

  const [locations, setLocations] = React.useState<VehicleJourneyLocation[]>(
    [],
  );

  const [vehicle, setVehicle] = React.useState<Vehicle>();

  const handleVehicleMove = React.useCallback(
    (vehicle: Vehicle) => {
      if (
        !locations.length ||
        locations[locations.length - 1].datetime > vehicle.datetime
      ) {
        setLocations(
          locations.concat([
            {
              id: new Date(vehicle.datetime).getTime(),
              coordinates: vehicle.coordinates,
              // delta: null,
              datetime: vehicle.datetime,
              direction: vehicle.heading,
            },
          ]),
        );
        setVehicle(vehicle);
      }
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
          setClickedStop(feature.properties.url);
          break;
        }
      }
    } else {
      setClickedStop(undefined);
    }
  }, []);

  const handleRowHover = React.useCallback((a: TripTime) => {
    if (a.stop.location && a.stop.atco_code) {
      setClickedStop(`/stops/${a.stop.atco_code}`);
    }
  }, []);

  const mapRef = React.useRef<MapGL | null>(null);

  const bounds = React.useMemo(() => {
    if (journey) {
      const bounds = getBounds(journey.stops, (item) => item.coordinates);
      return getBounds(journey.locations, (item) => item.coordinates, bounds);
    }
  }, [journey]);

  const onMapInit = React.useCallback((map: MapGL) => {
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
    return <LoadingSorry />;
  }

  let className = "journey-map has-sidebar";
  if (!journey.stops) {
    className += " no-stops";
  }

  return (
    <React.Fragment>
      <div className={className}>
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
            {journey.stops ? (
              <JourneyStops
                stops={journey.stops}
                clickedStopUrl={clickedStopUrl}
                setClickedStop={setClickedStop}
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
                vehicleId={window.VEHICLE_ID}
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
        vehicle={vehicle}
      />
    </React.Fragment>
  );
}
