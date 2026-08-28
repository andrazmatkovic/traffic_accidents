let currentLanguage = 'sl';
let allData = [];
let dataIndex = buildEmptyDataIndex();
let dataManifest = null;
let loadedYears = new Set();
let loadingYears = new Set();
let yearLoadPromises = new Map();
let map = null;
let expandedWebs = new Set();
let spiderMarkers = {};
let updateMapTimeout = null;

let state = {
    showMarkers: true,
    showHeatmap: false,
    selectedYear: [],
    selectedSeverities: [],
    selectedTypes: [],
    selectedWeather: [],
    selectedTraffic: [],
    selectedRoadSurface: [],
    selectedLocationTypes: [],
    markerGroup: null,
    heatmapLayer: null
};

function setLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem('language', lang);
    
    document.querySelectorAll('.language-toggle').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeLangBtn = document.querySelector(`[data-lang="${lang}"]`);
    if (activeLangBtn) activeLangBtn.classList.add('active');
    
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = translations[lang][key];
    });
    
    if (dataManifest) {
        buildUI(...getFilterOptions(), getActiveYear());
    }
}

const savedLanguage = localStorage.getItem('language') || 'sl';
setLanguage(savedLanguage);

// Only attach listeners if buttons exist
const langSLBtn = document.getElementById('langSL');
const langENBtn = document.getElementById('langEN');
if (langSLBtn) langSLBtn.addEventListener('click', () => setLanguage('sl'));
if (langENBtn) langENBtn.addEventListener('click', () => setLanguage('en'));

function debouncedUpdateMap() {
    if (updateMapTimeout) clearTimeout(updateMapTimeout);
    updateMapTimeout = setTimeout(updateMap, 150);
}

const menuToggle = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');

menuToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('open');
});

sidebarOverlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('open');
});

function closeSidebarOnMobile() {
    if (window.innerWidth <= 768) {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('open');
    }
}

function buildEmptyDataIndex() {
    return {
        byYear: new Map(),
        years: [],
        severities: [],
        types: [],
        weather: [],
        traffic: [],
        roadSurface: [],
        locationTypes: []
    };
}

function buildFilterOptionsFromManifest(manifest) {
    return {
        years: manifest.years || [],
        severities: manifest.filters?.severities || [],
        types: manifest.filters?.types || [],
        weather: manifest.filters?.weather || [],
        traffic: manifest.filters?.traffic || [],
        roadSurface: manifest.filters?.roadSurface || [],
        locationTypes: manifest.filters?.locationTypes || []
    };
}

function appendYearData(year, data) {
    const numericYear = Number(year);
    const existing = dataIndex.byYear.get(numericYear) || [];
    const nextYearData = existing.concat(data);
    dataIndex.byYear.set(numericYear, nextYearData);
    allData = dataManifest.years.flatMap(year => dataIndex.byYear.get(year) || []);
    loadedYears.add(numericYear);
}

function getFilterOptions() {
    return [
        dataIndex.years,
        dataIndex.severities,
        dataIndex.types,
        dataIndex.weather,
        dataIndex.traffic,
        dataIndex.roadSurface,
        dataIndex.locationTypes
    ];
}

function getChunkForYear(year) {
    return dataManifest.chunks.find(chunk => chunk.year === year);
}

function getActiveYear() {
    const yearFilter = document.getElementById('yearFilter');
    if (!yearFilter) return dataManifest?.defaultYear || null;
    return yearFilter.value ? parseInt(yearFilter.value) : null;
}

function loadYearChunk(year) {
    if (loadedYears.has(year)) {
        return Promise.resolve();
    }

    if (loadingYears.has(year)) {
        return yearLoadPromises.get(year) || Promise.resolve();
    }

    const chunk = getChunkForYear(year);
    if (!chunk) {
        return Promise.reject(new Error(`Missing data chunk for year ${year}`));
    }

    loadingYears.add(year);

    const loadPromise = fetch(`data/${chunk.file}`)
        .then(response => {
            if (!response.ok) throw new Error(`Failed to load data for ${year}`);
            return response.arrayBuffer();
        })
        .then(arrayBuffer => new Promise((resolve, reject) => {
            const worker = new Worker('decompress-worker-json.js');

            worker.onmessage = (event) => {
                worker.terminate();
                loadingYears.delete(year);
                yearLoadPromises.delete(year);

                if (event.data.success) {
                    appendYearData(year, event.data.data);
                    console.log(`✅ Loaded ${event.data.recordCount} accidents for ${year} in ${event.data.loadTime.toFixed(2)}s`);
                    resolve();
                } else {
                    reject(new Error(event.data.error));
                }
            };

            worker.onerror = (error) => {
                worker.terminate();
                loadingYears.delete(year);
                yearLoadPromises.delete(year);
                reject(error);
            };

            worker.postMessage({ arrayBuffer, year });
        }))
        .catch(error => {
            loadingYears.delete(year);
            yearLoadPromises.delete(year);
            throw error;
        });

    yearLoadPromises.set(year, loadPromise);
    return loadPromise;
}

