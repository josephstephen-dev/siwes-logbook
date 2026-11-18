if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
let deferred;
window.addEventListener("beforeinstallprompt", e => {
  e.preventDefault(); deferred = e;
  document.querySelectorAll(".install-app").forEach(b => (b.hidden = false));
});
document.addEventListener("click", e => {
  const b = e.target.closest(".install-app");
  if (b && deferred) { deferred.prompt(); deferred = null; b.hidden = true; }
});