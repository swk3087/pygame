export const MIN_MAP_SIZE = 8;
export const MAX_MAP_SIZE = 80;
export const PORTAL_CHAR_POOL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
export const TILE_TYPES = ["EMPTY", "WALL", "SPAWN", "GOAL", "SPIKE", "PORTAL"];

const BASE_LEGEND = {
  ".": "EMPTY",
  "#": "WALL",
  S: "SPAWN",
  G: "GOAL",
  "^": "SPIKE",
};

const BASE_TYPE_CHAR = {
  EMPTY: ".",
  WALL: "#",
  SPAWN: "S",
  GOAL: "G",
  SPIKE: "^",
};

function clamp(value, minValue, maxValue) {
  return Math.max(minValue, Math.min(maxValue, value));
}

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function makeEmptyGrid(width, height, fillChar = ".") {
  const row = fillChar.repeat(width);
  return Array.from({ length: height }, () => row);
}

function normalizeGridRows(grid, width, height) {
  const normalized = makeEmptyGrid(width, height, ".");
  if (!Array.isArray(grid)) {
    return normalized;
  }
  for (let y = 0; y < Math.min(height, grid.length); y += 1) {
    const src = typeof grid[y] === "string" ? grid[y] : "";
    const rowChars = [];
    for (let x = 0; x < width; x += 1) {
      rowChars.push(src[x] ?? ".");
    }
    normalized[y] = rowChars.join("");
  }
  return normalized;
}

export function createDefaultDocument() {
  const width = 20;
  const height = 12;
  const grid = makeEmptyGrid(width, height, ".");
  const rows = grid.map((row, y) => {
    if (y === 0 || y === height - 1) {
      return "#".repeat(width);
    }
    return `#${row.slice(1, -1)}#`;
  });
  rows[1] = `#S${rows[1].slice(2, -2)}G#`;
  return {
    meta: {
      id: "new_map",
      name: "새 맵",
      author: "editor",
      version: 1,
    },
    tile_size: 32,
    width,
    height,
    legend: { ...BASE_LEGEND },
    grid: rows,
    tutorial: [],
    rules: {
      time_limit_sec: null,
      allow_spikes: true,
    },
  };
}

export function normalizeDocument(rawDoc) {
  const fallback = createDefaultDocument();
  const doc = (rawDoc && typeof rawDoc === "object" ? deepClone(rawDoc) : fallback);
  doc.meta = typeof doc.meta === "object" && doc.meta ? doc.meta : deepClone(fallback.meta);
  doc.meta.id = String(doc.meta.id ?? fallback.meta.id);
  doc.meta.name = String(doc.meta.name ?? fallback.meta.name);
  doc.meta.author = String(doc.meta.author ?? fallback.meta.author);
  const version = Number(doc.meta.version);
  doc.meta.version = Number.isFinite(version) && version >= 1 ? Math.trunc(version) : 1;

  const width = clamp(Math.trunc(Number(doc.width) || fallback.width), MIN_MAP_SIZE, MAX_MAP_SIZE);
  const height = clamp(Math.trunc(Number(doc.height) || fallback.height), MIN_MAP_SIZE, MAX_MAP_SIZE);
  doc.width = width;
  doc.height = height;

  const tileSize = Math.trunc(Number(doc.tile_size) || fallback.tile_size);
  doc.tile_size = Math.max(1, tileSize);

  doc.legend = typeof doc.legend === "object" && doc.legend ? doc.legend : {};
  doc.legend = { ...BASE_LEGEND, ...doc.legend };

  doc.grid = normalizeGridRows(doc.grid, width, height);
  doc.tutorial = Array.isArray(doc.tutorial) ? doc.tutorial : [];

  const defaultRules = fallback.rules;
  doc.rules = typeof doc.rules === "object" && doc.rules ? doc.rules : {};
  doc.rules.allow_spikes = Boolean(
    "allow_spikes" in doc.rules ? doc.rules.allow_spikes : defaultRules.allow_spikes
  );
  const limit = doc.rules.time_limit_sec;
  doc.rules.time_limit_sec =
    limit === null || limit === "" || Number.isNaN(Number(limit)) ? null : Number(limit);

  return doc;
}

export class EditorState {
  constructor() {
    this.doc = createDefaultDocument();
    this.tool = "pen";
    this.selectedTileType = "WALL";
    this.selectedPortalId = 1;
    this.zoom = 1.0;
    this.panX = 32;
    this.panY = 32;
    this.selection = null;
    this.clipboard = null;
    this.pasteMode = false;
    this.pasteAnchor = null;
  }

  get width() {
    return this.doc.width;
  }

  get height() {
    return this.doc.height;
  }

  cloneDoc() {
    return deepClone(this.doc);
  }

  setDoc(nextDoc) {
    this.doc = normalizeDocument(nextDoc);
    this.normalizeLegendFromGrid();
    this.selection = null;
    this.pasteMode = false;
    this.pasteAnchor = null;
  }

  resizeMap(newWidth, newHeight) {
    const width = clamp(Math.trunc(Number(newWidth) || this.width), MIN_MAP_SIZE, MAX_MAP_SIZE);
    const height = clamp(Math.trunc(Number(newHeight) || this.height), MIN_MAP_SIZE, MAX_MAP_SIZE);
    if (width === this.width && height === this.height) {
      return false;
    }
    const oldGrid = this.doc.grid;
    const nextGrid = makeEmptyGrid(width, height, ".");
    for (let y = 0; y < Math.min(height, oldGrid.length); y += 1) {
      const src = oldGrid[y];
      const chars = [];
      for (let x = 0; x < width; x += 1) {
        chars.push(src[x] ?? ".");
      }
      nextGrid[y] = chars.join("");
    }
    this.doc.width = width;
    this.doc.height = height;
    this.doc.grid = nextGrid;
    this.normalizeLegendFromGrid();
    return true;
  }