async function hydrateRemainingYears(defaultYear, progressBar) {
    const remainingYears = dataManifest.years.filter(year => year !== defaultYear);
    let loadedCount = 1;
    const totalYears = dataManifest.years.length;

    for (const year of remainingYears) {
        try {
            await loadYearChunk(year);
            loadedCount += 1;
            progressBar.style.width = `${Math.round((loadedCount / totalYears) * 100)}%`;
            if (getActiveYear() === null) {
                updateMap();
            }
        } catch (error) {
            console.error(`Error loading background data for ${year}:`, error);
        }
    }
}

async function loadAccidentData() {
    const loadingMsg = document.getElementById('loadingMsg');
    const progressBar = document.getElementById('loadingProgress');

    try {
        const manifestResponse = await fetch('data/manifest.json');
        if (!manifestResponse.ok) throw new Error('Failed to load data manifest');
        dataManifest = await manifestResponse.json();
        Object.assign(dataIndex, buildFilterOptionsFromManifest(dataManifest));

        const defaultYear = dataManifest.defaultYear;
        loadingMsg.textContent = translations[currentLanguage].loadingDots;
        progressBar.style.width = '30%';

        await loadYearChunk(defaultYear);
        progressBar.style.width = '100%';

        setTimeout(() => {
            initializeApp(defaultYear);
            hydrateRemainingYears(defaultYear, progressBar);
        }, 150);
    } catch (error) {
        console.error('Error loading data:', error);
        loadingMsg.textContent = `❌ Error loading data: ${error.message}`;
    }
}

function initializeApp(defaultYear = null) {
    map = L.map('map').setView([46.0569, 14.5058], 12);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    const [years, severities, types, weather, traffic, roadSurface, locationTypes] = getFilterOptions();
    
    state.selectedYear = years;
    state.selectedSeverities = severities;
    state.selectedTypes = types;
    state.selectedWeather = weather;
    state.selectedTraffic = traffic;
    state.selectedRoadSurface = roadSurface;
    state.selectedLocationTypes = locationTypes;
    
    buildUI(years, severities, types, weather, traffic, roadSurface, locationTypes, defaultYear);
    updateMap();
}

