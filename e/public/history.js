function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function isEqualDoc(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export class HistoryManager {
  constructor(limit = 300) {
    this.limit = limit;
    this.undoStack = [];
    this.redoStack = [];
  }

  reset() {
    this.undoStack = [];
    this.redoStack = [];
  }

  record(beforeDoc, afterDoc, label = "edit") {
    if (!beforeDoc || !afterDoc) {
      return false;
    }
    if (isEqualDoc(beforeDoc, afterDoc)) {
      return false;
    }
    this.undoStack.push({
      before: deepClone(beforeDoc),
      after: deepClone(afterDoc),
      label,
    });
    if (this.undoStack.length > this.limit) {
      this.undoStack.shift();
    }
    this.redoStack = [];
    return true;
  }

  canUndo() {
    return this.undoStack.length > 0;
  }

  canRedo() {
    return this.redoStack.length > 0;
  }

  undo(currentDoc) {
    if (!this.canUndo()) {
      return null;
    }
    const entry = this.undoStack.pop();
    this.redoStack.push({
      before: deepClone(entry.before),
      after: deepClone(entry.after),
      label: entry.label,
    });
    return deepClone(entry.before ?? currentDoc);
  }

  redo(currentDoc) {
    if (!this.canRedo()) {
      return null;
    }
    const entry = this.redoStack.pop();
    this.undoStack.push({
      before: deepClone(entry.before),
      after: deepClone(entry.after),
      label: entry.label,
    });
    return deepClone(entry.after ?? currentDoc);
  }
}

