#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON_CMD=""

# Prioritize Python environments that have intelhex and esptool installed
for CANDIDATE in \
    "$DIR/venv/bin/python" \
    "$DIR/.venv/bin/python" \
    "$VIRTUAL_ENV/bin/python" \
    "/opt/anaconda3/bin/python3" \
    "/opt/anaconda3/bin/python" \
    "$HOME/.platformio/penv/bin/python" \
    "$(which python3 2>/dev/null)" \
    "$(which python 2>/dev/null)"
do
    if [ -n "$CANDIDATE" ] && [ -x "$CANDIDATE" ]; then
        if "$CANDIDATE" -c "import intelhex" >/dev/null 2>&1; then
            PYTHON_CMD="$CANDIDATE"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python"
    fi
fi

"$PYTHON_CMD" "$DIR/flash_device.py" "$@"

