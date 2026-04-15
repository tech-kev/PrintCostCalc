#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║                                                                            ║
# ║   ██████╗ ██████╗ ██╗███╗   ██╗████████╗                                   ║
# ║   ██╔══██╗██╔══██╗██║████╗  ██║╚══██╔══╝                                   ║
# ║   ██████╔╝██████╔╝██║██╔██╗ ██║   ██║                                      ║
# ║   ██╔═══╝ ██╔══██╗██║██║╚██╗██║   ██║                                      ║
# ║   ██║     ██║  ██║██║██║ ╚████║   ██║                                      ║
# ║   ╚═╝     ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝                                      ║
# ║    ██████╗ ██████╗ ███████╗████████╗ ██████╗ █████╗ ██╗      ██████╗       ║
# ║   ██╔════╝██╔═══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗██║     ██╔════╝       ║
# ║   ██║     ██║   ██║███████╗   ██║   ██║     ███████║██║     ██║            ║
# ║   ██║     ██║   ██║╚════██║   ██║   ██║     ██╔══██║██║     ██║            ║
# ║   ╚██████╗╚██████╔╝███████║   ██║   ╚██████╗██║  ██║███████╗╚██████╗       ║
# ║    ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝       ║
# ║                                                                            ║
# ║   One-Click Installer for PrintCostCalc                                    ║
# ║   https://github.com/tech-kev/PrintCostCalc                               ║
# ║                                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Verbose Mode ───────────────────────────────────────────────────────────
VERBOSE=false
for arg in "$@"; do case $arg in -v|--verbose) VERBOSE=true ;; esac; done

# ── Colors & Formatting ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Helper Functions ─────────────────────────────────────────────────────────

info()    { echo -e "  ${BLUE}ℹ${NC}  $1"; }
success() { echo -e "  ${GREEN}✔${NC}  $1"; }
warn()    { echo -e "  ${YELLOW}⚠${NC}  $1"; }
fail()    { echo -e "  ${RED}✖${NC}  $1"; exit 1; }

TOTAL_STEPS=5

progress_bar() {
    local current=$1
    local total=$2
    local width=47
    local filled=$(( (current * width) / total ))
    local empty=$(( width - filled ))
    local pct=$(( (current * 100) / total ))
    local bar=""
    for (( i=0; i<filled; i++ )); do bar+="█"; done
    for (( i=0; i<empty; i++ )); do bar+="░"; done
    echo -e "  ${GREEN}${bar}${NC}  ${BOLD}${pct}%%${NC}"
}

