/* Drag & Drop канбана на чистом HTML5 DnD API.
   Карточка (.kanban-card[draggable]) перетаскивается в зону ([data-drop-zone]).
   После drop — PATCH <api-base>/<id>/<move-suffix>, затем карточка перемещается
   в DOM и пересчитываются счётчики колонок (без перезагрузки страницы).
   Настройки читаются из data-атрибутов доски #kanban (по умолчанию — лиды):
   data-api-base, data-id-attr, data-status-key, data-move-suffix, data-entity. */
(function () {
  "use strict";

  function money(n) {
    try {
      return Number(n || 0).toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " ₽";
    } catch (e) {
      return (n || 0) + " ₽";
    }
  }

  function cardAmount(card) {
    // Сумма лежит в .kanban-card__money в виде "120 000 ₽" — парсим обратно
    var el = card.querySelector(".kanban-card__money");
    if (!el) return 0;
    var digits = (el.textContent || "").replace(/[^\d]/g, "");
    return parseInt(digits || "0", 10);
  }

  function refreshColumn(col) {
    var body = col.querySelector("[data-drop-zone]");
    if (!body) return;
    var cards = body.querySelectorAll(".kanban-card");
    var total = 0;
    cards.forEach(function (c) { total += cardAmount(c); });
    var sumEl = col.querySelector(".o_kanban_col__sum");
    if (sumEl) sumEl.textContent = money(total);
    var countEl = col.querySelector(".o_kanban_col__count");
    if (countEl) countEl.textContent = cards.length;
    // Полоска-прогресс после перетаскивания устаревает — обновится при перезагрузке
  }

  document.addEventListener("DOMContentLoaded", function () {
    var board = document.getElementById("kanban");
    if (!board) return;

    var apiBase = board.dataset.apiBase || "/api/leads";
    var idAttr = board.dataset.idAttr || "leadId";
    var statusKey = board.dataset.statusKey || "stage";
    var moveSuffix = board.dataset.moveSuffix || "stage";
    var entity = board.dataset.entity || "лид";

    var dragged = null;

    board.querySelectorAll(".kanban-card").forEach(function (card) {
      card.addEventListener("dragstart", function (e) {
        dragged = card;
        card.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
        try {
          e.dataTransfer.setData("text/plain", card.dataset[idAttr]);
        } catch (err) { /* ignore */ }
      });
      card.addEventListener("dragend", function () {
        card.classList.remove("dragging");
        board.querySelectorAll(".drag-over").forEach(function (z) {
          z.classList.remove("drag-over");
        });
        dragged = null;
      });
    });

    board.querySelectorAll("[data-drop-zone]").forEach(function (zone) {
      zone.addEventListener("dragover", function (e) {
        e.preventDefault(); // обязательно, иначе drop не сработает
        e.dataTransfer.dropEffect = "move";
        zone.classList.add("drag-over");
      });
      zone.addEventListener("dragleave", function () {
        zone.classList.remove("drag-over");
      });
      zone.addEventListener("drop", function (e) {
        e.preventDefault();
        zone.classList.remove("drag-over");
        if (!dragged) return;

        var cardId = dragged.dataset[idAttr];
        var newStage = zone.dataset.dropZone;
        var oldCol = dragged.closest(".o_kanban_col");
        var newCol = zone.closest(".o_kanban_col");

        if (oldCol === newCol) return; // та же колонка — ничего не делаем

        // Оптимистично двигаем карточку сразу, сервер догоним запросом
        zone.appendChild(dragged);
        refreshColumn(oldCol);
        refreshColumn(newCol);

        var payload = {};
        payload[statusKey] = newStage;
        window.apiFetch(apiBase + "/" + cardId + "/" + moveSuffix, {
          method: "PATCH",
          body: JSON.stringify(payload),
        }).catch(function (err) {
          alert("Не удалось переместить " + entity + ": " + err.message + "\nСтраница будет обновлена.");
          window.location.reload();
        });
      });
    });
  });
})();
