(function () {
  const DEBOUNCE_MS = 1000;
  const SWIPE_THRESHOLD_PX = 60;
  const SWIPE_MAX_VERTICAL_PX = 80;

  function isTyping() {
    const el = document.activeElement;
    if (!el) {
      return false;
    }
    const tag = el.tagName;
    return (
      tag === "INPUT" ||
      tag === "SELECT" ||
      tag === "TEXTAREA" ||
      el.isContentEditable
    );
  }

  function blocksPageNavigation() {
    const el = document.activeElement;
    if (!el) {
      return false;
    }
    if (el.isContentEditable) {
      return true;
    }
    const tag = el.tagName;
    if (tag === "TEXTAREA") {
      return true;
    }
    if (tag === "INPUT") {
      const type = (el.getAttribute("type") || "text").toLowerCase();
      return type !== "button" && type !== "submit" && type !== "checkbox";
    }
    return false;
  }

  function pageNav() {
    return document.querySelector("[data-page-nav]");
  }

  function navigatePage(direction) {
    const nav = pageNav();
    if (!nav) {
      return;
    }
    const url =
      direction === "next"
        ? nav.getAttribute("data-next-url")
        : nav.getAttribute("data-prev-url");
    if (!url) {
      return;
    }
    window.location.href = url;
  }

  let touchStartX = 0;
  let touchStartY = 0;
  let touchTracking = false;

  const filterForm = document.getElementById("library-filter-form");
  const helpDialog = document.getElementById("keyboard-help");

  function submitFilterForm() {
    if (!filterForm) {
      return;
    }
    filterForm.submit();
  }

  if (filterForm) {
    let debounceTimer = null;

    filterForm.querySelectorAll("[data-filter-search]").forEach((input) => {
      input.addEventListener("input", () => {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(submitFilterForm, DEBOUNCE_MS);
      });
    });

    filterForm.querySelectorAll("[data-filter-auto]").forEach((control) => {
      control.addEventListener("change", submitFilterForm);
    });
  }

  document.querySelectorAll("[data-sort-dir]").forEach((button) => {
    button.addEventListener("click", () => {
      const form = button.closest("form");
      if (!form) {
        return;
      }
      const input = form.querySelector('input[name="sort_dir"]');
      if (input) {
        input.value = button.dataset.sortDir;
      }
      form.submit();
    });
  });

  function openHelp() {
    if (helpDialog && typeof helpDialog.showModal === "function") {
      helpDialog.showModal();
    }
  }

  function closeHelp() {
    if (helpDialog && helpDialog.open) {
      helpDialog.close();
    }
  }

  document.querySelectorAll("[data-keyboard-help-open]").forEach((button) => {
    button.addEventListener("click", openHelp);
  });

  document.querySelectorAll("[data-keyboard-help-close]").forEach((button) => {
    button.addEventListener("click", closeHelp);
  });

  if (helpDialog) {
    helpDialog.addEventListener("click", (event) => {
      const rect = helpDialog.getBoundingClientRect();
      const inDialog =
        rect.top <= event.clientY &&
        event.clientY <= rect.top + rect.height &&
        rect.left <= event.clientX &&
        event.clientX <= rect.left + rect.width;
      if (!inDialog) {
        closeHelp();
      }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "?" && !event.ctrlKey && !event.metaKey && !event.altKey) {
      if (!isTyping()) {
        event.preventDefault();
        if (helpDialog && helpDialog.open) {
          closeHelp();
        } else {
          openHelp();
        }
      }
      return;
    }

    if (event.key === "Escape") {
      if (helpDialog && helpDialog.open) {
        event.preventDefault();
        closeHelp();
        return;
      }
      if (!isTyping() && filterForm && filterForm.dataset.clearUrl) {
        event.preventDefault();
        window.location.href = filterForm.dataset.clearUrl;
      }
      return;
    }

    if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey) {
      if (!isTyping()) {
        event.preventDefault();
        const titleSearch = document.getElementById("search-title");
        if (titleSearch) {
          titleSearch.focus();
          titleSearch.select();
        }
      }
      return;
    }

    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      if (blocksPageNavigation()) {
        return;
      }

      if (!pageNav()) {
        return;
      }

      event.preventDefault();
      navigatePage(event.key === "ArrowRight" ? "next" : "prev");
    }
  });

  document.addEventListener(
    "touchstart",
    (event) => {
      if (!pageNav() || (helpDialog && helpDialog.open)) {
        touchTracking = false;
        return;
      }
      if (event.touches.length !== 1) {
        touchTracking = false;
        return;
      }
      touchStartX = event.touches[0].clientX;
      touchStartY = event.touches[0].clientY;
      touchTracking = true;
    },
    { passive: true }
  );

  document.addEventListener(
    "touchend",
    (event) => {
      if (!touchTracking || !pageNav() || (helpDialog && helpDialog.open)) {
        return;
      }
      touchTracking = false;
      if (event.changedTouches.length !== 1) {
        return;
      }

      const touch = event.changedTouches[0];
      const deltaX = touch.clientX - touchStartX;
      const deltaY = touch.clientY - touchStartY;

      if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX) {
        return;
      }
      if (Math.abs(deltaY) > SWIPE_MAX_VERTICAL_PX) {
        return;
      }
      if (Math.abs(deltaX) <= Math.abs(deltaY)) {
        return;
      }

      navigatePage(deltaX < 0 ? "next" : "prev");
    },
    { passive: true }
  );
})();
