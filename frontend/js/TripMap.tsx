import React from "react";

import {
  Source,
  Layer,
  MapEvent,
  LayerProps,
  MapLayerMouseEvent,
} from "react-map-gl/maplibre";

import { useRoute } from "wouter";
import { useLocation } from "wouter";

import { LngLatBounds } from "maplibre-gl";

import TripTimetable, { Trip, TripTime } from "./TripTimetable";
import StopPopup, { Stop } from "./StopPopup";
import VehicleMarker, {
  Vehicle,
  getClickedVehicleMarkerId,
} from "./VehicleMarker";
import VehiclePopup from "./VehiclePopup";
import BusTimesMap from "./Map";

declare global {
  interface Window {
    SERVICE: number;
    TRIP_ID: number;
    VEHICLE_ID: number;
    STOPS: Trip;
  }
}

const apiRoot = process.env.API_ROOT;

const stopsStyle: LayerProps = {
  id: "stops",
  type: "symbol",
  layout: {
    "symbol-sort-key": ["get", "priority"],
    "text-field": ["get", "time"],
    "text-size": 11,
    "text-font": ["Stadia Regular"],
  },
  "paint": {
    "text-halo-color": "#fff",
    "text-halo-width": 2,
  },
};

const routeStyle: LayerProps = {
  type: "line",
  paint: {
    "line-color": "#666",
    "line-width": 3,
  },
};

const lineStyle: LayerProps = {
  type: "line",
  paint: {
    "line-color": "#666",
    "line-width": 3,
    "line-dasharray": [2, 2],
  },
};

type RouteProps = {
  times: TripTime[];
};

const Route = React.memo(function Route({ times }: RouteProps) {
  const lines = [];
  const lineStrings = [];
  let prevLocation,
    prevTime,
    i = null;

  for (const time of times) {
    if (time.track) {
      lineStrings.push(time.track);
    } else if (prevTime && prevLocation && time.stop.location) {
      if (prevTime.track || i === null) {
        lines.push([prevLocation, time.stop.location]);
        i = lines.length - 1;
      } else {
        lines[i].push(time.stop.location);
      }
    }

    prevTime = time;
    prevLocation = time.stop.location;
  }

  return (
    <React.Fragment>
      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: lineStrings.map((lineString) => {
            return {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: lineString,
              },
            };
          }),
        }}
      >
        <Layer {...routeStyle} />
      </Source>

      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: lines.map((line) => {
            return {
              type: "Feature",
              geometry: {
                type: "LineString",
                coordinates: line,
              },
            };
          }),
        }}
      >
        <Layer {...lineStyle} />
      </Source>

      <Source
        type="geojson"
        data={{
          type: "FeatureCollection",
          features: times
            .filter((stop) => stop.stop.location)
            .map((stop) => {
              return {
                type: "Feature",
                geometry: {
                  type: "Point",
                  coordinates: stop.stop.location,
                },
                properties: {
                  url: stop.stop.atco_code
                    ? `/stops/${stop.stop.atco_code}`
                    : null,
                  "name": stop.stop.name,
                  "bearing": stop.stop.bearing,
                  "time": stop.aimed_arrival_time || stop.aimed_departure_time || stop.expected_arrival_time,
                  "priority": stop.timing_status === "PTP" ? 0 : 1 // symbol-sort-key lower number - "higher" priority
                },
              };
            }),
        }}
      >
        <Layer {...stopsStyle} />
      </Source>
    </React.Fragment>
  );
});

