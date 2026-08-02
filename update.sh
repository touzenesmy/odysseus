#!/usr/bin/env bash
set -euo pipefail
BRANCH="Improvements"
PR_NUM=""
COMPOSE_FILE="docker-compose-baremetal.samy"
SERVICE="odysseus.service"
HUB_SERVICE="hub.service"
REMOTE_URL="https://github.com/touzenesmy/odysseus.git"
REMOTE_NAME="touzenesmy"
cd "$(dirname "$0")"

if [[ -z "$BRANCH" && -z "$PR_NUM" ]]; then
    echo ">> Error: set BRANCH or PR_NUM" >&2
    exit 1
fi

echo ">> Checking for local modifications..."
# git status --porcelain in one shot catches staged, unstaged, AND untracked
# files. Plain `git diff` variants never see untracked files, which can still
# make `git pull` blow up with "untracked working tree files would be
# overwritten by merge" even when your diff-based check reported "all clear."
STATUS_LINES="$(git status --porcelain)"

if [[ -n "$STATUS_LINES" ]]; then
    echo ""
    echo "=== Local changes detected ==="
    echo "$STATUS_LINES" | nl -ba
    echo "==============================="
    echo ""
    echo "  [s] Stash changes (recoverable later) and pull fresh"
    echo "  [d] Discard changes permanently (cannot be undone) and pull fresh"
    echo "  [a] Abort update"
    echo ""
    read -rp "Choose [s/d/a]: " CHOICE
    case "$CHOICE" in
        s|S)
            STASH_MSG="pre-update autostash $(date '+%F %T')"
            git stash push -u -m "$STASH_MSG"
            echo ">> Stashed as: $(git stash list -1)"
            echo ">> Recover later with: git stash pop"
            ;;
        d|D)
            git reset --hard HEAD
            git clean -fd
            echo ">> Local changes discarded."
            ;;
        *)
            echo ">> Aborted."
            exit 1
            ;;
    esac
fi

echo ">> Pulling latest code (${BRANCH:-current})..."
if [[ -n "$PR_NUM" ]]; then
    git fetch upstream "pull/${PR_NUM}/head:pr-${PR_NUM}" --force
    git checkout "pr-${PR_NUM}"
else
    if ! git remote get-url "$REMOTE_NAME" &>/dev/null; then
        git remote add "$REMOTE_NAME" "$REMOTE_URL"
    fi
    git fetch "$REMOTE_NAME" "$BRANCH"

    # Safety: prevent overwriting local commits that haven't been pushed
    LOCAL_AHEAD=$(git rev-list --count "$REMOTE_NAME/$BRANCH..$BRANCH" 2>/dev/null || echo 0)
    if [[ "$LOCAL_AHEAD" -gt 0 ]]; then
        echo ""
        echo "!!! WARNING: Local branch '$BRANCH' is $LOCAL_AHEAD commit(s) ahead of $REMOTE_NAME/$BRANCH !!!"
        echo "    Running this script will OVERWRITE those local commits."
        echo "    Push them first: git push origin $BRANCH"
        echo ""
        read -rp "    Continue anyway and discard local commits? [y/N]: " FORCE_CHOICE
        case "$FORCE_CHOICE" in
            y|Y)
                echo ">> Proceeding — local commits will be lost."
                ;;
            *)
                echo ">> Aborted."
                exit 1
                ;;
        esac
    fi

    git checkout -B "$BRANCH" "$REMOTE_NAME/$BRANCH"
fi

echo ">> Pulling latest container images..."
docker compose -f "$COMPOSE_FILE" pull

echo ">> Restarting Odysseus..."
sudo systemctl stop "$SERVICE"
echo ">> Checking system dependencies for Python builds..."
if command -v apt-get &>/dev/null; then
    BUILD_DEPS="python3-venv python3-dev build-essential libssl-dev libffi-dev"
    MISSING=""
    for pkg in $BUILD_DEPS; do
        dpkg -s "$pkg" &>/dev/null || MISSING="$MISSING $pkg"
    done
    if [[ -n "$MISSING" ]]; then
        echo ">> Installing:$MISSING"
        sudo apt-get update -qq
        sudo apt-get install -y $MISSING
    fi
fi

echo ">> Updating dependencies..."
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl start "$SERVICE"

echo ">> Restarting Hub..."
sudo systemctl restart "$HUB_SERVICE"

echo ">> Updated. Logs: journalctl -u $SERVICE -f"
journalctl -u odysseus.service -f
