import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from onvif import ONVIFCamera


load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class TapoConfig:
    ip: str
    port: int
    user: str
    password: str
    step: float
    speed: float
    touch_secs: float
    safety_timeout_secs: float

    @classmethod
    def from_env(cls) -> "TapoConfig":
        return cls(
            ip=os.getenv("TAPO_IP", "192.168.1.4"),
            port=int(os.getenv("TAPO_PORT", "2020")),
            user=os.getenv("TAPO_USER", "admin"),
            password=os.getenv("TAPO_PASS", ""),
            step=float(os.getenv("TAPO_STEP", "0.1")),
            speed=float(os.getenv("TAPO_SPEED", "0.5")),
            touch_secs=float(os.getenv("TAPO_TOUCH_MS", "100")) / 1000,
            safety_timeout_secs=float(os.getenv("TAPO_SAFETY_TIMEOUT_SECS", "5")),
        )


class TapoController:
    """Wrap the ONVIF connection and PTZ services for the Tapo camera."""

    def __init__(self, config: TapoConfig):
        if not config.password:
            raise RuntimeError("TAPO_PASS environment variable is not set.")

        self.config = config
        self.cam = ONVIFCamera(config.ip, config.port, config.user, config.password)
        self.ptz = self.cam.create_ptz_service()
        self.profile_token = self._get_profile_token()

    def _get_profile_token(self) -> str:
        profiles = self.cam.create_media_service().GetProfiles()
        if not profiles:
            raise RuntimeError("No media profiles found on the camera.")
        return profiles[0].token

    def move_step(self, pan: float, tilt: float) -> None:
        """Move by a relative step, falling back to a short touch if needed."""
        try:
            req = self.ptz.create_type("RelativeMove")
            req.ProfileToken = self.profile_token
            req.Translation = {"PanTilt": {"x": pan, "y": tilt}}
            req.Speed = {"PanTilt": {"x": 1.0, "y": 1.0}}
            self.ptz.RelativeMove(req)
        except Exception as exc:
            message = str(exc).lower()
            if "not supported" in message or "notsupported" in message:
                self._manual_touch(pan, tilt)
                return
            raise

    def move_continuous(self, pan: float, tilt: float) -> None:
        req = self.ptz.create_type("ContinuousMove")
        req.ProfileToken = self.profile_token
        req.Velocity = {"PanTilt": {"x": pan, "y": tilt}}
        self.ptz.ContinuousMove(req)

    def stop(self) -> None:
        self.ptz.Stop({"ProfileToken": self.profile_token})

    def _manual_touch(self, pan: float, tilt: float) -> None:
        self.move_continuous(pan, tilt)
        time.sleep(self.config.touch_secs)
        self.stop()


def direction_to_vector(direction: str, amount: float) -> tuple[float, float]:
    vectors = {
        "up": (0.0, -amount),
        "down": (0.0, amount),
        "left": (-amount, 0.0),
        "right": (amount, 0.0),
    }
    try:
        return vectors[direction]
    except KeyError as exc:
        raise ValueError(f"Invalid direction: {direction}") from exc


class TapoService:
    """Thread-safe facade used by CLI and HTTP layers."""

    def __init__(self, config: TapoConfig | None = None):
        self.config = config or TapoConfig.from_env()
        self._controller: TapoController | None = None
        self._lock = threading.RLock()
        self._stop_timer: threading.Timer | None = None

    def connect(self) -> TapoController:
        with self._lock:
            if self._controller is None:
                self._controller = TapoController(self.config)
            return self._controller

    def status(self) -> dict[str, object]:
        self.connect()
        return {
            "connected": True,
            "camera": {
                "ip": self.config.ip,
                "port": self.config.port,
                "user": self.config.user,
            },
        }

    def move_step(self, direction: str) -> dict[str, object]:
        pan, tilt = direction_to_vector(direction, self.config.step)
        with self._lock:
            self._cancel_stop_timer()
            self.connect().move_step(pan, tilt)
        return {"ok": True, "mode": "step", "direction": direction}

    def move_continuous(self, direction: str) -> dict[str, object]:
        pan, tilt = direction_to_vector(direction, self.config.speed)
        with self._lock:
            self.connect().move_continuous(pan, tilt)
            self._schedule_stop_timer()
        return {
            "ok": True,
            "mode": "continuous",
            "direction": direction,
            "timeout_secs": self.config.safety_timeout_secs,
        }

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._cancel_stop_timer()
            self.connect().stop()
        return {"ok": True, "mode": "stop"}

    def _schedule_stop_timer(self) -> None:
        self._cancel_stop_timer()
        self._stop_timer = threading.Timer(self.config.safety_timeout_secs, self._safe_stop)
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _cancel_stop_timer(self) -> None:
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    def _safe_stop(self) -> None:
        with self._lock:
            if self._controller is None:
                return
            try:
                self._controller.stop()
            finally:
                self._stop_timer = None
