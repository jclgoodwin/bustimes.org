import "leaflet/dist/leaflet.css";
import "leaflet.locatecontrol"; // Import plugin
import "leaflet.locatecontrol/dist/L.Control.Locate.min.css"; // Import styles
import L from "leaflet"; // Import L from leaflet to start using the plugin
import {
  doTileLayer,
  getBusIcon,
  updatePopupContent,
  getTransform,
} from "./maps.js";

import "./bigmap-classic.css";

import debounce from "lodash/debounce";

/* global reqwest, bustimes, INITIAL_VIEW_STATE */

var map = L.map("hugemap", {
    worldCopyJump: true,
    tap: false,
    minZoom: 6,
    maxBounds: [
      [48, -12],
      [62, 3],
    ],
  }),
  stopsGroup = L.layerGroup(),
  vehiclesGroup = L.layerGroup(),
  clickedTrip;

doTileLayer(map);

L.control.locate().addTo(map);

L.control
  .layers(
    undefined,
    {
      "Show stops": stopsGroup,
    },
    {
      collapsed: false,
    },
  )
  .addTo(map);

var lastStopsReq,
  stopsHighWater,
  showStops = true,
  bigStopMarkers,
  bigVehicleMarkers = true;

if (document.referrer && document.referrer.indexOf("/stops/") > -1) {
  var clickedStopMarker = "/stops/" + document.referrer.split("/stops/")[1];
  clickedStopMarker = clickedStopMarker.split("?")[0];
} else {
  try {
    if (localStorage.hideStops) {
      showStops = false;
    }
  } catch (e) {
    // ok
  }
}

stopsGroup
  .on("add", function () {
    if (map.getZoom() < 13) {
      map.setZoom(13); // loadStops will be called by moveend handler
    } else if (!showStops) {
      loadStops();
    }
    showStops = true;
    try {
      localStorage.removeItem("hideStops");
    } catch (e) {
      // ok
    }
  })
  .on("remove", function () {
    if (showStops) {
      // box was unchecked (not just a zoom out)
      showStops = false;
      try {
        localStorage.setItem("hideStops", "1");
      } catch (e) {
        // ok
      }
    }
  });

vehiclesGroup.addTo(map);

var railIcon = L.divIcon({
  iconSize: [18, 18],
  html: '<div class="rail"><svg xmlns="http://www.w3.org/2000/svg" width="12.4" height="7.8" viewBox="0 0 62 39"><g stroke="#fff" fill="none"><path d="M1,-8.9 46,12.4 16,26.6 61,47.9" stroke-width="6"/><path d="M0,12.4H62m0,14.2H0" stroke-width="6.4"/></g></svg></div>',
  popupAnchor: [0, -4],
  className: "stop",
});

function getStopIcon(properties) {
  if (
    properties.stop_type === "RLY" &&
    properties.url.indexOf("/stops/910") === 0
  ) {
    return railIcon;
  }

  var html = properties.icon || "";
  var className = "stop stop-" + html.length;
  if (properties.bearing !== null) {
    html +=
      '<div class="stop-arrow" style="' +
      getTransform(properties.bearing + 45) +
      '"></div>';
  } else {
    html += '<div class="stop-arrow no-direction"></div>';
  }
  return L.divIcon({
    iconSize: [16, 16],
    html: html,
    popupAnchor: [0, -8],
    className: className,
  });
}

var stops = {};

function handleStop(data) {
  var latLng = L.latLng(
    data.geometry.coordinates[1],
    data.geometry.coordinates[0],
  );
  if (bigStopMarkers || data.properties.stop_type === "RLY") {
    var marker = L.marker(
      L.latLng(data.geometry.coordinates[1], data.geometry.coordinates[0]),
      {
        icon: getStopIcon(data.properties),
        url: data.properties.url,
      },
    );
  } else {
    marker = L.circleMarker(latLng, {
      stroke: false,
      fillColor: "#333",
      fillOpacity: 0.5,
      radius: 3,
      url: data.properties.url,
    });
  }
  var a = document.createElement("a");
  a.className = "has-smalls";

  a.innerHTML = "<span>" + data.properties.name + "</span>";
  if (data.properties.services) {
    a.innerHTML +=
      "<small>" + data.properties.services.join("</small><small>") + "</small>";
  }
  a.href = data.properties.url;

  marker
    .bindPopup(a.outerHTML, {
      autoPan: false,
    })
    .on("popupopen", handleStopPopupOpen)
    .on("popupclose", handleStopPopupClose);

  marker.addTo(stopsGroup);
  stops[data.properties.url] = marker;
}

