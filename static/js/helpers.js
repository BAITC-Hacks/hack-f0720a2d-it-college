// Общие компоненты экранов, доступные формы, сообщения и безопасная локальная память.
import { esc, badge, meter, breakdown, missingList, fmt, FIELDS, alertBox } from "./ui.js";
export { esc, badge, meter, breakdown, missingList, fmt, FIELDS, alertBox };
const paths = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  inbox: '<path d="m3 13 3-8h12l3 8v6H3z"/><path d="M3 13h5l1.5 2.5h5L16 13h5"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  data: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"/><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
  response: '<path d="M4 5h16v11H9l-5 4z"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.5v.5"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  chevron: '<path d="m6 9 6 6 6-6"/>',
};
export const icon = (name) => '<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (paths[name] || paths.info) + "</svg>";
export const statusNames = { draft: "Черновик", confirmed: "Подтверждена", published: "Опубликована", pending: "На рассмотрении", accepted: "Выбрана", rejected: "Отклонена" };
export const statusBadge = (status) => '<span class="status status--' + esc(status) + '">' + esc(statusNames[status] || status) + "</span>";
export const titleOf = (task) => task.title || "Задача без названия";
export const dateOf = (date) => new Intl.DateTimeFormat("ru", { day: "numeric", month: "short" }).format(new Date(date.endsWith("Z") ? date : date + "Z"));
export const initials = (name) => name.split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase();
export const linkButton = (label, href, style = "primary", image = "") => '<a class="btn btn--' + style + '" href="' + esc(href) + '">' + (image ? icon(image) : "") + esc(label) + "</a>";
export const button = (label, id, style = "primary", type = "button") => '<button class="btn btn--' + style + '" id="' + id + '" type="' + type + '">' + esc(label) + "</button>";
export function safeLink(value) {
  try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) ? esc(u.href) : ""; }
  catch { return ""; }
}
export const prototypeLink = (link) => safeLink(link) ? '<a class="external-link" href="' + safeLink(link) + '" target="_blank" rel="noopener noreferrer">' + icon("external") + esc(link) + "</a>" : '<span class="caption">Не приложена</span>';
export const memory = {
  get(key, fallback = null) { try { return JSON.parse(localStorage.getItem("ai-sana:" + key)) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem("ai-sana:" + key, JSON.stringify(value)); } catch { /* API remains the source of truth. */ } },
  remove(key) { try { localStorage.removeItem("ai-sana:" + key); } catch { /* Private browsing. */ } },
};
export function field(name, label, value = "", options = {}) {
  const { textarea = false, hint = "", placeholder = "", required = false, min = "", max = "", type = "text", rows = 3 } = options;
  const attrs = ' id="f-' + name + '" name="' + name + '" placeholder="' + esc(placeholder) + '" aria-describedby="hint-' + name + ' error-' + name + '"' + (required ? " required" : "") + (min !== "" ? ' minlength="' + min + '"' : "") + (max !== "" ? ' maxlength="' + max + '"' : "");
  const input = textarea ? '<textarea class="textarea" rows="' + rows + '"' + attrs + ">" + esc(value) + "</textarea>" : '<input class="input" type="' + type + '" value="' + esc(value) + '"' + attrs + ">";
  return '<div class="field" data-field="' + name + '"><label class="field__label" for="f-' + name + '">' + esc(label) + (required ? ' <span class="caption">· обязательно</span>' : "") + '</label>' + input + '<div class="field__error" id="error-' + name + '"></div><div class="field__hint" id="hint-' + name + '">' + esc(hint) + "</div></div>";
}
export const formValues = (form) => Object.fromEntries(new FormData(form));
export function clearErrors(form) {
  form.querySelectorAll(".is-invalid").forEach(el => el.classList.remove("is-invalid"));
  form.querySelectorAll("[aria-invalid]").forEach(el => el.removeAttribute("aria-invalid"));
  const summary = form.querySelector("[data-errors]"); if (summary) summary.innerHTML = "";
}
export function markError(form, name, message) {
  const element = Array.from(form.querySelectorAll("[data-field]")).find(el => el.dataset.field === name);
  if (!element) return;
  element.classList.add("is-invalid");
  element.querySelector(".field__error").textContent = message;
  element.querySelector("input,textarea,select")?.setAttribute("aria-invalid", "true");
}
export function validate(form) {
  clearErrors(form);
  let valid = true;
  for (const control of form.querySelectorAll("input,textarea,select")) {
    const value = control.value.trim();
    let message = "";
    if (control.required && !value) message = "Заполните это поле";
    else if (value && control.minLength > 0 && value.length < control.minLength) message = "Добавьте подробностей: минимум " + control.minLength + " символов";
    else if (!control.validity.valid) message = control.type === "url" ? "Укажите полную ссылку с http:// или https://" : "Проверьте значение поля";
    if (message) { markError(form, control.name, message); valid = false; }
  }
  if (!valid) form.querySelector("[aria-invalid]")?.focus();
  return valid;
}
export function showError(root, error, form = null) {
  const box = (form || root).querySelector("[data-errors]");
  if (box) box.innerHTML = alertBox("error", "Не удалось выполнить действие", error.message || "Повторите попытку");
  if (form) for (const item of error.errors || []) {
    let message = "Проверьте значение поля";
    if (item.type === "string_too_short") message = "Минимум " + item.ctx?.min_length + " символов";
    if (item.type === "missing") message = "Заполните это поле";
    if (item.type === "value_error" && /[А-Яа-я]/.test(item.msg)) message = item.msg.replace(/^Value error, /, "");
    markError(form, item.loc?.at(-1), message);
  }
  if (!box) toast(error.message || "Не удалось выполнить действие", "error");
}
export async function busy(control, action) {
  if (control.disabled) return;
  control.disabled = true;
  control.setAttribute("aria-busy", "true");
  try { return await action(); } finally { control.disabled = false; control.removeAttribute("aria-busy"); }
}
let toastTimer;
export function toast(message, kind = "success") {
  const root = document.querySelector("#toast-region");
  root.innerHTML = alertBox(kind, message, "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { root.innerHTML = ""; }, 5000);
}
export function empty(title, text, actions = "") {
  return '<div class="empty"><div class="empty__icon">' + icon("inbox") + '</div><h2 class="h2">' + esc(title) + '</h2><p class="muted">' + esc(text) + '</p><div class="actions">' + actions + "</div></div>";
}
export function ratingPanel(task, { actions = "", hints = true } = {}) {
  return '<section class="panel rating-panel"><div class="eyebrow">Рейтинг готовности</div><div class="rating-total"><span class="score score--lg">' + fmt(task.score) + '</span><span class="caption">из 100</span>' + badge(task.score) + "</div>" + meter(task.score) + '<div class="rating-ticks mono"><span>0</span><span>40</span><span>70</span><span>90</span><span>100</span></div><div class="breakdown">' + breakdown(task.breakdown) + "</div>" + (hints && task.missing?.length ? '<div><div class="eyebrow">Что повысит рейтинг</div>' + missingList(task.missing) + "</div>" : "") + '<details class="rating-details"><summary>Как считается рейтинг</summary><p class="caption">Пустое поле — 0. Меньше 30 символов — половина веса. От 30 символов — полный вес. Рейтинг отражает полноту описания, а отклик открыт при любом уровне.</p></details>' + actions + "</section>";
}
export function readonlyCard(task) {
  return '<div class="readonly-fields">' + FIELDS.map(([key, label, weight]) => '<div class="readonly-row"><h3>' + esc(label) + '</h3><p class="' + (!task[key] ? "caption" : "") + '">' + esc(task[key] || "Пока не указано — можно уточнить у бизнеса.") + '</p><span class="mono caption">' + fmt(task.breakdown?.[key]?.earned || 0) + "/" + weight + "</span></div>").join("") + "</div>";
}
export const INDUSTRIES = ["Образование", "Ритейл", "ЖКХ", "Культура", "Социальная сфера", "Медицина и услуги", "Транспорт", "Спорт", "Другое"];
