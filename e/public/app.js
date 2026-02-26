import { EditorState, createDefaultDocument } from "./editor-state.js";
import { HistoryManager } from "./history.js";
import { fetchMapFile, fetchMapList, saveMapFile, validateMapData } from "./io.js";

const state = new EditorState();
const history = new HistoryManager(300);

const canvas = document.getElementById("editorCanvas");
const ctx = canvas.getContext("2d");

const fileNameInput = document.getElementById("fileName");
const mapSelect = document.getElementById("mapSelect");
const statusText = document.getElementById("statusText");
const errorList = document.getElementById("errorList");

const metaIdInput = document.getElementById("metaId");
const metaNameInput = document.getElementById("metaName");
const metaAuthorInput = document.getElementById("metaAuthor");
const metaVersionInput = document.getElementById("metaVersion");
const tileSizeInput = document.getElementById("tileSize");
const mapWidthInput = document.getElementById("mapWidth");
const mapHeightInput = document.getElementById("mapHeight");
const allowSpikesInput = document.getElementById("allowSpikes");
const timeLimitInput = document.getElementById("timeLimit");
const tutorialJsonInput = document.getElementById("tutorialJson");
const portalIdInput = document.getElementById("portalId");

const toolButtons = [...document.querySelectorAll(".tool-btn")];
const tileButtons = [...document.querySelectorAll(".tile-btn")];

const TILE_COLORS = {
  EMPTY: "#1c2231",
  WALL: "#6f7f9f",
  SPAWN: "#7390c9",
  GOAL: "#67b271",
  SPIKE: "#d36666",
  PORTAL: "#50b8d7",
};

let lastCanvasWidth = 0;
let lastCanvasHeight = 0;

let isSpacePressed = false;
let dragMode = null;
let hoverTile = null;
let panLast = null;
let rectPreview = null;

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.style.color = isError ? "#ff8890" : "#b9c9e8";
}

function setErrors(errors = []) {
  errorList.innerHTML = "";
  for (const err of errors) {
    const item = document.createElement("li");
    item.textContent = `${err.field}: ${err.message}`;
    errorList.appendChild(item);
  }
}

function normalizeFilename(rawValue) {
  let name = String(rawValue || "").trim();
  if (!name.toLowerCase().endsWith(".json")) {
    name = `${name}.json`;
  }
  return name;
}

function isInputFocused() {
  const active = document.activeElement;
  if (!active) {
    return false;
  }
  return ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
}

function syncControlValues() {
  metaIdInput.value = state.doc.meta.id;
  metaNameInput.value = state.doc.meta.name;
  metaAuthorInput.value = state.doc.meta.author;
  metaVersionInput.value = state.doc.meta.version;
  tileSizeInput.value = state.doc.tile_size;
  mapWidthInput.value = state.doc.width;
  mapHeightInput.value = state.doc.height;
  allowSpikesInput.value = state.doc.rules.allow_spikes ? "true" : "false";
  timeLimitInput.value =
    state.doc.rules.time_limit_sec === null ? "null" : String(state.doc.rules.time_limit_sec);
  tutorialJsonInput.value = JSON.stringify(state.doc.tutorial, null, 2);
  portalIdInput.value = state.selectedPortalId;
}

function syncToolButtons() {
  for (const btn of toolButtons) {
    btn.classList.toggle("active", btn.dataset.tool === state.tool);
  }
}

function syncTileButtons() {
  for (const btn of tileButtons) {
    btn.classList.toggle("active", btn.dataset.tile === state.selectedTileType);
  }
}

function commitDocChange(beforeDoc, label) {
  const after = state.cloneDoc();
  history.record(beforeDoc, after, label);
}

function setDocAndSync(nextDoc) {
  state.setDoc(nextDoc);
  syncControlValues();
  syncToolButtons();
  syncTileButtons();
  setErrors([]);
}

