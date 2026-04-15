import os

import uvicorn


def main() -> None:
    host = os.getenv("TAPO_WEB_HOST", "0.0.0.0")
    port = int(os.getenv("TAPO_WEB_PORT", "8000"))
    reload_enabled = os.getenv("TAPO_WEB_RELOAD", "").lower() in {"1", "true", "yes", "on"}

    uvicorn.run("backend.app:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    main()
