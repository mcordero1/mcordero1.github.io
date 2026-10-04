/* Apply the saved theme before paint; no external services or dependencies. */
(() => {
  "use strict";
  const root = document.documentElement;
  const storageKey = "profile-theme";
  const positionKey = "profile-language-position";
  let theme = "dark";
  try {
    if (localStorage.getItem(storageKey) === "light") theme = "light";
  } catch (_) { /* Controls still work when storage is unavailable. */ }
  root.dataset.theme = theme;
  // A fragment only records the last navigation click. Someone who keeps
  // reading may be much farther down, so restore the actual reading position.
  let savedPosition = null;
  try {
    const pending = JSON.parse(sessionStorage.getItem(positionKey) || "null");
    sessionStorage.removeItem(positionKey);
    if (pending && pending.path === location.pathname && Number.isFinite(pending.progress)) {
      savedPosition = pending;
      history.scrollRestoration = "manual";
    }
  } catch (_) { /* The section fragment still works without session storage. */ }
  function restorePosition() {
    if (!savedPosition) return;
    const section = document.getElementById(savedPosition.section);
    if (!section) return;
    const header = document.querySelector(".header");
    const readingLine = (header ? header.getBoundingClientRect().height : 0) + 32;
    const top = window.scrollY + section.getBoundingClientRect().top;
    const progress = Math.max(0, Math.min(1, savedPosition.progress));
    const desired = top + progress * section.getBoundingClientRect().height - readingLine;
    window.scrollTo({ top: Math.max(0, desired), behavior: "instant" });
  }
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
      languageLink.addEventListener("click", () => {
        const header = document.querySelector(".header");
        const readingLine = (header ? header.getBoundingClientRect().height : 0) + 32;
        const sections = [...document.querySelectorAll("main section[id]")];
        // Prefer the selected section while it is still on screen. This also
        // avoids picking the preceding section at a shared boundary.
        const selected = document.getElementById(decodeURIComponent(location.hash.slice(1)));
        const selectedRect = selected && selected.getBoundingClientRect();
        const selectedVisible = selectedRect && selectedRect.top <= readingLine + 120 && selectedRect.bottom > readingLine - 120;
        const current = (selectedVisible && sections.includes(selected) ? selected : null) || sections.find(section => {
          const rect = section.getBoundingClientRect();
          return rect.top <= readingLine && rect.bottom > readingLine;
        }) || sections.find(section => section.getBoundingClientRect().top > readingLine) || sections[sections.length - 1];
        if (!current) return;
        const rect = current.getBoundingClientRect();
        const progress = Math.max(0, Math.min(1, (readingLine - rect.top) / rect.height));
        const target = new URL(base, document.baseURI);
        target.hash = current.id;
        languageLink.href = target.href;
        try {
          sessionStorage.setItem(positionKey, JSON.stringify({ path: target.pathname, section: current.id, progress }));
        } catch (_) {}
      });
    }
    requestAnimationFrame(restorePosition);
  });
  window.addEventListener("load", () => {
    restorePosition();
    if (savedPosition) history.scrollRestoration = "auto";
  });
})();
