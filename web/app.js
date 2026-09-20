(function () {
  "use strict";

  const config = window.NORONHA_MAP || { layers: [] };
  const status = document.getElementById("map-status");
  const selector = document.getElementById("layer-select");
  const githubLink = document.getElementById("github-link");
  const tileSize = config.layers?.[0]?.tileSize || 256;
  const pixelCrs = L.Util.extend({}, L.CRS.Simple, {
    scale(zoom) {
      return tileSize * Math.pow(2, zoom);
    },
    zoom(scale) {
      return Math.log(scale / tileSize) / Math.LN2;
    }
  });
  const map = L.map("map", {
    crs: pixelCrs,
    attributionControl: false,
    zoomControl: false,
    minZoom: -2,
    maxZoom: 20,
    zoomSnap: 0.25,
    zoomDelta: 0.5,
    preferCanvas: true
  });

  L.control.zoom({ position: "bottomright" }).addTo(map);
  githubLink.href = config.githubUrl || githubLink.href;

  if (!Array.isArray(config.layers) || config.layers.length === 0) {
    status.textContent = "Map tiles have not been published yet. Build the local map package before deploying Pages.";
    map.setView([0, 0], 0);
    return;
  }

  let activeLayer;
  let activeTileLayer;

  function boundsFor(layer) {
    const southWest = map.unproject([0, layer.height], layer.maxZoom);
    const northEast = map.unproject([layer.width, 0], layer.maxZoom);
    return L.latLngBounds(southWest, northEast);
  }

  function initialBoundsFor(layer) {
    if (!Array.isArray(layer.initialBounds) || layer.initialBounds.length !== 4) {
      return boundsFor(layer);
    }
    const [left, top, right, bottom] = layer.initialBounds;
    const southWest = map.unproject([left, bottom], layer.maxZoom);
    const northEast = map.unproject([right, top], layer.maxZoom);
    return L.latLngBounds(southWest, northEast);
  }

  function showLayer(id) {
    const layer = config.layers.find((candidate) => candidate.id === id) || config.layers[0];
    const previousView = activeLayer ? { center: map.getCenter(), zoom: map.getZoom() } : null;
    if (activeTileLayer) {
      map.removeLayer(activeTileLayer);
    }

    const bounds = boundsFor(layer);
    activeTileLayer = L.tileLayer(`./tiles/${layer.id}/{z}/{x}/{y}.${layer.format}`, {
      bounds,
      tileSize: layer.tileSize,
      minZoom: 0,
      maxZoom: layer.maxZoom,
      minNativeZoom: 0,
      maxNativeZoom: layer.maxZoom,
      noWrap: true,
      keepBuffer: 2,
      updateWhenIdle: false
    }).addTo(map);

    activeLayer = layer;
    map.setMaxBounds(bounds.pad(0.08));
    map.setMaxZoom(layer.maxZoom);
    if (previousView) {
      map.setView(previousView.center, Math.min(previousView.zoom, layer.maxZoom), { animate: false });
    } else {
      map.fitBounds(initialBoundsFor(layer), { padding: [42, 42], animate: false });
      map.setMinZoom(map.getZoom());
    }
    status.classList.add("is-hidden");
  }

  for (const layer of config.layers) {
    const option = document.createElement("option");
    option.value = layer.id;
    option.textContent = layer.name;
    selector.append(option);
  }
  selector.firstElementChild.remove();
  selector.disabled = config.layers.length < 2;
  selector.addEventListener("change", () => showLayer(selector.value));

  const preferred = config.defaultLayer || config.layers[0].id;
  selector.value = preferred;
  showLayer(preferred);

  window.addEventListener("resize", () => {
    if (activeLayer) {
      map.invalidateSize({ animate: false });
    }
  });
}());
