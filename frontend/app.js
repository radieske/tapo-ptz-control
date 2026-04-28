const state = {
  pressedKeys: new Set(),
  activePatrolAxis: null,
};

const elements = {
  streamView: document.getElementById("stream-view"),
  streamStatus: document.getElementById("stream-status"),
  controlButtons: Array.from(document.querySelectorAll("[data-action][data-direction]")),
  patrolButtons: Array.from(document.querySelectorAll("[data-patrol-axis]")),
  patrolStopButton: document.getElementById("patrol-stop-button"),
};

const keyDirectionMap = new Map([
  ["KeyW", "up"],
  ["ArrowUp", "up"],
  ["KeyA", "left"],
  ["ArrowLeft", "left"],
  ["KeyS", "down"],
  ["ArrowDown", "down"],
  ["KeyD", "right"],
  ["ArrowRight", "right"],
]);

const stepButtonsByDirection = new Map(
  elements.controlButtons
    .filter((button) => button.dataset.action === "step")
    .map((button) => [button.dataset.direction, button]),
);

let reconnectTimer = null;
let statusPollTimer = null;

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

function setStreamStatus(text) {
  elements.streamStatus.textContent = text;
}

function setPatrolState(axis) {
  state.activePatrolAxis = axis;
  elements.patrolButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.patrolAxis === axis);
  });
}

function clearPatrolState() {
  setPatrolState(null);
}

function stopStatusPolling() {
  if (statusPollTimer !== null) {
    window.clearInterval(statusPollTimer);
    statusPollTimer = null;
  }
}

function ensureStatusPolling() {
  if (statusPollTimer !== null) {
    return;
  }

  statusPollTimer = window.setInterval(() => {
    void refreshStatus();
  }, 2000);
}

function flashButton(button, durationMs = 140) {
  button.classList.add("is-active");
  window.setTimeout(() => {
    button.classList.remove("is-active");
  }, durationMs);
}

function scheduleStreamReconnect() {
  if (reconnectTimer) {
    return;
  }

  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null;
    reloadStream();
  }, 2000);
}

function reloadStream() {
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  setStreamStatus("Connecting video...");
  elements.streamView.src = `/stream.mjpeg?ts=${Date.now()}`;
}

async function sendStep(direction) {
  await api("/move/step", {
    method: "POST",
    body: JSON.stringify({ direction }),
  });
}

async function sendExtreme(direction) {
  await api("/move/extreme", {
    method: "POST",
    body: JSON.stringify({ direction }),
  });
}

async function sendStop() {
  await api("/stop", { method: "POST" });
}

async function sendPatrolStart(axis) {
  await api("/patrol/start", {
    method: "POST",
    body: JSON.stringify({ axis }),
  });
}

async function refreshStatus() {
  try {
    const data = await api("/status", { method: "GET" });
    if (data.patrol?.running) {
      setPatrolState(data.patrol.axis || null);
      ensureStatusPolling();
      return;
    }
    clearPatrolState();
    stopStatusPolling();
  } catch (error) {
    console.error(error.message);
  }
}

async function handleStep(button) {
  clearPatrolState();
  flashButton(button);

  try {
    await sendStep(button.dataset.direction);
  } catch (error) {
    console.error(error.message);
  }
}

async function handleExtreme(button) {
  clearPatrolState();
  flashButton(button, 220);

  try {
    await sendExtreme(button.dataset.direction);
  } catch (error) {
    console.error(error.message);
  }
}

async function triggerKeyboardStep(direction) {
  const button = stepButtonsByDirection.get(direction);
  if (!button) {
    return;
  }

  await handleStep(button);
}

async function handlePatrolStart(button) {
  const axis = button.dataset.patrolAxis;
  flashButton(button, 220);

  try {
    await sendPatrolStart(axis);
    setPatrolState(axis);
    ensureStatusPolling();
  } catch (error) {
    console.error(error.message);
  }
}

async function handleStop() {
  clearPatrolState();
  stopStatusPolling();

  try {
    await sendStop();
  } catch (error) {
    console.error(error.message);
  }
}

function bindControlButton(button) {
  button.addEventListener("click", async () => {
    if (button.dataset.action === "step") {
      await handleStep(button);
      return;
    }

    await handleExtreme(button);
  });
}

function handleKeyboardDown(event) {
  const direction = keyDirectionMap.get(event.code);
  if (!direction) {
    return;
  }

  event.preventDefault();
  if (state.pressedKeys.has(event.code)) {
    return;
  }

  state.pressedKeys.add(event.code);
  void triggerKeyboardStep(direction);
}

function handleKeyboardUp(event) {
  if (!keyDirectionMap.has(event.code)) {
    return;
  }

  event.preventDefault();
  state.pressedKeys.delete(event.code);
}

elements.controlButtons.forEach(bindControlButton);

elements.patrolButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    await handlePatrolStart(button);
  });
});

elements.patrolStopButton.addEventListener("click", async () => {
  flashButton(elements.patrolStopButton, 220);
  await handleStop();
});

window.addEventListener("blur", () => {
  state.pressedKeys.clear();
});

window.addEventListener("keydown", handleKeyboardDown);
window.addEventListener("keyup", handleKeyboardUp);

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") {
    state.pressedKeys.clear();
  }
});

elements.streamView.addEventListener("load", () => {
  setStreamStatus("Live video connected.");
});

elements.streamView.addEventListener("error", () => {
  setStreamStatus("Could not load the video stream.");
  scheduleStreamReconnect();
});

void refreshStatus();
reloadStream();
