# Tapo C500 PTZ Control

Control the pan/tilt of the **TP-Link Tapo C500** camera on your **local network** using ONVIF, either from the terminal or from a web interface with integrated live view.

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
| `TAPO_STEP` | `0.1` | Base short-step intensity |
| `TAPO_VERTICAL_STEP_MULTIPLIER` | `1.5` | Extra reach for tap up/down moves |
| `TAPO_SPEED` | `0.5` | Continuous move speed used by CLI, extreme moves, and patrol sweeps |
| `TAPO_PATROL_SEGMENT_SIZE` | `0.08` | Patrol granularity; lower values make the sweep slower and smoother |
| `TAPO_PATROL_STEP_PAUSE_SECS` | `0.2` | Pause between patrol segments in seconds |
| `TAPO_TOUCH_MS` | `100` | Manual touch fallback duration in milliseconds |
| `TAPO_SAFETY_TIMEOUT_SECS` | `5` | Automatic stop timeout for continuous mode |
| `TAPO_RTSP_PORT` | `554` | Camera RTSP port used for the live view |
| `TAPO_STREAM_PATH` | `stream1` | Camera RTSP path used for the live view |

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

The browser view includes:

- a near-fullscreen live view
- a left bottom overlay pad for short tap moves in all four directions
- a right bottom overlay pad for one-click moves to each directional extreme
- keyboard tap shortcuts with `W`, `A`, `S`, `D` and the arrow keys
- a centered patrol control bar with horizontal patrol, vertical patrol, and stop
- automatic RTSP-to-MJPEG streaming through the backend

Start the web application with:

```bash
python run.py
```

Or directly with Uvicorn:

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` on the same machine or another device on the same LAN.

### Patrol behavior

The patrol controls run a three-step sweep:

1. Save the current position.
2. Move to one axis extreme, then the opposite extreme.
3. Return to the saved position.

To keep the sweep visually controlled, patrol movement is split into smaller intermediate moves. The manual extreme buttons are still direct one-click moves.

`Patrol H` scans left/right.  
`Patrol V` scans up/down.  
`Stop` cancels the patrol or any in-flight motion.

---

## HTTP API

| Method | Route | Action |
|--------|-------|--------|
| `GET` | `/status` | Check camera connectivity and patrol state |
| `GET` | `/stream.mjpeg` | Live MJPEG stream for the browser |
| `POST` | `/move/step` | Short step movement |
| `POST` | `/move/extreme` | Move to the directional extreme while preserving the other axis |
| `POST` | `/move/continuous` | Continuous movement |
| `POST` | `/patrol/start` | Start horizontal or vertical patrol |
| `POST` | `/patrol/stop` | Stop patrol only |
| `POST` | `/stop` | Stop current movement and cancel patrol |

Example patrol request:

```json
{
  "axis": "horizontal"
}
```

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

**Live view does not load**  
Check `TAPO_RTSP_PORT`, `TAPO_STREAM_PATH`, camera stream availability, and that dependencies from `requirements.txt` are installed.

**Tap up/down still feels too short**  
Increase `TAPO_VERTICAL_STEP_MULTIPLIER` in `.env`.

**`RelativeMove not supported`**  
The controller falls back to a short `ContinuousMove`. Adjust `TAPO_TOUCH_MS` if needed.

**Patrol stops early**  
Manual commands and `Stop` intentionally cancel patrol so you can immediately take control again.

**Patrol is still too fast**  
Lower `TAPO_PATROL_SEGMENT_SIZE` and/or increase `TAPO_PATROL_STEP_PAUSE_SECS` in `.env`.

---

## Project Structure

```text
tapo-ptz-control/
|-- backend/         # FastAPI HTTP API
|-- cli/             # Terminal entrypoint
|-- frontend/        # Static web interface
|-- shared/          # Shared ONVIF controller/service code
|-- run.py           # Single-command web launcher
|-- requirements.txt
`-- .env.example
```

---

## License

MIT
