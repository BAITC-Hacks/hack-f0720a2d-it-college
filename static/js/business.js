// Собственные карточки бизнеса: создание, редактирование и переход к предложениям.
import { api } from "./api.js";
import { bindTaskDeletion, deleteTaskButton } from "./task-actions.js";
import { esc, fmt, icon, titleOf, dateOf, statusBadge, badge, meter, linkButton, empty, alertBox } from "./helpers.js";

const filters = [["all", "Все"], ["draft", "Черновики"], ["confirmed", "Подтверждены"], ["published", "Опубликованы"]];

function taskRow(task, selectedId) {
  const nextStep = task.status !== "published"
    ? '<a class="text-link" href="#' + (task.context ? "publish" : "questions") + "/" + task.id + '">' +
      (task.context ? "Перейти к публикации" : "Продолжить создание") + icon("arrow") + "</a>"
    : task.has_pending_changes ? '<a class="text-link" href="#review-changes/' + task.id + '">Проверить изменения ' + icon("arrow") + '</a>' : "";
  return '<article class="owned-task' + (task.id === selectedId ? " is-selected" : "") + '" data-owned-task="' + task.id + '" tabindex="-1" aria-labelledby="owned-task-title-' + task.id + '">' +
    '<div class="stack tight owned-task__info"><div class="caption">' + esc(task.industry || "Отрасль не указана") + '</div><h2 class="h2" id="owned-task-title-' + task.id + '"><a class="ink-link" href="#task/' + task.id + '">' + esc(titleOf(task)) + '</a></h2><div class="caption">Обновлена ' + dateOf(task.updated_at) + '</div></div>' +
    '<div class="owned-task__status"><span class="owned-task__label caption">Статус</span>' + statusBadge(task.status) + (task.has_pending_changes ? '<p class="caption">Есть неподтверждённые изменения</p>' : '') + '</div>' +
    '<div class="stack tight owned-task__rating"><span class="owned-task__label caption">Готовность карточки</span><div class="rating-inline"><span class="score">' + fmt(task.score) + '</span><span class="caption">из 100</span></div>' + badge(task.score) + meter(task.score) + '</div>' +
    '<div class="owned-task__actions"><a class="text-link" href="#task/' + task.id + '">Открыть карточку ' + icon("external") + '</a><a class="text-link" href="#edit/' + task.id + '">' + icon("edit") + 'Редактировать карточку</a>' + nextStep +
    '<div class="actions"><a class="btn btn--secondary btn--sm" href="#proposals/' + task.id + '">Предложения</a>' + deleteTaskButton + '</div></div></article>';
}

export async function renderMyTasks(root, ctx, selectedId) {
  if (ctx.user.role !== "business") throw new Error("Мои задачи доступны только бизнесу");
  const tasks = await api.myTasks();
  if (!root.isConnected) return;
  root.className = "content-wide stack owned-tasks";
  const heading = '<div class="page-heading"><div class="stack tight"><h1 class="h1">Мои задачи</h1><p class="muted">Создавайте карточки, уточняйте описание и публикуйте задачи для команд.</p></div>' + linkButton("Создать задачу", "#new", "primary", "plus") + '</div>';
  if (!tasks.length) {
    root.innerHTML = heading + empty("Начните с первой задачи", "Опишите, что нужно вашему бизнесу. Уточняющие вопросы помогут собрать понятную карточку.", linkButton("Создать задачу", "#new", "primary", "plus"));
    return;
  }
  const selectedExists = tasks.some(task => task.id === selectedId);
  const selectionNotice = Number.isInteger(selectedId) && selectedId > 0 && !selectedExists
    ? alertBox("info", "Задача недоступна", "В вашем списке нет задачи с этим адресом. Выберите одну из своих карточек ниже.")
    : "";
  root.innerHTML = heading + selectionNotice + '<div class="owned-task-filters" role="group" aria-label="Статус задачи">' +
    filters.map(([key, name]) => '<button type="button" class="btn btn--secondary btn--sm" data-task-status="' + key + '" aria-pressed="' + (key === "all") + '">' + name + ' <span class="mono">' + (key === "all" ? tasks.length : tasks.filter(task => task.status === key).length) + '</span></button>').join("") +
    '</div><div id="owned-task-results"></div>';
  const results = root.querySelector("#owned-task-results");
  let filter = "all", deletionCleanups = [];
  const cleanupRows = () => { deletionCleanups.forEach(cleanup => cleanup()); deletionCleanups = []; };
  function renderRows() {
    cleanupRows();
    root.querySelectorAll("[data-task-status]").forEach(control => control.setAttribute("aria-pressed", String(control.dataset.taskStatus === filter)));
    const visible = tasks.filter(task => filter === "all" || task.status === filter);
    results.innerHTML = visible.length
      ? '<div class="owned-task-list"><div class="owned-task-list__head eyebrow" aria-hidden="true"><span>Задача</span><span>Статус</span><span>Готовность карточки</span><span>Управление</span></div>' + visible.map(task => taskRow(task, selectedId)).join("") + '</div>'
      : empty("Нет задач с таким статусом", "Выберите другой статус или создайте новую задачу.", '<button class="btn btn--secondary" type="button" data-show-all-tasks>Показать все задачи</button>');
    deletionCleanups = visible.map(task => bindTaskDeletion(results.querySelector('[data-owned-task="' + task.id + '"]'), ctx, task));
    results.querySelector("[data-show-all-tasks]")?.addEventListener("click", () => {
      filter = "all";
      renderRows();
      root.querySelector('[data-task-status="all"]').focus({ preventScroll: true });
    });
  }
  root.querySelectorAll("[data-task-status]").forEach(control => control.addEventListener("click", () => {
    filter = control.dataset.taskStatus;
    renderRows();
  }));
  renderRows();
  if (selectedExists) {
    const selected = results.querySelector('[data-owned-task="' + selectedId + '"]');
    selected.focus({ preventScroll: true });
    selected.scrollIntoView({ block: "nearest" });
  }
  return cleanupRows;
}
