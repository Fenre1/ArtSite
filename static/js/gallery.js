(() => {
  const root = document.querySelector("[data-gallery-root]");

  if (!root) {
    return;
  }

  const cards = Array.from(root.querySelectorAll("[data-art-card]"));
  const buttons = Array.from(root.querySelectorAll("[data-filter-button]"));
  const emptyState = root.querySelector("[data-empty-state]");
  const state = {
    type: "all",
    price: "all"
  };

  const applyFilters = () => {
    let visibleCount = 0;

    cards.forEach((card) => {
      const matchesType = state.type === "all" || card.dataset.type === state.type;
      const matchesPrice = state.price === "all" || card.dataset.priceBand === state.price;
      const isVisible = matchesType && matchesPrice;

      card.hidden = !isVisible;

      if (isVisible) {
        visibleCount += 1;
      }
    });

    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const group = button.dataset.filterGroup;
      const value = button.dataset.filterValue;

      if (!group || !value) {
        return;
      }

      state[group] = value;

      buttons
        .filter((candidate) => candidate.dataset.filterGroup === group)
        .forEach((candidate) => {
          candidate.setAttribute("aria-pressed", String(candidate === button));
        });

      applyFilters();
    });
  });

  applyFilters();
})();
