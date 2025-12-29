// Alignstar Demo - Using Leaflet.js for proper map rendering
class AlignstarDemo {
  constructor() {
    // Initialize map centered on continental US
    this.map = L.map("map", {
      zoomControl: false, // Disable default zoom control
    }).setView([39.8, -98.5], 5);

    // Add zoom control to top-right
    L.control
      .zoom({
        position: "topright",
      })
      .addTo(this.map);

    // State
    this.territories = L.featureGroup();
    this.selectedTerritories = new Set();
    this.currentTool = "pan";
    this.activeLayer = "zip_codes"; // Track which layer is active for selection

    // Layer view settings per hierarchy level
    this.layerViewSettings = {
      zipCodes: {
        visible: true,
        fill: true,
        outline: true,
        labels: true,
        dataField: "none",
      },
      territories: {
        visible: true,
        fill: true,
        outline: true,
        labels: true,
        dataField: "none",
      },
      regions: {
        visible: true,
        fill: true,
        outline: true,
        labels: true,
        dataField: "none",
      },
      areas: {
        visible: true,
        fill: true,
        outline: true,
        labels: true,
        dataField: "none",
      },
    };

    // Overlay layers state
    this.overlays = {
      traffic: false,
      transit: false,
      bicycling: false,
      demographics: false,
      weather: false,
    };

    // Overlay layer groups (placeholders for demo)
    this.overlayLayers = {};

    // Mock search data for demo
    this.searchData = [
      {
        id: "10001",
        name: "New York, NY 10001",
        type: "zip_codes",
        layer: "Zip Codes",
        properties: { population: 21102, households: 8942 },
      },
      {
        id: "10002",
        name: "New York, NY 10002",
        type: "zip_codes",
        layer: "Zip Codes",
        properties: { population: 81410, households: 34567 },
      },
      {
        id: "90210",
        name: "Beverly Hills, CA 90210",
        type: "zip_codes",
        layer: "Zip Codes",
        properties: { population: 21733, households: 9876 },
      },
      {
        id: "t-northeast",
        name: "Northeast Territory",
        type: "territories",
        layer: "Territories",
        properties: { zip_count: 234, total_population: 1200000 },
      },
      {
        id: "t-southeast",
        name: "Southeast Territory",
        type: "territories",
        layer: "Territories",
        properties: { zip_count: 189, total_population: 980000 },
      },
      {
        id: "t-midwest",
        name: "Midwest Territory",
        type: "territories",
        layer: "Territories",
        properties: { zip_count: 312, total_population: 1450000 },
      },
      {
        id: "t-west",
        name: "Western Territory",
        type: "territories",
        layer: "Territories",
        properties: { zip_count: 278, total_population: 1320000 },
      },
      {
        id: "r-atlantic",
        name: "Atlantic Region",
        type: "regions",
        layer: "Regions",
        properties: { territory_count: 5, total_population: 3200000 },
      },
      {
        id: "r-pacific",
        name: "Pacific Region",
        type: "regions",
        layer: "Regions",
        properties: { territory_count: 4, total_population: 2800000 },
      },
      {
        id: "r-central",
        name: "Central Region",
        type: "regions",
        layer: "Regions",
        properties: { territory_count: 6, total_population: 2100000 },
      },
      {
        id: "a-north",
        name: "North Area",
        type: "areas",
        layer: "Areas",
        properties: { region_count: 3, total_population: 5600000 },
      },
      {
        id: "a-south",
        name: "South Area",
        type: "areas",
        layer: "Areas",
        properties: { region_count: 2, total_population: 4200000 },
      },
    ];

    // Available data fields from map configuration (would come from create wizard)
    this.availableDataFields = {
      workload_index: { label: "Workload Index", aggregations: ["sum"] },
      population: { label: "Population", aggregations: ["sum", "avg"] },
      households: { label: "Households", aggregations: ["sum"] },
      avg_income: { label: "Avg Income", aggregations: ["avg"] },
    };

    // Base layers
    this.baseLayers = {
      osm: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "© OpenStreetMap contributors",
      }),
      satellite: L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
          attribution: "© Esri",
        }
      ),
      terrain: L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
        {
          attribution: "© Esri",
        }
      ),
      dark: L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
          attribution: "© OpenStreetMap © CARTO",
        }
      ),
    };

    this.currentBaseLayer = this.baseLayers.osm;
    this.currentBaseLayer.addTo(this.map);

    // Add territory layer
    this.territories.addTo(this.map);

    // Lasso drawing
    this.lassoPoints = [];
    this.lassoLayer = null;
    this.isDrawingLasso = false;

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.loadMapConfiguration();
    this.updateStatus("Ready - Load a GeoJSON file to get started");
  }

  loadMapConfiguration() {
    const params = new URLSearchParams(window.location.search);
    const forceDemo =
      params.get("demo") === "1" || params.get("demo") === "true";
    const reset = params.get("reset") === "1" || params.get("reset") === "true";

    if (reset) {
      try {
        localStorage.removeItem("alignstar_map");
      } catch {}
    }

    // Check if there's a saved map configuration from the create wizard
    const savedMap = localStorage.getItem("alignstar_map");
    if (savedMap && !forceDemo) {
      try {
        const mapData = JSON.parse(savedMap);

        // Load data field configurations
        if (mapData.dataFieldConfigs) {
          this.updateDataFieldSelectors(mapData.dataFieldConfigs);
        }

        // Load the actual data
        if (mapData.data) {
          this.loadGeoJSONData(mapData.data);
        }
      } catch (error) {
        console.error("Error loading map configuration:", error);
      }
    } else {
      // No saved map; generate demo data covering continental US
      const demo = this.generateDemoDemoGeoJSON();
      this.updateDataFieldSelectors(demo.dataFieldConfigs);
      this.loadGeoJSONData(demo.geojson);
      this.updateStatus(
        "Loaded demo map (large zip regions). Add ?demo=1 to URL to force demo, ?reset=1 to clear saved map."
      );
    }
  }

  // Generate demo rectangles across continental US with hierarchy properties
  generateDemoDemoGeoJSON() {
    const usBounds = { south: 24.5, west: -124.8, north: 49.4, east: -66.9 };
    // Use fewer, much larger cells so "zip codes" look like states-scale areas
    const cols = 5; // wide grid
    const rows = 3; // tall grid
    const zipCount = cols * rows; // 15 large zip-like regions
    const dLat = (usBounds.north - usBounds.south) / rows;
    const dLon = (usBounds.east - usBounds.west) / cols;

    const features = [];
    let zipIndex = 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (zipIndex >= zipCount) break;
        const minLat = usBounds.south + r * dLat;
        const minLon = usBounds.west + c * dLon;
        const maxLat = minLat + dLat * 0.95;
        const maxLon = minLon + dLon * 0.95;

        const zipId = String(90000 + zipIndex); // distinguish demo IDs
        const territoryId = `T${Math.floor(zipIndex / 2) + 1}`; // 1-2 zips per territory
        const regionId = `R${Math.floor(Math.floor(zipIndex / 2) / 5) + 1}`; // ~5 territories per region
        const areaId = `A${
          Math.floor(Math.floor(Math.floor(zipIndex / 2) / 5) / 2) + 1
        }`; // ~2 regions per area

        const coords = [
          [minLon, minLat],
          [maxLon, minLat],
          [maxLon, maxLat],
          [minLon, maxLat],
          [minLon, minLat],
        ];

        features.push({
          type: "Feature",
          geometry: { type: "Polygon", coordinates: [coords] },
          properties: {
            zip_id: zipId,
            name: `Demo Zip ${zipId}`,
            territory_id: territoryId,
            territory_name: `Territory ${territoryId}`,
            region_id: regionId,
            region_name: `Region ${regionId}`,
            area_id: areaId,
            area_name: `Area ${areaId}`,
            population: 20000 + Math.floor(Math.random() * 80000),
            households: 8000 + Math.floor(Math.random() * 20000),
            workload_index: Math.round(Math.random() * 100),
          },
        });
        zipIndex++;
      }
    }

    const territories = new Set(features.map((f) => f.properties.territory_id));
    const regions = new Set(features.map((f) => f.properties.region_id));
    const areas = new Set(features.map((f) => f.properties.area_id));

    const geojson = {
      type: "FeatureCollection",
      features,
      metadata: {
        totalTerritories: territories.size,
        totalRegions: regions.size,
        totalAreas: areas.size,
      },
    };

    // Provide minimal data field config to populate selectors
    const dataFieldConfigs = {
      population: {
        displayName: "Population",
        type: "number",
        aggregations: ["sum"],
      },
      households: {
        displayName: "Households",
        type: "number",
        aggregations: ["sum"],
      },
      workload_index: {
        displayName: "Workload Index",
        type: "number",
        aggregations: ["avg"],
      },
    };

    // Also set expected layer configs so naming tooltips work
    return { geojson, dataFieldConfigs };
  }

  updateDataFieldSelectors(dataFieldConfigs) {
    // Update all data field select dropdowns with configured fields
    document.querySelectorAll(".data-field-select").forEach((select) => {
      // Clear existing options except "None"
      select.innerHTML = '<option value="none">None</option>';

      // Add options for each configured field with its aggregations
      Object.keys(dataFieldConfigs).forEach((fieldName) => {
        const config = dataFieldConfigs[fieldName];

        if (
          config.type === "number" &&
          config.aggregations &&
          config.aggregations.length > 0
        ) {
          // Add an option for each aggregation method
          config.aggregations.forEach((agg) => {
            const optionValue = `${fieldName}_${agg}`;
            const optionLabel = `${config.displayName || fieldName} (${
              agg.charAt(0).toUpperCase() + agg.slice(1)
            })`;
            const option = document.createElement("option");
            option.value = optionValue;
            option.textContent = optionLabel;
            select.appendChild(option);
          });
        }
      });
    });
  }

  loadGeoJSONData(geojsonData) {
    // Load GeoJSON data directly from saved configuration
    this.territories.clearLayers();
    this.selectedTerritories.clear();

    const geoJsonLayer = L.geoJSON(geojsonData, {
      style: (feature) => this.getFeatureStyle(feature, false),
      onEachFeature: (feature, layer) => {
        layer.feature = feature;
        layer.on("click", (e) => {
          L.DomEvent.stopPropagation(e);
          this.toggleTerritorySelection(layer);
        });

        if (feature.properties && feature.properties.name) {
          layer.bindTooltip(feature.properties.name, {
            permanent: false,
            direction: "center",
            className: "territory-label",
          });
        }
      },
    });

    geoJsonLayer.addTo(this.territories);
    this.map.fitBounds(this.territories.getBounds());
    this.updateStatus(
      `Loaded ${Object.keys(this.territories._layers).length} features`
    );
  }

  setupEventListeners() {
    // Project selector dropdown
    const projectSelector = document.getElementById("projectSelector");
    const projectDropdown = document.getElementById("projectDropdown");

    if (projectSelector && projectDropdown) {
      projectSelector.addEventListener("click", (e) => {
        e.stopPropagation();
        const isVisible = projectDropdown.style.display === "block";
        projectDropdown.style.display = isVisible ? "none" : "block";
        projectSelector.classList.toggle("active", !isVisible);
      });

      // Handle project selection
      projectDropdown.querySelectorAll(".dropdown-item").forEach((item) => {
        item.addEventListener("click", (e) => {
          e.stopPropagation();
          const projectId = item.dataset.project;
          this.switchProject(projectId, item);
          projectDropdown.style.display = "none";
          projectSelector.classList.remove("active");
        });
      });

      // Handle settings action
      document
        .getElementById("mapSettingsAction")
        ?.addEventListener("click", (e) => {
          e.stopPropagation();
          this.updateStatus("Opening map settings...");
          projectDropdown.style.display = "none";
          projectSelector.classList.remove("active");
          // TODO: Navigate to settings page
        });

      // Handle new map action
      document
        .getElementById("newMapAction")
        ?.addEventListener("click", (e) => {
          e.stopPropagation();
          window.location.href = "create.html";
        });

      // Close dropdown when clicking outside
      document.addEventListener("click", (e) => {
        if (
          !projectSelector.contains(e.target) &&
          !projectDropdown.contains(e.target)
        ) {
          projectDropdown.style.display = "none";
          projectSelector.classList.remove("active");
        }
      });
    }

    // Search functionality
    const searchInput = document.getElementById("searchInput");
    const searchResults = document.getElementById("searchResults");

    if (searchInput && searchResults) {
      searchInput.addEventListener("input", (e) => {
        this.handleSearch(e.target.value);
      });

      searchInput.addEventListener("focus", () => {
        if (searchInput.value.trim()) {
          searchResults.style.display = "block";
        }
      });

      // Close search results when clicking outside
      document.addEventListener("click", (e) => {
        if (
          !searchInput.contains(e.target) &&
          !searchResults.contains(e.target)
        ) {
          searchResults.style.display = "none";
        }
      });
    }

    // Active layer selection (dropdown)
    document
      .getElementById("activeLayerSelect")
      ?.addEventListener("change", (e) => {
        this.activeLayer = e.target.value;
        this.updateStatus(
          `Active layer: ${this.getLayerDisplayName(e.target.value)}`
        );
        // Clear selection when changing layers
        this.clearSelection();
      });

    // Action buttons
    document.getElementById("assignBtn")?.addEventListener("click", () => {
      if (this.selectedTerritories.size > 0) {
        this.performAction("assign");
      }
    });

    document.getElementById("moveBtn")?.addEventListener("click", () => {
      if (this.selectedTerritories.size > 0) {
        this.performAction("move");
      }
    });

    document.getElementById("splitBtn")?.addEventListener("click", () => {
      if (this.selectedTerritories.size > 0) {
        this.performAction("split");
      }
    });

    document.getElementById("mergeBtn")?.addEventListener("click", () => {
      if (this.selectedTerritories.size > 0) {
        this.performAction("merge");
      }
    });

    document.getElementById("deleteBtn")?.addEventListener("click", () => {
      if (this.selectedTerritories.size > 0) {
        this.performAction("delete");
      }
    });

    // Tools
    document.getElementById("panBtn").addEventListener("click", () => {
      this.setTool("pan");
    });

    document.getElementById("lassoBtn").addEventListener("click", () => {
      this.setTool("lasso");
    });

    // Base map selection (dropdown)
    document
      .getElementById("baseMapSelect")
      ?.addEventListener("change", (e) => {
        this.changeBaseMap(e.target.value);
      });

    // Overlay toggles
    ["traffic", "transit", "bicycling", "demographics", "weather"].forEach(
      (overlayName) => {
        const checkbox = document.getElementById(
          `overlay${overlayName.charAt(0).toUpperCase() + overlayName.slice(1)}`
        );
        if (checkbox) {
          checkbox.addEventListener("change", (e) => {
            this.toggleOverlay(overlayName, e.target.checked);
          });
        }
      }
    );

    // Layer expand/collapse buttons
    document.querySelectorAll(".expand-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const layer = btn.dataset.layer;
        const options = document.getElementById(`${layer}Options`);
        const isExpanded = options.classList.contains("expanded");

        if (isExpanded) {
          options.classList.remove("expanded");
          btn.classList.remove("expanded");
        } else {
          options.classList.add("expanded");
          btn.classList.add("expanded");
        }
      });
    });

    // Layer visibility toggles
    ["zipCodes", "territories", "regions", "areas"].forEach((layer) => {
      const checkbox = document.getElementById(`${layer}Visible`);
      if (checkbox) {
        checkbox.addEventListener("change", (e) => {
          this.layerViewSettings[layer].visible = e.target.checked;
          this.updateTerritoryDisplay();
        });
      }
    });

    // Layer option checkboxes (fill, outline, labels)
    document.querySelectorAll(".layer-option-checkbox").forEach((checkbox) => {
      checkbox.addEventListener("change", (e) => {
        const layer = e.target.dataset.layer;
        const option = e.target.dataset.option;
        this.layerViewSettings[layer][option] = e.target.checked;
        this.updateTerritoryDisplay();
      });
    });

    // Data field selectors
    document.querySelectorAll(".data-field-select").forEach((select) => {
      select.addEventListener("change", (e) => {
        const layer = e.target.dataset.layer;
        this.layerViewSettings[layer].dataField = e.target.value;
        this.updateTerritoryDisplay();
      });
    });

    // Map events for lasso
    this.map.on("mousedown", (e) => this.handleMapMouseDown(e));
    this.map.on("mousemove", (e) => this.handleMapMouseMove(e));
    this.map.on("mouseup", (e) => this.handleMapMouseUp(e));
  }

  setTool(tool) {
    this.currentTool = tool;

    // Update button states
    document
      .getElementById("panBtn")
      .classList.toggle("active", tool === "pan");
    document
      .getElementById("lassoBtn")
      .classList.toggle("active", tool === "lasso");

    // Enable/disable map dragging
    if (tool === "pan") {
      this.map.dragging.enable();
      this.map.getContainer().style.cursor = "";
    } else {
      this.map.dragging.disable();
      this.map.getContainer().style.cursor = "crosshair";
    }

    this.updateStatus(
      `Tool: ${tool === "pan" ? "Pan/Zoom" : "Lasso Selection"}`
    );
  }

  changeBaseMap(baseMapType) {
    // Remove current base layer
    if (this.currentBaseLayer) {
      this.map.removeLayer(this.currentBaseLayer);
    }

    // Add new base layer
    if (baseMapType !== "none") {
      this.currentBaseLayer = this.baseLayers[baseMapType];
      this.currentBaseLayer.addTo(this.map);
    } else {
      this.currentBaseLayer = null;
    }

    this.updateStatus(
      `Base map: ${baseMapType === "none" ? "None" : baseMapType}`
    );
  }

  toggleOverlay(overlayName, enabled) {
    this.overlays[overlayName] = enabled;

    if (enabled) {
      // Create overlay layer if it doesn't exist
      if (!this.overlayLayers[overlayName]) {
        this.overlayLayers[overlayName] = this.createOverlayLayer(overlayName);
      }

      // Add to map
      if (this.overlayLayers[overlayName]) {
        this.overlayLayers[overlayName].addTo(this.map);
      }

      this.updateStatus(`${overlayName} overlay enabled`);
    } else {
      // Remove from map
      if (this.overlayLayers[overlayName]) {
        this.map.removeLayer(this.overlayLayers[overlayName]);
      }

      this.updateStatus(`${overlayName} overlay disabled`);
    }
  }

  createOverlayLayer(overlayName) {
    // Create placeholder overlay layers for demo
    // In a real app, these would be actual data layers

    switch (overlayName) {
      case "traffic":
        // Example: Create a semi-transparent red line layer for traffic
        return L.layerGroup();

      case "transit":
        // Example: Transit lines could be polylines
        return L.layerGroup();

      case "bicycling":
        // Example: Bike paths
        return L.layerGroup();

      case "demographics":
        // Example: Heat map or choropleth
        return L.layerGroup();

      case "weather":
        // Example: Weather overlay
        return L.layerGroup();

      default:
        return null;
    }
  }

  handleSearch(query) {
    const searchResults = document.getElementById("searchResults");

    if (!query.trim()) {
      searchResults.style.display = "none";
      return;
    }

    // Filter search data
    const results = this.searchData
      .filter(
        (item) =>
          item.name.toLowerCase().includes(query.toLowerCase()) ||
          item.id.toLowerCase().includes(query.toLowerCase())
      )
      .slice(0, 8); // Limit to 8 results

    if (results.length === 0) {
      searchResults.innerHTML =
        '<div class="search-empty">No results found</div>';
      searchResults.style.display = "block";
      return;
    }

    // Group results by layer
    const grouped = {};
    results.forEach((result) => {
      if (!grouped[result.layer]) {
        grouped[result.layer] = [];
      }
      grouped[result.layer].push(result);
    });

    // Build HTML
    let html = "";
    Object.keys(grouped).forEach((layer) => {
      html += `<div class="search-group">
        <div class="search-group-label">${layer}</div>`;

      grouped[layer].forEach((item) => {
        const propText = this.getSearchResultProperties(item);
        html += `
          <div class="search-result-item" data-id="${item.id}" data-type="${
          item.type
        }">
            <div class="search-result-name">${this.highlightMatch(
              item.name,
              query
            )}</div>
            <div class="search-result-meta">${propText}</div>
          </div>`;
      });

      html += "</div>";
    });

    searchResults.innerHTML = html;
    searchResults.style.display = "block";

    // Add click handlers to results
    searchResults.querySelectorAll(".search-result-item").forEach((item) => {
      item.addEventListener("click", () => {
        this.selectSearchResult(item.dataset.id, item.dataset.type);
        searchResults.style.display = "none";
        document.getElementById("searchInput").value = "";
      });
    });
  }

  getSearchResultProperties(item) {
    if (item.type === "zip_codes") {
      return `Pop: ${item.properties.population.toLocaleString()} • HH: ${item.properties.households.toLocaleString()}`;
    } else if (item.type === "territories") {
      return `${
        item.properties.zip_count
      } zip codes • Pop: ${item.properties.total_population.toLocaleString()}`;
    } else if (item.type === "regions") {
      return `${
        item.properties.territory_count
      } territories • Pop: ${item.properties.total_population.toLocaleString()}`;
    } else if (item.type === "areas") {
      return `${
        item.properties.region_count
      } regions • Pop: ${item.properties.total_population.toLocaleString()}`;
    }
    return "";
  }

  highlightMatch(text, query) {
    const regex = new RegExp(`(${query})`, "gi");
    return text.replace(regex, '<span class="search-highlight">$1</span>');
  }

  selectSearchResult(id, type) {
    this.updateStatus(`Selected: ${id} (${type})`);
    // In a real implementation, this would zoom to the feature and select it
    console.log("Selected search result:", id, type);
  }

  switchProject(projectId, itemElement) {
    // Remove active class from all items
    document.querySelectorAll(".dropdown-item").forEach((item) => {
      item.classList.remove("active");
    });

    // Add active class to selected item
    itemElement.classList.add("active");

    // Update the project selector display
    const projectName = itemElement.querySelector(
      ".dropdown-item-name"
    ).textContent;
    const projectMeta = itemElement.querySelector(
      ".dropdown-item-meta"
    ).textContent;

    document.querySelector(".project-name").textContent = projectName;
    document.querySelector(".project-meta").textContent = projectMeta;

    this.updateStatus(`Switched to: ${projectName}`);
    console.log("Switched to project:", projectId);
  }

  async loadGeoJSON(file) {
    try {
      const text = await file.text();
      const geojson = JSON.parse(text);

      // Clear existing territories
      this.territories.clearLayers();
      this.selectedTerritories.clear();

      // Add GeoJSON to map
      const geoJsonLayer = L.geoJSON(geojson, {
        style: (feature) => this.getFeatureStyle(feature, false),
        onEachFeature: (feature, layer) => {
          // Store feature reference
          layer.feature = feature;

          // Add click handler
          layer.on("click", (e) => {
            L.DomEvent.stopPropagation(e);
            this.toggleTerritorySelection(layer);
          });

          // Add tooltip if labels enabled
          if (feature.properties && feature.properties.name) {
            layer.bindTooltip(feature.properties.name, {
              permanent: this.layers.labels,
              direction: "center",
              className: "territory-label",
            });
          }
        },
      });

      geoJsonLayer.addTo(this.territories);

      // Fit map to loaded data
      this.map.fitBounds(this.territories.getBounds());

      this.updateStatus(
        `Loaded ${Object.keys(this.territories._layers).length} territories`
      );
    } catch (error) {
      console.error("Error loading GeoJSON:", error);
      this.updateStatus("Error loading file");
    }
  }

  getFeatureStyle(feature, isSelected) {
    // Determine which layer this feature belongs to based on active layer
    // For demo, we'll use a simple approach - in real app, feature would have layer type
    const layerKey = "territories"; // This would be determined from feature properties
    const settings = this.layerViewSettings[layerKey];

    if (!settings || !settings.visible) {
      return { fillOpacity: 0, opacity: 0 };
    }

    const baseStyle = {
      fillColor: this.getFeatureColor(feature, settings.dataField),
      fillOpacity: settings.fill ? (isSelected ? 0.7 : 0.3) : 0,
      color: settings.outline ? (isSelected ? "#fff" : "#666") : "transparent",
      weight: isSelected ? 3 : 1,
    };
    return baseStyle;
  }

  getFeatureColor(feature, dataField) {
    // If a data field is selected, color by that field's value
    if (dataField && dataField !== "none") {
      // Extract base field name (remove aggregation suffix like _sum, _avg)
      const baseField = dataField.replace(/_sum|_avg|_min|_max|_count/g, "");
      const value = feature.properties?.[baseField];

      if (value !== undefined && value !== null) {
        // Create color scale based on value
        // This is simplified - real implementation would use proper color scales
        const normalized = Math.min(Math.max(value / 100, 0), 1); // Normalize to 0-1
        const hue = 220 - normalized * 60; // Blue (220) to cyan (160)
        return `hsl(${hue}, 70%, ${50 + normalized * 20}%)`;
      }
    }

    // Default: Generate color based on feature properties or index
    const id = feature.properties?.id || feature.id || 0;
    const hue = (id * 137.5) % 360;
    return `hsl(${hue}, 60%, 55%)`;
  }

  toggleTerritorySelection(layer) {
    const featureId = layer.feature.properties?.id || layer._leaflet_id;

    if (this.selectedTerritories.has(featureId)) {
      this.selectedTerritories.delete(featureId);
      layer.setStyle(this.getFeatureStyle(layer.feature, false));
    } else {
      this.selectedTerritories.add(featureId);
      layer.setStyle(this.getFeatureStyle(layer.feature, true));
    }

    this.updateSelectionInfo();
  }

  updateTerritoryDisplay() {
    this.territories.eachLayer((layer) => {
      const featureId = layer.feature?.properties?.id || layer._leaflet_id;
      const isSelected = this.selectedTerritories.has(featureId);
      layer.setStyle(this.getFeatureStyle(layer.feature, isSelected));

      // Determine layer type for this feature (simplified for demo)
      const layerKey = "territories";
      const settings = this.layerViewSettings[layerKey];

      // Update tooltip visibility
      if (layer.getTooltip()) {
        if (settings && settings.visible && settings.labels) {
          layer.getTooltip().setOpacity(1);
        } else {
          layer.getTooltip().setOpacity(0);
        }
      }
    });
  }

  handleMapMouseDown(e) {
    if (this.currentTool === "lasso") {
      this.isDrawingLasso = true;
      this.lassoPoints = [e.latlng];

      // Create lasso polyline
      if (this.lassoLayer) {
        this.map.removeLayer(this.lassoLayer);
      }
      this.lassoLayer = L.polyline([e.latlng], {
        color: "#4a9eff",
        weight: 2,
        dashArray: "5, 5",
      }).addTo(this.map);

      L.DomEvent.stopPropagation(e);
    }
  }

  handleMapMouseMove(e) {
    if (this.currentTool === "lasso" && this.isDrawingLasso) {
      this.lassoPoints.push(e.latlng);
      this.lassoLayer.setLatLngs(this.lassoPoints);
    }
  }

  handleMapMouseUp(e) {
    if (this.currentTool === "lasso" && this.isDrawingLasso) {
      this.isDrawingLasso = false;

      // Close the lasso
      this.lassoPoints.push(this.lassoPoints[0]);
      this.lassoLayer.setLatLngs(this.lassoPoints);

      // Select territories within lasso
      this.selectTerritoriesInLasso();

      // Remove lasso drawing
      setTimeout(() => {
        if (this.lassoLayer) {
          this.map.removeLayer(this.lassoLayer);
          this.lassoLayer = null;
        }
      }, 500);
    }
  }

  selectTerritoriesInLasso() {
    if (this.lassoPoints.length < 3) return;

    // Create polygon from lasso points
    const lassoPolygon = L.polygon(this.lassoPoints);
    const lassoBounds = lassoPolygon.getBounds();

    // Clear previous selection
    this.selectedTerritories.clear();

    // Check each territory
    this.territories.eachLayer((layer) => {
      if (layer.getBounds) {
        const layerBounds = layer.getBounds();
        const layerCenter = layerBounds.getCenter();

        // Simple point-in-polygon check using the center
        if (lassoBounds.contains(layerCenter)) {
          const featureId = layer.feature?.properties?.id || layer._leaflet_id;
          this.selectedTerritories.add(featureId);
          layer.setStyle(this.getFeatureStyle(layer.feature, true));
        } else {
          layer.setStyle(this.getFeatureStyle(layer.feature, false));
        }
      }
    });

    this.updateSelectionInfo();
  }

  updateSelectionInfo() {
    const countNumber = document.querySelector(".count-number");
    const countLabel = document.querySelector(".count-label");
    const detailsDiv = document.getElementById("selectionDetails");

    if (this.selectedTerritories.size === 0) {
      if (countNumber) countNumber.textContent = "0";
      if (countLabel) {
        const layerName = this.getLayerDisplayName(this.activeLayer);
        countLabel.textContent = `${layerName.toLowerCase()} selected`;
      }
      if (detailsDiv) detailsDiv.innerHTML = "";
      this.updateActionButtons(false);
    } else {
      const selectedNames = [];
      this.territories.eachLayer((layer) => {
        const featureId = layer.feature?.properties?.id || layer._leaflet_id;
        if (this.selectedTerritories.has(featureId)) {
          const name = layer.feature?.properties?.name || `Item ${featureId}`;
          selectedNames.push(name);
        }
      });

      const layerName = this.getLayerDisplayName(this.activeLayer);
      if (countNumber) countNumber.textContent = this.selectedTerritories.size;
      if (countLabel) {
        const itemText =
          this.selectedTerritories.size === 1
            ? layerName.toLowerCase().replace(/s$/, "")
            : layerName.toLowerCase();
        countLabel.textContent = `${itemText} selected`;
      }

      if (detailsDiv) {
        detailsDiv.innerHTML =
          selectedNames.slice(0, 10).join(", ") +
          (selectedNames.length > 10
            ? ` and ${selectedNames.length - 10} more...`
            : "");
      }

      this.updateActionButtons(true);
    }
  }

  updateActionButtons(enabled) {
    const actionButtons = [
      "assignBtn",
      "moveBtn",
      "splitBtn",
      "mergeBtn",
      "deleteBtn",
    ];

    actionButtons.forEach((btnId) => {
      const btn = document.getElementById(btnId);
      if (btn) {
        btn.disabled = !enabled;
      }
    });
  }

  getLayerDisplayName(layerValue) {
    const names = {
      zip_codes: "Zip Codes",
      territories: "Territories",
      regions: "Regions",
      areas: "Areas",
    };
    return names[layerValue] || layerValue;
  }

  performAction(action) {
    const layerName = this.getLayerDisplayName(this.activeLayer);
    const count = this.selectedTerritories.size;

    switch (action) {
      case "assign":
        this.updateStatus(`Assigning ${count} ${layerName.toLowerCase()}...`);
        alert(
          `This would assign ${count} selected ${layerName.toLowerCase()} to a territory/region/area`
        );
        break;
      case "move":
        this.updateStatus(`Moving ${count} ${layerName.toLowerCase()}...`);
        alert(
          `This would move ${count} selected ${layerName.toLowerCase()} to a different parent`
        );
        break;
      case "split":
        this.updateStatus(`Splitting ${count} ${layerName.toLowerCase()}...`);
        alert(`This would split the selected ${layerName.toLowerCase()}`);
        break;
      case "merge":
        this.updateStatus(`Merging ${count} ${layerName.toLowerCase()}...`);
        alert(`This would merge ${count} selected ${layerName.toLowerCase()}`);
        break;
      case "delete":
        if (confirm(`Remove ${count} selected ${layerName.toLowerCase()}?`)) {
          this.updateStatus(`Removing ${count} ${layerName.toLowerCase()}...`);
          this.clearSelection();
        }
        break;
    }
  }

  clearSelection() {
    this.selectedTerritories.clear();
    this.territories.eachLayer((layer) => {
      layer.setStyle(this.getFeatureStyle(layer.feature, false));
    });
    this.updateSelectionInfo();
  }

  updateStatus(message) {
    document.getElementById("statusBar").textContent = message;
  }
}

// Initialize the app
const app = new AlignstarDemo();
