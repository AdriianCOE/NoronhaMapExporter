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
      x: -0.08, y: 0.05, width: 0.84, height: 0.38,
      opacity: 0.80, duration: 214000, animation: "cloud-drift-northwest"
    },
    {
      src: "./assets/cloud-system-2.webp",
      x: -0.06, y: 0.60, width: 0.76, height: 0.36,
      opacity: 0.76, duration: 287000, animation: "cloud-drift-southwest"
    },
    {
      src: "./assets/cloud-system-3.webp",
      x: 0.56, y: 0.01, width: 0.48, height: 0.27,
      opacity: 0.68, duration: 253000, animation: "cloud-drift-northeast"
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
  const CloudFieldLayer = L.Layer.extend({
    initialize(system, index) {
      this.system = system;
      this.index = index;
      this._bounds = L.latLngBounds([[0, 0], [0, 0]]);
    },

    onAdd(targetMap) {
      this._map = targetMap;
      if (!this._container) this._initContainer();
      this.getPane("cloudPane").appendChild(this._container);
      this._reset();
    },

    onRemove() {
      L.DomUtil.remove(this._container);
      this._map = null;
    },

    getEvents() {
      const events = { zoom: this._reset, viewreset: this._reset };
      if (this._map?._zoomAnimated) events.zoomanim = this._animateZoom;
      return events;
    },

    setBounds(bounds) {
      this._bounds = L.latLngBounds(bounds);
      if (this._map) this._reset();
      return this;
    },

    getElement() {
      return this._container;
    },

    _initContainer() {
      const zoomClass = map._zoomAnimated ? "leaflet-zoom-animated" : "leaflet-zoom-hide";
      this._container = L.DomUtil.create("div", `cloud-field ${zoomClass}`);
      this._container.dataset.cloudField = String(this.index + 1);
      this._container.style.setProperty("--cloud-opacity", String(this.system.opacity));
      this._motion = L.DomUtil.create("div", "cloud-field__motion", this._container);
      this._motion.style.animationName = this.system.animation;
      this._motion.style.animationDuration = `${this.system.duration}ms`;
      this._motion.style.animationDelay = `${-Math.round(this.system.duration * (this.index + 1) * 0.19)}ms`;
      this._image = L.DomUtil.create("img", "cloud-field__image", this._motion);
      this._image.alt = "";
      this._image.draggable = false;
      this._image.src = this.system.src;
      this._image.addEventListener("error", () => this.fire("error"));
    },

    _reset() {
      if (!this._map) return;
      const topLeft = this._map.latLngToLayerPoint(this._bounds.getNorthWest());
      const bottomRight = this._map.latLngToLayerPoint(this._bounds.getSouthEast());
      const size = bottomRight.subtract(topLeft);
      L.DomUtil.setPosition(this._container, topLeft);
      this._container.style.width = `${size.x}px`;
      this._container.style.height = `${size.y}px`;
    },

    _animateZoom(event) {
      const scale = this._map.getZoomScale(event.zoom);
      const offset = this._map._latLngBoundsToNewLayerBounds(this._bounds, event.zoom, event.center).min;
      L.DomUtil.setTransform(this._container, offset, scale);
    }
  });

  const cloudLayers = cloudSystems.map((system, index) => {
    const field = new CloudFieldLayer(system, index);
    field.on("error", () => {
      status.textContent = "An optional cloud system could not be loaded.";
      status.classList.remove("is-hidden");
    });
    return field;
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

  function cloudBounds(system) {
    const left = system.x * activeLayer.width;
    const top = system.y * activeLayer.height;
    const right = left + system.width * activeLayer.width;
    const bottom = top + system.height * activeLayer.height;
    return L.latLngBounds(
      map.unproject([left, bottom], activeLayer.maxZoom),
      map.unproject([right, top], activeLayer.maxZoom)
    );
  }

  function syncClouds() {
    if (!activeLayer) return;
    cloudLayers.forEach((field, index) => {
      field.setBounds(cloudBounds(cloudSystems[index]));
      if (!map.hasLayer(field)) field.addTo(map);
    });
    map.getContainer().classList.toggle("clouds-disabled", !cloudsEnabled);
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
    map.getContainer().classList.toggle("clouds-disabled", !enabled);
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
  const preferred = config.defaultLayer || config.layers[0].id;
  selector.value = preferred;
  showLayer(preferred);
  setClouds(cloudsEnabled);

  window.addEventListener("resize", () => {
    if (activeLayer) map.invalidateSize({ animate: false });
  });
}());
