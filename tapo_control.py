import sys
import os
import time
from dotenv import load_dotenv
from onvif import ONVIFCamera

load_dotenv()

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
IP       = os.getenv("TAPO_IP",   "192.168.1.4")
PORT     = int(os.getenv("TAPO_PORT", "2020"))
USER     = os.getenv("TAPO_USER", "admin")
PASSWORD = os.getenv("TAPO_PASS")

STEP       = float(os.getenv("TAPO_STEP",     "0.1"))   # short step intensity (0.0 – 1.0)
SPEED      = float(os.getenv("TAPO_SPEED",    "0.5"))   # continuous move speed (0.0 – 1.0)
TOUCH_SECS = float(os.getenv("TAPO_TOUCH_MS", "100")) / 1000  # manual touch duration in seconds
# ──────────────────────────────────────────────────────────────────────────────


class TapoController:
    """Wraps the ONVIF connection and PTZ services for the Tapo camera."""

    def __init__(self, ip: str, port: int, user: str, password: str):
        self.cam = ONVIFCamera(ip, port, user, password)
        self.ptz = self.cam.create_ptz_service()
        self.profile_token = self._get_profile_token()

    def _get_profile_token(self) -> str:
        profiles = self.cam.create_media_service().GetProfiles()
        if not profiles:
            raise RuntimeError("No media profiles found on the camera.")
        return profiles[0].token

    # ── Movement methods ──────────────────────────────────────────────────────

    def move_step(self, pan: float, tilt: float) -> None:
        """Move the camera by a relative step. Falls back to manual touch
        if RelativeMove is not supported by the camera."""
        try:
            req = self.ptz.create_type("RelativeMove")
            req.ProfileToken = self.profile_token
            req.Translation = {"PanTilt": {"x": pan, "y": tilt}}
            req.Speed = {"PanTilt": {"x": 1.0, "y": 1.0}}
            self.ptz.RelativeMove(req)
        except Exception as e:
            if "not supported" in str(e).lower() or "notsupported" in str(e).lower():
                self._manual_touch(pan, tilt)
            else:
                raise

    def move_continuous(self, pan: float, tilt: float) -> None:
        """Start a continuous move. Call stop() to interrupt."""
        req = self.ptz.create_type("ContinuousMove")
        req.ProfileToken = self.profile_token
        req.Velocity = {"PanTilt": {"x": pan, "y": tilt}}
        self.ptz.ContinuousMove(req)

    def stop(self) -> None:
        """Stop any ongoing movement."""
        self.ptz.Stop({"ProfileToken": self.profile_token})

    def _manual_touch(self, pan: float, tilt: float) -> None:
        """Fallback: run ContinuousMove for TOUCH_SECS seconds then stop.
        Used when the camera does not support RelativeMove."""
        self.move_continuous(pan, tilt)
        time.sleep(TOUCH_SECS)
        self.stop()


# ── UI helpers ────────────────────────────────────────────────────────────────

def print_menu() -> None:
    print("\n" + "=" * 44)
    print("  PTZ Control — Tapo C500")
    print("=" * 44)
    print("  w/s/a/d   -> Short step (tap)")
    print("  W/S/A/D   -> Continuous move")
    print("  b / B     -> Stop motor")
    print("  q         -> Quit")
    print("=" * 44)


def connect() -> TapoController:
    if not PASSWORD:
        print("Error: TAPO_PASS environment variable is not set.")
        print("  Copy .env.example to .env and fill in your credentials.")
        sys.exit(1)

    print(f"Connecting to {IP}:{PORT}...")
    try:
        ctrl = TapoController(IP, PORT, USER, PASSWORD)
        print("Connected successfully!\n")
        return ctrl
    except Exception as e:
        msg = str(e).lower()
        if "authority" in msg:
            print("Authentication error: check your credentials and make sure your system clock is synced.")
        elif "connection" in msg or "timeout" in msg:
            print(f"Network error: could not reach {IP}:{PORT}. Check IP and port.")
        else:
            print(f"Connection error: {e}")
        sys.exit(1)


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    ctrl = connect()
    print_menu()

    COMMANDS = {
        # Short step
        "w": lambda: ctrl.move_step(0,    -STEP),
        "s": lambda: ctrl.move_step(0,     STEP),
        "a": lambda: ctrl.move_step(-STEP, 0),
        "d": lambda: ctrl.move_step( STEP, 0),
        # Continuous move
        "S": lambda: ctrl.move_continuous(0,      -SPEED),
        "W": lambda: ctrl.move_continuous(0,       SPEED),
        "A": lambda: ctrl.move_continuous(-SPEED,  0),
        "D": lambda: ctrl.move_continuous( SPEED,  0),
        # Stop
        "b": lambda: ctrl.stop(),
        "B": lambda: ctrl.stop(),
    }

    while True:
        try:
            cmd = input("Command: ")
        except (KeyboardInterrupt, EOFError):
            print("\nQuitting...")
            break

        if cmd == "q":
            print("Quitting...")
            break

        handler = COMMANDS.get(cmd)
        if handler:
            try:
                handler()
            except Exception as e:
                print(f"Error executing command '{cmd}': {e}")
        else:
            print(f"Unknown command: '{cmd}'. Use w/a/s/d, W/A/S/D, b or q.")


if __name__ == "__main__":
    main()
