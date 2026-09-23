/* Detroid CRM — общий JS: тосты, меню пользователя, fetch-хелпер. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // Плавно прячем тосты через 5 секунд
    document.querySelectorAll(".o_toast").forEach(function (el) {
      setTimeout(function () {
        el.style.transition = "opacity 0.5s";
        el.style.opacity = "0";
        setTimeout(function () { el.remove(); }, 500);
      }, 5000);
    });

    // Выпадающее меню пользователя в navbar
    var user = document.querySelector(".o_navbar__user");
    var btn = document.querySelector(".o_navbar__user-btn");
    if (user && btn) {
      btn.addEventListener("click", function (e) {
        e.stopPropagation();
        user.classList.toggle("open");
      });
      document.addEventListener("click", function () {
        user.classList.remove("open");
      });
    }
  });

  // Хелпер для fetch с JSON
  window.apiFetch = async function apiFetch(url, options) {
    options = options || {};
    // CSRF-токен берём из <meta> в base.html — без него сервер отклонит запрос
    var meta = document.querySelector('meta[name="csrf-token"]');
    options.headers = Object.assign(
      { "Content-Type": "application/json" },
      meta && meta.content ? { "X-CSRFToken": meta.content } : {},
      options.headers || {}
    );
    const res = await fetch(url, options);
    if (!res.ok) {
      let msg = "Ошибка " + res.status;
      try {
        const data = await res.json();
        if (data && data.error) msg = data.error;
      } catch (e) { /* ignore */ }
      throw new Error(msg);
    }
    return res.json();
  };
})();
