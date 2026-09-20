(function () {
  "use strict";

  const config = window.NORONHA_MAP || { layers: [] };
  const status = document.getElementById("map-status");
  const selector = document.getElementById("layer-select");
  const githubLink = document.getElementById("github-link");
  const workshopLink = document.getElementById("workshop-link");
  const clouds = document.getElementById("cloud-layer");
  const cloudsToggle = document.getElementById("clouds-toggle");
  const cloudsState = document.getElementById("clouds-state");
  const resetButton = document.getElementById("reset-view");
  const fullscreenButton = document.getElementById("fullscreen-toggle");
  const menuToggle = document.getElementById("menu-toggle");
  const controlsPanel = document.getElementById("controls-panel");
  const aboutDialog = document.getElementById("about-dialog");
  const aboutOpen = document.getElementById("about-open");
  const aboutClose = document.getElementById("about-close");
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
  workshopLink.href = config.workshopUrl || workshopLink.href;

  if (!Array.isArray(config.layers) || config.layers.length === 0) {
    status.textContent = "Map tiles have not been published yet. Build the local map package before deploying Pages.";
    map.setView([0, 0], 0);
    return;
  }

  let activeLayer;
  let activeTileLayer;
  let cloudsEnabled = config.cloudsEnabled !== false;

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
    activeTileLayer = L.tileLayer(`./tiles/${layer.id}/${layer.revision}/{z}/{x}/{y}.${layer.format}`, {
      bounds,
      tileSize: layer.tileSize,
      minZoom: 0,
      maxZoom: layer.maxZoom,
      minNativeZoom: 0,
      maxNativeZoom: layer.maxZoom,
      noWrap: true,
      keepBuffer: 2,
      updateWhenIdle: false
    });
    activeTileLayer.on("loading", () => {
      status.textContent = `Loading ${layer.name}…`;
      status.classList.remove("is-hidden");
    });
    activeTileLayer.on("load", () => status.classList.add("is-hidden"));
    activeTileLayer.on("tileerror", () => {
      status.textContent = `A ${layer.name} tile could not be loaded.`;
      status.classList.remove("is-hidden");
    });
    activeTileLayer.addTo(map);

    activeLayer = layer;
    map.setMaxBounds(bounds.pad(0.08));
    map.setMaxZoom(layer.maxZoom);
    if (previousView) {
      map.setView(previousView.center, Math.min(previousView.zoom, layer.maxZoom), { animate: false });
    } else {
      map.fitBounds(initialBoundsFor(layer), { padding: [42, 42], animate: false });
      map.setMinZoom(map.getZoom());
    }
  }

  function resetView() {
    if (!activeLayer) return;
    map.fitBounds(initialBoundsFor(activeLayer), { padding: [42, 42], animate: false });
  }

  function setClouds(enabled) {
    cloudsEnabled = enabled;
    clouds.hidden = !enabled;
    cloudsToggle.setAttribute("aria-pressed", String(enabled));
    cloudsState.textContent = enabled ? "On" : "Off";
  }

  function closeMenu() {
    controlsPanel.classList.remove("is-open");
    menuToggle.setAttribute("aria-expanded", "false");
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

  cloudsToggle.addEventListener("click", () => setClouds(!cloudsEnabled));
  resetButton.addEventListener("click", () => {
    resetView();
    closeMenu();
  });
  menuToggle.addEventListener("click", () => {
    const open = !controlsPanel.classList.contains("is-open");
    controlsPanel.classList.toggle("is-open", open);
    menuToggle.setAttribute("aria-expanded", String(open));
  });
  aboutOpen.addEventListener("click", () => {
    closeMenu();
    aboutDialog.showModal();
  });
  aboutClose.addEventListener("click", () => aboutDialog.close());
  aboutDialog.addEventListener("click", (event) => {
    if (event.target === aboutDialog) aboutDialog.close();
  });

  if (document.documentElement.requestFullscreen) {
    fullscreenButton.addEventListener("click", async () => {
      closeMenu();
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else {
          await document.documentElement.requestFullscreen();
        }
      } catch {
        status.textContent = "Fullscreen is not available in this browser.";
        status.classList.remove("is-hidden");
      }
    });
    document.addEventListener("fullscreenchange", () => {
      fullscreenButton.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
      map.invalidateSize({ animate: false });
    });
  } else {
    fullscreenButton.hidden = true;
  }

  const preferred = config.defaultLayer || config.layers[0].id;
  selector.value = preferred;
  setClouds(cloudsEnabled);
  showLayer(preferred);

  window.addEventListener("resize", () => {
    if (activeLayer) {
      map.invalidateSize({ animate: false });
    }
  });
}());