function resizeCanvasIfNeeded() {
  const bounds = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(bounds.width));
  const height = Math.max(1, Math.floor(bounds.height));
  if (width !== lastCanvasWidth || height !== lastCanvasHeight) {
    lastCanvasWidth = width;
    lastCanvasHeight = height;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
}

function worldToScreen(x, y) {
  return {
    x: x * state.zoom + state.panX,
    y: y * state.zoom + state.panY,
  };
}

function screenToTile(sx, sy) {
  const worldX = (sx - state.panX) / state.zoom;
  const worldY = (sy - state.panY) / state.zoom;
  const tileSize = state.doc.tile_size;
  const tx = Math.floor(worldX / tileSize);
  const ty = Math.floor(worldY / tileSize);
  return { tx, ty };
}

function tileInBounds(tx, ty) {
  return tx >= 0 && ty >= 0 && tx < state.width && ty < state.height;
}

function getMousePos(evt) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: evt.clientX - rect.left,
    y: evt.clientY - rect.top,
  };
}

function applyTileFromButton(tx, ty, button) {
  if (!tileInBounds(tx, ty)) {
    return false;
  }
  const type = button === 2 ? "EMPTY" : state.selectedTileType;
  return state.setTileAt(tx, ty, type, state.selectedPortalId);
}

