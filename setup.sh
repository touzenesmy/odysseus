#!/usr/bin/env bash
set -euo pipefail

# ── Odysseus first-run setup ───────────────────────────────────────────────
# Clones the repo, adds the Improvements upstream remote, creates a Python
# venv, generates a systemd service and docker-compose file from templates,
# and launches Odysseus.
#
# Safe to re-run — existing files are never overwritten without asking.
# ───────────────────────────────────────────────────────────────────────────

REMOTE_URL="https://github.com/touzenesmy/odysseus.git"
REMOTE_NAME="touzenesmy"
BRANCH="Improvements"

USER_NAME="${USER:-$(whoami)}"
INSTALL_DIR="${HOME}/odysseus"
REPO_DIR=""

# ── Step 0: system dependencies ────────────────────────────────────────────
# Ensures Python, venv, pip, build tools, and git are installed before we
# try to use them.  Safe to re-run — apt/dnf skip already-installed packages.
SYSTEM_DEPS="python3 python3-venv python3-pip python3-dev git build-essential libssl-dev libffi-dev"

if command -v apt-get &>/dev/null; then
    echo ">> Checking system dependencies (apt)..."
    MISSING=""
    for pkg in $SYSTEM_DEPS; do
        dpkg -s "$pkg" &>/dev/null || MISSING="$MISSING $pkg"
    done
    if [[ -n "$MISSING" ]]; then
        echo ">> Installing:$MISSING"
        sudo apt-get update -qq
        sudo apt-get install -y $MISSING
    else
        echo ">> All system dependencies present"
    fi
elif command -v dnf &>/dev/null; then
    echo ">> Checking system dependencies (dnf)..."
    sudo dnf install -y python3 python3-pip python3-devel git make automake gcc gcc-c++ openssl-devel libffi-devel kernel-devel 2>/dev/null || true
    echo ">> System dependencies checked"
elif command -v pacman &>/dev/null; then
    echo ">> Checking system dependencies (pacman)..."
    sudo pacman -S --needed --noconfirm python python-pip python-virtualenv git base-devel openssl libffi 2>/dev/null || true
    echo ">> System dependencies checked"
else
    echo ">> ⚠  Unknown package manager.  Install these manually before continuing:"
    echo "      $SYSTEM_DEPS"
fi

# Warn if Docker is missing (non-fatal — you can install it later)
if ! command -v docker &>/dev/null; then
    echo ">> ⚠  Docker not found.  Install it before starting the service:"
    echo "      https://docs.docker.com/engine/install/"
fi

# ── Step 1: clone or locate the repo ───────────────────────────────────────
if [[ -d "${HOME}/odysseus/.git" ]]; then
    REPO_DIR="${HOME}/odysseus"
    echo ">> Found existing repo at ${REPO_DIR}"
elif [[ -d "./.git" ]] && git remote -v 2>/dev/null | grep -q odysseus; then
    REPO_DIR="$(pwd)"
    echo ">> Running inside an Odysseus repo: ${REPO_DIR}"
else
    echo ">> Cloning Odysseus into ${INSTALL_DIR} ..."
    git clone "${REMOTE_URL}" "${INSTALL_DIR}"
    REPO_DIR="${INSTALL_DIR}"
fi

cd "${REPO_DIR}"

# ── Step 2: add upstream remote ───────────────────────────────────────────
if ! git remote get-url "${REMOTE_NAME}" &>/dev/null; then
    git remote add "${REMOTE_NAME}" "${REMOTE_URL}"
    echo ">> Added remote '${REMOTE_NAME}' → ${REMOTE_URL}"
else
    echo ">> Remote '${REMOTE_NAME}' already exists"
fi

# ── Step 3: checkout Improvements branch ──────────────────────────────────
git fetch "${REMOTE_NAME}" "${BRANCH}"
git checkout -B "${BRANCH}" "${REMOTE_NAME}/${BRANCH}"
echo ">> On branch '${BRANCH}'"

# ── Step 4: Python virtual environment ────────────────────────────────────
if [[ ! -d venv ]]; then
    python3 -m venv venv
    echo ">> Created venv/"
fi
source venv/bin/activate
pip install -r requirements.txt
deactivate
echo ">> Python dependencies installed"

# ── Step 5: docker-compose file ──────────────────────────────────────────
COMPOSE_SRC="docker-compose-baremetal.samy"
COMPOSE_DST="docker-compose.yml"
if [[ -f "${COMPOSE_SRC}" && ! -f "${COMPOSE_DST}" ]]; then
    # Generate a friend-ready copy with their home path
    sed "s|/home/samy|${HOME}|g" "${COMPOSE_SRC}" > "${COMPOSE_DST}"
    echo ">> Created ${COMPOSE_DST} (paths adapted to ${HOME})"
elif [[ -f "${COMPOSE_DST}" ]]; then
    echo ">> ${COMPOSE_DST} already exists — skipping"
fi

# ── Step 6: systemd service file ──────────────────────────────────────────
SERVICE_FILE="odysseus.service"
if [[ ! -f /etc/systemd/system/${SERVICE_FILE} ]]; then
    cat > "${SERVICE_FILE}" <<SERVICEOF
[Unit]
Description=Odysseus UI
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${REPO_DIR}
ExecStartPre=/usr/bin/docker compose -f ${REPO_DIR}/docker-compose.yml up -d
ExecStartPre=/bin/bash -c 'for i in \$(seq 1 5); do ok=1; for port in 8100 8080 8091 8191 11434 5053; do timeout 1 bash -c "echo >/dev/tcp/127.0.0.1/\$port" 2>/dev/null || ok=0; done; [ \$ok -eq 1 ] && exit 0; sleep 1; done; exit 1'
ExecStart=${REPO_DIR}/venv/bin/uvicorn app:app --port 7000 --host 0.0.0.0
Restart=always
RestartSec=3
EnvironmentFile=-${REPO_DIR}/.env

[Install]
WantedBy=multi-user.target
SERVICEOF
    echo ">> Generated ${SERVICE_FILE}"

    echo ""
    echo ">> Installing systemd service..."
    sudo cp "${SERVICE_FILE}" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_FILE}"
    echo ">> ${SERVICE_FILE} installed and enabled"
else
    echo ">> ${SERVICE_FILE} already installed — skipping"
fi

# ── Step 7: .env reminder ─────────────────────────────────────────────────
if [[ ! -f .env ]]; then
    echo ">> ⚠  No .env file found. Create one before starting:"
    echo "      cp .env.example .env && nano .env"
fi

# ── Step 8: first launch ──────────────────────────────────────────────────
echo ""
echo "================================================"
echo "  Setup complete."
echo "  Start Odysseus:  sudo systemctl start ${SERVICE_FILE}"
echo "  View logs:       journalctl -u ${SERVICE_FILE} -f"
echo "  Update later:    cd ${REPO_DIR} && ./update.sh"
echo "================================================"
