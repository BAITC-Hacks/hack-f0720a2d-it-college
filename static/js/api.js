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
  aiStatus: () => apiRequest("/ai/status"),
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
  deleteTask: (id) => send("/tasks/" + id, undefined, "DELETE"),
  confirm: (id) => send("/tasks/" + id + "/confirm"),
  publish: (id) => send("/tasks/" + id + "/publish"),
  proposals: () => apiRequest("/proposals"),
  taskProposals: (id) => apiRequest("/tasks/" + id + "/proposals"),
  propose: (body) => send("/proposals", body),
  decide: (id, decision) => send("/proposals/" + id + "/" + decision),
};