function buildUI(years, severities, types, weather, traffic, roadSurface, locationTypes, selectedYear = null) {
    const sidebar = document.getElementById('sidebar');
    const t = translations[currentLanguage];
    
    sidebar.innerHTML = `
        <div class="filter-section">
            <h3>${t.visualization}</h3>
            <button class="toggle-btn active" id="markerToggle">${t.markers}</button>
            <button class="toggle-btn" id="heatmapToggle">${t.heatmap}</button>
        </div>
        
        <div class="filter-section">
            <h3>${t.year}</h3>
            <select class="filter-select" id="yearFilter">
                <option value="">${t.allYears}</option>
            </select>
        </div>
        
        <div class="filter-section">
            <h3>${t.severity}</h3>
            <div class="filter-checkbox-list" id="severityList"></div>
        </div>
        
        <div class="filter-section">
            <h3>${t.type}</h3>
            <div class="filter-checkbox-list" id="typeList"></div>
        </div>
        
        <div class="filter-section">
            <h3>${t.weather}</h3>
            <div class="filter-checkbox-list" id="weatherList"></div>
        </div>
        
        <div class="filter-section">
            <h3>${t.traffic}</h3>
            <div class="filter-checkbox-list" id="trafficList"></div>
        </div>
        
        <div class="filter-section">
            <h3>${t.roadSurface}</h3>
            <div class="filter-checkbox-list" id="roadList"></div>
        </div>
        
        <div class="filter-section">
            <h3>${t.locationType}</h3>
            <div class="filter-checkbox-list" id="locationList"></div>
        </div>
        
        <div class="stats-panel">
            <div class="stat-item">
                <span class="stat-label">${t.total}</span>
                <span class="stat-value" id="statCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">${t.serious}</span>
                <span class="stat-value" id="statSerious">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">${t.minor}</span>
                <span class="stat-value" id="statMinor">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">${t.property}</span>
                <span class="stat-value" id="statProperty">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">${t.fatal}</span>
                <span class="stat-value" id="statFatal">0</span>
            </div>
        </div>
        
        <div class="color-legend">
            <h4>${t.colorLegend}</h4>
            <div class="legend-item">
                <div class="legend-color" style="background: #dc3545;"></div>
                <span class="legend-text">${t.seriousInjury}</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #fd7e14;"></div>
                <span class="legend-text">${t.minorInjury}</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #8b0000;"></div>
                <span class="legend-text">${t.fatal_legend}</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #0066cc;"></div>
                <span class="legend-text">${t.propertyDamage}</span>
            </div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #ddd;">
            <h4 style="margin-top: 8px;">${t.multiAccidents}</h4>
            <div class="legend-item">
                <div class="legend-color" style="background: #667eea; border: 2px solid white;"></div>
                <span class="legend-text">${t.multiAccidentsDesc}</span>
            </div>
            <hr style="margin: 8px 0; border: none; border-top: 1px solid #ddd;">
            <h4 style="margin-top: 8px;">${t.heatmapLabel}</h4>
            <div class="legend-item">
                <div class="legend-color" style="background: #0066cc;"></div>
                <span class="legend-text">${t.lowDensity}</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #ff0000;"></div>
                <span class="legend-text">${t.highDensity}</span>
            </div>
        </div>
        
        <button class="reset-btn" id="resetBtn">${t.resetAll}</button>
    `;
    
    const yearFilter = document.getElementById('yearFilter');
    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearFilter.appendChild(option);
    });
    if (selectedYear) {
        yearFilter.value = selectedYear;
    }
    yearFilter.addEventListener('change', () => {
        const selectedYear = yearFilter.value ? parseInt(yearFilter.value) : null;
        if (selectedYear && !loadedYears.has(selectedYear)) {
            loadYearChunk(selectedYear).then(updateMap).catch(error => {
                console.error('Error loading selected year:', error);
            });
        } else {
            debouncedUpdateMap();
        }
        closeSidebarOnMobile();
    });
    
    populateCheckboxes('severityList', severities, 'severity');
    populateCheckboxes('typeList', types, 'type');
    populateCheckboxes('weatherList', weather, 'weather');
    populateCheckboxes('trafficList', traffic, 'traffic');
    populateCheckboxes('roadList', roadSurface, 'road');
    populateCheckboxes('locationList', locationTypes, 'location');
    
    document.getElementById('markerToggle').addEventListener('click', function() {
        if (!this.classList.contains('active')) {
            state.showMarkers = true;
            state.showHeatmap = false;
            document.getElementById('heatmapToggle').classList.remove('active');
            this.classList.add('active');
            debouncedUpdateMap();
        }
    });
    
    document.getElementById('heatmapToggle').addEventListener('click', function() {
        if (!this.classList.contains('active')) {
            state.showMarkers = false;
            state.showHeatmap = true;
            document.getElementById('markerToggle').classList.remove('active');
            this.classList.add('active');
            debouncedUpdateMap();
        }
    });
    
    document.getElementById('resetBtn').addEventListener('click', () => {
        document.querySelectorAll('.filter-option input').forEach(cb => cb.checked = true);
        document.getElementById('yearFilter').value = '';
        state.selectedYear = years;
        state.selectedSeverities = severities;
        state.selectedTypes = types;
        state.selectedWeather = weather;
        state.selectedTraffic = traffic;
        state.selectedRoadSurface = roadSurface;
        state.selectedLocationTypes = locationTypes;
        state.showMarkers = true;
        state.showHeatmap = false;
        document.getElementById('markerToggle').classList.add('active');
        document.getElementById('heatmapToggle').classList.remove('active');
        debouncedUpdateMap();
        closeSidebarOnMobile();
    });
}

