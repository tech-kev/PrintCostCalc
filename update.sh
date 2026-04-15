#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

INSTALL_DIR="/opt/printcostcalc"

if [[ $EUID -ne 0 ]]; then
    echo -e "  \033[0;31m✖\033[0m  Dieses Script muss als root ausgeführt werden: ${BOLD}sudo bash update.sh${NC}"
    exit 1
fi

echo ""
echo -e "  ${CYAN}PrintCostCalc — Update${NC}"
echo ""

cd "$INSTALL_DIR"

echo -e "  ${DIM}[1/3]${NC} Lade neueste Version..."
sudo -u printcostcalc git pull --quiet 2>/dev/null || git pull --quiet
echo -e "  ${GREEN}✔${NC}  Repository aktualisiert"

echo -e "  ${DIM}[2/3]${NC} Aktualisiere Abhängigkeiten..."
"$INSTALL_DIR/venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"
echo -e "  ${GREEN}✔${NC}  Abhängigkeiten aktualisiert"

echo -e "  ${DIM}[3/3]${NC} Starte Services neu..."
systemctl restart printcostcalc
if systemctl is-enabled --quiet printsync 2>/dev/null; then
    systemctl restart printsync
fi
echo -e "  ${GREEN}✔${NC}  Services neugestartet"

echo ""
echo -e "  ${GREEN}✔${NC}  Update abgeschlossen!"
echo ""
