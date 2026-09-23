// Предложения для бизнеса, сравнение команд и личный список откликов.
import { api } from "./api.js";
import { esc, icon, titleOf, dateOf, initials, statusBadge, prototypeLink, linkButton, empty, busy, showError, alertBox, toast, field, validate, formValues } from "./helpers.js";

const tabs = [["all", "Все"], ["pending", "На рассмотрении"], ["accepted", "Выбраны"], ["rejected", "Отклонены"]];
function tabBar(proposals, selected) {
  return '<div class="tabs" role="tablist" aria-label="Статус отклика">' + tabs.map(([key, name]) => '<button role="tab" class="tab" id="tab-' + key + '" aria-controls="proposal-results" aria-selected="' + (key === selected) + '" data-status="' + key + '">' + name + ' <span class="mono caption">' + (key === "all" ? proposals.length : proposals.filter(p => p.status === key).length) + "</span></button>").join("") + "</div>";
}
const count = (proposals, id) => proposals.filter(p => p.task_id === id).length;
const teamOf = (ctx, proposal) => ctx.teams.find(t => t.id === proposal.team_id) || { name: "Команда " + proposal.team_id, skills: [], tech: [] };

function progressSummary(proposal, business = false) {
  const progress = proposal.progress;
  if (!progress) return '<p class="caption">' + (proposal.status === "accepted" ? "Команда ещё не отправила результат этапа" : "Этап доступен после выбора команды бизнесом") + "</p>";
  const confirmed = progress.status === "confirmed";
  return '<div class="stack tight"><strong>' + (confirmed ? "Подтверждено · +" + progress.points + " баллов команде" : "Результат ожидает проверки · 0 баллов") + '</strong><p>' + esc(progress.description) + '</p>' + prototypeLink(progress.link) +
    (business && !confirmed && proposal.status === "accepted" ? '<button class="btn btn--primary btn--sm btn--wrap" data-confirm-progress="' + proposal.id + '">Подтвердить результат · +10</button><p class="caption">Подтверждайте только проверенный фактический результат. Начисление однократное.</p>' : "") + "</div>";
}

function progressForm(proposal) {
  if (proposal.status !== "accepted" || proposal.progress?.status === "confirmed") return "";
  const suffix = "_" + proposal.id;
  return '<details class="details-content"' + (proposal.progress ? "" : " open") + '><summary class="text-button">Передать результат этапа</summary><form class="stack" data-progress-form="' + proposal.id + '" novalidate><div data-errors></div>' +
    field("description" + suffix, "Что фактически сделано", proposal.progress?.description, { textarea: true, required: true, min: 30, max: 5000, hint: "Опишите проверяемый результат. После подтверждения бизнесом команда получит 10 баллов один раз." }) +
    field("link" + suffix, "Ссылка на результат", proposal.progress?.link, { type: "url", max: 500 }) +
    '<button type="submit" class="btn btn--primary">Отправить результат на проверку</button></form></details>';
}

