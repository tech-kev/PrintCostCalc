<p align="center">
  <img src="static/icons/icon.svg" width="80" alt="PrintCostCalc Logo">
</p>

<h1 align="center">PrintCostCalc</h1>

<p align="center">
  <strong>3D-Druck Kostenrechner</strong><br>
  Berechne die tatsächlichen Kosten deiner 3D-Drucke:<br>
  Filament, Strom, Arbeitszeit und Maschinenverschleiß.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.1-green?logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Docker-ready-blue?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Lizenz-MIT-yellow" alt="MIT License">
</p>

<p align="center"><img src="https://raw.githubusercontent.com/tech-kev/PrintCostCalc/refs/heads/main/screenshots/Screenshot01.png"></p>
<p align="center"><img src="https://raw.githubusercontent.com/tech-kev/PrintCostCalc/refs/heads/main/screenshots/Screenshot02.png"></p>
<p align="center"><img src="https://raw.githubusercontent.com/tech-kev/PrintCostCalc/refs/heads/main/screenshots/Screenshot03.png"></p>

---

## Features

| | Feature | Beschreibung |
|---|---|---|
| 🧮 | **Kostenberechnung** | Filament-, Strom-, Arbeits- und Maschinenkosten mit Live-Vorschau |
| 🖨️ | **Druckerprofile** | Strom- und Maschinenkosten automatisch vorbelegen |
| 🎨 | **Multi-Filament** | Mehrere Filamente pro Kalkulation (z.B. Multicolor-Drucke) |
| 🔗 | **Spoolman-Integration** | Filamente direkt aus Spoolman laden inkl. Ort und Preis |
| 📂 | **Drucker-Dateien (FTP)** | 3MF-Dateien automatisch vom Bambu Lab Drucker abrufen |
| 📄 | **PDF-Export** | Übersichtliche Kostenaufstellung als PDF |
| 📱 | **PWA** | Offline-fähig, installierbar auf dem Homescreen |
| 📦 | **3MF/GCode-Parsing** | Druckzeit, Gewicht und Vorschaubild automatisch auslesen |
| 💰 | **Endpreis anpassen** | Manuelles Aufrunden auf 50ct oder 1€ |
| 💾 | **Import / Export** | Kalkulationen, Profile und Einstellungen als JSON sichern und wiederherstellen |
| 👥 | **Benutzerverwaltung** | Admin/User-System mit Login |

---

## Installation

### Option 1: Docker (empfohlen)

```yaml
services:
  printcostcalc:
    image: techkev/printcostcalc:latest
    ports:
      - "5002:5002"
    environment:
      - SECRET_KEY=change-me-to-a-random-secret
    volumes:
      - printcostcalc_data:/app/instance
    restart: unless-stopped

volumes:
  printcostcalc_data:
```

```bash
docker compose up -d
```

> Danach erreichbar unter **http://localhost:5002**

### Option 2: Installer (Debian/Ubuntu/Fedora)

```bash
curl -sL https://raw.githubusercontent.com/tech-kev/PrintCostCalc/main/install.sh | sudo bash
```

Das Script klont das Repository, installiert alle Abhängigkeiten, erstellt einen Systembenutzer, richtet die Python-Umgebung ein und startet PrintCostCalc + PrintSync als systemd-Services.

> Danach erreichbar unter **http://localhost:5002**

#### Update

```bash
sudo bash /opt/printcostcalc/update.sh
```

#### Deinstallation

```bash
sudo bash /opt/printcostcalc/uninstall.sh
```

---

## Konfiguration

### Erster Start

Beim ersten Aufruf erscheint automatisch der **Setup-Assistent** zur Erstellung des Admin-Accounts.

### Einstellungen

| Einstellung | Beschreibung | Standard |
|---|---|---|
| **Spoolman-URL** | Verbindung zu einer Spoolman-Instanz | — |
| **Standard-Aufschlag** | Prozentualer Markup auf Materialpreis | 20% |
| **MwSt.-Satz** | Mehrwertsteuersatz | 19% |
| **Währung** | Währungssymbol | € |
| **Arbeitskosten** | Stundensatz für Vor-/Nachbearbeitung | 15€/Std |
| **Drucker-IP** | IP-Adresse des Bambu Lab Druckers | — |
| **FTP-Zugriffscode** | Access Code des Druckers | — |
| **Auto-Sync** | Automatische Synchronisation alle 5 Minuten | Aus |

### Umgebungsvariablen

| Variable | Beschreibung | Standard |
|---|---|---|
| `SECRET_KEY` | Flask Secret Key (unbedingt ändern!) | `printcostcalc-geheim-aendern` |

---

## PrintSync — Bambu Lab FTP-Sync

**PrintSync** synchronisiert automatisch 3MF-Dateien von deinem Bambu Lab Drucker und stellt sie in PrintCostCalc als Kalkulationsgrundlage bereit.

**Einrichtung:**

1. **Access Code** am Drucker-Display unter *Netzwerk/LAN* ablesen
2. In PrintCostCalc → **Einstellungen** → *Drucker-Synchronisation*:
   - IP-Adresse des Druckers eintragen
   - Access Code eintragen
   - *Verbindung testen* klicken
3. Unter **Drucker-Dateien** auf *Synchronisieren* klicken

Die Dateien erscheinen als Karten mit Vorschaubild, Druckzeit und Gewicht. Per Klick auf *Kalkulation erstellen* werden die Daten ins Formular übernommen — inklusive automatischer Spoolman-Zuordnung anhand des Dateinamens.

> **Dateiname-Schema:** `11+1+49_Modellname.gcode.3mf`
> Die Zahlen vor dem `_` sind Spoolman-Spulenorte und werden automatisch zugeordnet.

PrintSync läuft als eigenständiger Service (`printsync`) und prüft bei aktiviertem Auto-Sync alle 5 Minuten auf neue Dateien.

---

## Spoolman-Integration

1. In **Einstellungen** die Spoolman-URL eintragen (z.B. `http://192.168.1.100:7912`)
2. Mit *Verbindung testen* prüfen
3. Im Kalkulationsformular bei jedem Filament über den <kbd>☁</kbd>-Button eine Spule auswählen — Preis, Gewicht und Typ werden automatisch übernommen

---

## CLI-Benutzerverwaltung

```bash
# Docker
docker compose exec printcostcalc python manage_users.py list
docker compose exec printcostcalc python manage_users.py create <username>
docker compose exec printcostcalc python manage_users.py reset-password <username>

# Installer
cd /opt/printcostcalc
sudo -u printcostcalc venv/bin/python manage_users.py list
sudo -u printcostcalc venv/bin/python manage_users.py create <username>
sudo -u printcostcalc venv/bin/python manage_users.py reset-password <username>
```

---

## Lizenz

MIT License — siehe [LICENSE](LICENSE) für Details.
