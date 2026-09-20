(function () {
  "use strict";

  const config = window.NORONHA_MAP || { layers: [] };
  const status = document.getElementById("map-status");
  const selector = document.getElementById("layer-select");
  const githubLink = document.getElementById("github-link");
  const workshopLink = document.getElementById("workshop-link");
  const cloudsToggle = document.getElementById("clouds-toggle");
  const cloudsState = document.getElementById("clouds-state");
  const viewerVersion = document.getElementById("viewer-version");
  const aboutVersion = document.getElementById("about-version");
  const aboutDialog = document.getElementById("about-dialog");
  const aboutOpen = document.getElementById("about-open");
  const aboutClose = document.getElementById("about-close");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
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

  const cloudSystems = [
    {
      src: "./assets/cloud-system-1.webp",
      x: -0.04, y: -0.01, width: 0.72, height: 0.43,
      opacity: 0.34, driftX: 0.035, driftY: 0.012,
      duration: 190000, phase: 0
    },
    {
      src: "./assets/cloud-system-2.webp",
      x: 0.42, y: 0.10, width: 0.54, height: 0.36,
      opacity: 0.27, driftX: -0.026, driftY: 0.017,
      duration: 235000, phase: Math.PI * 0.72
    },
    {
      src: "./assets/cloud-system-3.webp",
      x: 0.12, y: 0.50, width: 0.72, height: 0.32,
      opacity: 0.25, driftX: 0.028, driftY: -0.014,
      duration: 275000, phase: Math.PI * 1.38
    }
  ];

  L.control.zoom({ position: "bottomright" }).addTo(map);
  map.createPane("cloudPane");
  map.getPane("cloudPane").style.zIndex = "350";
  map.getPane("cloudPane").style.pointerEvents = "none";
  githubLink.href = config.githubUrl || githubLink.href;
  workshopLink.href = config.workshopUrl || workshopLink.href;
  const version = config.viewerVersion || "v1.0.0-rc.2";
  viewerVersion.textContent = version;
  aboutVersion.textContent = version;

  if (!Array.isArray(config.layers) || config.layers.length === 0) {
    status.textContent = "Map tiles have not been published yet. Build the local map package before deploying Pages.";
    map.setView([0, 0], 0);
    return;
  }

  let activeLayer;
  let activeTileLayer;
  let cloudsEnabled = config.cloudsEnabled !== false;
  let cloudAnimationFrame;
  const cloudOverlays = cloudSystems.map((system, index) => {
    const overlay = L.imageOverlay(system.src, [[0, 0], [0, 0]], {
      pane: "cloudPane",
      opacity: system.opacity,
      interactive: false,
      className: `weather-cloud weather-cloud-${index + 1}`
    });
    overlay.on("error", () => {
      status.textContent = "An optional cloud system could not be loaded.";
      status.classList.remove("is-hidden");
    });
    return overlay;
  });

  function boundsFor(layer) {
    const southWest = map.unproject([0, layer.height], layer.maxZoom);
    const northEast = map.unproject([layer.width, 0], layer.maxZoom);
    return L.latLngBounds(southWest, northEast);
  }

  function initialBoundsFor(layer) {
    if (!Array.isArray(layer.initialBounds) || layer.initialBounds.length !== 4) return boundsFor(layer);
    const [left, top, right, bottom] = layer.initialBounds;
    return L.latLngBounds(
      map.unproject([left, bottom], layer.maxZoom),
      map.unproject([right, top], layer.maxZoom)
    );
  }

  function cloudBounds(system, offsetX = 0, offsetY = 0) {
    const left = (system.x + offsetX) * activeLayer.width;
    const top = (system.y + offsetY) * activeLayer.height;
    const right = left + system.width * activeLayer.width;
    const bottom = top + system.height * activeLayer.height;
    return L.latLngBounds(
      map.unproject([left, bottom], activeLayer.maxZoom),
      map.unproject([right, top], activeLayer.maxZoom)
    );
  }

  function positionClouds(timestamp) {
    if (!activeLayer) return;
    cloudSystems.forEach((system, index) => {
      const angle = reducedMotion.matches
        ? system.phase
        : ((timestamp % system.duration) / system.duration) * Math.PI * 2 + system.phase;
      const offsetX = reducedMotion.matches ? 0 : Math.sin(angle) * system.driftX;
      const offsetY = reducedMotion.matches ? 0 : Math.cos(angle * 0.72) * system.driftY;
      cloudOverlays[index].setBounds(cloudBounds(system, offsetX, offsetY));
    });
  }

  function animateClouds(timestamp) {
    positionClouds(timestamp);
    if (cloudsEnabled && !reducedMotion.matches) {
      cloudAnimationFrame = window.requestAnimationFrame(animateClouds);
    }
  }

  function stopCloudAnimation() {
    if (cloudAnimationFrame) {
      window.cancelAnimationFrame(cloudAnimationFrame);
      cloudAnimationFrame = undefined;
    }
  }

  function syncClouds() {
    if (!activeLayer) return;
    stopCloudAnimation();
    positionClouds(performance.now());
    cloudOverlays.forEach((overlay) => {
      if (cloudsEnabled && !map.hasLayer(overlay)) overlay.addTo(map);
      if (!cloudsEnabled && map.hasLayer(overlay)) map.removeLayer(overlay);
    });
    if (cloudsEnabled && !reducedMotion.matches) {
      cloudAnimationFrame = window.requestAnimationFrame(animateClouds);
    }
  }

  function showLayer(id) {
    const layer = config.layers.find((candidate) => candidate.id === id) || config.layers[0];
    const previousView = activeLayer ? { center: map.getCenter(), zoom: map.getZoom() } : null;
    if (activeTileLayer) map.removeLayer(activeTileLayer);

    const bounds = boundsFor(layer);
    activeTileLayer = L.tileLayer(`./tiles/${layer.id}/${layer.revision}/{z}/{x}/{y}.${layer.format}`, {
      bounds,
      tileSize: layer.tileSize,
      minZoom: map.getMinZoom(),
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
    syncClouds();
    if (previousView) {
      map.setView(previousView.center, Math.min(previousView.zoom, layer.maxZoom), { animate: false });
    } else {
      map.fitBounds(initialBoundsFor(layer), { padding: [42, 42], animate: false });
      map.setMinZoom(map.getZoom());
    }
  }

  function setClouds(enabled) {
    cloudsEnabled = enabled;
    cloudsToggle.setAttribute("aria-pressed", String(enabled));
    cloudsState.textContent = enabled ? "On" : "Off";
    syncClouds();
  }

  function closeAbout() {
    if (aboutDialog.open) aboutDialog.close();
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
  aboutOpen.addEventListener("click", () => aboutDialog.showModal());
  aboutClose.addEventListener("click", closeAbout);
  aboutDialog.addEventListener("click", (event) => {
    if (event.target === aboutDialog) closeAbout();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAbout();
  });
  reducedMotion.addEventListener("change", syncClouds);

  const preferred = config.defaultLayer || config.layers[0].id;
  selector.value = preferred;
  showLayer(preferred);
  setClouds(cloudsEnabled);

  window.addEventListener("resize", () => {
    if (activeLayer) map.invalidateSize({ animate: false });
  });
}());
