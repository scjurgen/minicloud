#!/bin/sh
VENV=./venv
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q flask
fi
exec "$VENV/bin/python" app.py "$@"
