import L from "leaflet";

var tiles =
  "https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png";
var attribution =
  '<a href="https://stadiamaps.com/">© Stadia Maps</a> <a href="https://openmaptiles.org/">© OpenMapTiles</a> <a href="https://www.openstreetmap.org/about/">© OpenStreetMap contributors</a>';

export function getTransform(heading, scale) {
  if (heading === null && !scale) {
    return "";
  }
  var transform = "transform:";
  if (heading !== null) {
    transform += " rotate(" + heading + "deg)";
  }
  if (scale) {
    transform += " scale(1.5)";
  }
  return "-webkit-" + transform + ";" + transform + ";";
}

export function getBusIcon(item, active) {
  var className = "bus";
  if (active) {
    className += " selected";
  }
  var heading = item.heading;
  if (heading !== null) {
    heading = parseInt(heading, 10);
    var arrow =
      '<div class="arrow" style="' +
      getTransform(heading + 90, active) +
      '"></div>';
    if (heading < 180) {
      className += " right";
      heading -= 90;
    } else {
      heading -= 270;
    }
  }
  var style = getTransform(heading, active);

  if (item.vehicle) {
    if (item.vehicle.livery) {
      className += " livery-" + item.vehicle.livery;
    } else if (item.vehicle.css) {
      style += "background:" + item.vehicle.css;
      if (item.vehicle.text_colour) {
        className += " white-text";
      }
    }
  }

  var svg = document.createElement("svg");
  svg.setAttribute("width", 24);
  svg.setAttribute("height", 16);
  svg.className = className;
  svg.style = style;
  if (item.service) {
    var text = document.createElement("text");
    text.setAttribute("x", "50%");
    text.setAttribute("y", "80%");
    text.innerHTML = item.service.line_name;
    svg.appendChild(text);
  }
  var html = svg.outerHTML;

  if (arrow) {
    html += arrow;
  }
  return L.divIcon({
    iconSize: [26, 13],
    html: html,
    popupAnchor: [0, -6],
  });
}

var timestampTimeout;

function getTimeDelta(seconds) {
  var minutes = Math.round(seconds / 60);
  if (minutes === 1) {
    return "1 minute";
  }
  return minutes + " minutes";
}

var popupContent; // cache popup content without ' ago' at the end

function getPopupContent(item) {
  if (item.service) {
    var content = item.service.line_name;
    if (item.destination) {
      content += " to " + item.destination;
    }
    if (item.tfl_code) {
      content =
        '<a href="/vehicles/tfl/' + item.tfl_code + '">' + content + "</a>";
    } else if (item.trip_id) {
      if (item.trip_id !== window.TRIP_ID) {
        content = '<a href="/trips/' + item.trip_id + '">' + content + "</a>";
      }
    } else if (
      item.service.url &&
      item.service.url !== window.location.pathname
    ) {
      content = '<a href="' + item.service.url + '">' + content + "</a>";
    }
  } else {
    content = "";
  }

  if (item.vehicle) {
    if (item.vehicle.url) {
      content +=
        '<div class="vehicle"><a href="' +
        item.vehicle.url +
        '">' +
        item.vehicle.name +
        "</a></div>";

      if (item.vehicle.features) {
        content += '<div class="features">' + item.vehicle.features + "</div>";
      }
    } else if (item.vehicle.name) {
      content += '<div class="operator">' + item.vehicle.name + "</div>";
    }
  }

  if (item.seats) {
    content +=
      '<div class="occupancy"><img src="/static/svg/seat.svg" width="14" height="14" alt="seats"> ' +
      item.seats +
      "</div>";
  }
  if (item.wheelchair) {
    content +=
      '<div class="occupancy"><img src="/static/svg/wheelchair.svg" width="14" height="14" alt="wheelchair space"> ' +
      item.wheelchair +
      "</div>";
  }

  if (typeof item.delay !== "undefined") {
    var delay = item.delay;
    if (-60 < delay && delay < 60) {
      delay = "On time";
    } else {
      if (delay < 0) {
        delay *= -1;
      }
      delay = getTimeDelta(delay);
      if (item.delay < 0) {
        delay += " early";
      } else {
        delay += " late";
      }
    }
    content += "<div>" + delay + "</div>";
  }

  popupContent = content;

  return content;
}