function populateCheckboxes(elementId, items, filterType) {
    const container = document.getElementById(elementId);
    container.innerHTML = '';
    const t = translations[currentLanguage];
    
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'filter-buttons';
    
    const selectAllBtn = document.createElement('button');
    selectAllBtn.className = 'filter-btn';
    selectAllBtn.textContent = t.selectAll;
    
    const deselectAllBtn = document.createElement('button');
    deselectAllBtn.className = 'filter-btn deselect';
    deselectAllBtn.textContent = t.deselectAll;
    
    buttonContainer.appendChild(selectAllBtn);
    buttonContainer.appendChild(deselectAllBtn);
    container.appendChild(buttonContainer);
    
    items.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'filter-option';
        const id = filterType + '-' + idx;
        const displayText = translateCategory(item, currentLanguage);
        div.innerHTML = `<input type="checkbox" id="${id}" class="${filterType}-filter" checked>
                         <label for="${id}">${displayText}</label>`;
        container.appendChild(div);
    });
    
    const stateKeyMap = {
        'severity': 'selectedSeverities',
        'type': 'selectedTypes',
        'weather': 'selectedWeather',
        'traffic': 'selectedTraffic',
        'road': 'selectedRoadSurface',
        'location': 'selectedLocationTypes'
    };
    
    selectAllBtn.addEventListener('click', () => {
        document.querySelectorAll(`.${filterType}-filter`).forEach(cb => cb.checked = true);
        updateFilterState();
    });
    
    deselectAllBtn.addEventListener('click', () => {
        document.querySelectorAll(`.${filterType}-filter`).forEach(cb => cb.checked = false);
        updateFilterState();
    });
    
    function updateFilterState() {
        const items_list = document.querySelectorAll(`.${filterType}-filter`);
        const stateKey = stateKeyMap[filterType];
        
        state[stateKey] = Array.from(items_list)
            .filter(cb => cb.checked)
            .map(cb => {
                const idx = parseInt(cb.id.split('-')[1]);
                return items[idx];
            });
        
        debouncedUpdateMap();
    }
    
    document.querySelectorAll(`.${filterType}-filter`).forEach((checkbox) => {
        checkbox.addEventListener('change', updateFilterState);
    });
}

function getSeverityColor(severity) {
    if (severity.includes('SMRTNI')) return '#8b0000';
    if (severity.includes('HUDO TELESNO') || severity.includes('HUDO')) return '#dc3545';
    if (severity.includes('LAŽJ') || severity.includes('LAJO')) return '#fd7e14';
    // Property damage, and NEDOLOČENO for the rare row where the source states
    // no severity at all. Both fall through to the same colour deliberately.
    return '#0066cc';
}

function getSeverityIntensity(severity) {
    if (severity.includes('SMRTNI')) return 1.0;
    if (severity.includes('HUDO TELESNO') || severity.includes('HUDO')) return 0.8;
    if (severity.includes('LAŽJ') || severity.includes('LAJO')) return 0.5;
    return 0.2;
}

function getFilteredAccidents() {
    const yearFilter = document.getElementById('yearFilter');
    const selectedYear = yearFilter.value ? parseInt(yearFilter.value) : null;
    const source = selectedYear ? (dataIndex.byYear.get(selectedYear) || []) : allData;
    const selectedSeverities = new Set(state.selectedSeverities);
    const selectedTypes = new Set(state.selectedTypes);
    const selectedWeather = new Set(state.selectedWeather);
    const selectedTraffic = new Set(state.selectedTraffic);
    const selectedRoadSurface = new Set(state.selectedRoadSurface);
    const selectedLocationTypes = new Set(state.selectedLocationTypes);

    return source.filter(accident => {
        const passSeverity = selectedSeverities.has(accident.KlasifikacijaNesrece);
        const passType = selectedTypes.has(accident.TipNesrece);
        const passWeather = selectedWeather.has(accident.VremenskeOkoliscine) || !accident.VremenskeOkoliscine;
        const passTraffic = selectedTraffic.has(accident.StanjePrometa) || !accident.StanjePrometa;
        const passRoad = selectedRoadSurface.has(accident.StanjeVozisca) || !accident.StanjeVozisca;
        const passLocation = selectedLocationTypes.has(accident.VNaselju) || !accident.VNaselju;

        return passSeverity && passType && passWeather && passTraffic && passRoad && passLocation;
    });
}

function groupAccidentsByLocation(accidents) {
    const locationMap = new Map();
    accidents.forEach(accident => {
        const key = `${accident.latitude},${accident.longitude}`;
        if (!locationMap.has(key)) {
            locationMap.set(key, []);
        }
        locationMap.get(key).push(accident);
    });
    return locationMap;
}

