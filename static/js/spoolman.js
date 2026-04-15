/* PrintCostCalc — Spoolman Modal (per filament row) */

document.addEventListener('DOMContentLoaded', function () {
    var modalEl = document.getElementById('spoolmanModal');
    if (!modalEl) return;

    var modal = new bootstrap.Modal(modalEl);
    var loading = document.getElementById('spoolmanLoading');
    var errorDiv = document.getElementById('spoolmanError');
    var emptyDiv = document.getElementById('spoolmanEmpty');
    var table = document.getElementById('spoolmanTable');
    var tbody = document.getElementById('spoolmanBody');
    var filterRow = document.getElementById('spoolmanFilterRow');
    var showAllCheckbox = document.getElementById('spoolmanShowAll');
    var filterLabel = document.getElementById('spoolmanFilterLabel');

    var cachedSpools = [];
    var detectedType = '';

    // Preload spools
    if (navigator.onLine) {
        fetch('/api/spoolman/spools')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (Array.isArray(data)) cachedSpools = data;
            })
            .catch(function () { });
    }

    // Listen for custom event from calculator.js
    document.addEventListener('openSpoolman', function (e) {
        detectedType = (e.detail && e.detail.filterType) ? e.detail.filterType.toUpperCase() : '';

        if (detectedType && detectedType !== 'SONSTIGE') {
            filterLabel.textContent = detectedType;
            filterRow.classList.remove('d-none');
            showAllCheckbox.checked = false;
        } else {
            filterRow.classList.add('d-none');
            showAllCheckbox.checked = true;
        }

        if (cachedSpools.length > 0) {
            loading.classList.add('d-none');
            errorDiv.classList.add('d-none');
            emptyDiv.classList.add('d-none');
            renderSpools();
            table.classList.remove('d-none');
            modal.show();
            return;
        }

        loading.classList.remove('d-none');
        errorDiv.classList.add('d-none');
        emptyDiv.classList.add('d-none');
        table.classList.add('d-none');
        tbody.innerHTML = '';
        modal.show();

        fetch('/api/spoolman/spools')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                loading.classList.add('d-none');
                if (data.error) {
                    errorDiv.textContent = data.error;
                    errorDiv.classList.remove('d-none');
                    return;
                }
                if (!Array.isArray(data) || data.length === 0) {
                    errorDiv.textContent = 'Keine Spulen gefunden.';
                    errorDiv.classList.remove('d-none');
                    return;
                }
                cachedSpools = data;
                renderSpools();
            })
            .catch(function () {
                loading.classList.add('d-none');
                errorDiv.textContent = 'Verbindung fehlgeschlagen.';
                errorDiv.classList.remove('d-none');
            });
    });

    showAllCheckbox.addEventListener('change', renderSpools);

    function renderSpools() {
        tbody.innerHTML = '';
        var filterActive = detectedType && !showAllCheckbox.checked;
        var shown = 0;

        cachedSpools.forEach(function (spool) {
            if (filterActive) {
                var spoolType = (spool.material || spool.filament_type || '').toUpperCase();
                if (spoolType && spoolType !== detectedType) return;
            }
            shown++;
            var tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.innerHTML =
                '<td><span class="spool-color" style="background-color:' +
                (spool.color_hex ? '#' + spool.color_hex : '#ccc') + '"></span></td>' +
                '<td>' + escHtml(spool.name) + '</td>' +
                '<td>' + escHtml(spool.material) + '</td>' +
                '<td>' + escHtml(spool.location || '') + '</td>' +
                '<td>' + (spool.remaining_weight != null ? Math.round(spool.remaining_weight) + ' g' : '-') + '</td>' +
                '<td>' + (spool.price != null ? parseFloat(spool.price).toFixed(2) + ' ' + CURRENCY : '-') + '</td>' +
                '<td><button type="button" class="btn btn-sm btn-accent">Wählen</button></td>';
            tr.querySelector('button').addEventListener('click', function () {
                if (window.onSpoolSelected) window.onSpoolSelected(spool);
                modal.hide();
            });
            tbody.appendChild(tr);
        });

        if (shown > 0) {
            table.classList.remove('d-none');
            emptyDiv.classList.add('d-none');
        } else {
            table.classList.add('d-none');
            emptyDiv.classList.remove('d-none');
        }
    }

    function escHtml(str) {
        var div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }
});