export default function TripMap() {
  const [, params] = useRoute<{ tripId: "" }>("/trips/:tripId");
  const [, navigate] = useLocation();
  const tripId: string | undefined = params?.tripId;

  const [trip, setTrip] = React.useState<Trip>(window.STOPS);

  const [loading, setLoading] = React.useState(false);

  const bounds = React.useMemo((): LngLatBounds => {
    const _bounds = new LngLatBounds();
    for (let item of trip.times) {
      if (item.stop.location) {
        _bounds.extend(item.stop.location);
      }
    }
    return _bounds;
  }, [trip]);

  const navigateToTrip = React.useCallback((item: Vehicle) => {
    navigate("/trips/" + item.trip_id);
  }, [navigate]);

  const [cursor, setCursor] = React.useState("");

  const onMouseEnter = React.useCallback(() => {
    setCursor("pointer");
  }, []);

  const onMouseLeave = React.useCallback(() => {
    setCursor("");
  }, []);

  const [clickedStop, setClickedStop] = React.useState<Stop>();

  const highlightedStop = React.useMemo(() => {
    if (clickedStop) {
      return clickedStop.properties.url;
    }
    if (document.referrer) {
      const referrer = new URL(document.referrer).pathname;
      if (referrer.indexOf("/stops/") === 0) {
        return referrer;
      }
    }
    return "";
  }, [clickedStop]);

  const handleMapClick = React.useCallback(
    (e: MapLayerMouseEvent) => {
      const vehicleId = getClickedVehicleMarkerId(e);
      if (vehicleId) {
        setClickedVehicleMarker(vehicleId);
        setClickedStop(undefined);
        e.preventDefault();
        return;
      }

      if (e.features?.length) {
        for (const stop of e.features) {
          if (
            !stop.properties.url ||
            stop.properties.url !== clickedStop?.properties?.url
          ) {
            setClickedStop(stop as any as Stop);
          }
        }
      } else {
        setClickedStop(undefined);
      }
      setClickedVehicleMarker(undefined);
      e.preventDefault();
    },
    [clickedStop],
  );

  const [tripVehicle, setTripVehicle] = React.useState<Vehicle>();
  const [vehicles, setVehicles] = React.useState<Vehicle[]>([]);

  const vehiclesById = React.useMemo<[number: Vehicle]>(() => {
    return Object.assign({}, ...vehicles.map((item) => ({ [item.id]: item })));
  }, [vehicles]);

  const timeout = React.useRef<number>();
  const vehiclesAbortController = React.useRef<AbortController>();

  const loadTrip = React.useCallback((tripId: string) => {
    setTripVehicle(undefined);
    if (window.STOPS.id && window.STOPS.id.toString() === tripId) {
      setTrip(window.STOPS);
      return;
    }
    fetch(`${apiRoot}api/trips/${tripId}/`).then((response) => {
      if (response.ok) {
        response.json().then(setTrip);
      }
    });
  }, []);

  React.useEffect(() => {
    const loadVehicles = (first = false) => {
      if (document.hidden) {
        return;
      }

      let url = `${apiRoot}vehicles.json`;
      if (window.VEHICLE_ID) {
        url = `${url}?id=${window.VEHICLE_ID}`;
      } else if (!window.SERVICE || !tripId) {
        return;
      } else {
        url = `${url}?service=${window.SERVICE}&trip=${tripId}`;
      }

      setLoading(true);

      clearTimeout(timeout.current);

      if (vehiclesAbortController.current) {
        vehiclesAbortController.current.abort();
      }
      vehiclesAbortController.current =
        new AbortController() as AbortController;

      fetch(url, {
        signal: vehiclesAbortController.current.signal,
      }).then(
        (response) => {
          if (!response.ok) {
            return;
          }
          response.json().then(function (items: Vehicle[]): void {
            setVehicles(items);
            setLoading(false);
            for (const item of items) {
              if (
                (tripId &&
                  item.trip_id &&
                  item.trip_id.toString() === tripId) ||
                (window.VEHICLE_ID && item.id === window.VEHICLE_ID)
              ) {
                if (first) {
                  setClickedVehicleMarker(item.id);
                }
                setTripVehicle(item);
                break;
              }
            }
          });
          if (!document.hidden) {
            timeout.current = window.setTimeout(loadVehicles, 12000); // 12 seconds
          }
        },
        (reason) => {
          // never mind
        },
      );
    };

    if (tripId) {
      loadTrip(tripId);
    }
    loadVehicles(true);

    const handleVisibilityChange = () => {
      clearTimeout(timeout.current);
      if (!document.hidden) {
        loadVehicles();
      }
    };

    window.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [tripId, loadTrip]);

  const [clickedVehicleMarkerId, setClickedVehicleMarker] =
    React.useState<number>();

  const handleMapLoad = React.useCallback((event: MapEvent) => {
    const map = event.target;
    map.keyboard.disableRotation();
    map.touchZoomRotate.disableRotation();
  }, []);

  const clickedVehicle =
    clickedVehicleMarkerId && vehiclesById[clickedVehicleMarkerId];

  return (
    <React.Fragment>
      <div className="trip-map has-sidebar">
        <BusTimesMap
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            left: 0,
          }}
          initialViewState={{
            bounds: bounds,
            fitBoundsOptions: {
              padding: 50,
            },
          }}
          cursor={cursor}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
          onClick={handleMapClick}
          onLoad={handleMapLoad}
          interactiveLayerIds={["stops"]}
        >
          <Route times={trip.times} />

          {vehicles.map((item) => {
            return (
              <VehicleMarker
                key={item.id}
                selected={item.id === clickedVehicleMarkerId || item.trip_id === tripId}
                vehicle={item}
              />
            );
          })}

          {clickedVehicle ? (
            <VehiclePopup
              item={clickedVehicle}
              activeLink={clickedVehicle.trip_id?.toString() === tripId}
              onTripClick={navigateToTrip}
              onClose={() => {
                setClickedVehicleMarker(undefined);
              }}
            />
          ) : null}

          {clickedStop ? (
            <StopPopup
              item={clickedStop}
              onClose={() => setClickedStop(undefined)}
            />
          ) : null}

          {loading ? (
            <div className="maplibregl-ctrl map-status-bar">Loading…</div>
          ) : null}
        </BusTimesMap>
      </div>
      <div className="trip-timetable map-sidebar">
        <TripTimetable
          trip={trip}
          vehicle={tripVehicle}
          highlightedStop={highlightedStop}
        />
      </div>
    </React.Fragment>
  );
}
