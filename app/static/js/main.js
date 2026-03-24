/**
 * Forge — shared client-side utilities.
 * Handles dashboard search filtering and Lucide icon initialization.
 */

document.addEventListener("DOMContentLoaded", () => {
  if (typeof lucide !== "undefined") {
    lucide.createIcons();
  }
  initSearch();
});

/* ── Dashboard Search ─────────────────────────────────────────────── */

function initSearch() {
  const input = document.getElementById("search-input");
  if (!input) return;

  const grid = document.getElementById("tool-grid");
  const countEl = document.getElementById("search-count");
  const emptyEl = document.getElementById("empty-state");
  const cards = Array.from(grid.querySelectorAll(".tool-card"));
  const total = cards.length;

  let debounceTimer = null;

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => filterCards(input.value), 200);
  });

  function filterCards(query) {
    const q = query.toLowerCase().trim();
    let visible = 0;

    cards.forEach(card => {
      const name = (card.dataset.name || "").toLowerCase();
      const tags = (card.dataset.tags || "").toLowerCase();
      const desc = (card.dataset.desc || "").toLowerCase();

      const match = !q || name.includes(q) || tags.includes(q) || desc.includes(q);
      card.style.display = match ? "" : "none";
      if (match) visible++;
    });

    if (countEl) {
      countEl.textContent = q
        ? `Showing ${visible} of ${total} tools`
        : `${total} tool${total !== 1 ? "s" : ""} available`;
    }

    if (emptyEl) {
      emptyEl.classList.toggle("visible", visible === 0 && q.length > 0);
    }
  }
}

/* ── SSE Terminal Helper (used by server-backed tools) ────────────── */

/**
 * Connect to an SSE endpoint and stream lines into a terminal element.
 * @param {string} url          - EventSource URL
 * @param {HTMLElement} termEl  - Container element with class "terminal-output"
 * @param {object} opts         - { onDone?: Function }
 */
function streamToTerminal(url, termEl, opts = {}) {
  termEl.textContent = "";
  const source = new EventSource(url);

  source.addEventListener("message", (e) => {
    const line = document.createElement("div");
    line.textContent = e.data;
    termEl.appendChild(line);
    termEl.scrollTop = termEl.scrollHeight;
  });

  source.addEventListener("error", () => {
    source.close();
    if (opts.onDone) opts.onDone();
  });

  source.addEventListener("done", () => {
    source.close();
    if (opts.onDone) opts.onDone();
  });

  return source;
}
