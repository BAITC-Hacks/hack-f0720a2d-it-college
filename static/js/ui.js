// AI Sana — рендер-хелперы для static/js. Возвращают HTML-строки с классами из components.css.
export const LEVELS = [
  { min: 90, code: "priority", label: "Приоритетная" },
  { min: 70, code: "ready", label: "Готовая" },
  { min: 40, code: "working", label: "Рабочая" },
  { min: 0, code: "draft", label: "Черновик" },
];
export const FIELDS = [
  ["context", "Контекст", 10], ["need", "Потребность", 10], ["users", "Пользователи", 10],
  ["data", "Данные и материалы", 20], ["constraints", "Ограничения", 10],
  ["expected_result", "Ожидаемый результат", 15], ["success_criteria", "Критерии успеха", 15],
  ["contact", "Связь с бизнесом", 10],
];
export const INDICATORS = [
  ["context_need", "Контекст и потребность", 20], ["data", "Данные и материалы", 20],
  ["expected_result", "Ожидаемый результат", 15], ["success_criteria", "Критерии успеха", 15],
  ["constraints", "Ограничения", 10], ["users", "Пользователи", 10], ["contact", "Связь с бизнесом", 10],
];
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const levelOf = (score) => LEVELS.find((l) => score >= l.min);
export const fmt = (n) => (Number.isInteger(n) ? String(n) : String(n).replace(".", ","));

export const badge = (score) => { const l = levelOf(score); return `<span class="badge badge--${l.code}">${l.label}</span>`; };
export const meter = (score, width = 160) => `<div class="meter meter--${levelOf(score).code}" style="width:${width}px" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${score}" aria-label="Готовность ${fmt(score)} из 100"><div class="meter__fill" style="width:${score}%"></div><span class="meter__tick"></span></div>`;

export const catalogRow = (t, i) => `
<a class="catalog-row" href="#task/${t.id}">
  <div class="catalog-row__rank">${String(i + 1).padStart(2, "0")}</div>
  <div class="stack" style="gap:8px;min-width:0">
    <div class="catalog-row__title">${esc(t.title)}</div>
    <div class="catalog-row__result"><span class="caption">Результат: </span>${t.expected_result ? esc(t.expected_result) : '<i class="caption">не указан</i>'}</div>
    <div class="caption">${esc(t.industry)}</div>
    ${t.level === "draft" ? '<span class="tag-draft">Требует уточнения · отклик открыт</span>' : ""}
  </div>
  <div class="caption">${t.proposals_count ?? 0} откл.</div>
  <div class="catalog-row__rating"><div style="display:flex;gap:10px;align-items:center">${badge(t.score)}<span class="score">${fmt(t.score)}</span></div>${meter(t.score)}</div>
</a>`;

export const breakdown = (bd) => INDICATORS.map(([k, label, max]) => {
  const e = bd?.[k]?.earned ?? 0; const st = e >= max ? "" : e > 0 ? "is-short" : "";
  return `<div class="breakdown__row"><span>${label}</span><div class="meter"><div class="meter__fill ${st}" style="width:${(e / max) * 100}%;${e >= max ? "background:var(--c-accent)" : ""}"></div></div><span class="mono" style="text-align:right">${fmt(e)}/${max}</span></div>`;
}).join("");

export const missingList = (missing) => `<ul class="missing">${missing.map((m) => { const [txt, pts] = m.split(" — "); return `<li><span>${esc(txt)}</span><b>${esc((pts || "").replace(" баллов", ""))}</b></li>`; }).join("")}</ul>`;

export const emptyState = ({ title, text, actions = "" }) => `<div class="empty"><div class="empty__icon" aria-hidden="true">∅</div><h2 class="h2">${esc(title)}</h2><p class="muted" style="margin:0;max-width:460px">${esc(text)}</p><div style="display:flex;gap:12px">${actions}</div></div>`;

export const alertBox = (kind, title, text) => `<div class="alert alert--${kind}" role="${kind === "error" ? "alert" : "status"}"><div><div class="alert__title">${esc(title)}</div><div class="alert__text">${esc(text)}</div></div></div>`;

// Ошибки FastAPI 422 → подсветка полей: <div class="field" data-field="idea">…<div class="field__error"></div></div>
export function showFieldErrors(form, detail) {
  form.querySelectorAll(".field.is-invalid").forEach((f) => f.classList.remove("is-invalid"));
  (detail || []).forEach((err) => {
    const name = err.loc?.[err.loc.length - 1];
    const f = form.querySelector(`.field[data-field="${name}"]`);
    if (!f) return;
    f.classList.add("is-invalid");
    const box = f.querySelector(".field__error"); if (box) box.textContent = err.msg;
    f.querySelector("input,textarea,select")?.setAttribute("aria-invalid", "true");
  });
}
