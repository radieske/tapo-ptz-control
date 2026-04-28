from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from shared.stream import TapoStreamService
from shared.tapo import TapoService


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Tapo PTZ Control API", version="1.0.0")
service = TapoService()
stream_service = TapoStreamService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MoveCommand(BaseModel):
    direction: str


@app.get("/status")
def get_status() -> dict[str, object]:
    try:
        return service.status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/move/step")
def move_step(command: MoveCommand) -> dict[str, object]:
    try:
        return service.move_step(command.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/move/continuous")
def move_continuous(command: MoveCommand) -> dict[str, object]:
    try:
        return service.move_continuous(command.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/stop")
def stop() -> dict[str, object]:
    try:
        return service.stop()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/stream.mjpeg")
def stream_mjpeg() -> StreamingResponse:
    try:
        stream_service.probe()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return StreamingResponse(
        stream_service.mjpeg_chunks(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="frontend-assets")


@app.get("/")
def index() -> FileResponse:
    if not FRONTEND_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend directory not found.")
    return FileResponse(FRONTEND_DIR / "index.html")
