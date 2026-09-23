// Каталог: живые фильтры, поиск, сортировка и рекомендации по интересам команды.
import { api } from "./api.js";
import { esc, badge, meter, fmt, icon, titleOf, empty, linkButton, memory } from "./helpers.js";

const levels = [["priority", "Приоритетная", "90–100"], ["ready", "Готовая", "70–89"], ["working", "Рабочая", "40–69"], ["draft", "Черновик", "0–39"]];

function row(task, index, ctx) {
  const owner = ctx.users.find(u => u.id === task.owner_id);
  return '<a class="catalog-row" href="#task/' + task.id + '"><span class="catalog-row__rank">' + String(index + 1).padStart(2, "0") + '</span><div class="catalog-row__body">' +
    '<h2 class="catalog-row__title">' + esc(titleOf(task)) + '</h2><div class="catalog-row__result"><span class="caption">Результат: </span>' + esc(task.expected_result || "Не указан") + '</div>' +
    '<div class="caption">' + esc(task.industry || "Отрасль не указана") + (owner ? " · " + esc(owner.name) : "") + "</div>" +
    (task.level === "draft" ? '<span class="tag-draft">Требует уточнения · отклик открыт</span>' : "") +
    '</div><div class="catalog-conditions"><span>' + icon("data") + esc(task.data ? "Данные описаны" : "Данные не указаны") + '</span><span>' + icon("clock") + esc(task.constraints ? "Есть ограничения" : "Ограничения не указаны") + '</span><span>' + icon("response") + task.proposals_count + " откл.</span></div>" +
    '<div class="catalog-row__rating"><div class="rating-inline">' + badge(task.score) + '<span class="score">' + fmt(task.score) + "</span></div>" + meter(task.score) + "</div></a>";
}

