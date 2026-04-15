/* PrintCostCalc — IndexedDB & Offline Sync */

(function () {
    var DB_NAME = 'PrintCostCalcDB';
    var DB_VERSION = 1;
    var db = null;

    function openDB() {
        return new Promise(function (resolve, reject) {
            if (db) { resolve(db); return; }
            var req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = function (e) {
                var d = e.target.result;
                if (!d.objectStoreNames.contains('calculations')) {
                    d.createObjectStore('calculations', { keyPath: 'uuid' });
                }
                if (!d.objectStoreNames.contains('printer_profiles')) {
                    d.createObjectStore('printer_profiles', { keyPath: 'id' });
                }
                if (!d.objectStoreNames.contains('settings')) {
                    d.createObjectStore('settings', { keyPath: 'id' });
                }
                if (!d.objectStoreNames.contains('pending_sync')) {
                    d.createObjectStore('pending_sync', { keyPath: 'uuid' });
                }
            };
            req.onsuccess = function (e) {
                db = e.target.result;
                resolve(db);
            };
            req.onerror = function () { reject(req.error); };
        });
    }

    function putItem(storeName, item) {
        return openDB().then(function (d) {
            return new Promise(function (resolve, reject) {
                var tx = d.transaction(storeName, 'readwrite');
                tx.objectStore(storeName).put(item);
                tx.oncomplete = function () { resolve(); };
                tx.onerror = function () { reject(tx.error); };
            });
        });
    }

    function getAllItems(storeName) {
        return openDB().then(function (d) {
            return new Promise(function (resolve, reject) {
                var tx = d.transaction(storeName, 'readonly');
                var req = tx.objectStore(storeName).getAll();
                req.onsuccess = function () { resolve(req.result); };
                req.onerror = function () { reject(req.error); };
            });
        });
    }

    function deleteItem(storeName, key) {
        return openDB().then(function (d) {
            return new Promise(function (resolve, reject) {
                var tx = d.transaction(storeName, 'readwrite');
                tx.objectStore(storeName).delete(key);
                tx.oncomplete = function () { resolve(); };
                tx.onerror = function () { reject(tx.error); };
            });
        });
    }

    // ── Sync: Download server data to IndexedDB ──────────────────────
    function syncFromServer() {
        if (!navigator.onLine) return Promise.resolve();
        var promises = [];

        promises.push(
            fetch('/api/calculations')
                .then(function (r) { return r.json(); })
                .then(function (calcs) {
                    var p = [];
                    calcs.forEach(function (c) { p.push(putItem('calculations', c)); });
                    return Promise.all(p);
                })
                .catch(function () { })
        );

        promises.push(
            fetch('/api/printer-profiles')
                .then(function (r) { return r.json(); })
                .then(function (profiles) {
                    var p = [];
                    profiles.forEach(function (pr) { p.push(putItem('printer_profiles', pr)); });
                    return Promise.all(p);
                })
                .catch(function () { })
        );

        promises.push(
            fetch('/api/settings')
                .then(function (r) { return r.json(); })
                .then(function (s) {
                    s.id = 1;
                    return putItem('settings', s);
                })
                .catch(function () { })
        );

        return Promise.all(promises);
    }

    // ── Sync: Upload pending changes to server ───────────────────────
    function processPendingSync() {
        if (!navigator.onLine) return Promise.resolve();
        return getAllItems('pending_sync').then(function (items) {
            var chain = Promise.resolve();
            items.forEach(function (item) {
                chain = chain.then(function () {
                    var url, method;
                    if (item.action === 'create') {
                        url = '/api/calculations';
                        method = 'POST';
                    } else if (item.action === 'update') {
                        url = '/api/calculations/' + item.uuid;
                        method = 'PUT';
                    } else if (item.action === 'delete') {
                        url = '/api/calculations/' + item.uuid;
                        method = 'DELETE';
                    } else {
                        return deleteItem('pending_sync', item.uuid);
                    }
                    return fetch(url, {
                        method: method,
                        headers: { 'Content-Type': 'application/json' },
                        body: item.action !== 'delete' ? JSON.stringify(item.data) : undefined
                    }).then(function (r) {
                        if (r.ok) return deleteItem('pending_sync', item.uuid);
                    }).catch(function () {
                        // Will retry next time
                    });
                });
            });
            return chain;
        });
    }

    // ── Online event handler ─────────────────────────────────────────
    window.addEventListener('online', function () {
        processPendingSync().then(syncFromServer);
    });

    // ── Initial sync on page load ────────────────────────────────────
    if (navigator.onLine) {
        openDB().then(function () {
            return processPendingSync();
        }).then(function () {
            return syncFromServer();
        }).catch(function (err) {
            console.log('Sync error:', err);
        });
    }

    // ── Expose API for other scripts ─────────────────────────────────
    window.PrintCostCalcSync = {
        openDB: openDB,
        putItem: putItem,
        getAllItems: getAllItems,
        deleteItem: deleteItem,
        syncFromServer: syncFromServer,
        processPendingSync: processPendingSync,
        addPendingAction: function (uuid, action, data) {
            return putItem('pending_sync', { uuid: uuid, action: action, data: data });
        }
    };
})();
