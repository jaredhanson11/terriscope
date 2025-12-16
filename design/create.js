// Map Creation Wizard
class MapCreationWizard {
  constructor() {
    this.currentStep = 1;
    this.totalSteps = 4;
    this.fileData = this.generateSampleData();
    this.selectedLayers = new Set();
    this.layerConfigs = [];
    this.dataFieldConfigs = {};
    this.config = {
      name: "",
      description: "",
      fields: {},
    };

    this.init();
  }

  init() {
    this.setupEventListeners();
    this.updateUI();
    // Auto-populate file info with sample data
    this.showSampleFileInfo();
  }

  generateSampleData() {
    // Generate sample territory data with hierarchical structure
    // Zip Code -> Territory -> Region -> Area
    const features = [];

    const areas = ["Northeast", "Southeast", "Midwest", "West"];
    const regionsPerArea = {
      Northeast: ["New England", "Mid-Atlantic"],
      Southeast: ["South Atlantic", "East South Central"],
      Midwest: ["East North Central", "West North Central"],
      West: ["Mountain", "Pacific"],
    };

    const territoriesPerRegion = {
      "New England": ["Territory 1A", "Territory 1B", "Territory 1C"],
      "Mid-Atlantic": ["Territory 2A", "Territory 2B"],
      "South Atlantic": ["Territory 3A", "Territory 3B", "Territory 3C"],
      "East South Central": ["Territory 4A", "Territory 4B"],
      "East North Central": ["Territory 5A", "Territory 5B", "Territory 5C"],
      "West North Central": ["Territory 6A", "Territory 6B"],
      Mountain: ["Territory 7A", "Territory 7B", "Territory 7C"],
      Pacific: ["Territory 8A", "Territory 8B", "Territory 8C", "Territory 8D"],
    };

    // Sample zip codes (just using realistic-looking numbers)
    const sampleZips = [
      "02101",
      "02108",
      "02109",
      "02110",
      "02111",
      "02113",
      "02114",
      "02115",
      "10001",
      "10002",
      "10003",
      "10004",
      "10005",
      "10006",
      "10007",
      "30301",
      "30302",
      "30303",
      "30304",
      "30305",
      "30306",
      "60601",
      "60602",
      "60603",
      "60604",
      "60605",
      "60606",
      "90001",
      "90002",
      "90003",
      "90004",
      "90005",
      "90006",
    ];

    let featureId = 1;
    let zipIndex = 0;

    areas.forEach((area) => {
      const regions = regionsPerArea[area];
      regions.forEach((region) => {
        const territories = territoriesPerRegion[region];
        territories.forEach((territory) => {
          // Generate 3-5 zip codes per territory
          const zipCount = Math.floor(Math.random() * 3) + 3;
          for (let i = 0; i < zipCount; i++) {
            const zip = sampleZips[zipIndex % sampleZips.length];
            zipIndex++;

            features.push({
              type: "Feature",
              id: featureId++,
              properties: {
                zip_code: zip,
                territory_id: territory.replace("Territory ", "T"),
                territory_name: territory,
                region_id: region.replace(/\s+/g, "_").toUpperCase(),
                region_name: region,
                area_id: area.toUpperCase(),
                area_name: area,
                workload_index: Math.floor(Math.random() * 100) + 1,
                population: Math.floor(Math.random() * 50000) + 10000,
                households: Math.floor(Math.random() * 20000) + 5000,
                avg_income: Math.floor(Math.random() * 50000) + 40000,
                rep_name: this.generateRepName(),
                status: ["Active", "Inactive", "Pending"][
                  Math.floor(Math.random() * 3)
                ],
              },
              geometry: {
                type: "Polygon",
                coordinates: [this.generateZipBoundary()],
              },
            });
          }
        });
      });
    });

    return {
      type: "FeatureCollection",
      features: features,
      metadata: {
        totalZipCodes: features.length,
        totalTerritories: Object.values(territoriesPerRegion).flat().length,
        totalRegions: Object.values(regionsPerArea).flat().length,
        totalAreas: areas.length,
      },
    };
  }

