/* Поиск 1в1 как в Odoo: панель фильтров, свой фильтр, избранное, Ctrl+K — фокус.
   Элементы конструктора/избранного есть только на странице лидов —
   все обращения к ним закрыты проверками, на остальных страницах тихо пропускаем. */
(function () {
  "use strict";

  var FIELD_OPS = {
    stage: [["=", "="], ["!=", "≠"]],
    manager: [["=", "="], ["!=", "≠"]],
    priority: [["=", "="], ["!=", "≠"], [">=", "≥"], ["<=", "≤"]],
    revenue: [["=", "="], [">=", "≥"], ["<=", "≤"]],
    tag: [["~", "содержит"]],
    source: [["~", "содержит"]],
  };

  function el(id) {
    return document.getElementById(id);
  }

  function make(tag, attrs) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    return node;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var sv = el("searchview");
    if (!sv) return;

    // ── Панель: открыть/закрыть ──
    var toggle = sv.querySelector(".o_searchview__toggle");
    var dropdown = sv.querySelector(".o_searchview__dropdown");
    var input = sv.querySelector(".o_searchview__input");

    if (toggle && dropdown) {
      toggle.addEventListener("click", function (e) {
        e.stopPropagation();
        dropdown.hidden = !dropdown.hidden;
      });
      document.addEventListener("click", function (e) {
        if (!sv.contains(e.target)) dropdown.hidden = true;
      });
    }

    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (input) input.focus();
      }
    });

    // ── Конструктор своего фильтра (только лиды) ──
    var dataEl = el("searchview-data");
    var cfToggle = el("custom-toggle");
    var cfBuilder = el("custom-builder");
    var cfField = el("cf-field");
    var cfOp = el("cf-op");
    var cfWrap = el("cf-value-wrap");
    var cfAdd = el("cf-add");
    var refData = { stages: [], managers: [] };
    if (dataEl) {
      try {
        refData = JSON.parse(dataEl.textContent || "{}");
      } catch (e) { /* ignore */ }
      refData.stages = refData.stages || [];
      refData.managers = refData.managers || [];
    }

    function rebuildValue() {
      if (!cfField || !cfOp || !cfWrap) return;
      var field = cfField.value;
      // Операторы под поле
      cfOp.innerHTML = "";
      (FIELD_OPS[field] || [["=", "="]]).forEach(function (pair) {
        cfOp.appendChild(make("option", { value: pair[0], text: pair[1] }));
      });
      // Значение под поле
      cfWrap.innerHTML = "";
      var node;
      if (field === "stage") {
        node = make("select", { id: "cf-value", class: "input input--small" });
        refData.stages.forEach(function (s) {
          node.appendChild(make("option", { value: s.value, text: s.title }));
        });
      } else if (field === "manager") {
        node = make("select", { id: "cf-value", class: "input input--small" });
        node.appendChild(make("option", { value: "me", text: "Я" }));
        node.appendChild(make("option", { value: "none", text: "Без менеджера" }));
        refData.managers.forEach(function (m) {
          node.appendChild(make("option", { value: String(m.id), text: m.name }));
        });
      } else if (field === "priority") {
        node = make("select", { id: "cf-value", class: "input input--small" });
        [["3", "★★★"], ["2", "★★"], ["1", "★"], ["0", "—"]].forEach(function (p) {
          node.appendChild(make("option", { value: p[0], text: p[1] }));
        });
      } else if (field === "revenue") {
        node = make("input", { id: "cf-value", type: "number", min: "0", step: "any",
                               class: "input input--small", placeholder: "Сумма, ₽" });
      } else {
        node = make("input", { id: "cf-value", type: "text", class: "input input--small",
                               placeholder: "Текст…", autocomplete: "off" });
      }
      cfWrap.appendChild(node);
    }

    if (cfToggle && cfBuilder) {
      cfToggle.addEventListener("click", function () {
        cfBuilder.hidden = !cfBuilder.hidden;
        if (!cfBuilder.hidden) rebuildValue();
      });
    }
    if (cfField) {
      cfField.addEventListener("change", rebuildValue);
    }
    if (cfAdd) {
      cfAdd.addEventListener("click", function () {
        var valEl = el("cf-value");
        var value = valEl ? (valEl.value || "").trim() : "";
        if (!cfField || !cfOp || !value) {
          if (valEl) valEl.focus();
          return;
        }
        var params = new URLSearchParams(window.location.search);
        params.append("flt", cfField.value + "|" + cfOp.value + "|" + value);
        window.location.search = params.toString();
      });
    }

    // ── Избранное: сохранить текущий поиск ──
    var favName = el("fav-name");
    var favSave = el("fav-save");
    if (favSave) {
      favSave.addEventListener("click", function () {
        var name = favName ? (favName.value || "").trim() : "";
        if (!name) {
          if (favName) favName.focus();
          return;
        }
        favSave.disabled = true;
        window.apiFetch("/api/favorites", {
          method: "POST",
          body: JSON.stringify({
            name: name,
            target: "leads",
            params: window.location.search.replace(/^\?/, ""),
          }),
        }).then(function () {
          window.location.reload();
        }).catch(function (err) {
          alert("Не удалось сохранить: " + err.message);
          favSave.disabled = false;
        });
      });
      if (favName) {
        favName.addEventListener("keydown", function (e) {
          if (e.key === "Enter") {
            e.preventDefault();
            favSave.click();
          }
        });
      }
    }

    // ── Избранное: удалить ──
    sv.querySelectorAll("[data-fav-del]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!confirm("Удалить «" + (btn.title || "фильтр") + "» из избранного?")) return;
        window.apiFetch("/api/favorites/" + btn.dataset.favDel, {
          method: "DELETE",
        }).then(function () {
          window.location.reload();
        }).catch(function (err) {
          alert("Не удалось удалить: " + err.message);
        });
      });
    });
  });
})();
