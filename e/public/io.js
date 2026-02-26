async function parseJsonResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.error || payload.message || `HTTP ${response.status}`;
    const err = new Error(message);
    err.payload = payload;
    throw err;
  }
  return payload;
}

export async function fetchMapList() {
  const response = await fetch("/api/maps");
  const payload = await parseJsonResponse(response);
  return payload.maps ?? [];
}

export async function fetchMapFile(filename) {
  const encoded = encodeURIComponent(filename);
  const response = await fetch(`/api/maps/${encoded}`);
  const payload = await parseJsonResponse(response);
  return payload.data;
}

export async function validateMapData(data) {
  const response = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
  });
  return parseJsonResponse(response);
}

export async function saveMapFile(filename, data) {
  const response = await fetch("/api/maps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, data }),
  });
  return parseJsonResponse(response);
}