function handleStopPopupOpen(event) {
  var marker = event.target;
  clickedStopMarker = marker.options.url;
}

function handleStopPopupClose(event) {
  if (map.hasLayer(event.target)) {
    clickedStopMarker = null;
  }
}

function loadStops() {
  if (lastStopsReq) {
    lastStopsReq.abort();
  }
  var bounds = map.getBounds();
  bigStopMarkers = map.getZoom() > 14;
  if (stopsHighWater && stopsHighWater.contains(bounds)) {
    if (!bigStopMarkers) {
      return;
    }
  }
  var params =
    "?ymax=" +
    round(bounds.getNorth()) +
    "&xmax=" +
    round(bounds.getEast()) +
    "&ymin=" +
    round(bounds.getSouth()) +
    "&xmin=" +
    round(bounds.getWest());
  lastStopsReq = reqwest({
    url: "/stops.json" + params,
    success: function (data) {
      if (data && data.features) {
        stopsHighWater = bounds;
        stopsGroup.clearLayers();
        stops = {};
        for (var i = data.features.length - 1; i >= 0; i -= 1) {
          handleStop(data.features[i]);
        }
        if (clickedStopMarker) {
          var stop = stops[clickedStopMarker];
          if (stop) {
            stop.openPopup();
          }
        }
      }
    },
  });
}

var lastVehiclesReq, loadVehiclesTimeout, vehiclesHighWater;

function loadVehicles(onMoveEnd) {
  var bounds = map.getBounds();
  if (
    onMoveEnd &&
    vehiclesHighWater &&
    vehiclesHighWater.contains(bounds) &&
    bigVehicleMarkers
  ) {
    // user has simply zoomed in – no need to reload vehicles yet
    return;
  }
  if (lastVehiclesReq) {
    lastVehiclesReq.abort();
  }
  if (loadVehiclesTimeout) {
    clearTimeout(loadVehiclesTimeout);
  }
  var params = window.location.search;
  if (params) {
    params += "&";
  } else {
    params = "?";
  }
  params +=
    "ymax=" +
    round(bounds.getNorth()) +
    "&xmax=" +
    round(bounds.getEast()) +
    "&ymin=" +
    round(bounds.getSouth()) +
    "&xmin=" +
    round(bounds.getWest());
  if (clickedTrip) {
    params += "&trip=" + clickedTrip;
  }
  lastVehiclesReq = reqwest({
    url: "https://bustimes.org/vehicles.json" + params,
    crossOrigin: true,
    success: function (data) {
      if (data) {
        vehiclesHighWater = bounds;
        processVehiclesData(data);
      }
      loadVehiclesTimeout = setTimeout(loadVehicles, 15000);
    },
    error: function () {
      loadVehiclesTimeout = setTimeout(loadVehicles, 15000);
    },
  });
}

function processVehiclesData(data) {
  var newMarkers = {};
  var wasZoomedIn = bigVehicleMarkers;
  bigVehicleMarkers = map.getZoom() > 12 || data.length < 500;
  if (bigVehicleMarkers !== wasZoomedIn) {
    vehiclesGroup.clearLayers();
    bustimes.vehicleMarkers = {};
  }
  for (var i = data.length - 1; i >= 0; i--) {
    var item = data[i];
    newMarkers[item.id] = processVehicle(item);
  }
  // remove old markers
  for (i in bustimes.vehicleMarkers) {
    if (!(i in newMarkers)) {
      vehiclesGroup.removeLayer(bustimes.vehicleMarkers[i]);
    }
  }
  bustimes.vehicleMarkers = newMarkers;
}

