// Оболочка, выбор пользователя и hash-навигация; экраны остаются отдельными модулями.
import { api, setCurrentUser } from "./api.js";
import { esc, icon, memory, toast, empty, linkButton } from "./helpers.js";
import { renderCatalog } from "./catalog.js";
import { renderConstructor } from "./constructor.js";
import { renderTask } from "./task.js";
import { renderBusiness, renderMyProposals } from "./proposals.js";

let users = [], teams = [], user = null, dispose = () => {};
let changingUser = false;
const header = document.querySelector("#app-header");
const main = document.querySelector("#main-content");
const roleName = (u) => u.role === "team" ? teams.find(t => t.id === u.team_id)?.name || u.name : u.name;

function renderHeader() {
  const route = location.hash.slice(1).split("/")[0] || "catalog";
  const isBusiness = user.role === "business";
  const nav = isBusiness
    ? [["catalog", "Каталог"], ["business", "Мои задачи"], ["proposals", "Предложения"]]
    : [["catalog", "Каталог"], ["recommendations", "Рекомендации"], ["proposals", "Мои отклики"]];
  const active = ["new", "questions", "edit", "publish", "published"].includes(route) ? "business" : route === "task" ? "catalog" : route;
  header.innerHTML = '<a href="#catalog" class="brand"><span class="brand-mark mono">AS</span><span>AI Sana</span></a>' +
    '<nav class="nav" aria-label="Основная навигация">' + nav.map(([path, label]) => '<a href="#' + path + '"' + (active === path ? ' aria-current="page"' : "") + ">" + label + "</a>").join("") + "</nav>" +
    '<div class="role-switch" role="group" aria-label="Роль">' + [["business", "Бизнес"], ["team", "Команда"]].map(([role, label]) => '<button type="button" data-role="' + role + '" aria-pressed="' + (user.role === role) + '">' + label + "</button>").join("") + "</div>" +
    '<label class="user-picker"><span class="sr-only">Текущий пользователь</span><select id="user-select" aria-label="Текущий пользователь">' +
    users.filter(u => u.role === user.role).map(u => '<option value="' + u.id + '"' + (u.id === user.id ? " selected" : "") + ">" + esc(roleName(u)) + "</option>").join("") + "</select></label>" +
    (isBusiness ? '<a class="btn btn--primary btn--sm header-create" href="#new">' + icon("plus") + "Создать задачу</a>" : "");
  header.querySelectorAll("[data-role]").forEach(btn => btn.addEventListener("click", () => {
    if (btn.dataset.role !== user.role) {
      const remembered = memory.get("last-user:" + btn.dataset.role);
      switchUser(users.find(u => u.id === remembered && u.role === btn.dataset.role) || users.find(u => u.role === btn.dataset.role));
    }
  }));
  header.querySelector("#user-select").addEventListener("change", event => switchUser(users.find(u => u.id === Number(event.target.value))));
}

async function switchUser(nextUser) {
  if (changingUser || !nextUser) return;
  changingUser = true;
  header.querySelectorAll("button,select").forEach(el => { el.disabled = true; });
  try {
    const selected = await api.login(nextUser.id, nextUser.role);
    dispose(); dispose = () => {};
    user = selected;
    setCurrentUser(user.id);
    memory.set("user-id", user.id);
    memory.set("last-user:" + user.role, user.id);
    if (location.hash === "#catalog") await render(); else location.hash = "#catalog";
    toast("Вы вошли: " + roleName(user));
  } catch (error) { toast(error.message, "error"); }
  finally { changingUser = false; renderHeader(); }
}

async function render() {
  dispose(); dispose = () => {};
  renderHeader();
  const root = document.createElement("div");
  root.innerHTML = '<div class="loading" role="status"><span class="spinner"></span>Загружаем…</div>';
  main.replaceChildren(root);
  const [route = "catalog", id] = location.hash.replace(/^#/, "").split("/");
  const ctx = { user, users, teams, navigate: path => {
    if (location.hash === "#" + path) render(); else location.hash = "#" + path;
  }};
  window.scrollTo(0, 0);
  try {
    let cleanup;
    if (route === "catalog" || route === "" || route === "recommendations") cleanup = await renderCatalog(root, ctx, route === "recommendations");
    else if (route === "task" && /^\d+$/.test(id)) cleanup = await renderTask(root, ctx, Number(id));
    else if (["new", "questions", "edit", "publish", "published"].includes(route) && user.role === "business") {
      if (route !== "new" && !/^\d+$/.test(id)) throw new Error("Некорректный адрес задачи");
      cleanup = await renderConstructor(root, ctx, route, Number(id));
    } else if (["business", "proposals"].includes(route)) {
      cleanup = user.role === "business" ? await renderBusiness(root, ctx, Number(id)) : await renderMyProposals(root, ctx);
    } else {
      root.className = "content-wide";
      root.innerHTML = empty("Страница недоступна", "Выберите раздел каталога или переключитесь на роль бизнеса.", linkButton("В каталог", "#catalog"));
    }
    if (root.isConnected) {
      dispose = typeof cleanup === "function" ? cleanup : () => {};
      const h1 = root.querySelector("h1");
      document.title = (h1?.textContent || "Каталог задач") + " — AI Sana";
    } else if (typeof cleanup === "function") cleanup();
  } catch (error) {
    if (!root.isConnected) return;
    root.className = "content-wide";
    root.innerHTML = empty("Не удалось открыть страницу", error.message, '<button class="btn btn--primary" id="retry">Повторить</button>' + linkButton("В каталог", "#catalog", "secondary"));
    root.querySelector("#retry").addEventListener("click", render);
  }
}

async function init() {
  try {
    [users, teams] = await Promise.all([api.users(), api.teams()]);
    if (!users.length) throw new Error("Нет пользователей. Загрузите демонстрационные данные командой python -m app.seed.seed.");
    user = users.find(u => u.id === memory.get("user-id")) || users.find(u => u.role === "business") || users[0];
    user = await api.login(user.id, user.role);
    setCurrentUser(user.id);
    await render();
  } catch (error) {
    header.innerHTML = '<a href="#" class="brand"><span class="brand-mark">AS</span>AI Sana</a>';
    main.innerHTML = '<div class="content-wide">' + empty("Не удалось подключиться", error.message, '<button class="btn btn--primary" id="retry-start">Повторить подключение</button>') + "</div>";
    main.querySelector("#retry-start").addEventListener("click", init);
  }
}
window.addEventListener("hashchange", () => { if (user) render(); });
main.addEventListener("input", event => {
  const control = event.target;
  if (!control.matches("input,textarea,select") || !control.hasAttribute("aria-invalid")) return;
  if (control.value.trim() && control.validity.valid && (control.minLength < 1 || control.value.trim().length >= control.minLength)) {
    control.removeAttribute("aria-invalid");
    control.closest(".field")?.classList.remove("is-invalid");
  }
});
init();
