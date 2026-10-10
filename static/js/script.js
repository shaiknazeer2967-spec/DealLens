document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("primary-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    // Close the mobile menu after a navigation link is used.
    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  document.querySelectorAll("textarea").forEach(function (el) {
    el.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = this.scrollHeight + "px";
    });
  });

  var form = document.querySelector("form[data-analyze]");
  if (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector("button[type='submit']");
      if (button) {
        button.disabled = true;
        button.classList.add("is-loading");
      }
    });
  }

  var historySearch = document.getElementById("history-search");
  var historyFilter = document.getElementById("history-filter");
  function filterHistory() {
    var query = (historySearch && historySearch.value || "").toLowerCase();
    var outcome = historyFilter && historyFilter.value || "";
    document.querySelectorAll("[data-history-row]").forEach(function (row) {
      var matchesText = !query || (row.dataset.search || "").toLowerCase().indexOf(query) !== -1;
      var matchesOutcome = !outcome || row.dataset.outcome === outcome;
      row.hidden = !(matchesText && matchesOutcome);
    });
  }
  if (historySearch) historySearch.addEventListener("input", filterHistory);
  if (historyFilter) historyFilter.addEventListener("change", filterHistory);
});
