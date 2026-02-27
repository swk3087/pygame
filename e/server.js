const fs = require("fs/promises");
const path = require("path");
const express = require("express");

const ROOT_DIR = __dirname;
const MAPS_DIR = path.resolve(ROOT_DIR, "maps");
const PUBLIC_DIR = path.resolve(ROOT_DIR, "public");
const DEFAULT_PORT = 5173;

const MIN_MAP_SIZE = 8;
const MAX_MAP_SIZE = 80;
const BASE_TILE_TYPES = new Set(["EMPTY", "WALL", "SPAWN", "GOAL", "SPIKE"]);

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function toInt(value, fallback = NaN) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return fallback;
  }
  return Math.trunc(num);
}

function sanitizeFilename(input) {
  if (typeof input !== "string") {
    throw new Error("filename must be a string");
  }
  const trimmed = input.trim();
  if (!/^[A-Za-z0-9._-]+\.json$/u.test(trimmed)) {
    throw new Error("invalid filename");
  }
  if (trimmed.includes("..")) {
    throw new Error("invalid filename");
  }
  return trimmed;
}

function resolveMapPath(filename) {
  const safeName = sanitizeFilename(filename);
  const resolved = path.resolve(MAPS_DIR, safeName);
  const mapsPrefix = `${MAPS_DIR}${path.sep}`;
  if (resolved !== path.resolve(MAPS_DIR, safeName) || !resolved.startsWith(mapsPrefix)) {
    throw new Error("path traversal blocked");
  }
  return resolved;
}

