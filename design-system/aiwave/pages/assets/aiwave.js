/* AIWave 原型互動層。
   誠實原則:這是設計審批用原型,所有狀態只存在瀏覽器 localStorage,
   不代表後端已實作;正式版一律走 Platform API。 */
(function () {
  "use strict";

  var KEY = "aiwave-proto";

  function store() {
    try { return JSON.parse(localStorage.getItem(KEY) || "{}"); }
    catch (e) { return {}; }
  }
  function save(state) { localStorage.setItem(KEY, JSON.stringify(state)); }

  window.AIWave = {
    get: function (name, fallback) {
      var s = store();
      return name in s ? s[name] : fallback;
    },
    set: function (name, value) {
      var s = store();
      s[name] = value;
      save(s);
    },
    /* 帳號切換(Demo 快速登入) */
    login: function (persona) {
      this.set("persona", persona);
    },
    persona: function () { return this.get("persona", null); },

    /* 吐司訊息:aria-live 由頁面上的 #toast 承載 */
    toast: function (message) {
      var el = document.getElementById("toast");
      if (!el) return;
      el.textContent = message;
      el.hidden = false;
      clearTimeout(el._timer);
      el._timer = setTimeout(function () { el.hidden = true; }, 4000);
    },

    /* TaskDraft 原型:欄位自動存草稿、重新整理可續填 */
    bindDraft: function (formId, draftName) {
      var form = document.getElementById(formId);
      if (!form) return;
      var draft = this.get(draftName, {});
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!el.name) return;
        if (el.type === "radio" || el.type === "checkbox") {
          if (draft[el.name] !== undefined) {
            el.checked = Array.isArray(draft[el.name])
              ? draft[el.name].indexOf(el.value) !== -1
              : draft[el.name] === el.value;
          }
        } else if (draft[el.name] !== undefined) {
          el.value = draft[el.name];
        }
      });
      var self = this;
      form.addEventListener("input", function () {
        var data = {};
        Array.prototype.forEach.call(form.elements, function (el) {
          if (!el.name) return;
          if (el.type === "radio") { if (el.checked) data[el.name] = el.value; }
          else if (el.type === "checkbox") {
            data[el.name] = data[el.name] || [];
            if (el.checked) data[el.name].push(el.value);
          } else { data[el.name] = el.value; }
        });
        self.set(draftName, data);
        var saved = document.getElementById("draft-saved");
        if (saved) {
          saved.textContent = "草稿已自動儲存(僅存於此瀏覽器)";
        }
      });
    },
    clearDraft: function (draftName) { this.set(draftName, {}); }
  };

  /* dialog 開關(宣告式:data-open-dialog / data-close-dialog) */
  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-open-dialog]");
    if (opener) {
      var dlg = document.getElementById(opener.getAttribute("data-open-dialog"));
      if (dlg) dlg.showModal();
    }
    var closer = event.target.closest("[data-close-dialog]");
    if (closer) {
      var parent = closer.closest("dialog");
      if (parent) parent.close();
    }
  });
})();
