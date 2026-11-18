(function () {
  const banner = document.getElementById("offline-banner");
  const dot = document.getElementById("net-state");
  const retry = document.getElementById("banner-retry");
  function show(on) {
    if (banner) banner.hidden = on;
    if (dot) {
      dot.classList.toggle("on", on);
      dot.title = on ? "Online" : "Offline";
      dot.setAttribute("aria-label", "Connection status: " + (on ? "online" : "offline"));
    }
    document.dispatchEvent(new CustomEvent("siwes:net", { detail: { online: on } }));
  }
  window.addEventListener("online", () => show(true));
  window.addEventListener("offline", () => show(false));
  if (retry) retry.addEventListener("click", async () => {
    try { await fetch("/healthz", { cache: "no-store" }); show(true); } catch (e) { show(false); }
  });
  show(navigator.onLine);
})();