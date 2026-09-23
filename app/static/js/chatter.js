/* Лента общения: кнопки Заметка/Сообщение + Ctrl+Enter. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var chatter = document.getElementById("chatter");
    if (!chatter) return;

    var kindInput = chatter.querySelector("#chatter-kind");
    var textarea = chatter.querySelector(".o_chatter__input");
    var tabs = chatter.querySelectorAll("[data-kind]");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.remove("o_chatter__btn--active"); });
        tab.classList.add("o_chatter__btn--active");
        if (kindInput) kindInput.value = tab.dataset.kind;
        if (textarea) {
          textarea.placeholder = tab.dataset.kind === "message"
            ? "Отправьте сообщение… (Ctrl+Enter — отправить)"
            : "Запишите внутреннюю записку… (Ctrl+Enter — отправить)";
          textarea.focus();
        }
      });
    });

    if (textarea) {
      textarea.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
          e.preventDefault();
          var form = textarea.closest("form");
          if (form) form.submit();
        }
      });
    }
  });
})();
