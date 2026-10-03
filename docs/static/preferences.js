/* Apply the saved theme before paint; no external services or dependencies. */
(() => {
  "use strict";
  const root = document.documentElement;
  const storageKey = "profile-theme";
  let theme = "dark";
  try {
    if (localStorage.getItem(storageKey) === "light") theme = "light";
  } catch (_) { /* Controls still work when storage is unavailable. */ }
  root.dataset.theme = theme;
  document.addEventListener("DOMContentLoaded", () => {
    const button = document.querySelector(".theme-toggle");
    const languageLink = document.querySelector(".language-toggle");
    const meta = document.querySelector('meta[name="theme-color"]');
    function updateTheme() {
      const light = root.dataset.theme === "light";
      const label = light ? button.dataset.darkLabel : button.dataset.lightLabel;
      button.title = label;
      button.setAttribute("aria-label", label);
      if (meta) meta.content = light ? "#f5f7f3" : "#0b1012";
    }
    if (button) {
      button.hidden = false;
      updateTheme();
      button.addEventListener("click", () => {
        root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
        try { localStorage.setItem(storageKey, root.dataset.theme); } catch (_) {}
        updateTheme();
      });
    }
    if (languageLink) {
      const base = languageLink.getAttribute("href");
      function updateLanguageLink() {
        const target = new URL(base, document.baseURI);
        target.hash = window.location.hash;
        languageLink.href = target.href;
      }
      updateLanguageLink();
      window.addEventListener("hashchange", updateLanguageLink);
    }
  });
})();
