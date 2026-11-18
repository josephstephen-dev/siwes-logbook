document.addEventListener("click", e => {
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  const input = document.getElementById(btn.dataset.copy);
  input.select();
  const done = () => {
    const old = btn.textContent;
    btn.textContent = "Copied";
    setTimeout(() => (btn.textContent = old), 1500);
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(input.value).then(done, () => { document.execCommand("copy"); done(); });
  } else {
    document.execCommand("copy");
    done();
  }
});