export async function renderBusinessProposals(root, ctx, selectedId) {
  const [ownedTasks, allProposals] = await Promise.all([api.myTasks(), api.proposals()]);
  if (!root.isConnected) return;
  const heading = '<div class="page-heading"><div class="stack tight"><h1 class="h1">Предложения</h1><p class="muted">Сравнивайте отклики команд и принимайте решения по каждой задаче.</p></div><button type="button" class="btn btn--secondary" id="refresh-business-proposals">Обновить</button></div>';
  const tasks = ownedTasks.filter(task => task.status === "published" || count(allProposals, task.id) || task.id === selectedId);
  if (!tasks.length) {
    root.className = "content-wide stack";
    root.innerHTML = heading + empty("Предложений пока нет", "Опубликуйте задачу из раздела «Мои задачи», чтобы команды могли откликнуться.", linkButton("Мои задачи", "#business"));
    root.querySelector("#refresh-business-proposals").addEventListener("click", () => ctx.navigate("proposals"));
    return;
  }
  const selected = tasks.find(task => task.id === selectedId) || tasks.find(task => count(allProposals, task.id)) || tasks[0];
  let proposals = allProposals.filter(proposal => proposal.task_id === selected.id);
  let filter = "all";
  root.className = "business-layout";
  root.innerHTML = '<aside class="task-sidebar"><button type="button" class="btn btn--secondary sidebar-toggle" aria-expanded="false">Выбрать задачу · ' + tasks.length + ' ' + icon("chevron") + '</button><div class="between"><h2 class="sidebar-title">Отклики к задачам</h2><span class="mono caption">' + tasks.length + "</span></div>" +
    tasks.map(task => '<a href="#proposals/' + task.id + '" class="my-task"' + (task.id === selected.id ? ' aria-current="true"' : "") + '><strong>' + esc(titleOf(task)) + '</strong><div class="between"><span class="caption">' + esc(task.industry || "Без отрасли") + '</span><span class="caption">' + icon("response") + " " + count(allProposals, task.id) + " откл.</span></div></a>").join("") +
    linkButton("Управлять задачами", "#business", "secondary") + '</aside><div class="stack business-main">' + heading +
    '<section class="panel"><div class="caption">' + esc(selected.industry || "Отрасль не указана") + '</div><h2 class="h2">' + esc(titleOf(selected)) + '</h2><div class="actions">' +
    linkButton("Открыть карточку", "#task/" + selected.id, "ghost", "external") + linkButton("Управлять задачей", "#business/" + selected.id, "ghost") + '</div></section><div id="proposal-tabs"></div>' +
    alertBox("info", "Выбор только за вами", "Можно выбрать одну команду, несколько или ни одной. Система не назначает исполнителей — сравнивайте по идее, плану и сроку.") +
    '<div data-errors></div><div id="proposal-results" role="tabpanel"></div></div>';
  root.querySelector("#refresh-business-proposals").addEventListener("click", () => ctx.navigate("proposals/" + selected.id));
  root.querySelector(".sidebar-toggle").addEventListener("click", event => {
    const expanded = root.querySelector(".task-sidebar").classList.toggle("is-expanded");
    event.currentTarget.setAttribute("aria-expanded", String(expanded));
  });
  function render() {
    root.querySelector("#proposal-tabs").innerHTML = tabBar(proposals, filter);
    root.querySelector("#proposal-results").setAttribute("aria-labelledby", "tab-" + filter);
    root.querySelectorAll("[data-status]").forEach(btn => btn.addEventListener("click", () => { filter = btn.dataset.status; render(); }));
    const visible = proposals.filter(proposal => filter === "all" || proposal.status === filter);
    root.querySelector("#proposal-results").innerHTML = visible.length ? comparison(visible, ctx) :
      empty(proposals.length ? "Нет откликов с таким статусом" : "Предложений пока нет",
        proposals.length ? "Переключитесь на вкладку «Все», чтобы увидеть остальные предложения." : selected.status === "published" ? "Когда команды отправят свои идеи, они появятся здесь." : "Опубликуйте задачу, чтобы команды могли предложить решения.",
        proposals.length ? '<button id="show-all-proposals" class="btn btn--secondary">Показать все</button>' :
          linkButton("К моей задаче", "#business/" + selected.id, "secondary"));
    root.querySelector("#show-all-proposals")?.addEventListener("click", () => { filter = "all"; render(); });
    root.querySelectorAll("[data-confirm-progress]").forEach(btn => btn.addEventListener("click", async () => {
      await busy(btn, async () => {
        try {
          const updated = await api.confirmProgress(Number(btn.dataset.confirmProgress));
          proposals = proposals.map(p => p.id === updated.id ? updated : p);
          if (root.isConnected) { toast("Результат подтверждён: команде начислено 10 баллов"); render(); }
        } catch (error) { showError(root, error); }
      });
    }));
    root.querySelectorAll("[data-decision]").forEach(btn => btn.addEventListener("click", async () => {
      await busy(btn, async () => {
        const controls = Array.from(root.querySelectorAll("[data-decision]"));
        controls.forEach(el => { el.disabled = true; });
        try {
          const updated = await api.decide(Number(btn.dataset.id), btn.dataset.decision);
          proposals = proposals.map(proposal => proposal.id === updated.id ? updated : proposal);
          if (root.isConnected) {
            root.querySelector("[data-errors]").innerHTML = "";
            toast(updated.status === "accepted" ? "Команда выбрана" : updated.status === "rejected" ? "Отклик отклонён" : "Отклик возвращён на рассмотрение");
            render();
          }
        } catch (error) { showError(root, error); }
        finally { controls.forEach(el => { el.disabled = false; }); }
      });
    }));
  }
  render();
}

function comparison(proposals, ctx) {
  const cell = (proposal, html) => '<div class="compare__cell ' + (proposal.status === "accepted" ? "is-accepted" : proposal.status === "rejected" ? "is-rejected" : "") + '">' + html + "</div>";
  const row = (label, getHtml) => '<div class="compare__row"><div class="compare__label">' + label + "</div>" + proposals.map(p => cell(p, getHtml(p))).join("") + "</div>";
  const actions = p => p.status === "pending"
    ? '<div class="stack tight"><button class="btn btn--primary btn--sm" data-decision="accept" data-id="' + p.id + '">' + icon("check") + 'Выбрать команду</button><button class="btn btn--danger btn--sm" data-decision="reject" data-id="' + p.id + '">Отклонить</button></div>'
    : '<div class="stack tight"><span class="caption">' + (p.status === "accepted" ? "Вы выбрали эту команду" : "Вы отклонили этот отклик") + '</span><button class="btn btn--ghost btn--sm btn--wrap" data-decision="reopen" data-id="' + p.id + '">' + (p.status === "accepted" ? "Отменить выбор" : "Вернуть на рассмотрение") + "</button></div>";
  return '<div class="compare-scroll" tabindex="0" role="region" aria-label="Сравнение предложений"><div class="compare" style="--cols:' + proposals.length + ';--compare-min:' + (160 + proposals.length * 220) + 'px">' +
    row("Сравнение", p => { const team = teamOf(ctx, p); return '<div class="stack tight"><div class="team-identity"><span class="avatar mono">' + esc(initials(team.name)) + '</span><div><strong>' + esc(team.name) + '</strong><div class="caption">отклик ' + dateOf(p.created_at) + "</div></div></div>" + statusBadge(p.status) + "</div>"; }) +
    row("Навыки", p => { const team = teamOf(ctx, p); return esc(team.skills.join(" · ")) + '<div class="caption mono tech-list">' + esc(team.tech.join(", ")) + "</div>"; }) +
    row("Идея решения", p => esc(p.idea)) +
    row("План", p => '<span class="muted">' + esc(p.plan) + "</span>") +
    row("Срок", p => '<span class="mono">' + esc(p.deadline) + "</span>") +
    row("Прототип", p => prototypeLink(p.link)) +
    row("Фактический прогресс", p => progressSummary(p, true)) +
    row("Решение", actions) + "</div></div>";
}

