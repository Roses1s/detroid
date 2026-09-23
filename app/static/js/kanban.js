/* Быстрое создание карточки прямо из колонки канбана (кнопка "+").
   Настройки — из data-атрибутов доски #kanban (по умолчанию — лиды):
   data-api-base, data-status-key, data-entity. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var board = document.getElementById("kanban");
    if (!board) return;

    var apiBase = board.dataset.apiBase || "/api/leads";
    var statusKey = board.dataset.statusKey || "stage";
    var entity = board.dataset.entity || "лид";

    // Открыть форму быстрого создания
    board.querySelectorAll("[data-quick-add]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var stage = btn.dataset.quickAdd;
        var form = board.querySelector('[data-quick-form="' + stage + '"]');
        if (!form) return;
        // закрыть остальные
        board.querySelectorAll(".kanban-quick").forEach(function (f) {
          if (f !== form) f.hidden = true;
        });
        form.hidden = !form.hidden;
        if (!form.hidden) {
          var input = form.querySelector("[data-quick-title]");
          if (input) input.focus();
        }
      });
    });

    // Отмена
    board.querySelectorAll("[data-quick-cancel]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var form = btn.closest(".kanban-quick");
        if (form) {
          form.hidden = true;
          var input = form.querySelector("[data-quick-title]");
          if (input) input.value = "";
        }
      });
    });

    // Сохранение: POST на api-base, затем перезагрузка (проще и надёжнее для MVP)
    board.querySelectorAll("[data-quick-save]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var form = btn.closest(".kanban-quick");
        var input = form.querySelector("[data-quick-title]");
        var title = (input.value || "").trim();
        if (!title) {
          input.focus();
          return;
        }
        var stage = form.dataset.quickForm;
        btn.disabled = true;
        var payload = { title: title };
        payload[statusKey] = stage;
        window.apiFetch(apiBase, {
          method: "POST",
          body: JSON.stringify(payload),
        }).then(function () {
          window.location.reload();
        }).catch(function (err) {
          alert("Не удалось создать " + entity + ": " + err.message);
          btn.disabled = false;
        });
      });
    });

    // Enter в поле = сохранить
    board.querySelectorAll("[data-quick-title]").forEach(function (input) {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          var form = input.closest(".kanban-quick");
          var save = form.querySelector("[data-quick-save]");
          if (save) save.click();
        }
      });
    });
  });
})();