function drawScene() {
  resizeCanvasIfNeeded();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const dpr = window.devicePixelRatio || 1;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const viewW = canvas.width / dpr;
  const viewH = canvas.height / dpr;

  ctx.fillStyle = "#11151d";
  ctx.fillRect(0, 0, viewW, viewH);

  const tileSizePx = state.doc.tile_size * state.zoom;
  const mapWorldW = state.doc.width * state.doc.tile_size;
  const mapWorldH = state.doc.height * state.doc.tile_size;
  const mapScreen = worldToScreen(0, 0);
  const mapScreenW = mapWorldW * state.zoom;
  const mapScreenH = mapWorldH * state.zoom;

  ctx.fillStyle = "#0f1624";
  ctx.fillRect(mapScreen.x, mapScreen.y, mapScreenW, mapScreenH);

  const startTx = Math.max(0, Math.floor((-state.panX / state.zoom) / state.doc.tile_size) - 1);
  const startTy = Math.max(0, Math.floor((-state.panY / state.zoom) / state.doc.tile_size) - 1);
  const endTx = Math.min(
    state.width - 1,
    Math.ceil(((viewW - state.panX) / state.zoom) / state.doc.tile_size) + 1
  );
  const endTy = Math.min(
    state.height - 1,
    Math.ceil(((viewH - state.panY) / state.zoom) / state.doc.tile_size) + 1
  );

  for (let ty = startTy; ty <= endTy; ty += 1) {
    for (let tx = startTx; tx <= endTx; tx += 1) {
      const ch = state.getCellChar(tx, ty);
      const mapped = ch ? state.doc.legend[ch] : "EMPTY";
      const tileType = typeof mapped === "string" && mapped.startsWith("PORTAL:") ? "PORTAL" : mapped;
      const screen = worldToScreen(tx * state.doc.tile_size, ty * state.doc.tile_size);
      const color = TILE_COLORS[tileType] ?? TILE_COLORS.EMPTY;

      ctx.fillStyle = color;
      ctx.fillRect(screen.x, screen.y, tileSizePx, tileSizePx);
      ctx.strokeStyle = "rgba(15,20,32,0.7)";
      ctx.lineWidth = 1;
      ctx.strokeRect(screen.x, screen.y, tileSizePx, tileSizePx);

      if (tileType === "PORTAL") {
        ctx.strokeStyle = "rgba(188,245,255,0.95)";
        ctx.lineWidth = Math.max(1, tileSizePx * 0.08);
        ctx.strokeRect(screen.x + tileSizePx * 0.2, screen.y + tileSizePx * 0.2, tileSizePx * 0.6, tileSizePx * 0.6);
      }
    }
  }

  if (state.selection) {
    const sel = state.selection;
    const screen = worldToScreen(sel.x * state.doc.tile_size, sel.y * state.doc.tile_size);
    ctx.strokeStyle = "#ffe48f";
    ctx.lineWidth = 2;
    ctx.strokeRect(screen.x, screen.y, sel.w * tileSizePx, sel.h * tileSizePx);
  }

  if (rectPreview) {
    const screen = worldToScreen(rectPreview.x * state.doc.tile_size, rectPreview.y * state.doc.tile_size);
    ctx.fillStyle = "rgba(120, 190, 255, 0.2)";
    ctx.fillRect(screen.x, screen.y, rectPreview.w * tileSizePx, rectPreview.h * tileSizePx);
    ctx.strokeStyle = "rgba(140, 208, 255, 0.9)";
    ctx.lineWidth = 2;
    ctx.strokeRect(screen.x, screen.y, rectPreview.w * tileSizePx, rectPreview.h * tileSizePx);
  }

  if (state.pasteMode && state.clipboard && state.pasteAnchor) {
    const anchor = state.pasteAnchor;
    const screen = worldToScreen(anchor.x * state.doc.tile_size, anchor.y * state.doc.tile_size);
    ctx.fillStyle = "rgba(120, 255, 163, 0.18)";
    ctx.fillRect(
      screen.x,
      screen.y,
      state.clipboard.w * tileSizePx,
      state.clipboard.h * tileSizePx
    );
    ctx.strokeStyle = "rgba(120, 255, 163, 0.9)";
    ctx.lineWidth = 2;
    ctx.strokeRect(
      screen.x,
      screen.y,
      state.clipboard.w * tileSizePx,
      state.clipboard.h * tileSizePx
    );
  }

  if (hoverTile && tileInBounds(hoverTile.tx, hoverTile.ty)) {
    const screen = worldToScreen(hoverTile.tx * state.doc.tile_size, hoverTile.ty * state.doc.tile_size);
    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = 1;
    ctx.strokeRect(screen.x + 0.5, screen.y + 0.5, tileSizePx - 1, tileSizePx - 1);
  }

  ctx.fillStyle = "rgba(8, 10, 18, 0.7)";
  ctx.fillRect(10, 10, 290, 54);
  ctx.fillStyle = "#d6e6ff";
  ctx.font = "12px Malgun Gothic, NanumGothic, Arial";
  ctx.fillText(
    `Tool:${state.tool}  Tile:${state.selectedTileType}  Portal:${state.selectedPortalId}`,
    18,
    30
  );
  ctx.fillText(
    `Map:${state.doc.width}x${state.doc.height}  Zoom:${state.zoom.toFixed(2)}  Spawn:${state.countTileType("SPAWN")}`,
    18,
    48
  );
}

function animationLoop() {
  drawScene();
  requestAnimationFrame(animationLoop);
}

async function refreshMapList(selectedName = null) {
  try {
    const maps = await fetchMapList();
    mapSelect.innerHTML = "";
    for (const map of maps) {
      const opt = document.createElement("option");
      opt.value = map.filename;
      opt.textContent = `${map.filename} | ${map.name}`;
      mapSelect.appendChild(opt);
    }
    if (selectedName) {
      mapSelect.value = selectedName;
    }
    setStatus(`맵 목록 ${maps.length}개 로드됨`);
  } catch (err) {
    setStatus(`맵 목록 로드 실패: ${err.message}`, true);
  }
}

async function runValidationAndShow() {
  const doc = state.toSerializable();
  const result = await validateMapData(doc);
  setErrors(result.errors || []);
  if (result.ok) {
    setStatus("검증 통과");
  } else {
    setStatus(`검증 실패 (${result.errors.length}개)`, true);
  }
  return result;
}

