# Tapo C500 PTZ Control

Control the pan/tilt of the **TP-Link Tapo C500** camera on your **local network** using ONVIF, either from the terminal or from a simple web interface served by a Python backend.

---

## Requirements

- Python 3.10+
- Camera and computer on the same local network
- Camera Account enabled in the Tapo app:
  `Settings > Advanced Settings > Camera Account`

---

## Installation

```bash
git clone https://github.com/radieske/tapo-ptz-control.git
cd tapo-ptz-control

python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

---

## Configuration

Copy the example file and fill in your camera credentials:

```bash
cp .env.example .env
```

Available variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TAPO_IP` | `192.168.1.4` | Camera IP address on the local network |
| `TAPO_PORT` | `2020` | Camera ONVIF port |
| `TAPO_USER` | `admin` | Camera Account username |
| `TAPO_PASS` | required | Camera Account password |
| `TAPO_STEP` | `0.1` | Short step intensity |
| `TAPO_SPEED` | `0.5` | Continuous move speed |
| `TAPO_TOUCH_MS` | `100` | Manual touch fallback duration in milliseconds |
| `TAPO_SAFETY_TIMEOUT_SECS` | `5` | Automatic stop timeout for continuous mode |

---

## Usage

### CLI

```bash
python -m cli.tapo_control
```

CLI commands:

| Key | Action |
|-----|--------|
| `w` | Tilt up (short step) |
| `s` | Tilt down (short step) |
| `a` | Pan left (short step) |
| `d` | Pan right (short step) |
| `W` | Tilt up (continuous) |
| `S` | Tilt down (continuous) |
| `A` | Pan left (continuous) |
| `D` | Pan right (continuous) |
| `b / B` | Stop motor |
| `q` | Quit |

### Web UI

You do not need to start the CLI first. The backend already talks directly to the camera and serves the frontend.

Start the web application with a single command:

```bash
python run.py
```

Or, if you prefer, the raw Uvicorn command:

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in the same machine or another device on the same LAN.

Available API routes:

| Method | Route | Action |
|--------|-------|--------|
| `GET` | `/status` | Check camera connectivity |
| `POST` | `/move/step` | Short step movement |
| `POST` | `/move/continuous` | Continuous movement |
| `POST` | `/stop` | Stop the motor |

The frontend is served by FastAPI from the `frontend/` directory.

Optional web env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `TAPO_WEB_HOST` | `0.0.0.0` | Host used by the web server |
| `TAPO_WEB_PORT` | `8000` | Port used by the web server |
| `TAPO_WEB_RELOAD` | `false` | Enables auto reload during development |

---

## Troubleshooting

**`Authority Failure` on connect**  
The computer and camera clocks must stay in sync. Make sure NTP synchronization is enabled.

**`Connection refused` or timeout**  
Check the IP, port, and that both devices are on the same network.

**`RelativeMove not supported`**  
The controller falls back to a short `ContinuousMove`. Adjust `TAPO_TOUCH_MS` if needed.

**Continuous mode keeps moving**  
The backend automatically sends a stop after `TAPO_SAFETY_TIMEOUT_SECS` seconds without a fresh movement command.

---

## Project Structure

```text
tapo-ptz-control/
├── backend/         # FastAPI HTTP API
├── cli/             # Terminal entrypoint
├── frontend/        # Static web interface
├── shared/          # Shared ONVIF controller/service code
├── run.py           # Single-command web launcher
├── requirements.txt
└── .env.example
```

---

## License

MIT
