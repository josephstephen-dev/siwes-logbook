document.querySelectorAll("[data-toggle=password]").forEach(btn => {
  btn.addEventListener("click", () => {
    const input = btn.parentElement.querySelector("input");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Hide" : "Show";
  });
});

// Strength meter and live rules list (setup and reset pages)
(function () {
  const input = document.getElementById("password");
  const list = document.getElementById("rules");
  if (!input || !list) return;
  const bar = document.getElementById("strength-bar");
  const label = document.getElementById("strength-label");
  const rules = {
    len: v => v.length >= 10,
    letter: v => /[A-Za-z]/.test(v),
    num: v => /\d/.test(v),
  };
  input.addEventListener("input", () => {
    const v = input.value;
    let score = 0;
    list.querySelectorAll("li").forEach(li => {
      const ok = rules[li.dataset.rule](v);
      li.classList.toggle("ok", ok);
      if (ok) score++;
    });
    if (v.length >= 14) score++;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
    if (/[^A-Za-z0-9]/.test(v)) score++;
    const names = ["–", "Weak", "Weak", "Fair", "Good", "Strong", "Strong"];
    bar.style.width = (v ? Math.min(score, 6) / 6 * 100 : 0) + "%";
    label.textContent = "Strength: " + (v ? names[Math.min(score, 6)] : "–");
  });
})();