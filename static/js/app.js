// Инициализация каркаса экранов и локального переключателя роли.
import { initConstructor } from "./constructor.js";
import { initCatalog } from "./catalog.js";
import { initProposals } from "./proposals.js";

const roleSelect = document.querySelector("#role-select");
roleSelect.addEventListener("change", () => {
  document.body.dataset.role = roleSelect.value;
});
document.body.dataset.role = roleSelect.value;

initConstructor(document.querySelector("#constructor"));
initCatalog(document.querySelector("#catalog"));
initProposals(document.querySelector("#proposals"));
