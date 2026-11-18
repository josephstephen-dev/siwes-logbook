(function () {
  // Once an entry is recorded, its saved draft on this device is no longer needed.
  document.querySelectorAll("[data-clear-draft]").forEach(el => {
    el.dataset.clearDraft.split(" ").forEach(k => { try { localStorage.removeItem(k); } catch (e) {} });
  });

  const ta = document.getElementById("entry-body");
  if (!ta) return;
  const key = ta.dataset.draftKey, min = +ta.dataset.min, max = +ta.dataset.max;
  const counter = document.getElementById("counter"), state = document.getElementById("save-state");
  const open = document.getElementById("open-confirm"), dlg = document.getElementById("confirm-dialog");
  const form = document.getElementById("entry-form"), hint = document.getElementById("min-hint");
  const submitBtn = document.getElementById("confirm-submit");
  const failBox = document.getElementById("submit-failed"), retryBtn = document.getElementById("retry-submit");
  const label = open.textContent;
  let pending = false, sending = false;

  try {
    const saved = localStorage.getItem(key);
    if (saved && !ta.value.trim()) { ta.value = saved; state.textContent = "Draft restored from this device"; }
  } catch (e) {}

  function update() {
    const n = ta.value.trim().length;
    counter.textContent = n + " / " + max;
    open.disabled = sending || n < min || n > max;
    hint.style.color = n > 0 && n < min ? "var(--warn-ink)" : "";
  }
  update();

  let timer;
  ta.addEventListener("input", () => {
    update();
    clearTimeout(timer);
    timer = setTimeout(() => {
      try { localStorage.setItem(key, ta.value); state.textContent = "Saved on this device"; }
      catch (e) { state.textContent = "Couldn't save on this device"; }
    }, 500);
  });

  open.addEventListener("click", () => dlg.showModal());
  document.getElementById("cancel-confirm").addEventListener("click", () => dlg.close());
  form.addEventListener("submit", e => { e.preventDefault(); if (dlg.open) dlg.close(); send(); });
  if (retryBtn) retryBtn.addEventListener("click", send);
  document.addEventListener("siwes:net", ev => { if (ev.detail.online && pending) send(); });

  async function send() {
    if (sending) return;
    sending = true; pending = false;
    if (failBox) failBox.hidden = true;
    submitBtn.disabled = true; open.disabled = true; open.textContent = "Saving…";
    try {
      const res = await fetch(form.getAttribute("action") || location.href,
        { method: "POST", body: new FormData(form), credentials: "same-origin" });
      if (res.ok && res.redirected) { location.href = res.url; return; }
      state.textContent = "This page expired. Reloading; your text is kept.";
      setTimeout(() => location.reload(), 900);
    } catch (err) {
      pending = true;                       // network failure: keep the text, offer a retry
      if (failBox) failBox.hidden = false;
      state.textContent = "Not sent. Kept on this device.";
    } finally {
      sending = false; submitBtn.disabled = false; open.textContent = label; update();
    }
  }
})();