function getVehicleMarker(latLng, item, isClickedMarker) {
  if (bigVehicleMarkers) {
    var marker = L.marker(latLng, {
      icon: getBusIcon(item, isClickedMarker),
      zIndexOffset: 1000,
    });
  } else {
    marker = L.circleMarker(latLng, {
      stroke: false,
      fillColor: "#333",
      fillOpacity: 0.6,
      radius: 3,
    });
  }
  marker
    .addTo(vehiclesGroup)
    .bindPopup("", {
      autoPan: false,
    })
    .on("popupopen", handlePopupOpen)
    .on("popupclose", handlePopupClose);
  return marker;
}

// like handleVehicle in 'maps.js' but with support for varying marker size based on zoom level
function processVehicle(item) {
  var isClickedMarker = item.id === bustimes.clickedMarker;
  var latLng = L.latLng(item.coordinates[1], item.coordinates[0]);
  if (item.id in bustimes.vehicleMarkers) {
    var marker = bustimes.vehicleMarkers[item.id]; // existing marker
    if (bigVehicleMarkers) {
      marker.setIcon(getBusIcon(item, isClickedMarker));
    }
    marker.setLatLng(latLng);
  } else {
    marker = getVehicleMarker(latLng, item, isClickedMarker);
  }
  marker.options.item = item;
  if (isClickedMarker) {
    bustimes.vehicleMarkers[item.id] = marker; // make updatePopupContent work
    marker.openPopup(); // just in case
    updatePopupContent();
  }
  return marker;
}

function handlePopupOpen(event) {
  var marker = event.target;
  var item = marker.options.item;

  bustimes.clickedMarker = item.id;
  clickedTrip = item.trip_id;
  updatePopupContent();

  if (bigVehicleMarkers) {
    marker.setIcon(getBusIcon(item, true));
    marker.setZIndexOffset(2000);
  }
}

function handlePopupClose(event) {
  if (map.hasLayer(event.target)) {
    bustimes.clickedMarker = null;
    clickedTrip = null;
    if (bigVehicleMarkers) {
      // make the icon small again
      event.target.setIcon(getBusIcon(event.target.options.item));
      event.target.setZIndexOffset(1000);
    }
  }
}

function round(number) {
  // round to 6 decimal places
  return Math.round(number * 1000000) / 1000000;
}

// update window location hash
function updateLocation() {
  var latLng = map.getCenter(),
    string = map.getZoom() + "/" + round(latLng.lat) + "/" + round(latLng.lng);

  if (window.history.replaceState) {
    try {
      window.history.replaceState(null, null, "#" + string);
    } catch (e) {
      // probably SecurityError (document is not fully active)
    }
  }
  try {
    localStorage.setItem("vehicleMap", string);
  } catch (e) {
    // ok
  }
}

var mapContainer = map.getContainer();

map.on(
  "moveend",
  debounce(function () {
    loadVehicles(true);

    if (map.getZoom() < 13) {
      // zoomed out
      mapContainer.classList.add("zoomed-out");
    } else {
      mapContainer.classList.remove("zoomed-out");
    }

    if (showStops) {
      if (map.getZoom() < 13) {
        // zoomed out
        showStops = false; // indicate that it wasn't an explicit box uncheck
        stopsGroup.remove();
        showStops = true;
      } else {
        stopsGroup.addTo(map);
        loadStops();
      }
    }

    updateLocation();
  }, 500),
);

var parts;
if (window.location.hash) {
  parts = window.location.hash.substring(1).split("/");
} else {
  try {
    if (localStorage.vehicleMap) {
      parts = localStorage.vehicleMap.split("/");
    }
  } catch (e) {
    // ok
  }
}
if (parts) {
  if (parts.length === 1) {
    parts = parts[0].split(",");
  }
  try {
    if (parts.length === 3) {
      map.setView([parts[1], parts[2]], parts[0]);
    } else {
      map.setView([parts[0], parts[1]], 14);
    }
  } catch (e) {
    // oh well
  }
}

if (!map._loaded) {
  map.setView(
    [INITIAL_VIEW_STATE.longitude, INITIAL_VIEW_STATE.latitude],
    INITIAL_VIEW_STATE.zoom + 1,
  );
}

function handleVisibilityChange(event) {
  if (event.target.hidden) {
    if (loadVehiclesTimeout) {
      clearTimeout(loadVehiclesTimeout);
    }
  } else {
    loadVehicles();
  }
}

if (document.addEventListener) {
  document.addEventListener("visibilitychange", handleVisibilityChange);
}