  generateRepName() {
    const firstNames = [
      "John",
      "Sarah",
      "Michael",
      "Emily",
      "David",
      "Lisa",
      "James",
      "Jennifer",
      "Robert",
      "Mary",
    ];
    const lastNames = [
      "Smith",
      "Johnson",
      "Williams",
      "Brown",
      "Jones",
      "Garcia",
      "Miller",
      "Davis",
      "Rodriguez",
      "Martinez",
    ];
    return `${firstNames[Math.floor(Math.random() * firstNames.length)]} ${
      lastNames[Math.floor(Math.random() * lastNames.length)]
    }`;
  }

  generateZipBoundary() {
    // Generate a simple rectangular boundary for demo purposes
    const baseLon = -122 + Math.random() * 70; // Roughly across USA
    const baseLat = 25 + Math.random() * 24; // Roughly across USA
    const size = 0.05; // Small area for zip code

    return [
      [baseLon, baseLat],
      [baseLon + size, baseLat],
      [baseLon + size, baseLat + size],
      [baseLon, baseLat + size],
      [baseLon, baseLat],
    ];
  }

  showSampleFileInfo() {
    document.getElementById("fileName").textContent = "sample_territories.ztt";
    document.getElementById("fileSize").textContent = "256 KB";
    document.getElementById("uploadBox").style.display = "none";
    document.getElementById("fileInfo").style.display = "block";
  }

  setupEventListeners() {
    // Navigation
    document
      .getElementById("backBtn")
      .addEventListener("click", () => this.previousStep());
    document
      .getElementById("nextBtn")
      .addEventListener("click", () => this.nextStep());

    // File upload (disabled for demo - just show message)
    const uploadBox = document.getElementById("uploadBox");
    const fileInput = document.getElementById("fileInput");

    uploadBox.addEventListener("click", () => {
      alert(
        'For this demo, sample data is pre-loaded. Click "Next" to continue.'
      );
    });

    document.getElementById("changeFileBtn")?.addEventListener("click", () => {
      alert("For this demo, sample data is pre-loaded.");
    });

    // Create map
    document
      .getElementById("createMapBtn")
      ?.addEventListener("click", () => this.createMap());
  }

  async handleFileSelect(file) {
    if (!file) return;

    try {
      // Show file info
      document.getElementById("fileName").textContent = file.name;
      document.getElementById("fileSize").textContent = this.formatFileSize(
        file.size
      );
      document.getElementById("uploadBox").style.display = "none";
      document.getElementById("fileInfo").style.display = "block";

      // Read file
      const text = await file.text();

      // Parse based on extension
      if (file.name.endsWith(".ztt")) {
        this.fileData = await this.parseZTT(text);
      } else if (
        file.name.endsWith(".geojson") ||
        file.name.endsWith(".json")
      ) {
        this.fileData = JSON.parse(text);
      } else {
        throw new Error("Unsupported file format");
      }

      // Auto-advance to next step
      setTimeout(() => this.nextStep(), 500);
    } catch (error) {
      console.error("Error reading file:", error);
      alert("Error reading file: " + error.message);
    }
  }

