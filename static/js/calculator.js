/* PrintCostCalc — Live Calculator & Form Logic */

document.addEventListener('DOMContentLoaded', function () {
    // ── Element references ───────────────────────────────────────────
    var printHours = document.getElementById('printHours');
    var printMinutes = document.getElementById('printMinutes');
    var filamentWeight = document.getElementById('filamentWeight');
    var markupSlider = document.getElementById('markupSlider');
    var markupValue = document.getElementById('markupValue');
    var filamentCostDisplay = document.getElementById('filamentCostDisplay');

    var electricityToggle = document.getElementById('electricityToggle');
    var powerConsumption = document.getElementById('powerConsumption');
    var energyCost = document.getElementById('energyCost');
    var electricityCostDisplay = document.getElementById('electricityCostDisplay');

    var laborToggle = document.getElementById('laborToggle');
    var prepTime = document.getElementById('prepTime');
    var prepCost = document.getElementById('prepCost');
    var postTime = document.getElementById('postTime');
    var postCost = document.getElementById('postCost');
    var laborCostDisplay = document.getElementById('laborCostDisplay');

    var machineToggle = document.getElementById('machineToggle');
    var machinePurchasePrice = document.getElementById('machinePurchasePrice');
    var machineReturnYears = document.getElementById('machineReturnYears');
    var machineDailyHoursSlider = document.getElementById('machineDailyHoursSlider');
    var dailyHoursValue = document.getElementById('dailyHoursValue');
    var machineRepairSlider = document.getElementById('machineRepairSlider');
    var repairValue = document.getElementById('repairValue');
    var machineCostDisplay = document.getElementById('machineCostDisplay');

    var vatPercent = document.getElementById('vatPercent');
    var subtotalDisplay = document.getElementById('subtotalDisplay');
    var calculatedPriceDisplay = document.getElementById('calculatedPriceDisplay');
    var totalPriceDisplay = document.getElementById('totalPriceDisplay');
    var otherCostDisplay = document.getElementById('otherCostDisplay');
    var finalPriceOverride = document.getElementById('finalPriceOverride');
    var printerProfile = document.getElementById('printerProfile');

    // ── UUID generation ──────────────────────────────────────────────
    var uuidField = document.getElementById('calcUuid');
    if (uuidField && !uuidField.value) {
        uuidField.value = crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0;
            return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
    }

    function val(el) { return parseFloat(el.value) || 0; }
    function fmt(n) { return n.toFixed(2).replace('.', ','); }
    function escAttr(s) { return (s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }

    // ── Dynamic Filaments ─────────────────────────────────────────────
    var filamentsList = document.getElementById('filamentsList');
    var filamentsJsonField = document.getElementById('filamentsJson');
    var addFilamentBtn = document.getElementById('addFilament');
    var hasSpoolman = !!document.getElementById('spoolmanModal');
    var filamentTypes = ['PLA', 'PETG', 'ABS', 'ASA', 'TPU', 'Nylon', 'PC', 'Sonstige'];

    // Load filament types from Spoolman
    if (hasSpoolman && navigator.onLine) {
        fetch('/api/spoolman/spools')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!Array.isArray(data) || data.length === 0) return;
                var seen = {};
                var types = [];
                data.forEach(function (s) {
                    var mat = (s.material || '').toUpperCase();
                    if (mat && !seen[mat]) { seen[mat] = true; types.push(mat); }
                });
                types.sort();
                if (types.length > 0) {
                    types.push('Sonstige');
                    filamentTypes = types;
                    // Update all existing selects
                    filamentsList.querySelectorAll('.fil-type').forEach(function (sel) {
                        populateTypeSelect(sel, sel.value || 'PLA');
                    });
                }
            })
            .catch(function () { });
    }

    function populateTypeSelect(sel, currentVal) {
        var val = (sel.tagName === 'SELECT' ? sel.value : sel) || currentVal || 'PLA';
        if (sel.tagName !== 'SELECT') return;
        sel.innerHTML = '';
        filamentTypes.forEach(function (t) {
            var opt = document.createElement('option');
            opt.value = t;
            opt.textContent = t;
            if (t.toUpperCase() === (currentVal || '').toUpperCase()) opt.selected = true;
            sel.appendChild(opt);
        });
        if (!sel.value) {
            var opt = document.createElement('option');
            opt.value = currentVal;
            opt.textContent = currentVal;
            opt.selected = true;
            sel.insertBefore(opt, sel.firstChild);
        }
    }

    function addFilamentRow(data) {
        data = data || {};
        var row = document.createElement('div');
        row.className = 'filament-row card card-body p-2 mb-2';
        if (data.location) row.dataset.location = data.location;

        var html = '<div class="row g-2 align-items-end">';
        if (data.location) {
            html += '<div class="col-auto d-flex align-items-end"><span class="badge bg-secondary mb-1">Ort ' + escAttr(data.location) + '</span></div>';
        }
        html +=
            '<div class="col">' +
            '<label class="form-label small mb-0">Name</label>' +
            '<input type="text" class="form-control form-control-sm fil-name" value="' + escAttr(data.name || '') + '">' +
            '</div>' +
            '<div class="col-auto" style="width:110px">' +
            '<label class="form-label small mb-0">Typ</label>' +
            '<select class="form-select form-select-sm fil-type"></select>' +
            '</div>' +
            '<div class="col-auto" style="width:100px">' +
            '<label class="form-label small mb-0">Gramm</label>' +
            '<input type="number" class="form-control form-control-sm fil-grams" step="0.01" min="0" value="' + (data.grams_used || 0) + '">' +
            '</div>' +
            '<div class="col-auto" style="width:90px">' +
            '<label class="form-label small mb-0">Preis</label>' +
            '<input type="number" class="form-control form-control-sm fil-price" step="0.01" min="0" value="' + (data.spool_price || 0) + '">' +
            '</div>' +
            '<div class="col-auto" style="width:90px">' +
            '<label class="form-label small mb-0">Spule (g)</label>' +
            '<input type="number" class="form-control form-control-sm fil-weight" step="1" min="1" value="' + (data.spool_weight || 1000) + '">' +
            '</div>';
        if (hasSpoolman) {
            html += '<div class="col-auto d-flex align-items-end">' +
                '<button type="button" class="btn btn-sm btn-outline-secondary fil-spoolman mb-0" title="Aus Spoolman laden"><i class="bi bi-cloud-download"></i></button>' +
                '</div>';
        }
        html += '<div class="col-auto d-flex align-items-end">' +
            '<button type="button" class="btn btn-sm btn-outline-danger remove-fil mb-0"><i class="bi bi-x-lg"></i></button>' +
            '</div></div>';
        row.innerHTML = html;

        filamentsList.appendChild(row);

        // Populate type dropdown
        populateTypeSelect(row.querySelector('.fil-type'), data.filament_type || 'PLA');

        row.querySelector('.remove-fil').addEventListener('click', function () {
            row.remove();
            updateFilamentsJson();
            calculate();
        });
        row.querySelectorAll('input').forEach(function (inp) {
            inp.addEventListener('input', function () {
                updateFilamentsJson();
                calculate();
            });
        });

        // Spoolman button per row
        var spBtn = row.querySelector('.fil-spoolman');
        if (spBtn) {
            spBtn.addEventListener('click', function () {
                var rowType = row.querySelector('.fil-type').value.toUpperCase();
                openSpoolmanForRow(row, rowType);
            });
        }

        return row;
    }

    function updateFilamentsJson() {
        var items = [];
        filamentsList.querySelectorAll('.filament-row').forEach(function (row) {
            items.push({
                name: row.querySelector('.fil-name').value,
                filament_type: row.querySelector('.fil-type').value,
                grams_used: parseFloat(row.querySelector('.fil-grams').value) || 0,
                spool_price: parseFloat(row.querySelector('.fil-price').value) || 0,
                spool_weight: parseFloat(row.querySelector('.fil-weight').value) || 1000,
                location: row.dataset.location || '',
            });
        });
        filamentsJsonField.value = JSON.stringify(items);
    }

    function getFilamentsCost() {
        var total = 0;
        var markup = 1 + val(markupSlider) / 100;
        filamentsList.querySelectorAll('.filament-row').forEach(function (row) {
            var grams = parseFloat(row.querySelector('.fil-grams').value) || 0;
            var price = parseFloat(row.querySelector('.fil-price').value) || 0;
            var weight = parseFloat(row.querySelector('.fil-weight').value) || 1000;
            if (weight > 0) total += (grams / weight) * price * markup;
        });
        return total;
    }

    addFilamentBtn.addEventListener('click', function () {
        var isFirst = filamentsList.querySelectorAll('.filament-row').length === 0;
        addFilamentRow({
            filament_type: 'PLA',
            spool_weight: 1000,
            grams_used: isFirst ? val(filamentWeight) : 0
        });
        updateFilamentsJson();
    });

    // Load existing filaments or add default row
    var loadedFilaments = false;
    try {
        var existingFil = JSON.parse(filamentsJsonField.value);
        if (Array.isArray(existingFil) && existingFil.length > 0) {
            existingFil.forEach(function (f) { addFilamentRow(f); });
            loadedFilaments = true;
        }
    } catch (e) { }
    if (!loadedFilaments) {
        addFilamentRow({
            filament_type: 'PLA',
            spool_weight: 1000,
            grams_used: val(filamentWeight)
        });
    }

    // ── Spoolman Modal (per filament row) ─────────────────────────────
    var activeFilamentRow = null;

    function openSpoolmanForRow(row, filterType) {
        activeFilamentRow = row;
        // Dispatch custom event that spoolman.js listens for
        var evt = new CustomEvent('openSpoolman', { detail: { filterType: filterType } });
        document.dispatchEvent(evt);
    }

    // Called by spoolman.js when a spool is selected
    window.onSpoolSelected = function (spool) {
        if (!activeFilamentRow) return;
        activeFilamentRow.querySelector('.fil-name').value = spool.name || '';
        activeFilamentRow.querySelector('.fil-type').value = spool.filament_type || spool.material || 'PLA';
        activeFilamentRow.querySelector('.fil-price').value = spool.price || 0;
        activeFilamentRow.querySelector('.fil-weight').value = spool.spool_weight || 1000;
        if (spool.location) activeFilamentRow.dataset.location = spool.location;
        updateFilamentsJson();
        calculate();
        activeFilamentRow = null;
    };

    // ── Auto-match filaments from filename locations ────────────────
    function matchFilamentsFromFilename(filename, totalWeight) {
        // Parse pattern: "7+53_name.gcode.3mf" -> locations ["7", "53"]
        var basename = filename.replace(/\.(gcode\.3mf|3mf|gcode|gco)$/i, '');
        var m = basename.match(/^([\d+]+)_/);
        if (!m) return;
        var locations = m[1].split('+').filter(function (s) { return s.trim(); });
        if (locations.length === 0) return;

        // Fetch spools from Spoolman
        fetch('/api/spoolman/spools')
            .then(function (r) { return r.json(); })
            .then(function (spools) {
                if (!Array.isArray(spools) || spools.length === 0) return;

                // Clear existing filament rows
                filamentsList.innerHTML = '';

                var perSpool = locations.length > 0 ? Math.round((totalWeight / locations.length) * 100) / 100 : 0;

                locations.forEach(function (loc) {
                    var data = {
                        name: '', spool_price: 0, spool_weight: 1000,
                        grams_used: perSpool, filament_type: 'PLA', location: loc
                    };
                    for (var i = 0; i < spools.length; i++) {
                        if (String(spools[i].location || '') === loc) {
                            data.name = spools[i].name || '';
                            data.spool_price = spools[i].price || 0;
                            data.spool_weight = spools[i].spool_weight || 1000;
                            data.filament_type = spools[i].filament_type || 'PLA';
                            break;
                        }
                    }
                    addFilamentRow(data);
                });

                updateFilamentsJson();
                calculate();
            })
            .catch(function () { });
    }

    // ── Live calculation ─────────────────────────────────────────────
    function calculate() {
        var hours = val(printHours) + val(printMinutes) / 60;

        var filCost = getFilamentsCost();
        filamentCostDisplay.textContent = fmt(filCost) + ' ' + CURRENCY;

        var elecCost = 0;
        if (electricityToggle.checked) {
            elecCost = (val(powerConsumption) / 1000) * hours * val(energyCost);
        }
        electricityCostDisplay.textContent = fmt(elecCost) + ' ' + CURRENCY;

        var labCost = 0;
        if (laborToggle.checked) {
            labCost = (val(prepTime) / 60 * val(prepCost)) + (val(postTime) / 60 * val(postCost));
        }
        laborCostDisplay.textContent = fmt(labCost) + ' ' + CURRENCY;

        var machCost = 0;
        if (machineToggle.checked) {
            var yrs = val(machineReturnYears);
            var dh = val(machineDailyHoursSlider);
            if (yrs > 0 && dh > 0) {
                machCost = (val(machinePurchasePrice) * (1 + val(machineRepairSlider) / 100))
                    / (yrs * 365 * dh) * hours;
            }
        }
        machineCostDisplay.textContent = fmt(machCost) + ' ' + CURRENCY;

        var otherTotal = getOtherCostsTotal();
        otherCostDisplay.textContent = fmt(otherTotal) + ' ' + CURRENCY;

        var subtotal = filCost + elecCost + labCost + machCost + otherTotal;
        var vat = val(vatPercent);
        var calculated = subtotal * (1 + vat / 100);
        subtotalDisplay.textContent = fmt(subtotal);
        calculatedPriceDisplay.textContent = fmt(calculated);

        var overrideVal = parseFloat(finalPriceOverride.value);
        totalPriceDisplay.textContent = fmt(overrideVal > 0 ? overrideVal : calculated);
        window._calculatedPrice = calculated;
    }

    // ── Sliders ──────────────────────────────────────────────────────
    markupSlider.addEventListener('input', function () {
        markupValue.textContent = this.value + '%';
        calculate();
    });
    machineDailyHoursSlider.addEventListener('input', function () {
        dailyHoursValue.textContent = this.value + ' Std';
        calculate();
    });
    machineRepairSlider.addEventListener('input', function () {
        repairValue.textContent = this.value + '%';
        calculate();
    });

    document.querySelectorAll('.calc-input').forEach(function (el) {
        el.addEventListener('input', calculate);
    });

    // Sync filament weight field to single filament row
    filamentWeight.addEventListener('input', function () {
        var rows = filamentsList.querySelectorAll('.filament-row');
        if (rows.length === 1) {
            rows[0].querySelector('.fil-grams').value = this.value;
            updateFilamentsJson();
        }
    });

    // ── Toggle sections ──────────────────────────────────────────────
    document.querySelectorAll('.toggle-section').forEach(function (toggle) {
        toggle.addEventListener('change', function () {
            var target = document.getElementById(this.dataset.section);
            if (this.checked) target.classList.remove('section-disabled');
            else target.classList.add('section-disabled');
            calculate();
        });
    });

    // ── Printer profile ──────────────────────────────────────────────
    function applyPrinterProfile() {
        var id = parseInt(printerProfile.value);
        if (id && printerProfilesMap[id]) {
            var p = printerProfilesMap[id];
            powerConsumption.value = p.power_consumption;
            energyCost.value = p.energy_cost_per_kwh;
            machinePurchasePrice.value = p.purchase_price;
            machineReturnYears.value = p.investment_return_years;
            machineDailyHoursSlider.value = p.daily_usage_hours;
            dailyHoursValue.textContent = p.daily_usage_hours + ' Std';
            machineRepairSlider.value = p.repair_cost_percent;
            repairValue.textContent = p.repair_cost_percent + '%';
            electricityToggle.checked = true;
            document.getElementById('electricityFields').classList.remove('section-disabled');
            machineToggle.checked = true;
            document.getElementById('machineFields').classList.remove('section-disabled');
            calculate();
        }
    }
    printerProfile.addEventListener('change', applyPrinterProfile);

    // ── File upload ──────────────────────────────────────────────────
    var fileUpload = document.getElementById('fileUpload');
    var fileStatus = document.getElementById('fileStatus');
    fileUpload.addEventListener('change', function () {
        var file = this.files[0];
        if (!file) return;
        if (!navigator.onLine) {
            fileStatus.innerHTML = '<span class="text-warning">Offline nicht verfügbar.</span>';
            return;
        }
        fileStatus.innerHTML = '<span class="text-muted"><span class="spinner-border spinner-border-sm"></span> Analysiere...</span>';
        var fd = new FormData();
        fd.append('file', file);
        fetch('/api/parse-file', { method: 'POST', body: fd })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) { fileStatus.innerHTML = '<span class="text-danger">' + data.error + '</span>'; return; }
                fileStatus.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> Analysiert.</span>';
                if (data.printing_time_hours != null) printHours.value = data.printing_time_hours;
                if (data.printing_time_minutes != null) printMinutes.value = data.printing_time_minutes;
                if (data.filament_weight_grams != null) filamentWeight.value = data.filament_weight_grams;
                // Preview images
                var previewImages = data.preview_images || [];
                if (!previewImages.length && data.preview_image_base64) {
                    previewImages = [data.preview_image_base64];
                }
                if (previewImages.length > 0) {
                    document.getElementById('previewImageField').value = previewImages[0];
                    document.getElementById('previewImagesJson').value = JSON.stringify(previewImages);
                    var wrap = document.getElementById('previewImagesWrap');
                    wrap.innerHTML = '';
                    previewImages.forEach(function (b64) {
                        var img = document.createElement('img');
                        img.className = 'img-thumbnail preview-thumb';
                        img.src = 'data:image/png;base64,' + b64;
                        img.style.maxWidth = '180px';
                        img.style.maxHeight = '180px';
                        wrap.appendChild(img);
                    });
                    document.getElementById('previewContainer').style.display = 'block';
                }
                var jobName = document.getElementById('jobName');
                if (!jobName.value) jobName.value = file.name.replace(/\.(3mf|gcode|gco)$/i, '');
                // Match filaments from filename locations
                try {
                    matchFilamentsFromFilename(file.name, data.filament_weight_grams || val(filamentWeight));
                } catch (e) {
                    console.error('Filament matching error:', e);
                }
                calculate();
            })
            .catch(function (err) { fileStatus.innerHTML = '<span class="text-danger">Fehler: ' + (err.message || err) + '</span>'; console.error('File upload error:', err); });
    });

    // ── Dynamic "Other Costs" ────────────────────────────────────────
    var otherCostsList = document.getElementById('otherCostsList');
    var addOtherCostBtn = document.getElementById('addOtherCost');
    var otherCostsJsonField = document.getElementById('otherCostsJson');

    function addOtherCostRow(name, cost) {
        var row = document.createElement('div');
        row.className = 'other-cost-row';
        row.innerHTML =
            '<input type="text" class="form-control other-cost-name" placeholder="Bezeichnung" value="' + (name || '') + '">' +
            '<input type="number" class="form-control other-cost-value calc-input" placeholder="Kosten" step="0.01" min="0" value="' + (cost || '') + '">' +
            '<button type="button" class="btn btn-sm btn-outline-danger remove-other-cost"><i class="bi bi-x-lg"></i></button>';
        otherCostsList.appendChild(row);
        row.querySelector('.remove-other-cost').addEventListener('click', function () { row.remove(); updateOtherCostsJson(); calculate(); });
        row.querySelectorAll('input').forEach(function (inp) { inp.addEventListener('input', function () { updateOtherCostsJson(); calculate(); }); });
    }

    function updateOtherCostsJson() {
        var items = [];
        otherCostsList.querySelectorAll('.other-cost-row').forEach(function (row) {
            var n = row.querySelector('.other-cost-name').value;
            var c = parseFloat(row.querySelector('.other-cost-value').value) || 0;
            if (n || c) items.push({ name: n, cost: c });
        });
        otherCostsJsonField.value = JSON.stringify(items);
    }

    function getOtherCostsTotal() {
        var total = 0;
        otherCostsList.querySelectorAll('.other-cost-value').forEach(function (inp) { total += parseFloat(inp.value) || 0; });
        return total;
    }

    addOtherCostBtn.addEventListener('click', function () { addOtherCostRow('', ''); });
    try {
        var existing = JSON.parse(otherCostsJsonField.value);
        if (Array.isArray(existing)) existing.forEach(function (item) { addOtherCostRow(item.name || '', item.cost || 0); });
    } catch (e) { }

    document.getElementById('calcForm').addEventListener('submit', function () {
        updateFilamentsJson();
        updateOtherCostsJson();
    });

    // ── Final price override + rounding ──────────────────────────────
    finalPriceOverride.addEventListener('input', calculate);
    document.getElementById('roundUp1').addEventListener('click', function () {
        finalPriceOverride.value = Math.ceil(window._calculatedPrice || 0).toFixed(2); calculate();
    });
    document.getElementById('roundUp50ct').addEventListener('click', function () {
        finalPriceOverride.value = (Math.ceil((window._calculatedPrice || 0) * 2) / 2).toFixed(2); calculate();
    });
    document.getElementById('resetOverride').addEventListener('click', function () {
        finalPriceOverride.value = ''; calculate();
    });

    // ── Apply default printer on new calculation ─────────────────────
    if (printerProfile.value && !document.getElementById('calcForm').dataset.edit) {
        applyPrinterProfile();
    }

    calculate();
});
