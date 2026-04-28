import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None


load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True)
class TapoStreamConfig:
    ip: str
    user: str
    password: str
    rtsp_port: int
    stream_path: str
    jpeg_quality: int = 80
    reconnect_delay_secs: float = 1.0

    @classmethod
    def from_env(cls) -> "TapoStreamConfig":
        return cls(
            ip=os.getenv("TAPO_IP", "192.168.1.7"),
            user=os.getenv("TAPO_USER", "admin"),
            password=os.getenv("TAPO_PASS", ""),
            rtsp_port=int(os.getenv("TAPO_RTSP_PORT", "554")),
            stream_path=os.getenv("TAPO_STREAM_PATH", "stream1"),
        )

    @property
    def rtsp_url(self) -> str:
        if not self.password:
            raise RuntimeError("TAPO_PASS environment variable is not set.")

        user = quote(self.user, safe="")
        password = quote(self.password, safe="")
        path = self.stream_path.lstrip("/")
        return f"rtsp://{user}:{password}@{self.ip}:{self.rtsp_port}/{path}"


class TapoStreamService:
    def __init__(self, config: TapoStreamConfig | None = None):
        self.config = config or TapoStreamConfig.from_env()

    def probe(self) -> None:
        self._ensure_opencv()
        capture = self._open_capture()
        capture.release()

    def mjpeg_chunks(self):
        while True:
            try:
                capture = self._open_capture()
            except RuntimeError:
                time.sleep(self.config.reconnect_delay_secs)
                continue

            try:
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break

                    ok, encoded = cv2.imencode(
                        ".jpg",
                        frame,
                        [int(cv2.IMWRITE_JPEG_QUALITY), self.config.jpeg_quality],
                    )
                    if not ok:
                        continue

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + encoded.tobytes()
                        + b"\r\n"
                    )
            finally:
                capture.release()

            time.sleep(self.config.reconnect_delay_secs)

    def _open_capture(self):
        self._ensure_opencv()
        capture = cv2.VideoCapture(self.config.rtsp_url, cv2.CAP_FFMPEG)
        if capture.isOpened():
            return capture

        capture.release()
        raise RuntimeError(
            "Could not open the RTSP stream. Check TAPO_RTSP_PORT, TAPO_STREAM_PATH, "
            "and whether the camera stream is enabled."
        )

    @staticmethod
    def _ensure_opencv() -> None:
        if cv2 is None:
            raise RuntimeError(
                "OpenCV is not installed. Install dependencies with: pip install -r requirements.txt"
            )
