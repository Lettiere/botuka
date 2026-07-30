(function () {
  "use strict";
  const category = document.getElementById("categoria");
  const family = document.getElementById("familia");
  const type = document.getElementById("tipo");
  const segment = document.getElementById("segmento");
  if (!category || !family || !type || !segment) return;
  const filter = (select, attribute, value) => {
    [...select.options].forEach((option, index) => {
      if (!index) return;
      const relation = option.dataset[attribute] || "";
      option.hidden = Boolean(value) && !(attribute === "types" ? relation.split(" ").includes(value) : relation === value);
      if (option.hidden && option.selected) select.value = "";
    });
  };
  category.addEventListener("change", () => {
    filter(family, "category", category.value);
    filter(type, "family", ""); filter(segment, "types", "");
    type.value = ""; segment.value = "";
  });
  family.addEventListener("change", () => {
    filter(type, "family", family.value); type.value = ""; segment.value = "";
  });
  type.addEventListener("change", () => filter(segment, "types", type.value));
  filter(family, "category", category.value);
  filter(type, "family", family.value);
  filter(segment, "types", type.value);
})();
