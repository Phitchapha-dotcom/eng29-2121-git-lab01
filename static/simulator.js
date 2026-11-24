/* Progressive enhancement for the Lab 04 simulator form.
   Without JavaScript every group stays visible; nothing is disabled or lost. */
(function () {
  "use strict";

  var form = document.getElementById("sim-form");
  if (!form) {
    return;
  }

  var groups = Array.prototype.slice.call(
    form.querySelectorAll("[data-sim-group]")
  );
  var radios = Array.prototype.slice.call(
    form.querySelectorAll('input[name="mode"]')
  );
  var button = form.querySelector('button[type="submit"]');
  var labels = { dc: "DC", ac: "AC", tran: "Transient" };

  function apply() {
    var checked = form.querySelector('input[name="mode"]:checked');
    var mode = checked ? checked.value : "dc";
    groups.forEach(function (group) {
      var scope = group.getAttribute("data-sim-scope");
      group.hidden = !(scope === "all" || scope === mode);
    });
    if (button) {
      button.textContent = "Run " + (labels[mode] || mode) + " ด้วย ngspice";
    }
  }

  radios.forEach(function (radio) {
    radio.addEventListener("change", apply);
  });
  apply();
})();