function createSmartMarker(latlng, accidents, isMultiple) {
    const color = getSeverityColor(accidents[0].KlasifikacijaNesrece);
    const t = translations[currentLanguage];
    
    let popupContent = '';
    if (isMultiple) {
        popupContent = `<div style="font-family: Arial, sans-serif; font-size: 12px;">
            <b>${accidents.length} ${t.accidentsAtLocation}</b><br>
            <small style="color: #666;">${t.clickToSpread}</small>
        </div>`;
    } else {
        const a = accidents[0];
        popupContent = `<div style="font-family: Arial, sans-serif; font-size: 12px;">
            <b>${a.TekstCesteNaselja}</b><br>
            <small>${t.date} ${a.DatumPN} ${a.UraPN}</small><br>
            <small>${t.typeLabel} ${a.TipNesrece}</small><br>
            <small>${t.severityLabel} ${translateCategory(a.KlasifikacijaNesrece, currentLanguage)}</small>
        </div>`;
    }
    
    let iconSize = [12, 12];
    let svgContent = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14" fill="${color}"><circle cx="7" cy="7" r="6" stroke="white" stroke-width="1"/></svg>`;
    
    if (isMultiple) {
        iconSize = [24, 24];
        svgContent = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" fill="${color}" stroke="white" stroke-width="2"/>
            <circle cx="12" cy="12" r="8" fill="none" stroke="white" stroke-width="1.5" opacity="0.8"/>
            <text x="12" y="16" font-size="10" font-weight="bold" fill="white" text-anchor="middle" font-family="Arial, sans-serif">${accidents.length}</text>
        </svg>`;
    }
    
    const marker = L.marker(latlng, {
        icon: L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(svgContent),
            iconSize: iconSize,
            iconAnchor: [iconSize[0]/2, iconSize[0]/2]
        })
    });
    
    marker.accidentCount = accidents.length;
    marker.bindPopup(popupContent);
    
    if (isMultiple) {
        const locationKey = `${latlng.lat},${latlng.lng}`;
        marker.on('click', function(e) {
            if (expandedWebs.has(locationKey)) {
                collapseWeb(locationKey);
            } else {
                spreadMarkersInWeb(latlng, accidents, color, locationKey);
                expandedWebs.add(locationKey);
            }
            e.originalEvent.stopPropagation();
        });
    }
    
    return marker;
}

function spreadMarkersInWeb(centerLatlng, accidents, baseColor, locationKey) {
    const count = accidents.length;
    const radius = 0.00002 + (count * 0.00003);
    const angleSlice = (Math.PI * 2) / Math.max(count, 1);
    const t = translations[currentLanguage];
    
    spiderMarkers[locationKey] = [];
    
    accidents.forEach((accident, index) => {
        const angle = angleSlice * index;
        const cosLat = Math.cos(centerLatlng.lat * Math.PI / 180);
        const offsetLat = centerLatlng.lat + (radius * Math.cos(angle));
        const offsetLng = centerLatlng.lng + (radius * Math.sin(angle) / cosLat);
        
        const color = getSeverityColor(accident.KlasifikacijaNesrece);
        const popupContent = `<div style="font-family: Arial, sans-serif; font-size: 12px;">
            <b>${accident.TekstCesteNaselja}</b><br>
            <small>${t.date} ${accident.DatumPN} ${accident.UraPN}</small><br>
            <small>${t.typeLabel} ${accident.TipNesrece}</small><br>
            <small>${t.severityLabel} ${translateCategory(accident.KlasifikacijaNesrece, currentLanguage)}</small><br>
            <hr style="margin: 4px 0; border: none; border-top: 1px solid #ddd;">
            <small style="color: #999;">${t.partOf} ${count} ${t.accidentsAtLocation}</small>
        </div>`;
        
        const spiderMarker = L.marker([offsetLat, offsetLng], {
            icon: L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14" fill="${color}"><circle cx="7" cy="7" r="5" stroke="white" stroke-width="1.5"/></svg>`),
                iconSize: [14, 14],
                iconAnchor: [7, 7]
            })
        });
        
        spiderMarker.bindPopup(popupContent);
        spiderMarker.addTo(state.markerGroup);
        spiderMarkers[locationKey].push(spiderMarker);
        
        const line = L.polyline([centerLatlng, [offsetLat, offsetLng]], {
            color: baseColor,
            weight: 1,
            opacity: 0.4,
            dashArray: '3, 3'
        });
        line.addTo(state.markerGroup);
        spiderMarkers[locationKey].push(line);
    });
}

function collapseWeb(locationKey) {
    if (spiderMarkers[locationKey]) {
        spiderMarkers[locationKey].forEach(item => {
            state.markerGroup.removeLayer(item);
        });
        expandedWebs.delete(locationKey);
        delete spiderMarkers[locationKey];
    }
}

