// Generate animated sparkles for Keycloak login page
(function () {
  var container = document.getElementById("sparkles-container");
  if (!container) return;

  // Generate 80 static sparkles
  for (var i = 0; i < 80; i++) {
    var sparkle = document.createElement("div");
    sparkle.className = "sparkle sparkle-static";
    sparkle.style.left = Math.random() * 100 + "%";
    sparkle.style.top = Math.random() * 100 + "%";
    sparkle.style.animationDelay = Math.random() * 3 + "s";
    sparkle.style.animationDuration = Math.random() * 3 + 2 + "s";
    sparkle.innerHTML =
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0L14.59 8.41L23 11L14.59 13.59L12 22L9.41 13.59L1 11L9.41 8.41L12 0Z"/></svg>';
    container.appendChild(sparkle);
  }

  // Generate 12 moving sparkles
  for (var i = 0; i < 12; i++) {
    var sparkle = document.createElement("div");
    sparkle.className = "sparkle sparkle-moving";
    sparkle.style.left = Math.random() * 100 + "%";
    sparkle.style.top = Math.random() * 100 + "%";
    sparkle.style.animationDelay = Math.random() * 2 + "s";
    sparkle.style.animationDuration = Math.random() * 2 + 3 + "s";
    sparkle.innerHTML =
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0L14.59 8.41L23 11L14.59 13.59L12 22L9.41 13.59L1 11L9.41 8.41L12 0Z"/></svg>';
    container.appendChild(sparkle);
  }

  // Generate 10 floating sparkles
  for (var i = 0; i < 10; i++) {
    var sparkle = document.createElement("div");
    sparkle.className = "sparkle sparkle-floating";
    sparkle.style.left = Math.random() * 100 + "%";
    sparkle.style.top = Math.random() * 100 + "%";
    sparkle.style.animationDelay = Math.random() * 4 + "s";
    sparkle.style.animationDuration = Math.random() * 3 + 4 + "s";
    sparkle.innerHTML =
      '<svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0L14.59 8.41L23 11L14.59 13.59L12 22L9.41 13.59L1 11L9.41 8.41L12 0Z"/></svg>';
    container.appendChild(sparkle);
  }
})();
