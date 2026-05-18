// Custom department dropdown to replace native HTML select
(function () {
  "use strict";

  function init() {
    console.log("department-select.js loaded");
    var select = document.getElementById("department");
    if (!select) return;

    // Departments array from FreeMarker (will be injected by template)
    var departments = window.departmentsData || [];

    // Create custom dropdown wrapper
    var wrapper = select.parentElement;
    if (!wrapper || !wrapper.classList.contains("department-picker-wrapper")) {
      return;
    }

    // Hide native select
    select.style.display = "none";

    // Create custom dropdown button
    var dropdownButton = document.createElement("button");
    dropdownButton.type = "button";
    dropdownButton.className = "department-select-custom";
    dropdownButton.setAttribute("role", "combobox");
    dropdownButton.setAttribute("tabindex", "0");
    dropdownButton.setAttribute("aria-haspopup", "listbox");
    dropdownButton.setAttribute("aria-expanded", "false");

    var selectedText = document.createElement("span");
    selectedText.className = "department-select-value";
    var currentValue =
      select.value || (departments.length > 0 ? departments[0].id : "");
    var currentOption = departments.find(function (d) {
      return d.id === currentValue;
    });
    selectedText.textContent = currentOption
      ? currentOption.title
      : "Select department...";

    // Create SVG in proper namespace (critical fix!)
    var SVG_NS = "http://www.w3.org/2000/svg";

    var chevronIcon = document.createElementNS(SVG_NS, "svg");
    chevronIcon.setAttribute("width", "16");
    chevronIcon.setAttribute("height", "16");
    chevronIcon.setAttribute("viewBox", "0 0 24 24");
    chevronIcon.setAttribute("fill", "none");
    chevronIcon.setAttribute("stroke", "white");
    chevronIcon.setAttribute("stroke-width", "2.5");
    chevronIcon.setAttribute("stroke-linecap", "round");
    chevronIcon.setAttribute("stroke-linejoin", "round");
    chevronIcon.classList.add("department-select-chevron");

    // Create path element in SVG namespace
    var path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", "m6 9 6 6 6-6");
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", "white");

    chevronIcon.appendChild(path);

    // Apply styles
    chevronIcon.style.width = "1rem";
    chevronIcon.style.height = "1rem";
    chevronIcon.style.opacity = "1"; /* Fully opaque chevron */
    chevronIcon.style.display = "block"; /* Ensure it's displayed */
    chevronIcon.style.visibility = "visible"; /* Force visibility */
    chevronIcon.style.zIndex = "20"; /* Ensure it's above shine effects */
    chevronIcon.style.position = "relative"; /* Ensure positioning context */
    chevronIcon.style.color = "white"; /* Ensure white color */
    chevronIcon.style.verticalAlign = "middle"; /* Center vertically */
    chevronIcon.style.minWidth = "1rem"; /* Ensure minimum width */
    chevronIcon.style.minHeight = "1rem"; /* Ensure minimum height */

    // Add liquid glass shine effects (matching Login.tsx)
    var shine1 = document.createElement("div");
    shine1.className = "department-select-shine-1";
    shine1.style.position = "absolute";
    shine1.style.inset = "0";
    shine1.style.background =
      "linear-gradient(135deg, rgba(255,255,255,0.2) 0%, transparent 45%)";
    shine1.style.pointerEvents = "none";
    shine1.style.borderRadius = "0.75rem";
    shine1.style.zIndex = "1";

    var shine2 = document.createElement("div");
    shine2.className = "department-select-shine-2";
    shine2.style.position = "absolute";
    shine2.style.top = "0";
    shine2.style.left = "0";
    shine2.style.width = "100%";
    shine2.style.height = "1px";
    shine2.style.background =
      "linear-gradient(to right, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)";
    shine2.style.pointerEvents = "none";
    shine2.style.zIndex = "1";

    dropdownButton.appendChild(shine1);
    dropdownButton.appendChild(shine2);
    dropdownButton.appendChild(selectedText);
    dropdownButton.appendChild(chevronIcon);

    // Create dropdown menu
    var dropdownMenu = document.createElement("div");
    dropdownMenu.className = "department-select-menu";
    dropdownMenu.setAttribute("role", "listbox");

    // Create checkmark icon SVG (for selected items)
    var SVG_NS = "http://www.w3.org/2000/svg";

    departments.forEach(function (dept) {
      var option = document.createElement("div");
      option.className = "department-select-option";
      option.setAttribute("role", "option");
      option.setAttribute("data-value", dept.id);

      // Create text span
      var optionText = document.createElement("span");
      optionText.className = "department-select-option-text";
      optionText.textContent = dept.title;
      option.appendChild(optionText);

      // Create checkmark icon container (positioned absolutely on the right)
      var checkmarkContainer = document.createElement("span");
      checkmarkContainer.className = "department-select-checkmark";
      checkmarkContainer.style.position = "absolute";
      checkmarkContainer.style.right = "0.875rem";
      checkmarkContainer.style.display = "flex";
      checkmarkContainer.style.alignItems = "center";
      checkmarkContainer.style.justifyContent = "center";
      checkmarkContainer.style.width = "0.875rem";
      checkmarkContainer.style.height = "0.875rem";

      // Create checkmark SVG icon
      var checkmarkSvg = document.createElementNS(SVG_NS, "svg");
      checkmarkSvg.setAttribute("width", "16");
      checkmarkSvg.setAttribute("height", "16");
      checkmarkSvg.setAttribute("viewBox", "0 0 24 24");
      checkmarkSvg.setAttribute("fill", "none");
      checkmarkSvg.setAttribute("stroke", "white");
      checkmarkSvg.setAttribute("stroke-width", "3");
      checkmarkSvg.setAttribute("stroke-linecap", "round");
      checkmarkSvg.setAttribute("stroke-linejoin", "round");
      checkmarkSvg.style.width = "1rem";
      checkmarkSvg.style.height = "1rem";
      checkmarkSvg.style.display = "none"; // Hidden by default, shown for selected

      var checkmarkPath = document.createElementNS(SVG_NS, "path");
      checkmarkPath.setAttribute("d", "M20 6L9 17l-5-5");
      checkmarkSvg.appendChild(checkmarkPath);
      checkmarkContainer.appendChild(checkmarkSvg);
      option.appendChild(checkmarkContainer);

      if (dept.id === currentValue) {
        option.classList.add("selected");
        checkmarkSvg.style.display = "block"; // Show checkmark for selected item
      }

      dropdownMenu.appendChild(option);
    });

    wrapper.appendChild(dropdownButton);
    wrapper.appendChild(dropdownMenu);

    var isOpen = false;
    var isInternalUpdate = false; // Guard flag to prevent feedback loop

    function updateSelected(value) {
      var option = departments.find(function (d) {
        return d.id === value;
      });
      if (!option) return;

      // IMPORTANT: update currentValue so comparisons work
      currentValue = value;

      selectedText.textContent = option.title;

      isInternalUpdate = true;
      select.value = value;
      isInternalUpdate = false;

      // Update selected state in menu
      var options = dropdownMenu.querySelectorAll(".department-select-option");
      options.forEach(function (opt) {
        opt.classList.remove("selected");
        var checkmark = opt.querySelector(".department-select-checkmark svg");
        if (checkmark) {
          checkmark.style.display = "none"; // Hide checkmark
        }
        if (opt.getAttribute("data-value") === value) {
          opt.classList.add("selected");
          if (checkmark) {
            checkmark.style.display = "block"; // Show checkmark for selected
          }
        }
      });

      // Update URL and filter providers (shallow refresh - replaceState, no reload)
      applyDept(value);

      // Don't dispatch change event - custom UI is source of truth
      // If external code needs to listen, they can watch the select.value directly
    }

    function toggleDropdown() {
      isOpen = !isOpen;
      dropdownButton.setAttribute("aria-expanded", isOpen.toString());
      dropdownButton.classList.toggle("open", isOpen);
      dropdownMenu.classList.toggle("open", isOpen);
    }

    function closeDropdown() {
      if (isOpen) {
        isOpen = false;
        dropdownButton.setAttribute("aria-expanded", "false");
        dropdownButton.classList.remove("open");
        dropdownMenu.classList.remove("open");
      }
    }

    // Button click handler
    dropdownButton.addEventListener("click", function (e) {
      e.stopPropagation();
      toggleDropdown();
    });

    // Keyboard support
    dropdownButton.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleDropdown();
      } else if (e.key === "Escape") {
        closeDropdown();
      }
    });

    // Option click handler
    dropdownMenu.addEventListener("click", function (e) {
      var option = e.target.closest(".department-select-option");
      if (!option) return;

      var value = option.getAttribute("data-value");

      // Close first to start animation immediately
      closeDropdown();

      // Then do heavy DOM updates in next frame
      requestAnimationFrame(function () {
        updateSelected(value);
      });
    });

    // Close on outside click
    document.addEventListener("click", function (e) {
      if (!wrapper.contains(e.target)) {
        closeDropdown();
      }
    });

    // Listen to native select changes (from other code or programmatic changes)
    select.addEventListener("change", function () {
      // Skip if this change was triggered internally
      if (isInternalUpdate) return;

      // Only update if value actually changed to avoid loops
      var newValue = select.value;
      if (newValue !== currentValue) {
        updateSelected(newValue);
      }
    });

    // Apply department filter logic (from existing code)
    function applyDept(dept) {
      // Update URL without reload - use replaceState for shallow refresh (no history entry)
      var url = new URL(window.location.href);
      if (dept) {
        url.searchParams.set("department", dept);
      } else {
        url.searchParams.delete("department");
      }
      // Use replaceState instead of pushState to replace current history entry (shallow refresh)
      window.history.replaceState({}, "", url.toString());

      // Filter provider buttons in DOM
      var allowedProvidersByDept = window.allowedProvidersByDept || {};
      var platformProviders = window.platformProviders || [];

      var allowed =
        dept &&
        allowedProvidersByDept[dept] &&
        allowedProvidersByDept[dept].length
          ? allowedProvidersByDept[dept]
          : platformProviders;

      // Filter action buttons (provider buttons) - show/hide based on department selection
      var actionButtons = document.querySelectorAll(
        ".action-button[id^='social-']"
      );
      var visibleNonGuestCount = 0;
      var visibleGuestCount = 0;

      actionButtons.forEach(function (btn) {
        var alias = btn.id.replace("social-", "");
        var show = allowed.indexOf(alias) !== -1;
        btn.style.display = show ? "" : "none";

        // Count visible providers for OR divider
        if (show) {
          if (alias.startsWith("default-idp-guest-")) {
            visibleGuestCount++;
          } else {
            visibleNonGuestCount++;
          }
        }
      });

      // Update OR divider visibility based on actual visible providers
      var orDivider = document.querySelector(".or-divider");
      if (orDivider) {
        if (visibleNonGuestCount > 0 && visibleGuestCount > 0) {
          orDivider.style.display = "";
        } else {
          orDivider.style.display = "none";
        }
      }
    }

    // Apply initial state
    var initial = select.value || "";
    if (!initial) {
      var urlParams = new URLSearchParams(window.location.search);
      initial = urlParams.get("department") || "";
    }
    if (!initial && departments.length > 0) {
      initial = departments[0].id;
      // Update URL to reflect first department if none selected
      var url = new URL(window.location.href);
      url.searchParams.set("department", initial);
      window.history.replaceState({}, "", url.toString());
    }
    if (select.value !== initial) {
      select.value = initial;
      updateSelected(initial);
    } else if (initial) {
      // Even if select already has the value, ensure URL and filters are applied
      applyDept(initial);
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
