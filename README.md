# MiniCloud

A minimal local-network file server for uploading and downloading files from any browser.

## Requirements

Python 3 (3.8+). No other dependencies needed — `run.sh` sets up a virtual environment automatically.

## Usage

```sh
./run.sh              # listens on http://0.0.0.0:8080
./run.sh --port 80    # custom port (requires sudo on Linux/macOS)
```

On first run, a `venv/` directory is created and Flask is installed into it. Subsequent starts are instant.

Files are stored in the `shared/` directory.

## Features

- Drag-and-drop upload or file picker — any file type accepted
- Upload progress bar
- Download and delete files from the browser
- Works on macOS, Linux, and Raspberry Pi (Debian)

## Compatibility

Tested on macOS and accessible from Windows and other machines on the same local network. Access via hostname if direct IP is blocked by network policy:

```
http://hostname.local:8080
```
