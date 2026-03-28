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
  const minSlider = root.querySelector('[data-price-slider="min"]');
  const maxSlider = root.querySelector('[data-price-slider="max"]');
  const minOutput = root.querySelector('[data-price-output="min"]');
  const maxOutput = root.querySelector('[data-price-output="max"]');
  const hasPriceSliders = Boolean(minSlider && maxSlider);
  const slidersEnabled = hasPriceSliders && !minSlider.disabled && !maxSlider.disabled;

  const sliderMin = hasPriceSliders ? Number(minSlider.min) : 0;
  const sliderMax = hasPriceSliders ? Number(maxSlider.max) : 0;

  const state = {
    type: "all",
    sort: "newest",
    minPrice: hasPriceSliders ? Number(minSlider.value) : sliderMin,
    maxPrice: hasPriceSliders ? Number(maxSlider.value) : sliderMax
  };

  const formatPrice = (value) => {
    return `EUR ${Number(value).toLocaleString("nl-NL")}`;
  };

  const updatePriceOutputs = () => {
    if (minOutput) {
      minOutput.textContent = formatPrice(state.minPrice);
    }

    if (maxOutput) {
      maxOutput.textContent = formatPrice(state.maxPrice);
    }
  };

  const syncSliders = (changed) => {
    if (!hasPriceSliders) {
      return;
    }

    let minValue = Number(minSlider.value);
    let maxValue = Number(maxSlider.value);

    if (changed === "min" && minValue > maxValue) {
      maxValue = minValue;
      maxSlider.value = String(maxValue);
    }

    if (changed === "max" && maxValue < minValue) {
      minValue = maxValue;
      minSlider.value = String(minValue);
    }

    state.minPrice = minValue;
    state.maxPrice = maxValue;
    updatePriceOutputs();
  };

  const matchesPrice = (card) => {
    if (!slidersEnabled) {
      return true;
    }

    const rawPrice = card.dataset.price;
    const hasPrice = rawPrice !== "";

    if (!hasPrice) {
      return state.minPrice === sliderMin && state.maxPrice === sliderMax;
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

  if (hasPriceSliders) {
    syncSliders();

    minSlider.addEventListener("input", () => {
      syncSliders("min");
      applyFiltersAndSorting();
    });

    maxSlider.addEventListener("input", () => {
      syncSliders("max");
      applyFiltersAndSorting();
    });
  }

  updatePriceOutputs();
  applyFiltersAndSorting();
})();
