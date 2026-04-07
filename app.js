const taiwanBounds = L.latLngBounds(
  L.latLng(21.85, 118.0),
  L.latLng(26.5, 122.2)
);

const stationCountEl = document.getElementById("station-count");
const locationStatusEl = document.getElementById("location-status");
const nearestListEl = document.getElementById("nearest-list");
const nearestCaptionEl = document.getElementById("nearest-caption");
const mapSummaryEl = document.getElementById("map-summary");
const locateButton = document.getElementById("locate-button");
const resetButton = document.getElementById("reset-button");

const map = L.map("map", {
  zoomControl: true,
  minZoom: 7
});

map.fitBounds(taiwanBounds);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

let stationLayer;
let stationFeatures = [];
let userMarker;

function formatDistance(km) {
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;
}

function haversineKm(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const earthKm = 6371;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);

  const sinLat = Math.sin(dLat / 2);
  const sinLon = Math.sin(dLon / 2);
  const h =
    sinLat * sinLat +
    Math.cos(lat1) * Math.cos(lat2) * sinLon * sinLon;

  return 2 * earthKm * Math.asin(Math.sqrt(h));
}

function cleanText(value, fallback) {
  if (typeof value !== "string") {
    return fallback;
  }

  const trimmed = value.trim();
  return trimmed ? trimmed : fallback;
}

function stationTitle(properties, index) {
  return cleanText(
    properties["name:zh"] ||
      properties.name ||
      properties["name:en"] ||
      properties.branch,
    `Charging Station ${index + 1}`
  );
}

function stationCity(properties) {
  return cleanText(
    properties["addr:city"] ||
      properties["addr:district"] ||
      properties["addr:province"] ||
      properties.operator,
    "Taiwan"
  );
}

function stationPopup(feature, index) {
  const props = feature.properties || {};
  const title = stationTitle(props, index);
  const operator = cleanText(props.operator || props.brand || props.network, "Unknown operator");
  const city = stationCity(props);
  const openingHours = cleanText(props.opening_hours, "Hours not listed");
  const website = cleanText(props.website, "");

  const websiteRow = website
    ? `<p><strong>Website:</strong> <a href="${website}" target="_blank" rel="noreferrer">Open link</a></p>`
    : "";

  return `
    <div class="popup">
      <h3>${title}</h3>
      <p><strong>Area:</strong> ${city}</p>
      <p><strong>Operator:</strong> ${operator}</p>
      <p><strong>Hours:</strong> ${openingHours}</p>
      ${websiteRow}
    </div>
  `;
}

function renderNearestStations(userLatLng) {
  const nearest = stationFeatures
    .map((feature, index) => {
      const [lng, lat] = feature.geometry.coordinates;
      return {
        feature,
        index,
        distanceKm: haversineKm(userLatLng, { lat, lng })
      };
    })
    .sort((a, b) => a.distanceKm - b.distanceKm)
    .slice(0, 6);

  if (!nearest.length) {
    nearestListEl.innerHTML = '<p class="empty-state">No nearby stations were found in the dataset.</p>';
    nearestCaptionEl.textContent = "Dataset is empty.";
    return;
  }

  nearestCaptionEl.textContent = "Sorted by straight-line distance from your current position.";
  nearestListEl.innerHTML = nearest
    .map(({ feature, index, distanceKm }) => {
      const props = feature.properties || {};
      const title = stationTitle(props, index);
      const area = stationCity(props);
      const operator = cleanText(props.operator || props.brand || props.network, "Unknown operator");

      return `
        <article class="station-item" data-lat="${feature.geometry.coordinates[1]}" data-lng="${feature.geometry.coordinates[0]}">
          <h3>${title}</h3>
          <p>${area}</p>
          <p>${operator}</p>
          <p><strong>${formatDistance(distanceKm)}</strong> away</p>
        </article>
      `;
    })
    .join("");

  nearestListEl.querySelectorAll(".station-item").forEach((item) => {
    item.addEventListener("click", () => {
      const lat = Number(item.dataset.lat);
      const lng = Number(item.dataset.lng);
      map.flyTo([lat, lng], 15, { duration: 0.8 });
    });
  });
}

function showUserLocation(lat, lng) {
  const userLatLng = { lat, lng };

  if (userMarker) {
    userMarker.setLatLng([lat, lng]);
  } else {
    const userIcon = L.divIcon({
      className: "",
      html: '<div class="user-dot"></div>',
      iconSize: [16, 16],
      iconAnchor: [8, 8]
    });

    userMarker = L.marker([lat, lng], { icon: userIcon })
      .addTo(map)
      .bindPopup("You are here");
  }

  locationStatusEl.textContent = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  map.flyTo([lat, lng], 13, { duration: 0.8 });
  renderNearestStations(userLatLng);
}

function requestLocation() {
  if (!navigator.geolocation) {
    locationStatusEl.textContent = "Geolocation is not supported in this browser.";
    return;
  }

  locationStatusEl.textContent = "Locating you...";

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const { latitude, longitude } = position.coords;
      showUserLocation(latitude, longitude);
    },
    (error) => {
      const message =
        error.code === error.PERMISSION_DENIED
          ? "Location permission was denied."
          : "Could not retrieve your location.";
      locationStatusEl.textContent = message;
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 120000
    }
  );
}

function createStationLayer(features) {
  return L.geoJSON(features, {
    pointToLayer: (_, latlng) =>
      L.circleMarker(latlng, {
        radius: 5,
        color: "#0b5d4e",
        weight: 1,
        fillColor: "#10b981",
        fillOpacity: 0.86
      }),
    onEachFeature: (feature, layer) => {
      const index = stationFeatures.indexOf(feature);
      layer.bindPopup(stationPopup(feature, index));
    }
  });
}

async function loadStations() {
  try {
    const response = await fetch("data/chargers.geojson");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const geojson = await response.json();
    stationFeatures = (geojson.features || []).filter((feature) => {
      const coords = feature?.geometry?.coordinates;
      return Array.isArray(coords) && coords.length === 2;
    });

    stationLayer = createStationLayer(stationFeatures).addTo(map);
    stationCountEl.textContent = String(stationFeatures.length);
    mapSummaryEl.textContent = `${stationFeatures.length} charging stations mapped`;

    const bounds = stationLayer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.08));
    }
  } catch (error) {
    stationCountEl.textContent = "0";
    mapSummaryEl.textContent = "Failed to load station dataset";
    nearestListEl.innerHTML = '<p class="empty-state">The charger dataset could not be loaded.</p>';
    locationStatusEl.textContent = "Map loaded, but station data failed.";
    console.error(error);
  }
}

locateButton.addEventListener("click", requestLocation);
resetButton.addEventListener("click", () => {
  if (stationLayer && stationLayer.getBounds().isValid()) {
    map.fitBounds(stationLayer.getBounds().pad(0.08));
  } else {
    map.fitBounds(taiwanBounds);
  }
});

loadStations().then(() => {
  requestLocation();
});
