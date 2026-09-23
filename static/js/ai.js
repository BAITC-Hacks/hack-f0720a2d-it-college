// Настройки подключения сохраняются сервером; ключ не попадает в LocalStorage.
import { api } from "./api.js";
import { esc, field, formValues, validate, busy, showError, clearErrors, toast, linkButton, alertBox } from "./helpers.js";

export async function renderAISettings(root, ctx) {
  let settings = await api.aiSettings();
  if (!root.isConnected) return;
  root.className = "content-wide stack ai-settings";
  root.innerHTML = '<div class="page-heading"><div class="stack tight"><h1 class="h1">Настройки AI</h1><p class="muted">Подключите LM Studio, llmster или другой совместимый сервер для анализа задач.</p></div>' + linkButton("Создать задачу", "#new") + '</div>' +
    '<form class="panel panel--roomy stack" id="ai-settings-form" novalidate><div data-errors></div>' +
    field("base_url", "Адрес API", settings.base_url, { type: "url", required: true, max: 2000, placeholder: "http://127.0.0.1:1234/v1", hint: "Локальный или публичный HTTP(S) адрес. Для llmster можно указать https://ваш-сервер/v1." }) +
    field("api_key", "API-ключ", "", { type: "password", hint: settings.has_api_key ? "Ключ уже сохранён. Оставьте поле пустым, чтобы сохранить его для этого адреса." : "Необязательно для локального сервера без авторизации." }) +
    '<label class="check-row"><input type="checkbox" name="clear_api_key"><span>Удалить сохранённый ключ</span></label>' +
    '<div class="field" data-field="model"><label class="field__label" for="ai-model">Модель</label><select class="select" name="model" id="ai-model"><option value="">Автоматически — первая доступная текстовая модель</option>' +
    (settings.model ? '<option selected value="' + esc(settings.model) + '">' + esc(settings.model) + '</option>' : '') + '</select><div class="field__error"></div><p class="caption">Список загружается с выбранного сервера. Модель должна поддерживать текстовые диалоги.</p></div>' +
    '<div class="actions"><button type="button" class="btn btn--secondary" id="refresh-models">Обновить список моделей</button><span class="caption" id="ai-connection-status" role="status"></span></div>' +
    '<details><summary class="text-button">Совместимость ответа</summary><div class="details-content"><label class="field__label" for="ai-format">Формат JSON</label><select class="select" id="ai-format" name="response_format"><option value="auto">Автоматически</option><option value="json_schema">JSON Schema</option><option value="json_object">JSON Object</option><option value="text">JSON в тексте</option></select><p class="caption">Автоматический режим проверяет поддержку формата сервером. Полученные сведения всегда проходят проверку.</p></div></details>' +
    '<div class="form-footer"><span class="caption">Настройки сохраняются для текущего бизнес-пользователя.</span><button type="submit" class="btn btn--primary" id="save-ai-settings">Сохранить настройки</button></div></form>' +
    alertBox("info", "Модель работает с вашими сведениями", "Описание и ответы отправляются указанному AI-серверу. Перед публикацией вы проверяете и подтверждаете карточку.");
  const form = root.querySelector("form"), status = root.querySelector("#ai-connection-status");
  form.elements.api_key.autocomplete = "new-password";
  form.elements.response_format.value = settings.response_format;
  const payload = () => ({ ...formValues(form), clear_api_key: form.elements.clear_api_key.checked });
  let loading = false;
  const freeze = (value) => form.querySelectorAll("input,select,button").forEach(control => { control.disabled = value; });
  async function refresh() {
    if (loading || !validate(form)) return;
    const body = payload();
    loading = true; freeze(true);
    status.textContent = "Подключаемся к серверу…";
    try {
      const result = await api.aiModels(body);
      if (!root.isConnected) return;
      form.elements.model.innerHTML = '<option value="">Автоматически — первая доступная текстовая модель</option>' + result.models.map(model =>
        '<option value="' + esc(model.id) + '">' + esc(model.id) + (model.chat_candidate ? '' : ' · возможно, не для диалогов') + '</option>').join("");
      form.elements.model.value = result.models.some(model => model.id === body.model) ? body.model : "";
      status.textContent = result.models.length ? 'Доступно моделей: ' + result.models.length + (result.selected_model ? '. Выбрана: ' + result.selected_model : '. Выберите модель.') : "Сервер доступен, но список моделей пуст. Добавьте текстовую модель на сервере.";
      clearErrors(form);
    } catch (error) {
      if (root.isConnected) { status.textContent = "Подключение не проверено"; showError(root, error, form); }
    } finally { loading = false; freeze(false); }
  }
  form.elements.base_url.addEventListener("input", () => {
    form.elements.model.innerHTML = '<option value="">Автоматически — первая доступная текстовая модель</option>';
    status.textContent = "Обновите список для нового адреса. Старый ключ на новый адрес не отправляется.";
  });
  root.querySelector("#refresh-models").addEventListener("click", refresh);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (loading || !validate(form)) return;
    const body = payload();
    await busy(root.querySelector("#save-ai-settings"), async () => {
      try {
        settings = await api.saveAISettings(body);
        if (!root.isConnected) return;
        form.elements.base_url.value = settings.base_url;
        form.elements.api_key.value = "";
        form.elements.clear_api_key.checked = false;
        root.querySelector("#hint-api_key").textContent = settings.has_api_key ? "Ключ сохранён. Оставьте поле пустым, чтобы сохранить его для этого адреса." : "Ключ не задан.";
        clearErrors(form); toast("Настройки AI сохранены");
      } catch (error) { if (root.isConnected) showError(root, error, form); }
    });
  });
  await refresh();
}