function applyMetaFromInputs() {
  const before = state.cloneDoc();
  state.doc.meta.id = metaIdInput.value.trim() || "new_map";
  state.doc.meta.name = metaNameInput.value.trim() || "새 맵";
  state.doc.meta.author = metaAuthorInput.value.trim() || "editor";
  state.doc.meta.version = Math.max(1, Math.trunc(Number(metaVersionInput.value) || 1));
  state.doc.tile_size = Math.max(1, Math.trunc(Number(tileSizeInput.value) || 32));
  state.doc.rules.allow_spikes = allowSpikesInput.value === "true";

  const rawLimit = timeLimitInput.value.trim();
  if (rawLimit === "" || rawLimit.toLowerCase() === "null") {
    state.doc.rules.time_limit_sec = null;
  } else {
    const parsed = Number(rawLimit);
    state.doc.rules.time_limit_sec = Number.isFinite(parsed) ? parsed : null;
  }

  try {
    const parsedTutorial = JSON.parse(tutorialJsonInput.value || "[]");
    if (Array.isArray(parsedTutorial)) {
      state.doc.tutorial = parsedTutorial;
    } else {
      setStatus("tutorial JSON은 배열이어야 합니다.", true);
    }
  } catch {
    setStatus("tutorial JSON 파싱 실패", true);
  }

  commitDocChange(before, "meta");
}

function bindPanelEvents() {
  document.getElementById("newMapBtn").addEventListener("click", () => {
    const before = state.cloneDoc();
    setDocAndSync(createDefaultDocument());
    history.record(before, state.cloneDoc(), "new_map");
    setStatus("새 맵 생성");
  });

  document.getElementById("saveBtn").addEventListener("click", async () => {
    try {
      applyMetaFromInputs();
      const filename = normalizeFilename(fileNameInput.value);
      fileNameInput.value = filename;
      const validation = await runValidationAndShow();
      if (!validation.ok) {
        return;
      }
      await saveMapFile(filename, state.toSerializable());
      await refreshMapList(filename);
      setStatus(`저장 완료: ${filename}`);
    } catch (err) {
      const payloadErrors = err.payload && err.payload.errors ? err.payload.errors : [];
      setErrors(payloadErrors);
      setStatus(`저장 실패: ${err.message}`, true);
    }
  });

  document.getElementById("saveAsBtn").addEventListener("click", async () => {
    const suggested = normalizeFilename(fileNameInput.value || `${state.doc.meta.id}.json`);
    const input = window.prompt("저장할 파일명을 입력하세요", suggested);
    if (!input) {
      return;
    }
    fileNameInput.value = normalizeFilename(input);
    document.getElementById("saveBtn").click();
  });

  document.getElementById("reloadListBtn").addEventListener("click", () => {
    refreshMapList();
  });

  document.getElementById("loadBtn").addEventListener("click", async () => {
    const filename = mapSelect.value;
    if (!filename) {
      setStatus("불러올 파일을 먼저 선택하세요.", true);
      return;
    }
    try {
      const data = await fetchMapFile(filename);
      setDocAndSync(data);
      history.reset();
      fileNameInput.value = filename;
      setStatus(`불러오기 완료: ${filename}`);
    } catch (err) {
      setStatus(`불러오기 실패: ${err.message}`, true);
    }
  });

  document.getElementById("validateBtn").addEventListener("click", async () => {
    try {
      applyMetaFromInputs();
      await runValidationAndShow();
    } catch (err) {
      setStatus(`검증 실패: ${err.message}`, true);
    }
  });

  document.getElementById("resizeBtn").addEventListener("click", () => {
    const before = state.cloneDoc();
    const changed = state.resizeMap(mapWidthInput.value, mapHeightInput.value);
    if (changed) {
      commitDocChange(before, "resize");
      syncControlValues();
      setStatus(`맵 크기 변경: ${state.width}x${state.height}`);
    } else {
      setStatus("맵 크기 변경 없음");
    }
  });

  for (const btn of toolButtons) {
    btn.addEventListener("click", () => {
      state.tool = btn.dataset.tool;
      rectPreview = null;
      syncToolButtons();
    });
  }

  for (const btn of tileButtons) {
    btn.addEventListener("click", () => {
      state.selectedTileType = btn.dataset.tile;
      syncTileButtons();
    });
  }

  portalIdInput.addEventListener("change", () => {
    state.selectedPortalId = Math.max(1, Math.trunc(Number(portalIdInput.value) || 1));
    portalIdInput.value = state.selectedPortalId;
  });

  for (const el of [
    metaIdInput,
    metaNameInput,
    metaAuthorInput,
    metaVersionInput,
    tileSizeInput,
    allowSpikesInput,
    timeLimitInput,
    tutorialJsonInput,
  ]) {
    el.addEventListener("change", applyMetaFromInputs);
  }
}

