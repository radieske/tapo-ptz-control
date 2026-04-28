const state = {
  mode: "tap",
  activeDirection: null,
};

const elements = {
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  hintText: document.getElementById("hint-text"),
  feedback: document.getElementById("feedback"),
  streamView: document.getElementById("stream-view"),
  streamStatus: document.getElementById("stream-status"),
  reloadStreamButton: document.getElementById("reload-stream-button"),
  stopButton: document.getElementById("stop-button"),
  modeButtons: Array.from(document.querySelectorAll("[data-mode]")),
  directionButtons: Array.from(document.querySelectorAll("[data-direction]")),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || "Request failed.";
    throw new Error(detail);
  }
  return payload;
}

function setMode(mode) {
  state.mode = mode;
  elements.modeButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.mode === mode);
  });
  elements.hintText.textContent =
    mode === "tap"
      ? "Tap a direction for a short step."
      : "Press and hold a direction to keep moving. Release to stop.";
  elements.feedback.textContent = "";
}

function setStatus(kind, text) {
  elements.statusDot.classList.remove("is-online", "is-error");
  if (kind === "online") {
    elements.statusDot.classList.add("is-online");
  }
  if (kind === "error") {
    elements.statusDot.classList.add("is-error");
  }
  elements.statusText.textContent = text;
}

function setStreamStatus(kind, text) {
  elements.streamStatus.classList.remove("is-online", "is-error");
  if (kind === "online") {
    elements.streamStatus.classList.add("is-online");
  }
  if (kind === "error") {
    elements.streamStatus.classList.add("is-error");
  }
  elements.streamStatus.textContent = text;
}

function reloadStream() {
  setStreamStatus("loading", "Connecting video...");
  elements.streamView.src = `/stream.mjpeg?ts=${Date.now()}`;
}

async function refreshStatus() {
  try {
    const data = await api("/status", { method: "GET" });
    setStatus("online", `Connected to ${data.camera.ip}:${data.camera.port}`);
  } catch (error) {
    setStatus("error", `Camera unavailable: ${error.message}`);
  }
}

async function sendStep(direction) {
  const data = await api("/move/step", {
    method: "POST",
    body: JSON.stringify({ direction }),
  });
  elements.feedback.textContent = `Step ${data.direction}.`;
}

async function sendContinuous(direction) {
  const data = await api("/move/continuous", {
    method: "POST",
    body: JSON.stringify({ direction }),
  });
  elements.feedback.textContent = `Moving ${data.direction}. Safety stop in ${data.timeout_secs}s.`;
}

async function sendStop() {
  const data = await api("/stop", { method: "POST" });
  elements.feedback.textContent = data.ok ? "Motor stopped." : "";
}

async function handleTap(button) {
  try {
    await sendStep(button.dataset.direction);
  } catch (error) {
    elements.feedback.textContent = error.message;
  }
}

async function startContinuous(button) {
  const direction = button.dataset.direction;
  if (state.activeDirection === direction) {
    return;
  }

  state.activeDirection = direction;
  button.classList.add("is-pressed");

  try {
    await sendContinuous(direction);
  } catch (error) {
    elements.feedback.textContent = error.message;
    state.activeDirection = null;
    button.classList.remove("is-pressed");
  }
}

async function stopContinuous() {
  if (!state.activeDirection) {
    return;
  }

  state.activeDirection = null;
  elements.directionButtons.forEach((button) => button.classList.remove("is-pressed"));

  try {
    await sendStop();
  } catch (error) {
    elements.feedback.textContent = error.message;
  }
}

function bindDirectionButton(button) {
  button.addEventListener("click", async () => {
    if (state.mode !== "tap") {
      return;
    }
    await handleTap(button);
  });

  const start = async (event) => {
    if (state.mode !== "continuous") {
      return;
    }
    event.preventDefault();
    await startContinuous(button);
  };

  const stop = async (event) => {
    if (state.mode !== "continuous") {
      return;
    }
    event.preventDefault();
    await stopContinuous();
  };

  button.addEventListener("mousedown", start);
  button.addEventListener("mouseup", stop);
  button.addEventListener("mouseleave", stop);
  button.addEventListener("touchstart", start, { passive: false });
  button.addEventListener("touchend", stop, { passive: false });
  button.addEventListener("touchcancel", stop, { passive: false });
}

elements.modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

elements.directionButtons.forEach(bindDirectionButton);

elements.stopButton.addEventListener("click", async () => {
  state.activeDirection = null;
  elements.directionButtons.forEach((button) => button.classList.remove("is-pressed"));
  try {
    await sendStop();
  } catch (error) {
    elements.feedback.textContent = error.message;
  }
});

window.addEventListener("mouseup", stopContinuous);
window.addEventListener("touchend", stopContinuous, { passive: false });
window.addEventListener("touchcancel", stopContinuous, { passive: false });
window.addEventListener("blur", stopContinuous);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") {
    void stopContinuous();
  }
});

elements.streamView.addEventListener("load", () => {
  setStreamStatus("online", "Live video connected.");
});

elements.streamView.addEventListener("error", () => {
  setStreamStatus("error", "Could not load the video stream.");
});

elements.reloadStreamButton.addEventListener("click", reloadStream);

setMode("tap");
void refreshStatus();
reloadStream();
