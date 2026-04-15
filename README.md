# Tapo C500 — PTZ Control via Terminal (ONVIF)

Control the pan/tilt of the **TP-Link Tapo C500** camera directly from your terminal using the **ONVIF** protocol via the `onvif-zeep` library.

---

## Requirements

- Python 3.10+
- Camera and computer on the **same local network**
- **Camera Account** enabled in the Tapo app:
  `Settings > Advanced Settings > Camera Account`

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/tapo-ptz-control.git
cd tapo-ptz-control

# (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Credentials are read from **environment variables** — never hardcode passwords in the source code.

```bash
# Copy the example file and fill in your credentials
cp .env.example .env
```

Then edit `.env` with your values.

### Available variables

| Variable        | Default         | Description                                          |
|-----------------|-----------------|------------------------------------------------------|
| `TAPO_IP`       | `192.168.1.4`   | Camera IP address on the local network               |
| `TAPO_PORT`     | `2020`          | Camera ONVIF port                                    |
| `TAPO_USER`     | `admin`         | Camera Account username                              |
| `TAPO_PASS`     | *(required)*    | Camera Account password                              |
| `TAPO_STEP`     | `0.1`           | Short step intensity (0.0 – 1.0)                     |
| `TAPO_SPEED`    | `0.5`           | Continuous move speed (0.0 – 1.0)                    |
| `TAPO_TOUCH_MS` | `100`           | Manual touch duration in ms (RelativeMove fallback)  |

---

## Usage

```bash
python tapo_control.py
```

### Commands

| Key     | Action                        |
|---------|-------------------------------|
| `w`     | Tilt up (short step)          |
| `s`     | Tilt down (short step)        |
| `a`     | Pan left (short step)         |
| `d`     | Pan right (short step)        |
| `W`     | Tilt up (continuous)          |
| `S`     | Tilt down (continuous)        |
| `A`     | Pan left (continuous)         |
| `D`     | Pan right (continuous)        |
| `b / B` | Stop motor                    |
| `q`     | Quit                          |

---

## Troubleshooting

**`Authority Failure` on connect**
The ONVIF protocol requires the computer and camera clocks to be in sync (within ~5 seconds). Make sure NTP synchronization is enabled on your system.

**`Connection refused` or timeout**
Check that the IP and port are correct and that both devices are on the same network. The default ONVIF port for the Tapo C500 is `2020`.

**`RelativeMove not supported`**
The script automatically falls back to a manual touch (ContinuousMove for 100 ms). You can adjust the duration via `TAPO_TOUCH_MS`.

---

## Project structure

```
tapo-ptz-control/
├── tapo_control.py   # Main script
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variable template
├── .gitignore        # Git ignore rules
└── README.md         # This file
```

---

## License

MIT
