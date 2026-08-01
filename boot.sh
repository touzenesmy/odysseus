#!/usr/bin/env bash
set -euo pipefail
SERVICE="odysseus.service"
echo ">> Restarting Odysseus (systemd handles containers + uvicorn)..."
sudo systemctl restart "$SERVICE"
echo ">> Done. Open http://localhost:7000"
echo ">> Logs: journalctl -u $SERVICE -f"
