// Все обращения к FastAPI и передача текущего пользователя собраны здесь.
let currentUserId = null;
export function setCurrentUser(userId) { currentUserId = userId; }
export class ApiError extends Error {
  constructor(message, status = 0, errors = []) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}
export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set("Content-Type", "application/json");
  if (currentUserId) headers.set("X-User-Id", String(currentUserId));
  let response;
  try { response = await fetch("/api" + path, { ...options, headers }); }
  catch { throw new ApiError("Нет связи с сервером. Проверьте подключение и повторите действие."); }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(
    typeof data?.detail === "string" ? data.detail : "Не удалось выполнить запрос",
    response.status, data?.errors || (Array.isArray(data?.detail) ? data.detail : []),
  );
  return data;
}
const send = (path, body, method = "POST") => apiRequest(path, {
  method, ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});
export const api = {
<<<<<<< HEAD
  aiStatus: () => apiRequest("/ai/status"),
=======
  aiSettings: () => apiRequest("/ai/settings"),
  saveAISettings: (body) => send("/ai/settings", body, "PUT"),
  aiModels: (body) => body ? send("/ai/models", body) : apiRequest("/ai/models"),
  reviewProgress: (id, action) => send("/proposals/" + id + "/progress/" + action),
>>>>>>> ab5a473797132f7124443376acd5c95546baa5a2
  users: () => apiRequest("/users"),
  login: (userId, role) => send("/users/login", { user_id: userId, role }),
  teams: () => apiRequest("/teams"),
  catalog: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value));
    return apiRequest("/catalog" + (query.size ? "?" + query : ""));
  },
  myTasks: () => apiRequest("/tasks"),
  task: (id) => apiRequest("/tasks/" + id),
  draft: (body) => send("/tasks/draft", body),
  questions: (id) => send("/tasks/" + id + "/questions"),
  buildCard: (id, answers) => send("/tasks/" + id + "/card", { answers }),
  updateTask: (id, body) => send("/tasks/" + id, body, "PATCH"),
  confirm: (id, updatedAt) => send("/tasks/" + id + "/confirm", updatedAt ? { expected_updated_at: updatedAt } : undefined),
  deleteTask: (id) => send("/tasks/" + id, undefined, "DELETE"),
  publish: (id) => send("/tasks/" + id + "/publish"),
  proposals: () => apiRequest("/proposals"),
  taskProposals: (id) => apiRequest("/tasks/" + id + "/proposals"),
  propose: (body) => send("/proposals", body),
  decide: (id, decision) => send("/proposals/" + id + "/" + decision),
  submitProgress: (id, body) => send("/proposals/" + id + "/progress", body),
  confirmProgress: (id) => send("/proposals/" + id + "/progress/confirm"),
};