function validateMapDocument(doc) {
  const errors = [];

  if (!isObject(doc)) {
    return {
      ok: false,
      errors: [{ field: "root", message: "문서 루트는 객체여야 합니다." }],
    };
  }

  const meta = doc.meta;
  if (!isObject(meta)) {
    errors.push({ field: "meta", message: "meta 객체가 필요합니다." });
  } else {
    if (typeof meta.id !== "string" || meta.id.trim() === "") {
      errors.push({ field: "meta.id", message: "meta.id는 비어있지 않은 문자열이어야 합니다." });
    }
    if (typeof meta.name !== "string" || meta.name.trim() === "") {
      errors.push({ field: "meta.name", message: "meta.name은 비어있지 않은 문자열이어야 합니다." });
    }
    if (typeof meta.author !== "string") {
      errors.push({ field: "meta.author", message: "meta.author는 문자열이어야 합니다." });
    }
    const version = toInt(meta.version);
    if (!Number.isFinite(version) || version < 1) {
      errors.push({ field: "meta.version", message: "meta.version은 1 이상의 정수여야 합니다." });
    }
  }

  const tileSize = toInt(doc.tile_size);
  if (!Number.isFinite(tileSize) || tileSize < 1) {
    errors.push({ field: "tile_size", message: "tile_size는 1 이상의 정수여야 합니다." });
  }

  const width = toInt(doc.width);
  const height = toInt(doc.height);
  if (!Number.isFinite(width) || width < MIN_MAP_SIZE || width > MAX_MAP_SIZE) {
    errors.push({
      field: "width",
      message: `width는 ${MIN_MAP_SIZE}~${MAX_MAP_SIZE} 범위 정수여야 합니다.`,
    });
  }
  if (!Number.isFinite(height) || height < MIN_MAP_SIZE || height > MAX_MAP_SIZE) {
    errors.push({
      field: "height",
      message: `height는 ${MIN_MAP_SIZE}~${MAX_MAP_SIZE} 범위 정수여야 합니다.`,
    });
  }

  const legend = doc.legend;
  if (!isObject(legend)) {
    errors.push({ field: "legend", message: "legend 객체가 필요합니다." });
  }

  const grid = doc.grid;
  if (!Array.isArray(grid) || !grid.every((row) => typeof row === "string")) {
    errors.push({ field: "grid", message: "grid는 문자열 배열이어야 합니다." });
  }

  if (Array.isArray(grid) && Number.isFinite(height) && grid.length !== height) {
    errors.push({
      field: "grid",
      message: `height(${height})와 grid 줄 수(${grid.length})가 일치하지 않습니다.`,
    });
  }
  if (Array.isArray(grid) && Number.isFinite(width)) {
    for (let i = 0; i < grid.length; i += 1) {
      if (grid[i].length !== width) {
        errors.push({
          field: `grid[${i}]`,
          message: `width(${width})와 grid[${i}] 길이(${grid[i].length})가 일치하지 않습니다.`,
        });
      }
    }
  }

  const portalChars = new Map();
  if (isObject(legend)) {
    for (const [ch, mapped] of Object.entries(legend)) {
      if (typeof ch !== "string" || ch.length !== 1) {
        errors.push({ field: `legend.${ch}`, message: "legend 키는 1글자여야 합니다." });
        continue;
      }
      if (typeof mapped !== "string") {
        errors.push({ field: `legend.${ch}`, message: "legend 값은 문자열이어야 합니다." });
        continue;
      }
      if (BASE_TILE_TYPES.has(mapped)) {
        continue;
      }
      const match = mapped.match(/^PORTAL:(-?\d+)$/u);
      if (!match) {
        errors.push({
          field: `legend.${ch}`,
          message: "legend 값은 EMPTY/WALL/SPAWN/GOAL/SPIKE/PORTAL:n 이어야 합니다.",
        });
        continue;
      }
      const portalId = Number(match[1]);
      if (!Number.isInteger(portalId) || portalId < 1) {
        errors.push({ field: `legend.${ch}`, message: "PORTAL:n 의 n은 1 이상의 정수여야 합니다." });
        continue;
      }
      portalChars.set(ch, portalId);
    }
  }

  let spawnCount = 0;
  if (Array.isArray(grid) && isObject(legend)) {
    for (let y = 0; y < grid.length; y += 1) {
      const row = grid[y];
      for (let x = 0; x < row.length; x += 1) {
        const ch = row[x];
        const mapped = legend[ch];
        if (typeof mapped !== "string") {
          errors.push({
            field: `grid[${y}][${x}]`,
            message: `legend에 없는 문자 '${ch}'가 사용되었습니다.`,
          });
          continue;
        }
        if (mapped === "SPAWN") {
          spawnCount += 1;
        } else if (mapped.startsWith("PORTAL:") && !portalChars.has(ch)) {
          errors.push({
            field: `grid[${y}][${x}]`,
            message: `포탈 문자 '${ch}'의 legend 값이 올바르지 않습니다.`,
          });
        }
      }
    }
  }

  if (spawnCount === 0) {
    errors.push({ field: "grid", message: "SPAWN 타일이 1개 필요합니다. (현재 0개)" });
  } else if (spawnCount > 1) {
    errors.push({
      field: "grid",
      message: `SPAWN 타일은 정확히 1개여야 합니다. (현재 ${spawnCount}개)`,
    });
  }

  if (!Array.isArray(doc.tutorial)) {
    errors.push({ field: "tutorial", message: "tutorial은 배열이어야 합니다." });
  } else {
    for (let i = 0; i < doc.tutorial.length; i += 1) {
      const entry = doc.tutorial[i];
      if (!isObject(entry)) {
        errors.push({ field: `tutorial[${i}]`, message: "tutorial 항목은 객체여야 합니다." });
        continue;
      }
      if (entry.type !== "text") {
        errors.push({ field: `tutorial[${i}].type`, message: "tutorial.type은 'text'만 허용합니다." });
      }
      const at = entry.at;
      if (
        !Array.isArray(at) ||
        at.length !== 2 ||
        !Number.isInteger(at[0]) ||
        !Number.isInteger(at[1])
      ) {
        errors.push({ field: `tutorial[${i}].at`, message: "tutorial.at은 [int, int]여야 합니다." });
      }
      if (typeof entry.message !== "string") {
        errors.push({ field: `tutorial[${i}].message`, message: "tutorial.message는 문자열이어야 합니다." });
      }
    }
  }

  if (!isObject(doc.rules)) {
    errors.push({ field: "rules", message: "rules 객체가 필요합니다." });
  } else {
    const rules = doc.rules;
    if (rules.time_limit_sec !== null && typeof rules.time_limit_sec !== "number") {
      errors.push({
        field: "rules.time_limit_sec",
        message: "rules.time_limit_sec은 null 또는 숫자여야 합니다.",
      });
    } else if (typeof rules.time_limit_sec === "number" && rules.time_limit_sec < 0) {
      errors.push({
        field: "rules.time_limit_sec",
        message: "rules.time_limit_sec은 음수가 될 수 없습니다.",
      });
    }
    if (typeof rules.allow_spikes !== "boolean") {
      errors.push({
        field: "rules.allow_spikes",
        message: "rules.allow_spikes는 boolean이어야 합니다.",
      });
    }
  }

  return { ok: errors.length === 0, errors };
}

