// Единая точка всех fetch-вызовов фронтенда.
let currentUserId = null;

export function setCurrentUser(userId) {
  currentUserId = userId;
}

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (currentUserId) headers.set("X-User-Id", String(currentUserId));

  const response = await fetch(`/api${path}`, { ...options, headers });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.detail || "Не удалось выполнить запрос");
  }
  return data;
}

export const api = {
  users: () => apiRequest("/users"),
  login: (userId, role) => apiRequest("/users/login", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  }),
  catalog: (params = "") => apiRequest(`/catalog${params}`),
  teams: () => apiRequest("/teams"),
};