  getCellChar(tx, ty) {
    if (tx < 0 || ty < 0 || tx >= this.width || ty >= this.height) {
      return null;
    }
    return this.doc.grid[ty][tx];
  }

  setCellChar(tx, ty, char) {
    if (tx < 0 || ty < 0 || tx >= this.width || ty >= this.height) {
      return false;
    }
    const row = this.doc.grid[ty];
    if (row[tx] === char) {
      return false;
    }
    this.doc.grid[ty] = `${row.slice(0, tx)}${char}${row.slice(tx + 1)}`;
    return true;
  }

  getTileTypeAt(tx, ty) {
    const ch = this.getCellChar(tx, ty);
    if (!ch) {
      return "WALL";
    }
    const mapped = this.doc.legend[ch];
    if (typeof mapped !== "string") {
      return "EMPTY";
    }
    return mapped.startsWith("PORTAL:") ? "PORTAL" : mapped;
  }

  ensurePortalChar(portalId) {
    const pid = Math.max(1, Math.trunc(Number(portalId) || 1));
    const token = `PORTAL:${pid}`;
    const entries = Object.entries(this.doc.legend);
    for (const [ch, mapped] of entries) {
      if (mapped === token) {
        return ch;
      }
    }

    const usedChars = new Set(Object.keys(this.doc.legend));
    for (const ch of PORTAL_CHAR_POOL) {
      if (!usedChars.has(ch)) {
        this.doc.legend[ch] = token;
        return ch;
      }
    }
    throw new Error("포탈 문자 풀이 부족합니다. 사용 문자 수를 줄여주세요.");
  }

  setTileAt(tx, ty, tileType, portalId = this.selectedPortalId) {
    let targetChar = ".";
    if (tileType === "PORTAL") {
      targetChar = this.ensurePortalChar(portalId);
    } else {
      targetChar = BASE_TYPE_CHAR[tileType] ?? ".";
      this.doc.legend[targetChar] = BASE_LEGEND[targetChar];
    }
    const changed = this.setCellChar(tx, ty, targetChar);
    if (changed) {
      this.normalizeLegendFromGrid();
    }
    return changed;
  }

  fillRect(rect, tileType, portalId = this.selectedPortalId) {
    const { x, y, w, h } = rect;
    let changed = false;
    for (let ty = y; ty < y + h; ty += 1) {
      for (let tx = x; tx < x + w; tx += 1) {
        changed = this.setTileAt(tx, ty, tileType, portalId) || changed;
      }
    }
    return changed;
  }

  clearRect(rect) {
    return this.fillRect(rect, "EMPTY");
  }

  countTileType(tileType) {
    let count = 0;
    for (let y = 0; y < this.height; y += 1) {
      for (let x = 0; x < this.width; x += 1) {
        if (this.getTileTypeAt(x, y) === tileType) {
          count += 1;
        }
      }
    }
    return count;
  }

  normalizeLegendFromGrid() {
    const used = new Set();
    for (const row of this.doc.grid) {
      for (const ch of row) {
        used.add(ch);
      }
    }
    const nextLegend = {};
    for (const [ch, mapped] of Object.entries(this.doc.legend)) {
      if (used.has(ch)) {
        nextLegend[ch] = mapped;
      }
    }
    for (const [ch, mapped] of Object.entries(BASE_LEGEND)) {
      if (used.has(ch)) {
        nextLegend[ch] = mapped;
      }
    }
    for (const ch of used) {
      if (!(ch in nextLegend)) {
        nextLegend[ch] = "EMPTY";
      }
    }
    this.doc.legend = nextLegend;
  }

  normalizeRect(a, b) {
    const x1 = Math.min(a.x, b.x);
    const y1 = Math.min(a.y, b.y);
    const x2 = Math.max(a.x, b.x);
    const y2 = Math.max(a.y, b.y);
    const x = clamp(x1, 0, this.width - 1);
    const y = clamp(y1, 0, this.height - 1);
    const maxX = clamp(x2, 0, this.width - 1);
    const maxY = clamp(y2, 0, this.height - 1);
    return {
      x,
      y,
      w: maxX - x + 1,
      h: maxY - y + 1,
    };
  }

  copySelectionToClipboard() {
    if (!this.selection) {
      return false;
    }
    const rect = this.selection;
    const cells = [];
    const legend = {};
    for (let y = 0; y < rect.h; y += 1) {
      const row = [];
      for (let x = 0; x < rect.w; x += 1) {
        const ch = this.getCellChar(rect.x + x, rect.y + y) ?? ".";
        row.push(ch);
        if (this.doc.legend[ch]) {
          legend[ch] = this.doc.legend[ch];
        }
      }
      cells.push(row.join(""));
    }
    this.clipboard = {
      w: rect.w,
      h: rect.h,
      cells,
      legend,
    };
    return true;
  }

  pasteClipboardAt(tx, ty) {
    if (!this.clipboard) {
      return false;
    }
    let changed = false;
    const { cells, legend } = this.clipboard;
    for (const [ch, mapped] of Object.entries(legend)) {
      this.doc.legend[ch] = mapped;
    }
    for (let y = 0; y < cells.length; y += 1) {
      const row = cells[y];
      for (let x = 0; x < row.length; x += 1) {
        changed = this.setCellChar(tx + x, ty + y, row[x]) || changed;
      }
    }
    if (changed) {
      this.normalizeLegendFromGrid();
    }
    return changed;
  }

  toSerializable() {
    this.normalizeLegendFromGrid();
    return normalizeDocument(this.doc);
  }
}