  async parseZTT(text) {
    // ZTT files are typically tab-delimited or have a specific format
    // For this demo, we'll assume it's a JSON-like format or convert CSV/TSV to GeoJSON

    // Try parsing as JSON first
    try {
      return JSON.parse(text);
    } catch (e) {
      // If not JSON, try parsing as delimited text
      const lines = text.split("\n").filter((line) => line.trim());
      if (lines.length === 0) throw new Error("Empty file");

      // Assume first line is header
      const headers = lines[0].split("\t");
      const features = [];

      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split("\t");
        const properties = {};
        headers.forEach((header, index) => {
          properties[header.trim()] = values[index]?.trim() || "";
        });

        // Try to find geometry fields
        // This is a simplified example - real ZTT parsing would be more complex
        features.push({
          type: "Feature",
          properties: properties,
          geometry: {
            type: "Point",
            coordinates: [0, 0], // Placeholder
          },
        });
      }

      return {
        type: "FeatureCollection",
        features: features,
      };
    }
  }

  formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  nextStep() {
    if (!this.validateStep(this.currentStep)) {
      return;
    }

    if (this.currentStep < this.totalSteps) {
      this.currentStep++;
      this.updateUI();

      // Initialize step-specific content
      if (this.currentStep === 2) {
        this.initializeLayersStep();
      } else if (this.currentStep === 3) {
        this.initializeDataConfigStep();
      } else if (this.currentStep === 4) {
        this.initializeReviewStep();
      }
    }
  }

  previousStep() {
    if (this.currentStep > 1) {
      this.currentStep--;
      this.updateUI();
    }
  }

  validateStep(step) {
    switch (step) {
      case 1:
        // Always valid - sample data is pre-loaded
        return true;
      case 2:
        const enabledLayers = this.layerConfigs.filter((l) => l.enabled);
        if (enabledLayers.length === 0) {
          alert("Please enable at least one layer");
          return false;
        }
        // Check that all enabled layers have valid field mappings
        for (const layer of enabledLayers) {
          if (!layer.idField || !layer.nameField) {
            alert(
              `Please select both ID and Name columns for layer: ${layer.name}`
            );
            return false;
          }
        }
        return true;
      case 3:
        // Validate data field configurations
        return true;
      case 4:
        return true;
      default:
        return true;
    }
  }

  updateUI() {
    // Update progress steps
    document.querySelectorAll(".step").forEach((step, index) => {
      const stepNum = index + 1;
      step.classList.remove("active", "completed");
      if (stepNum === this.currentStep) {
        step.classList.add("active");
      } else if (stepNum < this.currentStep) {
        step.classList.add("completed");
      }
    });

    // Update step content
    document.querySelectorAll(".step-content").forEach((content, index) => {
      content.classList.toggle("active", index + 1 === this.currentStep);
    });

    // Update navigation buttons
    document.getElementById("backBtn").disabled = this.currentStep === 1;

    const nextBtn = document.getElementById("nextBtn");
    if (this.currentStep === this.totalSteps) {
      nextBtn.style.display = "none";
    } else {
      nextBtn.style.display = "block";
    }

    // Update help text
    this.updateHelpText();
  }

  updateHelpText() {
    const helpTexts = {
      1: {
        title: "Step 1: Sample Data Loaded",
        content:
          "Pre-loaded sample data shows a typical territory structure with Zip Codes → Territories → Regions → Areas. Each record includes workload index and additional demographic data.",
      },
      2: {
        title: "Step 2: Configure Layers",
        content:
          "Map your Excel/CSV columns to each layer in the hierarchy. Rename layers as needed. All layers are enabled by default - you can disable layers you don't need. Each layer must have an ID column and a Name column.",
      },
      3: {
        title: "Step 3: Configure Data",
        content:
          "Select each field to configure its data type. For numeric fields, choose one or more aggregation methods to control how values roll up through the hierarchy (sum, average, min, max, etc.).",
      },
      4: {
        title: "Step 4: Review & Create",
        content:
          "Review your configuration including all hierarchy levels, field mappings, and aggregation settings. Give your map a name and create it to start working with territories.",
      },
    };

    const help = helpTexts[this.currentStep];
    document.getElementById("helpText").innerHTML = `
            <p><strong>${help.title}</strong></p>
            <p>${help.content}</p>
        `;
  }

  initializeLayersStep() {
    const configList = document.getElementById("layerConfigList");
    configList.innerHTML = "";

    // Get all available fields from sample data
    const availableFields = Object.keys(this.fileData.features[0].properties);

    // Define the layer hierarchy with their configurations
    this.layerConfigs = [
      {
        level: "zip_code",
        defaultName: "Zip Codes",
        name: "Zip Codes",
        description: "Base layer - Individual zip code territories",
        idField: "zip_code",
        nameField: "zip_code",
        enabled: true,
        order: 0,
      },
      {
        level: "territory",
        defaultName: "Territories",
        name: "Territories",
        description: "Grouped zip codes into sales territories",
        idField: "territory_id",
        nameField: "territory_name",
        enabled: true,
        order: 1,
      },
      {
        level: "region",
        defaultName: "Regions",
        name: "Regions",
        description: "Multiple territories grouped into regions",
        idField: "region_id",
        nameField: "region_name",
        enabled: true,
        order: 2,
      },
      {
        level: "area",
        defaultName: "Areas",
        name: "Areas",
        description: "High-level geographic areas",
        idField: "area_id",
        nameField: "area_name",
        enabled: true,
        order: 3,
      },
    ];

    // Add all layers to selected by default
    this.layerConfigs.forEach((layer) => {
      if (layer.enabled) {
        this.selectedLayers.add(layer.level);
      }
    });

    // Create configuration UI for each layer
    this.layerConfigs.forEach((layer, index) => {
      const configItem = document.createElement("div");
      configItem.className =
        "layer-config-item" + (layer.enabled ? " enabled" : "");
      configItem.dataset.level = layer.level;

      configItem.innerHTML = `
                <div class="layer-config-header">
                    <div class="layer-toggle">
                        <input type="checkbox" class="layer-checkbox" ${
                          layer.enabled ? "checked" : ""
                        } data-index="${index}">
                        <span class="layer-level-badge">Layer ${
                          index + 1
                        }</span>
                    </div>
                    <span style="color: #888; font-size: 13px;">${
                      layer.description
                    }</span>
                </div>
                <div class="layer-config-body">
                    <div class="layer-field-row">
                        <label>Layer Name:</label>
                        <input type="text" class="layer-name-input" value="${
                          layer.name
                        }" data-index="${index}" placeholder="Enter layer name">
                    </div>
                    <div class="layer-field-row">
                        <label>ID Column:</label>
                        <select class="layer-field-select id-field" data-index="${index}">
                            ${this.generateFieldOptions(
                              availableFields,
                              layer.idField
                            )}
                        </select>
                    </div>
                    <div class="layer-field-row">
                        <label>Name Column:</label>
                        <select class="layer-field-select name-field" data-index="${index}">
                            ${this.generateFieldOptions(
                              availableFields,
                              layer.nameField
                            )}
                        </select>
                    </div>
                    <div class="layer-description">
                        Excel columns: ${layer.idField}, ${layer.nameField}
                    </div>
                </div>
            `;

      // Add event listeners
      const checkbox = configItem.querySelector(".layer-checkbox");
      checkbox.addEventListener("change", (e) => {
        const idx = parseInt(e.target.dataset.index);
        this.layerConfigs[idx].enabled = e.target.checked;
        configItem.classList.toggle("enabled", e.target.checked);

        if (e.target.checked) {
          this.selectedLayers.add(layer.level);
        } else {
          this.selectedLayers.delete(layer.level);
        }
        this.updateLayerPreview();
      });

      const nameInput = configItem.querySelector(".layer-name-input");
      nameInput.addEventListener("input", (e) => {
        const idx = parseInt(e.target.dataset.index);
        this.layerConfigs[idx].name = e.target.value;
        this.updateLayerPreview();
      });

      const idSelect = configItem.querySelector(".id-field");
      idSelect.addEventListener("change", (e) => {
        const idx = parseInt(e.target.dataset.index);
        this.layerConfigs[idx].idField = e.target.value;
        this.updateLayerPreview();
      });

      const nameSelect = configItem.querySelector(".name-field");
      nameSelect.addEventListener("change", (e) => {
        const idx = parseInt(e.target.dataset.index);
        this.layerConfigs[idx].nameField = e.target.value;
        this.updateLayerPreview();
      });

      configList.appendChild(configItem);
    });

    // Show initial preview
    this.updateLayerPreview();
  }

  generateFieldOptions(fields, selectedField) {
    return fields
      .map(
        (field) =>
          `<option value="${field}" ${
            field === selectedField ? "selected" : ""
          }>${field}</option>`
      )
      .join("");
  }

  updateLayerPreview() {
    const preview = document.getElementById("layerPreview");
    const enabledLayers = this.layerConfigs.filter((l) => l.enabled);

    if (enabledLayers.length === 0) {
      preview.innerHTML =
        "<p>No layers enabled. Enable at least one layer to continue.</p>";
      return;
    }

    // Show summary of layer configuration
    let html = "<h4>Layer Hierarchy</h4>";
    html += '<div style="margin-top: 15px;">';

    enabledLayers.forEach((layer, index) => {
      const sample = this.fileData.features[0].properties;
      html += `
                <div style="background: #2d2d2d; padding: 12px; border-radius: 4px; margin-bottom: 10px; border-left: 3px solid #4a9eff;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <strong style="color: #4a9eff;">${layer.name}</strong>
                        <span style="font-size: 11px; color: #888;">Level ${
                          index + 1
                        }</span>
                    </div>
                    <div style="font-size: 12px; color: #ccc;">
                        <div style="margin: 4px 0;">ID: <code style="background: #1a1a1a; padding: 2px 6px; border-radius: 3px;">${
                          layer.idField
                        }</code> = "${sample[layer.idField]}"</div>
                        <div style="margin: 4px 0;">Name: <code style="background: #1a1a1a; padding: 2px 6px; border-radius: 3px;">${
                          layer.nameField
                        }</code> = "${sample[layer.nameField]}"</div>
                    </div>
                </div>
            `;
    });

    html += "</div>";

    // Show sample data table
    html += '<h4 style="margin-top: 20px;">Sample Data</h4>';
    html += '<div style="overflow-x: auto; margin-top: 10px;">';
    html += '<table style="width: 100%; font-size: 11px;">';
    html += "<thead><tr>";

    enabledLayers.forEach((layer) => {
      html += `<th style="padding: 8px; background: #3a3a3a; border-bottom: 2px solid #555; text-align: left;">${layer.name}</th>`;
    });

    html += "</tr></thead><tbody>";

    // Show first 3 rows
    for (let i = 0; i < Math.min(3, this.fileData.features.length); i++) {
      const props = this.fileData.features[i].properties;
      html += "<tr>";
      enabledLayers.forEach((layer) => {
        html += `<td style="padding: 8px; border-bottom: 1px solid #3a3a3a; color: #ccc;">${
          props[layer.nameField] || "-"
        }</td>`;
      });
      html += "</tr>";
    }

    html += "</tbody></table></div>";

    preview.innerHTML = html;
  }

  extractLayers(data) {
    if (data.type === "FeatureCollection") {
      return [
        {
          name: "Main Layer",
          featureCount: data.features.length,
          geometryType: data.features[0]?.geometry?.type || "Unknown",
          data: data,
        },
      ];
    }
    return [
      {
        name: "Imported Data",
        featureCount: 1,
        geometryType: "Unknown",
        data: data,
      },
    ];
  }

  initializeDataConfigStep() {
    const features = this.fileData.features || [];
    if (features.length === 0) return;

    // Get all available fields from sample data
    const allFields = Object.keys(features[0].properties || {});

    // Get fields that are used in layer configurations (ID and Name columns)
    const usedInLayers = new Set();
    this.layerConfigs.forEach((layer) => {
      if (layer.enabled) {
        usedInLayers.add(layer.idField);
        usedInLayers.add(layer.nameField);
      }
    });

    // Get data fields (excluding hierarchy fields)
    const dataFields = allFields.filter((field) => !usedInLayers.has(field));

    // Initialize data field configs if not already set
    dataFields.forEach((field) => {
      if (!this.dataFieldConfigs[field]) {
        const sampleValue = features[0].properties[field];
        const isNumeric =
          typeof sampleValue === "number" || !isNaN(parseFloat(sampleValue));

        this.dataFieldConfigs[field] = {
          type: isNumeric ? "number" : "text",
          aggregations: isNumeric ? ["sum"] : [],
          displayName: field,
        };
      }
    });

    // Build the field list
    const fieldList = document.getElementById("dataFieldsList");
    if (!fieldList) return;

    fieldList.innerHTML = "";

    dataFields.forEach((field) => {
      const config = this.dataFieldConfigs[field];
      const fieldItem = document.createElement("div");
      fieldItem.className = "data-field-item";
      fieldItem.dataset.field = field;

      const sampleValue = features[0].properties[field];

      fieldItem.innerHTML = `
                <div>
                    <div class="data-field-name">${field}</div>
                    <div class="data-field-type">${config.type}</div>
                </div>
            `;

      fieldItem.addEventListener("click", () => {
        document.querySelectorAll(".data-field-item").forEach((item) => {
          item.classList.remove("selected");
        });
        fieldItem.classList.add("selected");
        this.showFieldConfig(field);
      });

      fieldList.appendChild(fieldItem);
    });

    // Auto-select first field
    if (dataFields.length > 0) {
      fieldList.firstChild.click();
    }
  }

  showFieldConfig(fieldName) {
    const configPanel = document.getElementById("fieldConfigForm");
    if (!configPanel) return;

    const config = this.dataFieldConfigs[fieldName];
    const features = this.fileData.features || [];
    const sampleValues = features
      .slice(0, 5)
      .map((f) => f.properties[fieldName]);

    let html = `
            <div class="config-group">
                <h4>Field Name</h4>
                <div class="config-row">
                    <input type="text" value="${fieldName}" readonly style="background: #1a1a1a; color: #888;">
                </div>
            </div>
            
            <div class="config-group">
                <h4>Data Type</h4>
                <div class="config-option">
                    <label>
                        <input type="radio" name="type_${fieldName}" value="text" ${
      config.type === "text" ? "checked" : ""
    }>
                        <span>Text</span>
                    </label>
                </div>
                <div class="config-option">
                    <label>
                        <input type="radio" name="type_${fieldName}" value="number" ${
      config.type === "number" ? "checked" : ""
    }>
                        <span>Number</span>
                    </label>
                </div>
                <div class="config-option">
                    <label>
                        <input type="radio" name="type_${fieldName}" value="date" ${
      config.type === "date" ? "checked" : ""
    }>
                        <span>Date</span>
                    </label>
                </div>
            </div>
        `;

    // Show aggregation options only for numeric fields
    if (config.type === "number") {
      const aggregationMethods = [
        { value: "sum", label: "Sum", description: "Add all values together" },
        {
          value: "average",
          label: "Average",
          description: "Calculate the mean value",
        },
        {
          value: "min",
          label: "Minimum",
          description: "Take the smallest value",
        },
        {
          value: "max",
          label: "Maximum",
          description: "Take the largest value",
        },
        {
          value: "count",
          label: "Count",
          description: "Count number of items",
        },
        {
          value: "first",
          label: "First",
          description: "Use the first value encountered",
        },
        {
          value: "last",
          label: "Last",
          description: "Use the last value encountered",
        },
      ];

      html += `
                <div class="config-group">
                    <h4>Aggregation Methods</h4>
                    <p style="font-size: 12px; color: #888; margin-bottom: 12px;">
                        Select one or more ways this field should roll up through the hierarchy
                    </p>
                    <div class="aggregation-grid">
            `;

      aggregationMethods.forEach((method) => {
        const isChecked = config.aggregations.includes(method.value);
        html += `
                    <div class="aggregation-method ${
                      isChecked ? "selected" : ""
                    }">
                        <input type="checkbox" 
                               id="agg_${fieldName}_${method.value}" 
                               value="${method.value}" 
                               ${isChecked ? "checked" : ""}
                               data-field="${fieldName}">
                        <label for="agg_${fieldName}_${method.value}">
                            <div class="method-name">${method.label}</div>
                            <div class="method-description">${
                              method.description
                            }</div>
                        </label>
                    </div>
                `;
      });

      html += `
                    </div>
                </div>
            `;
    }

    // Show sample values
    html += `
            <div class="field-sample">
                <div class="sample-label">Sample Values</div>
                <div class="sample-values">${sampleValues.join(", ")}</div>
            </div>
        `;

    configPanel.innerHTML = html;

    // Add event listeners
    configPanel.querySelectorAll('input[type="radio"]').forEach((radio) => {
      radio.addEventListener("change", (e) => {
        const newType = e.target.value;
        this.dataFieldConfigs[fieldName].type = newType;

        // Reset aggregations when changing type
        if (
          newType === "number" &&
          this.dataFieldConfigs[fieldName].aggregations.length === 0
        ) {
          this.dataFieldConfigs[fieldName].aggregations = ["sum"];
        } else if (newType !== "number") {
          this.dataFieldConfigs[fieldName].aggregations = [];
        }

        // Update the field type badge in the list
        const fieldItem = document.querySelector(
          `.data-field-item[data-field="${fieldName}"]`
        );
        if (fieldItem) {
          fieldItem.querySelector(".data-field-type").textContent = newType;
        }

        // Refresh the config panel
        this.showFieldConfig(fieldName);
      });
    });

    configPanel
      .querySelectorAll('input[type="checkbox"]')
      .forEach((checkbox) => {
        checkbox.addEventListener("change", (e) => {
          const method = e.target.value;
          const field = e.target.dataset.field;

          if (e.target.checked) {
            if (!this.dataFieldConfigs[field].aggregations.includes(method)) {
              this.dataFieldConfigs[field].aggregations.push(method);
            }
            e.target.closest(".aggregation-method").classList.add("selected");
          } else {
            const index =
              this.dataFieldConfigs[field].aggregations.indexOf(method);
            if (index > -1) {
              this.dataFieldConfigs[field].aggregations.splice(index, 1);
            }
            e.target
              .closest(".aggregation-method")
              .classList.remove("selected");
          }
        });
      });
  }

  initializeReviewStep() {
    const summary = document.getElementById("importSummary");
    const features = this.fileData.features || [];
    const enabledLayers = this.layerConfigs.filter((l) => l.enabled);

    // Build hierarchy summary
    let layersHtml = "";
    enabledLayers.forEach((layer, index) => {
      layersHtml += `
                <div style="padding: 8px; background: #2d2d2d; border-radius: 4px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #4a9eff;">${layer.name}</strong>
                        <span style="font-size: 11px; color: #888;">Level ${
                          index + 1
                        }</span>
                    </div>
                    <div style="font-size: 11px; color: #ccc; margin-top: 4px;">
                        ID: <code>${layer.idField}</code> | Name: <code>${
        layer.nameField
      }</code>
                    </div>
                </div>
            `;
    });

    // Build field configurations summary
    let fieldsHtml = "";
    const configuredFields = Object.keys(this.dataFieldConfigs);

    if (configuredFields.length > 0) {
      fieldsHtml =
        '<h4 style="margin-top: 20px; margin-bottom: 10px;">Data Fields</h4>';

      configuredFields.forEach((field) => {
        const config = this.dataFieldConfigs[field];
        let aggDisplay = "";

        if (config.type === "number" && config.aggregations.length > 0) {
          aggDisplay = config.aggregations
            .map(
              (agg) =>
                `<span style="background: #4a9eff; color: #fff; padding: 2px 8px; border-radius: 3px; font-size: 10px; margin-right: 4px;">${agg.toUpperCase()}</span>`
            )
            .join("");
        } else {
          aggDisplay = `<span style="color: #888; font-size: 11px;">No aggregation</span>`;
        }

        fieldsHtml += `
                    <div style="padding: 10px; border-bottom: 1px solid #3a3a3a; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <code style="color: #ccc; font-weight: bold;">${field}</code>
                            <span style="color: #888; font-size: 11px; margin-left: 8px;">(${config.type})</span>
                        </div>
                        <div>${aggDisplay}</div>
                    </div>
                `;
      });
    }

    summary.innerHTML = `
            <div style="margin-bottom: 20px;">
                <h3 style="margin-bottom: 15px;">Hierarchy Configuration</h3>
                ${layersHtml}
            </div>
            
            ${fieldsHtml}
            
            <div style="margin-top: 20px; padding: 12px; background: #2d2d2d; border-radius: 4px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 13px;">
                    <div>
                        <div style="color: #888;">Total Zip Codes</div>
                        <div style="font-size: 18px; font-weight: bold; color: #4a9eff;">${features.length}</div>
                    </div>
                    <div>
                        <div style="color: #888;">Total Territories</div>
                        <div style="font-size: 18px; font-weight: bold; color: #4a9eff;">${this.fileData.metadata.totalTerritories}</div>
                    </div>
                    <div>
                        <div style="color: #888;">Total Regions</div>
                        <div style="font-size: 18px; font-weight: bold; color: #4a9eff;">${this.fileData.metadata.totalRegions}</div>
                    </div>
                    <div>
                        <div style="color: #888;">Total Areas</div>
                        <div style="font-size: 18px; font-weight: bold; color: #4a9eff;">${this.fileData.metadata.totalAreas}</div>
                    </div>
                </div>
            </div>
        `;
  }

  createMap() {
    const mapName = document.getElementById("mapNameInput").value.trim();
    if (!mapName) {
      alert("Please enter a map name");
      return;
    }

    this.config.name = mapName;
    this.config.description = document
      .getElementById("mapDescInput")
      .value.trim();

    // Store configuration in localStorage for demo purposes
    const mapData = {
      config: this.config,
      layerConfigs: this.layerConfigs,
      dataFieldConfigs: this.dataFieldConfigs,
      data: this.fileData,
    };

    localStorage.setItem("alignstar_map", JSON.stringify(mapData));

    alert("Map created successfully!");

    // Redirect to main demo with the loaded map
    window.location.href = "index.html?map=created";
  }
}

// Initialize the wizard
const wizard = new MapCreationWizard();
