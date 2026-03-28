(() => {
  const root = document.querySelector("[data-gallery-root]");

  if (!root) {
    return;
  }

  const grid = root.querySelector("[data-gallery-grid]");
  const cards = Array.from(root.querySelectorAll("[data-art-card]"));
  const filterButtons = Array.from(root.querySelectorAll("[data-filter-button]"));
  const sortButtons = Array.from(root.querySelectorAll("[data-sort-button]"));
  const emptyState = root.querySelector("[data-empty-state]");
  const minInput = root.querySelector('[data-price-input="min"]');
  const maxInput = root.querySelector('[data-price-input="max"]');
  const hasPriceInputs = Boolean(minInput && maxInput);
  const inputsEnabled = hasPriceInputs && !minInput.disabled && !maxInput.disabled;

  const inputMin = hasPriceInputs ? Number(minInput.min) : 0;
  const inputMax = hasPriceInputs ? Number(maxInput.max) : 0;

  const state = {
    type: "all",
    sort: "newest",
    minPrice: hasPriceInputs ? Number(minInput.value) : inputMin,
    maxPrice: hasPriceInputs ? Number(maxInput.value) : inputMax
  };

  const clampPrice = (value) => {
    return Math.min(inputMax, Math.max(inputMin, value));
  };

  const readPriceInput = (input, fallback) => {
    if (!input) {
      return fallback;
    }

    const rawValue = input.value.trim();

    if (rawValue === "") {
      return fallback;
    }

    const parsedValue = Number(rawValue);
    return Number.isFinite(parsedValue) ? clampPrice(parsedValue) : fallback;
  };

  const syncPriceInputs = (changed) => {
    if (!hasPriceInputs) {
      return;
    }

    let minValue = readPriceInput(minInput, inputMin);
    let maxValue = readPriceInput(maxInput, inputMax);

    if (changed === "min" && minValue > maxValue) {
      maxValue = minValue;
    }

    if (changed === "max" && maxValue < minValue) {
      minValue = maxValue;
    }

    state.minPrice = minValue;
    state.maxPrice = maxValue;
    minInput.value = String(minValue);
    maxInput.value = String(maxValue);
  };

  const matchesPrice = (card) => {
    if (!inputsEnabled) {
      return true;
    }

    const rawPrice = card.dataset.price;
    const hasPrice = rawPrice !== "";

    if (!hasPrice) {
      return state.minPrice === inputMin && state.maxPrice === inputMax;
    }

    const price = Number(rawPrice);
    return price >= state.minPrice && price <= state.maxPrice;
  };

  const compareCards = (left, right) => {
    const leftDate = Number(left.dataset.dateAdded || 0);
    const rightDate = Number(right.dataset.dateAdded || 0);
    const leftOrder = Number(left.dataset.defaultOrder || 0);
    const rightOrder = Number(right.dataset.defaultOrder || 0);
    const leftHasPrice = left.dataset.price !== "";
    const rightHasPrice = right.dataset.price !== "";
    const leftPrice = leftHasPrice ? Number(left.dataset.price) : null;
    const rightPrice = rightHasPrice ? Number(right.dataset.price) : null;

    if (state.sort === "oldest") {
      return leftDate - rightDate || leftOrder - rightOrder;
    }

    if (state.sort === "price-asc") {
      if (leftHasPrice && rightHasPrice) {
        return leftPrice - rightPrice || rightDate - leftDate || leftOrder - rightOrder;
      }

      if (leftHasPrice) {
        return -1;
      }

      if (rightHasPrice) {
        return 1;
      }

      return rightDate - leftDate || leftOrder - rightOrder;
    }

    if (state.sort === "price-desc") {
      if (leftHasPrice && rightHasPrice) {
        return rightPrice - leftPrice || rightDate - leftDate || leftOrder - rightOrder;
      }

      if (leftHasPrice) {
        return -1;
      }

      if (rightHasPrice) {
        return 1;
      }

      return rightDate - leftDate || leftOrder - rightOrder;
    }

    return rightDate - leftDate || leftOrder - rightOrder;
  };

  const applyFiltersAndSorting = () => {
    let visibleCount = 0;

    cards
      .slice()
      .sort(compareCards)
      .forEach((card) => {
        const matchesType = state.type === "all" || card.dataset.type === state.type;
        const visible = matchesType && matchesPrice(card);

        card.hidden = !visible;
        grid.appendChild(card);

        if (visible) {
          visibleCount += 1;
        }
      });

    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const group = button.dataset.filterGroup;
      const value = button.dataset.filterValue;

      if (!group || !value) {
        return;
      }

      state[group] = value;

      filterButtons
        .filter((candidate) => candidate.dataset.filterGroup === group)
        .forEach((candidate) => {
          candidate.setAttribute("aria-pressed", String(candidate === button));
        });

      applyFiltersAndSorting();
    });
  });

  sortButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const value = button.dataset.filterValue;

      if (!value) {
        return;
      }

      state.sort = value;

      sortButtons.forEach((candidate) => {
        candidate.setAttribute("aria-pressed", String(candidate === button));
      });

      applyFiltersAndSorting();
    });
  });

  if (hasPriceInputs) {
    syncPriceInputs();

    const handlePriceTyping = (changed, input) => {
      if (!input || input.value.trim() === "") {
        return;
      }

      syncPriceInputs(changed);
      applyFiltersAndSorting();
    };

    const handlePriceCommit = (changed) => {
      syncPriceInputs(changed);
      applyFiltersAndSorting();
    };

    minInput.addEventListener("input", () => {
      handlePriceTyping("min", minInput);
    });

    maxInput.addEventListener("input", () => {
      handlePriceTyping("max", maxInput);
    });

    minInput.addEventListener("change", () => {
      handlePriceCommit("min");
    });

    maxInput.addEventListener("change", () => {
      handlePriceCommit("max");
    });
  }

  applyFiltersAndSorting();
})();