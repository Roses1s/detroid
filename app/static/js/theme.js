/* Переключатель «Тёмный режим» в меню пользователя (как в Odoo).
   Выбор хранится в localStorage, начальное значение ставит
   инлайн-скрипт в <head> (до отрисовки, без мигания). */
(function () {
  "use strict";
  var KEY = "detroid-theme";

  function current() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function apply(theme, btn) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) { /* приватный режим — просто не запоминаем */ }
    if (btn) btn.setAttribute("aria-checked", theme === "dark" ? "true" : "false");
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.setAttribute("aria-checked", current() === "dark" ? "true" : "false");
    btn.addEventListener("click", function (e) {
      e.stopPropagation(); // меню пользователя остаётся открытым
      apply(current() === "dark" ? "light" : "dark", btn);
    });
  });
})();
