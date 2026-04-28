import os
import threading
import time
import math
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
    vertical_step_multiplier: float
    patrol_segment_size: float
    patrol_step_pause_secs: float

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
            vertical_step_multiplier=float(os.getenv("TAPO_VERTICAL_STEP_MULTIPLIER", "1.5")),
            patrol_segment_size=float(os.getenv("TAPO_PATROL_SEGMENT_SIZE", "0.08")),
            patrol_step_pause_secs=float(os.getenv("TAPO_PATROL_STEP_PAUSE_SECS", "0.2")),
        )


@dataclass(frozen=True)
class PTZPosition:
    pan: float
    tilt: float


class TapoController:
    """Wrap the ONVIF connection and PTZ services for the Tapo camera."""

    def __init__(self, config: TapoConfig):
        if not config.password:
            raise RuntimeError("TAPO_PASS environment variable is not set.")

        self.config = config
        self.cam = ONVIFCamera(config.ip, config.port, config.user, config.password)
        self.ptz = self.cam.create_ptz_service()
        self.profile_token = self._get_profile_token()
        self.min_pan, self.max_pan, self.min_tilt, self.max_tilt = self._get_pan_tilt_limits()

    def _get_profile_token(self) -> str:
        profiles = self.cam.create_media_service().GetProfiles()
        if not profiles:
            raise RuntimeError("No media profiles found on the camera.")
        return profiles[0].token

    def _get_pan_tilt_limits(self) -> tuple[float, float, float, float]:
        try:
            nodes = self.ptz.GetNodes()
            space = nodes[0].SupportedPTZSpaces.AbsolutePanTiltPositionSpace[0]
            return (
                float(space.XRange.Min),
                float(space.XRange.Max),
                float(space.YRange.Min),
                float(space.YRange.Max),
            )
        except Exception:
            return (-1.0, 1.0, -1.0, 1.0)

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

    def absolute_move(self, pan: float, tilt: float, speed: float = 1.0) -> None:
        req = self.ptz.create_type("AbsoluteMove")
        req.ProfileToken = self.profile_token
        req.Position = {
            "PanTilt": {
                "x": self._clamp(pan, self.min_pan, self.max_pan),
                "y": self._clamp(tilt, self.min_tilt, self.max_tilt),
            }
        }
        req.Speed = {"PanTilt": {"x": speed, "y": speed}}
        self.ptz.AbsoluteMove(req)

    def get_position(self) -> PTZPosition:
        status = self.ptz.GetStatus({"ProfileToken": self.profile_token})
        pan_tilt = getattr(status.Position, "PanTilt", None)
        if pan_tilt is None:
            raise RuntimeError("The camera did not report a PTZ position.")
        return PTZPosition(pan=float(pan_tilt.x), tilt=float(pan_tilt.y))

    def target_for_extreme(self, direction: str) -> PTZPosition:
        current = self.get_position()
        targets = {
            "left": PTZPosition(self.min_pan, current.tilt),
            "right": PTZPosition(self.max_pan, current.tilt),
            "up": PTZPosition(current.pan, self.min_tilt),
            "down": PTZPosition(current.pan, self.max_tilt),
        }
        try:
            return targets[direction]
        except KeyError as exc:
            raise ValueError(f"Invalid direction: {direction}") from exc

    def wait_until_position(
        self,
        target: PTZPosition,
        timeout_secs: float = 20.0,
        tolerance: float = 0.03,
        cancel_event: threading.Event | None = None,
    ) -> bool:
        deadline = time.monotonic() + timeout_secs
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                return False

            current = self.get_position()
            if (
                abs(current.pan - target.pan) <= tolerance
                and abs(current.tilt - target.tilt) <= tolerance
            ):
                return True

            time.sleep(0.2)
        return False

    def move_smoothly_to(
        self,
        target: PTZPosition,
        speed: float,
        segment_size: float,
        step_pause_secs: float,
        cancel_event: threading.Event | None = None,
    ) -> bool:
        current = self.get_position()
        delta_pan = target.pan - current.pan
        delta_tilt = target.tilt - current.tilt
        distance = max(abs(delta_pan), abs(delta_tilt))
        steps = max(1, math.ceil(distance / max(segment_size, 0.01)))

        for step_index in range(1, steps + 1):
            if cancel_event is not None and cancel_event.is_set():
                return False

            fraction = step_index / steps
            intermediate = PTZPosition(
                pan=current.pan + (delta_pan * fraction),
                tilt=current.tilt + (delta_tilt * fraction),
            )
            self.absolute_move(intermediate.pan, intermediate.tilt, speed=speed)
            reached = self.wait_until_position(intermediate, cancel_event=cancel_event)
            if not reached:
                return False

            if step_pause_secs > 0:
                time.sleep(step_pause_secs)

        return True

    def stop(self) -> None:
        self.ptz.Stop({"ProfileToken": self.profile_token})

    def _manual_touch(self, pan: float, tilt: float) -> None:
        self.move_continuous(pan, tilt)
        time.sleep(self.config.touch_secs)
        self.stop()

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))


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
        self._patrol_thread: threading.Thread | None = None
        self._patrol_cancel: threading.Event | None = None
        self._patrol_axis: str | None = None

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
            "patrol": {
                "running": self._is_patrol_running(),
                "axis": self._patrol_axis,
            },
        }

    def move_step(self, direction: str) -> dict[str, object]:
        amount = self.config.step
        if direction in {"up", "down"}:
            amount *= self.config.vertical_step_multiplier

        pan, tilt = direction_to_vector(direction, amount)
        with self._lock:
            self._cancel_stop_timer()
            self._cancel_patrol_locked()
            self.connect().move_step(pan, tilt)
        return {"ok": True, "mode": "step", "direction": direction}

    def move_continuous(self, direction: str) -> dict[str, object]:
        pan, tilt = direction_to_vector(direction, self.config.speed)
        with self._lock:
            self._cancel_patrol_locked()
            self.connect().move_continuous(pan, tilt)
            self._schedule_stop_timer()
        return {
            "ok": True,
            "mode": "continuous",
            "direction": direction,
            "timeout_secs": self.config.safety_timeout_secs,
        }

    def move_extreme(self, direction: str) -> dict[str, object]:
        with self._lock:
            self._cancel_stop_timer()
            self._cancel_patrol_locked()
            controller = self.connect()
            target = controller.target_for_extreme(direction)
            controller.absolute_move(target.pan, target.tilt)
        return {"ok": True, "mode": "extreme", "direction": direction}

    def start_patrol(self, axis: str) -> dict[str, object]:
        if axis not in {"horizontal", "vertical"}:
            raise ValueError(f"Invalid patrol axis: {axis}")

        with self._lock:
            self._cancel_stop_timer()
            self._cancel_patrol_locked()
            controller = self.connect()
            origin = controller.get_position()
            cancel_event = threading.Event()
            thread = threading.Thread(
                target=self._run_patrol,
                args=(axis, origin, cancel_event),
                daemon=True,
            )
            self._patrol_axis = axis
            self._patrol_cancel = cancel_event
            self._patrol_thread = thread
            thread.start()

        return {"ok": True, "mode": "patrol", "axis": axis}

    def stop(self) -> dict[str, object]:
        with self._lock:
            self._cancel_stop_timer()
            self._cancel_patrol_locked()
            self.connect().stop()
        return {"ok": True, "mode": "stop"}

    def stop_patrol(self) -> dict[str, object]:
        with self._lock:
            running = self._is_patrol_running()
            self._cancel_stop_timer()
            self._cancel_patrol_locked()
            if self._controller is not None:
                self._controller.stop()
        return {"ok": True, "mode": "patrol-stop", "was_running": running}

    def _run_patrol(self, axis: str, origin: PTZPosition, cancel_event: threading.Event) -> None:
        controller = self.connect()
        try:
            if axis == "horizontal":
                targets = (
                    PTZPosition(controller.min_pan, origin.tilt),
                    PTZPosition(controller.max_pan, origin.tilt),
                    origin,
                )
            else:
                targets = (
                    PTZPosition(origin.pan, controller.min_tilt),
                    PTZPosition(origin.pan, controller.max_tilt),
                    origin,
                )

            for target in targets:
                if cancel_event.is_set():
                    break
                reached = controller.move_smoothly_to(
                    target,
                    speed=self.config.speed,
                    segment_size=self.config.patrol_segment_size,
                    step_pause_secs=self.config.patrol_step_pause_secs,
                    cancel_event=cancel_event,
                )
                if not reached or cancel_event.is_set():
                    break
                time.sleep(0.25)
        finally:
            with self._lock:
                if self._patrol_cancel is cancel_event:
                    self._patrol_cancel = None
                    self._patrol_thread = None
                    self._patrol_axis = None

    def _is_patrol_running(self) -> bool:
        return self._patrol_thread is not None and self._patrol_thread.is_alive()

    def _schedule_stop_timer(self) -> None:
        self._cancel_stop_timer()
        self._stop_timer = threading.Timer(self.config.safety_timeout_secs, self._safe_stop)
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _cancel_stop_timer(self) -> None:
        if self._stop_timer is not None:
            self._stop_timer.cancel()
            self._stop_timer = None

    def _cancel_patrol_locked(self) -> None:
        cancel_event = self._patrol_cancel

        if cancel_event is None:
            return

        cancel_event.set()
        if self._controller is not None:
            try:
                self._controller.stop()
            except Exception:
                pass

        self._patrol_cancel = None
        self._patrol_thread = None
        self._patrol_axis = None

    def _safe_stop(self) -> None:
        with self._lock:
            if self._controller is None:
                return
            try:
                self._controller.stop()
            finally:
                self._stop_timer = None