function getTimestamp(datetime) {
  var now = new Date();
  var then = new Date(datetime);
  var ago = Math.round((now.getTime() - then.getTime()) / 1000);

  if (ago >= 1800) {
    return "Updated at " + then.toTimeString().slice(0, 8);
  } else {
    var content =
      '<time datetime="' +
      datetime +
      '" title="' +
      then.toTimeString().slice(0, 8) +
      '">';
    if (ago >= 59) {
      content += getTimeDelta(ago);
      timestampTimeout = setTimeout(updateTimestamp, (61 - (ago % 60)) * 1000);
    } else {
      if (ago === 1) {
        content += "1 second";
      } else {
        content += ago + " seconds";
      }
      timestampTimeout = setTimeout(updateTimestamp, 1000);
    }
    return content + " ago</time>";
  }
}

function updateTimestamp() {
  var marker = window.bustimes.vehicleMarkers[window.bustimes.clickedMarker];
  if (marker) {
    var item = marker.options.item;
    marker.getPopup().setContent(popupContent + getTimestamp(item.datetime));
  }
}

export function updatePopupContent() {
  if (timestampTimeout) {
    clearTimeout(timestampTimeout);
  }
  var marker = window.bustimes.vehicleMarkers[window.bustimes.clickedMarker];
  if (marker) {
    var item = marker.options.item;
    marker
      .getPopup()
      .setContent(getPopupContent(item) + getTimestamp(item.datetime));
  }
}

function handlePopupOpen(event) {
  var marker = event.target;
  var item = marker.options.item;

  window.bustimes.clickedMarker = item.id;
  updatePopupContent();

  marker.setIcon(getBusIcon(item, true));
  marker.setZIndexOffset(2000);
}

function handlePopupClose(event) {
  if (window.bustimes.map.hasLayer(event.target)) {
    window.bustimes.clickedMarker = null;
    // make the icon small again
    event.target.setIcon(getBusIcon(event.target.options.item));
    event.target.setZIndexOffset(1000);
  }
}

function handleVehicle(item) {
  var isClickedMarker = item.id === window.bustimes.clickedMarker,
    icon = getBusIcon(item, isClickedMarker),
    latLng = L.latLng(item.coordinates[1], item.coordinates[0]);

  if (item.id in window.bustimes.vehicleMarkers) {
    // update existing
    var marker = window.bustimes.vehicleMarkers[item.id];
    if (marker.options.item.datetime !== item.datetime) {
      marker.setLatLng(latLng);
      marker.setIcon(icon);
      marker.options.item = item;
      if (isClickedMarker) {
        updatePopupContent();
      }
    }
  } else {
    marker = L.marker(latLng, {
      icon: getBusIcon(item, isClickedMarker),
      zIndexOffset: 1000,
      item: item,
    });
    marker
      .addTo(window.bustimes.map)
      .bindPopup("", { autoPan: false })
      .on("popupopen", handlePopupOpen)
      .on("popupclose", handlePopupClose);
  }
  return marker;
}

export function handleVehicles(items) {
  var newMarkers = {};
  for (var i = items.length - 1; i >= 0; i--) {
    var item = items[i];
    newMarkers[item.id] = handleVehicle(item);
  }
  // remove old markers
  for (i in window.bustimes.vehicleMarkers) {
    if (!(i in newMarkers)) {
      window.bustimes.map.removeLayer(window.bustimes.vehicleMarkers[i]);
    }
  }
  window.bustimes.vehicleMarkers = newMarkers;
}

export function doTileLayer(map) {
  map.attributionControl.setPrefix("");
  L.tileLayer(tiles, {
    attribution: attribution,
  }).addTo(map);
}

window.bustimes = {
  vehicleMarkers: {},
  popupOptions: {},
};