function startPan(evt) {
  dragMode = { type: "pan" };
  panLast = { x: evt.clientX, y: evt.clientY };
}

function handleCanvasMouseDown(evt) {
  const pos = getMousePos(evt);
  const tile = screenToTile(pos.x, pos.y);
  hoverTile = tile;

  if (state.pasteMode) {
    if (evt.button === 2) {
      state.pasteMode = false;
      state.pasteAnchor = null;
      setStatus("붙여넣기 취소");
      return;
    }
    if (evt.button === 0 && state.clipboard && tileInBounds(tile.tx, tile.ty)) {
      const before = state.cloneDoc();
      const changed = state.pasteClipboardAt(tile.tx, tile.ty);
      if (changed) {
        commitDocChange(before, "paste");
        setStatus("붙여넣기 완료");
      }
      state.pasteMode = false;
      state.pasteAnchor = null;
    }
    return;
  }

  if (evt.button === 1 || isSpacePressed) {
    startPan(evt);
    return;
  }

  if (![0, 2].includes(evt.button)) {
    return;
  }

  if (state.tool === "pen") {
    dragMode = {
      type: "pen",
      button: evt.button,
      before: state.cloneDoc(),
    };
    applyTileFromButton(tile.tx, tile.ty, evt.button);
    return;
  }

  if (state.tool === "rect") {
    dragMode = {
      type: "rect",
      button: evt.button,
      start: tile,
      current: tile,
      before: state.cloneDoc(),
    };
    rectPreview = state.normalizeRect(tile, tile);
    return;
  }

  if (state.tool === "select" && evt.button === 0) {
    dragMode = {
      type: "select",
      start: tile,
      current: tile,
    };
    rectPreview = state.normalizeRect(tile, tile);
  }
}

function handleCanvasMouseMove(evt) {
  const pos = getMousePos(evt);
  const tile = screenToTile(pos.x, pos.y);
  hoverTile = tile;

  if (state.pasteMode) {
    if (tileInBounds(tile.tx, tile.ty)) {
      state.pasteAnchor = tile;
    }
    return;
  }

  if (!dragMode) {
    return;
  }

  if (dragMode.type === "pan" && panLast) {
    state.panX += evt.clientX - panLast.x;
    state.panY += evt.clientY - panLast.y;
    panLast = { x: evt.clientX, y: evt.clientY };
    return;
  }

  if (dragMode.type === "pen") {
    applyTileFromButton(tile.tx, tile.ty, dragMode.button);
    return;
  }

  if (dragMode.type === "rect" || dragMode.type === "select") {
    dragMode.current = tile;
    rectPreview = state.normalizeRect(dragMode.start, dragMode.current);
  }
}