function updateMap() {
    const filtered = getFilteredAccidents();
    const currentZoom = map.getZoom();
    
    expandedWebs.forEach(key => {
        if (spiderMarkers[key]) {
            collapseWeb(key);
        }
    });
    expandedWebs.clear();
    
    if (state.markerGroup && map.hasLayer(state.markerGroup)) {
        map.removeLayer(state.markerGroup);
    }
    
    if (state.heatmapLayer && map.hasLayer(state.heatmapLayer)) {
        map.removeLayer(state.heatmapLayer);
    }
    
    if (state.showMarkers) {
        state.markerGroup = L.markerClusterGroup({
            maxClusterRadius: currentZoom < 14 ? 80 : 50,
            disableClusteringAtZoom: 17,
            chunkedLoading: true,
            chunkInterval: 200,
            iconCreateFunction: function(cluster) {
                let totalAccidents = 0;
                cluster.getAllChildMarkers().forEach(marker => {
                    totalAccidents += (marker.accidentCount || 1);
                });
                
                const c = ' marker-cluster-';
                if (totalAccidents < 10) {
                    return new L.DivIcon({
                        html: '<div><span>' + totalAccidents + '</span></div>',
                        className: 'marker-cluster' + c + 'small',
                        iconSize: new L.Point(40, 40)
                    });
                } else if (totalAccidents < 100) {
                    return new L.DivIcon({
                        html: '<div><span>' + totalAccidents + '</span></div>',
                        className: 'marker-cluster' + c + 'medium',
                        iconSize: new L.Point(40, 40)
                    });
                } else {
                    return new L.DivIcon({
                        html: '<div><span>' + totalAccidents + '</span></div>',
                        className: 'marker-cluster' + c + 'large',
                        iconSize: new L.Point(40, 40)
                    });
                }
            }
        });
        
        const locationMap = groupAccidentsByLocation(filtered);
        const markers = [];
        locationMap.forEach((accidents, key) => {
            const [lat, lng] = key.split(',').map(Number);
            const latlng = L.latLng(lat, lng);
            const isMultiple = accidents.length > 1;
            const marker = createSmartMarker(latlng, accidents, isMultiple);
            markers.push(marker);
        });
        state.markerGroup.addLayers(markers);
        
        map.addLayer(state.markerGroup);
    }
    
    if (state.showHeatmap) {
        const heatmapData = filtered.map(accident => {
            return [
                accident.latitude,
                accident.longitude,
                getSeverityIntensity(accident.KlasifikacijaNesrece)
            ];
        });
        
        state.heatmapLayer = L.heatLayer(heatmapData, {
            radius: 18,
            blur: 12,
            maxZoom: 16,
            minOpacity: 0.1,
            max: 1.0,
            gradient: {
                0.0: 'rgba(0, 102, 204, 0)',
                0.2: 'rgba(0, 204, 0, 0.4)',
                0.4: 'rgba(255, 255, 0, 0.5)',
                0.6: 'rgba(255, 102, 0, 0.6)',
                1.0: 'rgba(255, 0, 0, 0.8)'
            }
        });
        
        map.addLayer(state.heatmapLayer);
    }
    
    updateStats(filtered);
}

function updateStats(accidents) {
    const stats = {
        total: accidents.length,
        serious: 0,
        minor: 0,
        property: 0,
        fatal: 0
    };
    
    accidents.forEach(a => {
        if (a.KlasifikacijaNesrece.includes('SMRTNI')) stats.fatal++;
        else if (a.KlasifikacijaNesrece.includes('HUDO TELESNO') || a.KlasifikacijaNesrece.includes('HUDO')) stats.serious++;
        else if (a.KlasifikacijaNesrece.includes('LAŽJ') || a.KlasifikacijaNesrece.includes('LAJO')) stats.minor++;
        // NEDOLOČENO lands here too. The source leaves severity blank on a
        // single row out of 202k, and counting it as property damage keeps the
        // four buckets summing to the total, which is worth more than isolating
        // one unclassifiable accident.
        else stats.property++;
    });
    
    document.getElementById('statCount').textContent = stats.total.toLocaleString();
    document.getElementById('statSerious').textContent = stats.serious;
    document.getElementById('statMinor').textContent = stats.minor;
    document.getElementById('statProperty').textContent = stats.property;
    document.getElementById('statFatal').textContent = stats.fatal;
}

loadAccidentData();