step() {
    local label=$1
    local current=${2:-0}
    echo ""
    echo -e "  ${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}${CYAN}${label}${NC}"
    if [[ $current -gt 0 ]]; then
        progress_bar "$current" "$TOTAL_STEPS"
    fi
    echo -e "  ${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

spinner() {
    local pid=$1
    local msg=$2
    local chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    while kill -0 "$pid" 2>/dev/null; do
        for (( i=0; i<${#chars}; i++ )); do
            printf "\r  ${CYAN}%s${NC}  %s" "${chars:$i:1}" "$msg"
            sleep 0.1
        done
    done
    wait "$pid"
    local exit_code=$?
    printf "\r"
    return $exit_code
}

run_task() {
    local msg="$1"
    shift
    if $VERBOSE; then
        info "$msg"
        "$@" 2>&1 | while IFS= read -r line; do
            echo -e "  ${DIM}│${NC} $line"
        done
    else
        "$@" &>/dev/null &
        spinner $! "$msg"
    fi
}

ask() {
    local prompt=$1
    local default=$2
    local var_name=$3
    if [[ -n "$default" ]]; then
        echo -ne "  ${BOLD}${prompt}${NC} ${DIM}[${default}]${NC}: "
    else
        echo -ne "  ${BOLD}${prompt}${NC}: "
    fi
    read -r input < /dev/tty
    eval "$var_name=\"${input:-$default}\""
}

# ── Pre-flight Checks ────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    fail "Dieses Script muss als root ausgeführt werden. Versuche: ${BOLD}sudo bash install.sh${NC}"
fi

clear
echo ""
echo -e "  ${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "  ${CYAN}║${NC}                                                          ${CYAN}║${NC}"
echo -e "  ${CYAN}║${NC}   ${BOLD}PrintCostCalc — Installer${NC}                              ${CYAN}║${NC}"
echo -e "  ${CYAN}║${NC}                                                          ${CYAN}║${NC}"
echo -e "  ${CYAN}║${NC}   ${DIM}3D-Druck Kostenrechner${NC}                                 ${CYAN}║${NC}"
echo -e "  ${CYAN}║${NC}                                                          ${CYAN}║${NC}"
echo -e "  ${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
if $VERBOSE; then
    info "Verbose-Modus aktiv"
    echo ""
fi

# ── Detect Package Manager ───────────────────────────────────────────────────
if command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    PKG_UPDATE="apt-get update"
    PKG_INSTALL="apt-get install -y"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_UPDATE="dnf check-update || true"
    PKG_INSTALL="dnf install -y"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
    PKG_UPDATE="yum check-update || true"
    PKG_INSTALL="yum install -y"
else
    fail "Nicht unterstützter Paketmanager. Unterstützt: apt (Debian/Ubuntu), dnf (Fedora/Rocky), yum (CentOS)."
fi

success "Paketmanager: ${BOLD}${PKG_MANAGER}${NC}"

# ── Interactive Setup ────────────────────────────────────────────────────────

step "Konfiguration"

INSTALL_DIR_DEFAULT="/opt/printcostcalc"
ask "Installationsverzeichnis" "$INSTALL_DIR_DEFAULT" INSTALL_DIR
ask "Port" "5002" PORT

GIT_REPO_URL="https://github.com/tech-kev/PrintCostCalc.git"

# Generate secret key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${DIM}┌─────────────────────────────────────────────────────┐${NC}"
echo -e "  ${DIM}│${NC}  Verzeichnis:  ${BOLD}${INSTALL_DIR}${NC}"
echo -e "  ${DIM}│${NC}  Port:         ${BOLD}${PORT}${NC}"
echo -e "  ${DIM}└─────────────────────────────────────────────────────┘${NC}"
echo ""
echo -ne "  ${BOLD}Installation starten? [J/n]${NC}: "
read -r confirm < /dev/tty
if [[ "${confirm,,}" == "n" ]]; then
    info "Installation abgebrochen."
    exit 0
fi

# ── Step 1: System Dependencies ──────────────────────────────────────────────

step "Schritt 1/5 — Systemabhängigkeiten installieren" 1

_task_install_packages() {
    $PKG_UPDATE
    if [[ "$PKG_MANAGER" == "apt" ]]; then
        $PKG_INSTALL python3 python3-pip python3-venv python3-dev git build-essential libffi-dev libssl-dev
    else
        $PKG_INSTALL python3 python3-pip python3-devel git gcc libffi-devel openssl-devel
    fi
}
run_task "Installiere Systempakete..." _task_install_packages
success "Systemabhängigkeiten installiert"

# Verify Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ]]; then
    fail "Python 3.10+ erforderlich (gefunden: ${PYTHON_VERSION})"
fi
success "Python ${PYTHON_VERSION} gefunden"

# ── Step 2: Create User & Clone ──────────────────────────────────────────────

step "Schritt 2/5 — Anwendung einrichten" 2

if ! id -u printcostcalc &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$INSTALL_DIR" printcostcalc
    success "Systembenutzer erstellt: printcostcalc"
else
    success "Systembenutzer printcostcalc existiert bereits"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LOCAL_SRC=""
if [[ -f "$SCRIPT_DIR/app.py" ]]; then
    LOCAL_SRC="$SCRIPT_DIR"
elif [[ -f "$(pwd)/app.py" ]]; then
    LOCAL_SRC="$(pwd)"
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Verzeichnis existiert, aktualisiere..."
    cd "$INSTALL_DIR"
    sudo -u printcostcalc git pull --quiet 2>/dev/null || git pull --quiet
    success "Repository aktualisiert"
elif [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/app.py" ]]; then
    warn "Verzeichnis existiert, nutze vorhandene Dateien"
else
    [[ -d "$INSTALL_DIR" ]] && rmdir "$INSTALL_DIR" 2>/dev/null || true

    info "Klone Repository..."
    CLONE_ERR=$(GIT_TERMINAL_PROMPT=0 git clone "$GIT_REPO_URL" "$INSTALL_DIR" 2>&1) && success "Repository geklont" || {
        warn "git clone fehlgeschlagen: ${CLONE_ERR}"
        if [[ -n "$LOCAL_SRC" ]]; then
            info "Nutze lokales Verzeichnis (${LOCAL_SRC})..."
            mkdir -p "$INSTALL_DIR"
            cp -r "$LOCAL_SRC"/* "$INSTALL_DIR"/
            cd "$INSTALL_DIR" && git init --quiet && git add -A && git commit --quiet -m "Initial install" 2>/dev/null || true
            success "Dateien aus lokalem Verzeichnis kopiert"
        else
            fail "Repository konnte nicht geklont werden und kein lokales Verzeichnis gefunden."
        fi
    }
fi

mkdir -p "$INSTALL_DIR"/{instance,logs}
chown -R printcostcalc:printcostcalc "$INSTALL_DIR"
success "Verzeichnisstruktur erstellt"

# ── Step 3: Python Environment ───────────────────────────────────────────────

step "Schritt 3/5 — Python-Umgebung einrichten" 3

cd "$INSTALL_DIR"

if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    python3 -m venv "$INSTALL_DIR/venv"
    success "Virtuelle Umgebung erstellt"
else
    success "Virtuelle Umgebung existiert"
fi

_task_install_pip() {
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
}
run_task "Installiere Python-Abhängigkeiten..." _task_install_pip
success "Python-Abhängigkeiten installiert"

# ── Step 4: Configuration ────────────────────────────────────────────────────

step "Schritt 4/5 — Konfiguration erstellen" 4

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cat > "$INSTALL_DIR/.env" << ENVEOF
# PrintCostCalc — Konfiguration
# Erstellt am $(date +%Y-%m-%d)
SECRET_KEY=${SECRET_KEY}
PORT=${PORT}
ENVEOF
    chown printcostcalc:printcostcalc "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    success "Konfigurationsdatei erstellt (.env)"
else
    success "Konfigurationsdatei existiert bereits"
fi

# ── Step 5: Systemd Service ──────────────────────────────────────────────────

step "Schritt 5/5 — Systemd-Service einrichten" 5

cat > /etc/systemd/system/printcostcalc.service << SERVICEEOF
[Unit]
Description=PrintCostCalc — 3D-Druck Kostenrechner
Documentation=https://github.com/tech-kev/PrintCostCalc
After=network.target

[Service]
Type=exec
User=printcostcalc
Group=printcostcalc
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/gunicorn \\
    --bind 0.0.0.0:${PORT} \\
    --workers 1 \\
    --threads 2 \\
    --timeout 120 \\
    --access-logfile ${INSTALL_DIR}/logs/access.log \\
    --error-logfile ${INSTALL_DIR}/logs/error.log \\
    app:app
Restart=on-failure
RestartSec=5s

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICEEOF

# PrintSync Worker Service
cat > /etc/systemd/system/printsync.service << SERVICEEOF
[Unit]
Description=PrintSync — Bambu Lab FTP Sync für PrintCostCalc
After=printcostcalc.service

[Service]
Type=exec
User=printcostcalc
Group=printcostcalc
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/ftp_worker.py
Restart=on-failure
RestartSec=10s

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${INSTALL_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable --quiet printcostcalc
systemctl enable --quiet printsync
systemctl restart printcostcalc
systemctl restart printsync

sleep 2
if systemctl is-active --quiet printcostcalc; then
    success "PrintCostCalc gestartet"
else
    warn "Service möglicherweise nicht gestartet. Prüfe: ${BOLD}journalctl -u printcostcalc -n 50${NC}"
fi

if systemctl is-active --quiet printsync; then
    success "PrintSync gestartet"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo ""
echo -e "  ${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "  ${GREEN}║${NC}                                                          ${GREEN}║${NC}"
echo -e "  ${GREEN}║${NC}   ${BOLD}${GREEN}✔  Installation abgeschlossen!${NC}                         ${GREEN}║${NC}"
echo -e "  ${GREEN}║${NC}                                                          ${GREEN}║${NC}"
echo -e "  ${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}PrintCostCalc öffnen:${NC}"
echo -e "    ${CYAN}➜${NC}  http://localhost:${PORT}"
echo ""
echo -e "  ${BOLD}Befehle:${NC}"
echo -e "    ${DIM}Status:${NC}    systemctl status printcostcalc"
echo -e "    ${DIM}Logs:${NC}      journalctl -u printcostcalc -f"
echo -e "    ${DIM}Neustart:${NC}  systemctl restart printcostcalc"
echo -e "    ${DIM}Update:${NC}    cd ${INSTALL_DIR} && git pull && systemctl restart printcostcalc"
echo ""
echo -e "  ${BOLD}Dateien:${NC}"
echo -e "    ${DIM}Config:${NC}    ${INSTALL_DIR}/.env"
echo -e "    ${DIM}Datenbank:${NC} ${INSTALL_DIR}/instance/"
echo -e "    ${DIM}Logs:${NC}      ${INSTALL_DIR}/logs/"
echo ""
echo -e "  ${DIM}────────────────────────────────────────────────────────${NC}"
echo -e "  ${DIM}PrintCostCalc • https://github.com/tech-kev/PrintCostCalc${NC}"
echo ""