export async function renderCatalog(root, ctx, recommendations = false) {
  const tasks = await api.catalog();
  if (!root.isConnected) return;
  const team = ctx.teams.find(t => t.id === ctx.user.team_id);
  const interests = team?.interests || [];
  const matches = task => interests.some(interest => (task.industry || "").toLocaleLowerCase().includes(interest.toLocaleLowerCase()) || interest.toLocaleLowerCase().includes((task.industry || "\0").toLocaleLowerCase()));
  const source = recommendations && team ? tasks.filter(task => task.score >= 40 && matches(task)) : tasks;
  const industries = [...new Set(tasks.map(t => t.industry).filter(Boolean))].sort((a, b) => a.localeCompare(b, "ru"));
  const saved = memory.get("catalog-filters", {});
  const state = {
    search: recommendations ? "" : saved.search || "",
    levels: new Set(recommendations ? levels.map(l => l[0]) : saved.levels || levels.map(l => l[0])),
    industries: new Set(recommendations ? [] : (saved.industries || []).filter(i => industries.includes(i))),
    sort: recommendations ? "rating" : saved.sort || "rating",
  };
  const check = (value, label, count, name, checked, range = "") => '<label class="check-row"><input type="checkbox" name="' + name + '" value="' + esc(value) + '"' + (checked ? " checked" : "") + '><span>' + esc(label) + (range ? ' <small class="mono">' + range + "</small>" : "") + '</span><span class="check-count mono">' + count + "</span></label>";
  root.className = "catalog-layout";
  root.innerHTML = '<aside class="filter-sidebar" aria-label="Фильтры"><label class="field" for="catalog-search"><span class="field__label">Поиск</span><span class="search-box">' + icon("search") + '<input id="catalog-search" type="search" placeholder="Название или результат" value="' + esc(state.search) + '"></span></label>' +
    '<button class="btn btn--secondary sidebar-toggle" aria-expanded="false" type="button">Фильтры по готовности и теме ' + icon("chevron") + '</button>' +
    '<fieldset><legend>Готовность описания</legend>' + levels.map(([code, label, range]) => check(code, label, source.filter(t => t.level === code).length, "level", state.levels.has(code), range)).join("") + "</fieldset>" +
    '<fieldset><legend>Тема</legend>' + industries.map(ind => check(ind, ind, source.filter(t => t.industry === ind).length, "industry", state.industries.has(ind))).join("") + "</fieldset>" +
    '<div class="filter-note">Рейтинг показывает, насколько полно бизнес описал задачу, а не известность компании. Откликнуться можно на любую задачу.</div>' +
    '<button class="btn btn--ghost btn--sm" id="reset-filters">Сбросить фильтры</button></aside>' +
    '<div class="catalog-main stack"><div class="page-heading"><div class="stack tight"><h1 class="h1">' + (recommendations ? "По интересам команды" : "Каталог задач") + '</h1><p class="muted" id="catalog-subtitle"></p></div>' +
    '<label class="sort-control"><span class="caption">Сортировка</span><select class="select" id="sort"><option value="rating">По рейтингу готовности</option><option value="new">Сначала новые</option><option value="proposals">Меньше откликов</option></select></label></div>' +
    (recommendations ? '<div class="filter-note">Задачи от 40 баллов, подобранные по отрасли и интересам ' + esc(team?.name || "вашей команды") + '. Вы сами решаете, куда откликнуться. <a href="#catalog">Открыть весь каталог, включая черновые задачи</a></div>' : "") +
    '<div class="filter-chips actions" id="filter-chips"></div><div id="catalog-results" aria-live="polite"></div></div>';
  root.querySelector("#sort").value = state.sort;
  root.querySelector(".sidebar-toggle").addEventListener("click", event => {
    const expanded = root.querySelector(".filter-sidebar").classList.toggle("is-expanded");
    event.currentTarget.setAttribute("aria-expanded", String(expanded));
  });

  function update() {
    if (!root.isConnected) return;
    const query = state.search.trim().toLocaleLowerCase();
    const filtered = source.filter(t => state.levels.has(t.level) && (!state.industries.size || state.industries.has(t.industry)) && (!query || [t.title, t.expected_result, t.raw_text, t.industry].some(v => v?.toLocaleLowerCase().includes(query))));
    if (state.sort === "new") filtered.sort((a, b) => b.created_at.localeCompare(a.created_at) || b.id - a.id);
    else if (state.sort === "proposals") filtered.sort((a, b) => a.proposals_count - b.proposals_count || b.score - a.score);
    else filtered.sort((a, b) => b.score - a.score || b.created_at.localeCompare(a.created_at));
    root.querySelector("#catalog-subtitle").textContent = filtered.length + " из " + source.length + " задач. Чем полнее описание, тем выше задача в списке.";
    const chipLabels = [...state.industries].map(i => [i, "industry", i]);
    if (state.levels.size !== 4) levels.filter(l => state.levels.has(l[0])).forEach(l => chipLabels.push([l[1], "level", l[0]]));
    root.querySelector("#filter-chips").innerHTML = chipLabels.map(([label, type, value]) => '<button class="chip" data-remove="' + type + '" data-value="' + esc(value) + '" aria-label="Убрать фильтр ' + esc(label) + '">' + esc(label) + icon("x") + "</button>").join("");
    root.querySelectorAll("[data-remove]").forEach(btn => btn.addEventListener("click", () => {
      if (btn.dataset.remove === "industry") state.industries.delete(btn.dataset.value);
      else state.levels = new Set(levels.map(l => l[0]));
      syncInputs(); update();
    }));
    const results = root.querySelector("#catalog-results");
    results.innerHTML = filtered.length ? '<div class="catalog"><div class="catalog__head eyebrow"><span>№</span><span>Задача и ожидаемый результат</span><span>Условия</span><span class="align-right">Готовность</span></div>' + filtered.map((task, i) => row(task, i, ctx)).join("") + "</div>" :
      empty(source.length ? "Нет задач с такими фильтрами" : recommendations ? "Пока нет задач по вашим интересам" : "Задач пока нет", source.length ? "Попробуйте другой запрос или покажите все уровни готовности. На черновые задачи тоже можно откликнуться." : recommendations ? "Посмотрите общий каталог: на любую опубликованную задачу можно отправить своё предложение." : "После публикации бизнесом задачи появятся здесь.",
        source.length ? '<button class="btn btn--dark" id="show-levels">Показать все уровни</button><button class="btn btn--secondary" id="empty-reset">Сбросить фильтры</button>' : linkButton(recommendations ? "Весь каталог" : "Создать задачу", recommendations || ctx.user.role === "team" ? "#catalog" : "#new"));
    root.querySelector("#show-levels")?.addEventListener("click", () => { state.levels = new Set(levels.map(l => l[0])); syncInputs(); update(); });
    root.querySelector("#empty-reset")?.addEventListener("click", reset);
    if (!recommendations) memory.set("catalog-filters", { ...state, levels: [...state.levels], industries: [...state.industries] });
  }
  function syncInputs() {
    root.querySelectorAll('input[name="level"]').forEach(el => { el.checked = state.levels.has(el.value); });
    root.querySelectorAll('input[name="industry"]').forEach(el => { el.checked = state.industries.has(el.value); });
    root.querySelector("#catalog-search").value = state.search;
  }
  function reset() { state.search = ""; state.levels = new Set(levels.map(l => l[0])); state.industries.clear(); syncInputs(); update(); }
  root.querySelector("#catalog-search").addEventListener("input", e => { state.search = e.target.value; update(); });
  root.querySelector("#sort").addEventListener("change", e => { state.sort = e.target.value; update(); });
  root.querySelectorAll('input[type="checkbox"]').forEach(el => el.addEventListener("change", () => {
    const selected = el.name === "level" ? state.levels : state.industries;
    if (el.checked) selected.add(el.value); else selected.delete(el.value); update();
  }));
  root.querySelector("#reset-filters").addEventListener("click", reset);
  update();
}