function handleCanvasMouseUp(_evt) {
  if (!dragMode) {
    return;
  }

  if (dragMode.type === "pan") {
    dragMode = null;
    panLast = null;
    return;
  }

  if (dragMode.type === "pen") {
    commitDocChange(dragMode.before, "paint");
    dragMode = null;
    return;
  }

  if (dragMode.type === "rect") {
    const rect = state.normalizeRect(dragMode.start, dragMode.current);
    const type = dragMode.button === 2 ? "EMPTY" : state.selectedTileType;
    state.fillRect(rect, type, state.selectedPortalId);
    commitDocChange(dragMode.before, "rect_fill");
    dragMode = null;
    rectPreview = null;
    return;
  }

  if (dragMode.type === "select") {
    state.selection = state.normalizeRect(dragMode.start, dragMode.current);
    setStatus(`선택: ${state.selection.w}x${state.selection.h}`);
    dragMode = null;
    rectPreview = null;
  }
}

function bindCanvasEvents() {
  canvas.addEventListener("contextmenu", (evt) => evt.preventDefault());
  canvas.addEventListener("mousedown", handleCanvasMouseDown);
  window.addEventListener("mousemove", handleCanvasMouseMove);
  window.addEventListener("mouseup", handleCanvasMouseUp);
  canvas.addEventListener("wheel", (evt) => {
    evt.preventDefault();
    const pos = getMousePos(evt);
    const worldX = (pos.x - state.panX) / state.zoom;
    const worldY = (pos.y - state.panY) / state.zoom;
    const factor = evt.deltaY < 0 ? 1.1 : 0.9;
    const nextZoom = Math.max(0.25, Math.min(4.0, state.zoom * factor));
    state.zoom = nextZoom;
    state.panX = pos.x - worldX * state.zoom;
    state.panY = pos.y - worldY * state.zoom;
  });
}

function bindKeyboardEvents() {
  window.addEventListener("keydown", (evt) => {
    if (evt.code === "Space") {
      isSpacePressed = true;
      return;
    }
    if (isInputFocused()) {
      return;
    }

    if (evt.ctrlKey && evt.key.toLowerCase() === "z") {
      evt.preventDefault();
      const next = history.undo(state.cloneDoc());
      if (next) {
        setDocAndSync(next);
        setStatus("실행 취소");
      }
      return;
    }
    if (evt.ctrlKey && evt.key.toLowerCase() === "y") {
      evt.preventDefault();
      const next = history.redo(state.cloneDoc());
      if (next) {
        setDocAndSync(next);
        setStatus("다시 실행");
      }
      return;
    }
    if (evt.ctrlKey && evt.key.toLowerCase() === "c") {
      evt.preventDefault();
      if (state.copySelectionToClipboard()) {
        setStatus("선택 영역 복사됨");
      }
      return;
    }
    if (evt.ctrlKey && evt.key.toLowerCase() === "v") {
      evt.preventDefault();
      if (state.clipboard) {
        state.pasteMode = true;
        state.pasteAnchor = hoverTile && tileInBounds(hoverTile.tx, hoverTile.ty) ? hoverTile : null;
        setStatus("붙여넣기 모드: 좌클릭 확정, 우클릭 취소");
      }
      return;
    }
    if (evt.ctrlKey && evt.key.toLowerCase() === "s") {
      evt.preventDefault();
      document.getElementById("saveBtn").click();
      return;
    }
    if (evt.key === "Escape") {
      state.pasteMode = false;
      state.pasteAnchor = null;
      rectPreview = null;
      dragMode = null;
      return;
    }
    if (evt.key === "Delete" && state.selection) {
      evt.preventDefault();
      const before = state.cloneDoc();
      state.clearRect(state.selection);
      commitDocChange(before, "delete_selection");
      setStatus("선택 영역 삭제");
    }
  });

  window.addEventListener("keyup", (evt) => {
    if (evt.code === "Space") {
      isSpacePressed = false;
    }
  });
}

async function boot() {
  bindPanelEvents();
  bindCanvasEvents();
  bindKeyboardEvents();
  syncControlValues();
  syncToolButtons();
  syncTileButtons();
  await refreshMapList();
  animationLoop();
}

boot();