export async function renderMyProposals(root, ctx) {
  let proposals = await api.proposals();
  // Владелец мог удалить задачу между запросом откликов и загрузкой карточек.
  // 404 исключаем из списка, сетевые ошибки оставляем видимыми для повторной попытки.
  const ids = [...new Set(proposals.map(p => p.task_id))];
  const tasks = (await Promise.all(ids.map(id => api.task(id).catch(error => {
    if (error.status === 404) return null;
    throw error;
  })))).filter(Boolean);
  const existingIds = new Set(tasks.map(task => task.id));
  if (!root.isConnected) return;
  let filter = "all";
  root.className = "content-wide stack";
  root.innerHTML = '<div class="page-heading"><div class="stack tight"><h1 class="h1">Мои отклики</h1><p class="muted">Ваши идеи и решения бизнеса. Статус сохраняется между посещениями.</p><p class="caption">Баллы команды за подтверждённые результаты: <strong id="team-progress-points">0</strong>. Это не рейтинг бизнес-задач.</p></div><button class="btn btn--secondary" id="refresh-proposals">Обновить статусы</button></div><div id="my-proposal-tabs"></div><div data-errors></div><div id="proposal-results" role="tabpanel" class="stack"></div>';
  root.querySelector("#refresh-proposals").addEventListener("click", () => ctx.navigate("proposals"));
  function render() {
    // После отправки результата заново берём актуальные объекты, а не старый снимок списка.
    const visibleProposals = proposals.filter(proposal => existingIds.has(proposal.task_id));
    root.querySelector("#team-progress-points").textContent = String(visibleProposals.reduce((sum, p) => sum + (p.progress?.points || 0), 0));
    root.querySelector("#my-proposal-tabs").innerHTML = tabBar(visibleProposals, filter);
    root.querySelector("#proposal-results").setAttribute("aria-labelledby", "tab-" + filter);
    root.querySelectorAll("[data-status]").forEach(btn => btn.addEventListener("click", () => { filter = btn.dataset.status; render(); }));
    const visible = visibleProposals.filter(p => filter === "all" || p.status === filter);
    root.querySelector("#proposal-results").innerHTML = visible.length ? visible.map(p => {
      const task = tasks.find(t => t.id === p.task_id);
      return '<article class="panel proposal-card"><div class="between"><div class="stack tight"><span class="caption">' + esc(task.industry || "Без отрасли") + " · " + dateOf(p.created_at) + '</span><h2 class="h2"><a class="ink-link" href="#task/' + p.task_id + '">' + esc(titleOf(task)) + "</a></h2></div>" + statusBadge(p.status) + '</div><div class="proposal-body"><div><div class="eyebrow">Идея решения</div><p>' + esc(p.idea) + '</p></div><div><div class="eyebrow">План работы</div><p class="muted">' + esc(p.plan) + '</p></div></div><div class="form-footer"><span class="mono">' + icon("clock") + " " + esc(p.deadline) + "</span>" + prototypeLink(p.link) + '<a class="text-link" href="#task/' + p.task_id + '">Открыть задачу ' + icon("arrow") + '</a></div><section class="stack"><h3 class="h3">Фактический прогресс</h3>' + progressSummary(p) + progressForm(p) + "</section></article>";
    }).join("") : empty(visibleProposals.length ? "Нет откликов с таким статусом" : "Вы ещё не отправляли отклики", "Выберите задачу в каталоге и расскажите, как ваша команда её решит.", linkButton("Найти задачу", "#catalog"));
    root.querySelectorAll("[data-progress-form]").forEach(form => form.addEventListener("submit", async event => {
      event.preventDefault();
      if (!validate(form)) return;
      await busy(form.querySelector('[type="submit"]'), async () => {
        try {
          const id = Number(form.dataset.progressForm), values = formValues(form);
          const updated = await api.submitProgress(id, { description: values["description_" + id], link: values["link_" + id] || null });
          proposals = proposals.map(p => p.id === updated.id ? updated : p);
          if (root.isConnected) { toast("Результат передан бизнесу. Баллы появятся после проверки."); render(); }
        } catch (error) { showError(root, error, form); }
      });
    }));
  }
  render();
}