function normalizeForSave(doc) {
  return JSON.parse(JSON.stringify(doc));
}

async function listMapFiles() {
  await fs.mkdir(MAPS_DIR, { recursive: true });
  const items = await fs.readdir(MAPS_DIR, { withFileTypes: true });
  return items
    .filter((it) => it.isFile() && it.name.toLowerCase().endsWith(".json"))
    .map((it) => it.name)
    .sort((a, b) => a.localeCompare(b));
}

function createApp() {
  const app = express();
  app.use(express.json({ limit: "2mb" }));
  app.use(express.static(PUBLIC_DIR));

  app.get("/api/maps", async (_req, res) => {
    try {
      const files = await listMapFiles();
      const maps = [];
      for (const filename of files) {
        const fullPath = path.join(MAPS_DIR, filename);
        let id = filename.replace(/\.json$/iu, "");
        let name = id;
        try {
          const data = JSON.parse(await fs.readFile(fullPath, "utf-8"));
          if (isObject(data.meta)) {
            if (typeof data.meta.id === "string" && data.meta.id.trim() !== "") {
              id = data.meta.id.trim();
            }
            if (typeof data.meta.name === "string" && data.meta.name.trim() !== "") {
              name = data.meta.name.trim();
            }
          }
        } catch {
          name = `${name} (파싱 오류)`;
        }
        maps.push({ filename, id, name });
      }
      res.json({ maps });
    } catch (err) {
      res.status(500).json({ error: "목록을 읽지 못했습니다.", detail: String(err) });
    }
  });

  app.get("/api/maps/:filename", async (req, res) => {
    try {
      const fullPath = resolveMapPath(req.params.filename);
      const raw = await fs.readFile(fullPath, "utf-8");
      const data = JSON.parse(raw);
      res.json({ filename: path.basename(fullPath), data });
    } catch (err) {
      if (String(err).includes("ENOENT")) {
        res.status(404).json({ error: "파일이 없습니다." });
      } else if (String(err).includes("invalid filename") || String(err).includes("path traversal")) {
        res.status(400).json({ error: "잘못된 파일명입니다." });
      } else {
        res.status(500).json({ error: "파일을 읽지 못했습니다.", detail: String(err) });
      }
    }
  });

  app.post("/api/validate", (req, res) => {
    const data = req.body && req.body.data;
    const result = validateMapDocument(data);
    res.json(result);
  });

  app.post("/api/maps", async (req, res) => {
    try {
      const filename = sanitizeFilename(req.body && req.body.filename);
      const data = req.body && req.body.data;
      const result = validateMapDocument(data);
      if (!result.ok) {
        res.status(400).json(result);
        return;
      }

      const fullPath = resolveMapPath(filename);
      const normalized = normalizeForSave(data);
      await fs.mkdir(MAPS_DIR, { recursive: true });
      await fs.writeFile(fullPath, `${JSON.stringify(normalized, null, 2)}\n`, "utf-8");
      res.json({ ok: true, filename });
    } catch (err) {
      if (String(err).includes("invalid filename") || String(err).includes("path traversal")) {
        res.status(400).json({ error: "잘못된 파일명입니다." });
      } else {
        res.status(500).json({ error: "저장 실패", detail: String(err) });
      }
    }
  });

  app.use((req, res) => {
    if (req.path.startsWith("/api/")) {
      res.status(404).json({ error: "API 경로를 찾을 수 없습니다." });
      return;
    }
    res.sendFile(path.join(PUBLIC_DIR, "index.html"));
  });

  return app;
}

function startServer() {
  const port = Number(process.env.PORT || DEFAULT_PORT);
  const app = createApp();
  app.listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`[e] map editor server running: http://localhost:${port}`);
  });
}

if (require.main === module) {
  startServer();
}

module.exports = {
  createApp,
  sanitizeFilename,
  validateMapDocument,
};

