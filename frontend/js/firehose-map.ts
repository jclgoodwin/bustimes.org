import "./polyfills";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import busIconUrl from "data-url:../bus-droplet.png";
// import maplibreWorkerUrl from "url:maplibre-gl/dist/maplibre-gl-worker.mjs";

// maplibregl.setWorkerUrl(maplibreWorkerUrl);

type View = { zoom: number; center: [number, number] };

const parseVehicleMap = (raw: string | null): View | null => {
  if (!raw) return null;
  const [zoom, lat, lng] = raw.split("/").map(Number);
  if (!Number.isFinite(zoom) || !Number.isFinite(lat) || !Number.isFinite(lng))
    return null;
  return { zoom, center: [lng, lat] };
};

const initialView = parseVehicleMap(localStorage.getItem("vehicleMap"));

const map = new maplibregl.Map({
  container: "hugemap",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: initialView?.center ?? [-2.9, 54],
  zoom: initialView?.zoom ?? 5,
  attributionControl: {
    compact: false,
    customAttribution: "",
  },
});

window.addEventListener("storage", (e) => {
  if (e.key !== "vehicleMap") return;
  const view = parseVehicleMap(e.newValue);
  if (view) map.easeTo(view);
});

map.on("load", () => {
  // Add GeoJSON source for vehicle locations
  map.addSource("vehicles", {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: [],
    },
  });

  const busImage = new Image();
  busImage.src = busIconUrl;
  busImage.onload = () => {
    if (!map.hasImage("vehicle-marker")) {
      map.addImage("vehicle-marker", busImage, { pixelRatio: 2, sdf: true });
    }
  };

  map.addLayer({
    id: "vehicle-labels",
    type: "symbol",
    source: "vehicles",
    layout: {
      "icon-image": "vehicle-marker",
      // arrow points to the bottom-left of the icon (compass 225° when
      // un-rotated), so subtract 225 to align with heading
      "icon-rotate": ["-", ["coalesce", ["get", "heading"], 0], 225],
      "icon-rotation-alignment": "map",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
      "text-field": ["get", "line_name"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 12,
      "text-allow-overlap": true,
      "text-ignore-placement": true,
    },
    paint: {
      "text-color": "#fff",
      "icon-color": ["coalesce", ["get", "colour"], "#000"],
    },
  });

  map.on("mouseenter", "vehicle-labels", () => {
    map.getCanvas().style.cursor = "pointer";
  });

  map.on("mouseleave", "vehicle-labels", () => {
    map.getCanvas().style.cursor = "";
  });

  map.on("click", "vehicle-labels", (e) => {
    const feature = e.features?.[0];
    if (!feature || feature.geometry.type !== "Point") return;

    const id = Number((feature.properties as { id: number | string }).id);
    const coords = feature.geometry.coordinates as [number, number];
    openVehiclePopup(id, coords, feature.properties as VehicleProps);
    map.panTo(coords);
  });

  // messages may have arrived (and populated `vehicles`) before the source
  // existed, so render whatever's already been received
  syncVehiclesSource();
});

const wsProtocol = window.location.protocol === "http:" ? "ws" : "wss";

const statusBar = document.getElementById("skew");

const vehicles = new Map(); // Track all vehicles by id

const syncVehiclesSource = () => {
  const source = map.getSource("vehicles");
  if (source && source.type === "geojson") {
    source.setData({
      type: "FeatureCollection",
      features: Array.from(vehicles.values()),
    });
  }
};

let openPopup: maplibregl.Popup | null = null;
let openPopupId: number | null = null;
let openPopupProps: VehicleProps | null = null;

const openVehiclePopup = (
  id: number,
  coords: [number, number],
  props: VehicleProps,
) => {
  const tracked = id === singleVehicleId;
  openPopupProps = props;
  openPopup = new maplibregl.Popup({
    offset: [0, -6],
    closeOnClick: !tracked,
    closeButton: !tracked,
  })
    .setLngLat(coords)
    .setHTML(popupHTML(openPopupProps))
    .addTo(map);
  openPopupId = id;
  openPopup.on("close", () => {
    openPopup = null;
    openPopupId = null;
    openPopupProps = null;
  });
};

