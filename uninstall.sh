#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="/opt/printcostcalc"

if [[ $EUID -ne 0 ]]; then
    echo -e "  ${RED}✖${NC}  Dieses Script muss als root ausgeführt werden: ${BOLD}sudo bash uninstall.sh${NC}"
    exit 1
fi

echo ""
echo -e "  ${YELLOW}⚠  PrintCostCalc wird vollständig deinstalliert!${NC}"
echo ""
echo -e "  Folgendes wird entfernt:"
echo -e "    - systemd-Services (printcostcalc, printsync)"
echo -e "    - Systembenutzer printcostcalc"
echo -e "    - Installationsverzeichnis ${BOLD}${INSTALL_DIR}${NC} (inkl. Datenbank!)"
echo ""
echo -ne "  ${BOLD}Fortfahren? [j/N]${NC}: "
read -r confirm < /dev/tty
if [[ "${confirm,,}" != "j" ]]; then
    echo "  Abgebrochen."
    exit 0
fi

echo ""

# Stop and disable services
for svc in printcostcalc printsync; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        systemctl stop "$svc"
        echo -e "  ${GREEN}✔${NC}  Service $svc gestoppt"
    fi
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        systemctl disable --quiet "$svc"
    fi
    rm -f "/etc/systemd/system/${svc}.service"
done
systemctl daemon-reload

echo -e "  ${GREEN}✔${NC}  systemd-Services entfernt"

# Remove user
if id -u printcostcalc &>/dev/null; then
    userdel printcostcalc 2>/dev/null || true
    echo -e "  ${GREEN}✔${NC}  Systembenutzer entfernt"
fi

# Remove install directory
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    echo -e "  ${GREEN}✔${NC}  ${INSTALL_DIR} entfernt"
fi

echo ""
echo -e "  ${GREEN}✔${NC}  PrintCostCalc vollständig deinstalliert."
echo ""