const randomColour = () =>
  `#${Math.floor(Math.random() * 0xffffff)
    .toString(16)
    .padStart(6, "0")}`;

type VehicleItem = {
  id: number;
  coordinates: [number, number];
  heading?: number;
  datetime?: string;
  destination?: string;
  service?: { line_name?: string };
};

type VehicleProps = {
  id: number;
  heading: number;
  datetime?: string;
  destination?: string;
  line_name?: string;
};

const popupHTML = (props: VehicleProps) => {
  let when = "";
  if (props.datetime) {
    const seconds = Math.round(
      (Date.now() - new Date(props.datetime).getTime()) / 1000,
    );
    when = `<time>${new Date(props.datetime).toLocaleTimeString()} (${seconds}s ago)</time>`;
  }
  return [
    props.line_name &&
      `<strong>${props.line_name}</strong>${props.destination ? ` to ${props.destination}` : ""}`,
    when,
    `<a href="#${props.id}">vehicle ${props.id}</a>`,
  ]
    .filter(Boolean)
    .join("<br>");
};

setInterval(() => {
  if (openPopup && openPopupProps) {
    openPopup.setHTML(popupHTML(openPopupProps));
  }
}, 1000);

const getSingleVehicleId = (): number | null => {
  const hash = window.location.hash.slice(1);
  if (!hash) return null;
  const id = Number(hash);
  return Number.isFinite(id) ? id : null;
};

const wsPath = () => {
  const id = getSingleVehicleId();
  return id !== null ? `/firehose/${id}` : "/firehose";
};

let currentWs: WebSocket | null = null;
let singleVehicleId: number | null = null;
let hasCenteredOnVehicle = false;

const connect = () => {
  singleVehicleId = getSingleVehicleId();
  hasCenteredOnVehicle = false;

  const ws = new WebSocket(
    `${wsProtocol}://${window.location.host}${wsPath()}`,
  );
  currentWs = ws;

  ws.onopen = () => {
    const source = map.getSource("vehicles");
    if (source && source.type === "geojson") {
      source.setData({ type: "FeatureCollection", features: [] });
    }

    if (statusBar) {
      statusBar.prepend("connected\n");
    }
  };

  ws.onclose = () => {
    if (ws !== currentWs) return; // superseded by a newer connection
    if (statusBar) {
      const reconnectButton = document.createElement("button");
      statusBar.prepend("disconnected\n");
    }
    setTimeout(connect, 1000);
  };

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    const items: VehicleItem[] = message.items || [];

    for (const item of items) {
      vehicles.set(item.id, {
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: item.coordinates,
        },
        properties: {
          id: item.id,
          heading: item.heading ?? 0,
          datetime: item.datetime,
          destination: item.destination,
          line_name: item.service?.line_name,
          colour: randomColour(),
        },
      });

      const tracked = item.id === singleVehicleId;

      if (tracked || (openPopup && openPopupId === item.id)) {
        const props: VehicleProps = {
          id: item.id,
          heading: item.heading ?? 0,
          datetime: item.datetime,
          destination: item.destination,
          line_name: item.service?.line_name,
        };
        if (openPopupId === item.id) {
          openPopupProps = props;
          openPopup?.setLngLat(item.coordinates).setHTML(popupHTML(props));
        } else {
          openVehiclePopup(item.id, item.coordinates, props);
        }
      }

      if (tracked) {
        if (hasCenteredOnVehicle) {
          map.panTo(item.coordinates);
        } else {
          map.flyTo({
            center: item.coordinates,
            zoom: Math.max(map.getZoom(), 15),
          });
          hasCenteredOnVehicle = true;
        }
      } else if (openPopup && openPopupId === item.id) {
        map.panTo(item.coordinates);
      }
    }

    const source = map.getSource("vehicles");
    if (source && source.type === "geojson") {
      source.setData({
        type: "FeatureCollection",
        features: Array.from(vehicles.values()),
      });
    }
  };
};

window.addEventListener("hashchange", () => {
  openPopup?.remove();
  currentWs?.close();
  connect();
});

connect();
