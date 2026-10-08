// FiboTask Pro — theme, toasts, confirmations, fib helpers. No deps.
(function () {
  const root = document.documentElement;
  try {
    const saved = localStorage.getItem("fibotask-theme");
    if (saved) root.dataset.theme = saved;
    else if (matchMedia("(prefers-color-scheme: dark)").matches) root.dataset.theme = "dark";
  } catch (e) {}
  document.getElementById("themeToggle")?.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("fibotask-theme", root.dataset.theme); } catch (e) {}
  });

  // toasts
  document.querySelectorAll(".toast").forEach((t) => {
    const kill = () => { t.classList.add("hide"); setTimeout(() => t.remove(), 320); };
    t.querySelector(".toast-x")?.addEventListener("click", kill);
    setTimeout(kill, 4200);
  });

  // confirm popup for destructive actions (delete, clear completed)
  const veil = document.getElementById("confirmVeil");
  const cTitle = document.getElementById("confirmTitle");
  const cMsg = document.getElementById("confirmMsg");
  const cGo = document.getElementById("confirmGo");
  const cCancel = document.getElementById("confirmCancel");
  let pendingForm = null, lastFocus = null;
  const closeModal = () => {
    if (!veil) return;
    veil.hidden = true;
    document.body.classList.remove("no-scroll");
    pendingForm = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  };
  if (veil && cGo) {
    document.querySelectorAll("form.js-confirm").forEach((f) => {
      f.addEventListener("submit", (e) => {
        if (f.dataset.confirmed === "1") { delete f.dataset.confirmed; return; }
        e.preventDefault();
        pendingForm = f;
        lastFocus = document.activeElement;
        if (cTitle) cTitle.textContent = f.dataset.confirmTitle || "Are you sure?";
        if (cMsg) cMsg.textContent = f.dataset.confirm || "This cannot be undone.";
        cGo.textContent = f.dataset.confirmGo || "Confirm";
        veil.hidden = false;
        document.body.classList.add("no-scroll");
        cGo.focus();
      });
    });
    cCancel?.addEventListener("click", closeModal);
    cGo.addEventListener("click", () => {
      const f = pendingForm;
      veil.hidden = true;
      document.body.classList.remove("no-scroll");
      pendingForm = null;
      if (f) { f.dataset.confirmed = "1"; f.requestSubmit(); }
    });
    veil.addEventListener("click", (e) => { if (e.target === veil) closeModal(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !veil.hidden) closeModal(); });
  }

  // char counter
  const title = document.getElementById("id_title");
  const counter = document.getElementById("charCount");
  if (title && counter) {
    const upd = () => { counter.textContent = `${title.value.length}/255`; };
    title.addEventListener("input", upd); upd();
  }

  // fibonacci: slider <-> number sync
  const nInput = document.getElementById("id_n");
  const nRange = document.getElementById("nRange");
  if (nInput && nRange) {
    const max = parseInt(nRange.max || "1000", 10);
    nRange.addEventListener("input", () => { nInput.value = nRange.value; });
    nInput.addEventListener("input", () => {
      const v = parseInt(nInput.value || "0", 10);
      if (v >= 1 && v <= max) nRange.value = String(v);
    });
  }

  // copy + downloads
  const seriesEl = document.getElementById("seriesText");
  document.getElementById("copyBtn")?.addEventListener("click", async (e) => {
    const txt = seriesEl?.dataset.raw || seriesEl?.textContent || "";
    try { await navigator.clipboard.writeText(txt); e.target.textContent = "Copied ✓"; }
    catch { e.target.textContent = "Copy failed"; }
    setTimeout(() => { e.target.textContent = "Copy"; }, 1600);
  });
  const dl = (name, text, type) => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  };
  document.getElementById("csvBtn")?.addEventListener("click", () => {
    const raw = seriesEl?.dataset.raw || "";
    dl("fibonacci.csv", "index,value\n" + raw.split(",").map((v, i) => `${i},${v.trim()}`).join("\n"), "text/csv");
  });
  document.getElementById("jsonBtn")?.addEventListener("click", () => {
    const raw = seriesEl?.dataset.raw || "";
    dl("fibonacci.json", JSON.stringify(raw.split(",").map((v) => Number(v.trim())), null, 2), "application/json");
  });
  // reveal on scroll (landing + cards)
  try {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }),
      { threshold: 0.12 }
    );
    document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
  } catch (e) {
    document.querySelectorAll(".reveal").forEach((el) => el.classList.add("in"));
  }

  // landing story loop: size -> split -> start (12s cycle)
  const stage = document.getElementById("storyStage");
  if (stage && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const chips = Array.from(stage.querySelectorAll(".pts-row i"));
    const ring = document.getElementById("storyRing");
    const sclock = document.getElementById("storyClock");
    const done = document.getElementById("storyDone");
    const dots = Array.from(stage.querySelectorAll(".story-dots i"));
    const CIRC = 326.7, ACT = 4000, ACTS = 4;
    let act = 1, raf = null;
    const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    const setAct = (n) => {
      act = n;
      stage.dataset.act = String(n);
      dots.forEach((d, i) => d.classList.toggle("on", i === n - 1));
      // restart CSS slam/pop animations by re-cloning? transitions handle acts; keyframed
      // children re-run because [data-act] selector re-applies `backwards` animations:
      stage.querySelectorAll(".act").forEach((a) => { a.style.animation = "none"; void a.offsetWidth; a.style.animation = ""; });
    };
    const tick = () => {
      const t = (Date.now() % (ACT * ACTS)) / ACT; // 0..ACTS
      const n = Math.floor(t) + 1;
      if (n !== act) {
        setAct(n);
        if (done) done.classList.remove("show");
      }
      if (act === 2) {
        // chips light up one by one, landing on 13
        const idx = Math.min(chips.length - 1, Math.floor((t - Math.floor(t)) * 7));
        chips.forEach((c, i) => c.classList.toggle("hot", i <= idx));
      } else if (act === 4) {
        const p = t - Math.floor(t); // 0..1 across act 3
        const left = Math.ceil(780 * (1 - p));
        if (sclock) sclock.textContent = fmt(Math.max(left, 0));
        if (ring) ring.style.strokeDashoffset = String(CIRC * (1 - p));
        if (p > 0.86 && done && !done.classList.contains("show")) done.classList.add("show");
      }
      raf = requestAnimationFrame(tick);
    };
    // pause when tab hidden or stage off-screen (perf + honesty)
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && raf === null) { tick(); }
      else if (!e.isIntersecting && raf !== null) { cancelAnimationFrame(raf); raf = null; }
    });
    io.observe(stage);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && raf !== null) { cancelAnimationFrame(raf); raf = null; }
      else if (!document.hidden && raf === null) tick();
    });
    tick();
  }

  // focus timer
  const clock = document.getElementById("focusClock");
  if (clock) {
    const total = parseInt(clock.dataset.seconds || "780", 10);
    let left = total, timer = null;
    const bar = document.getElementById("focusBar");
    const startB = document.getElementById("focusStart");
    const pauseB = document.getElementById("focusPause");
    const resetB = document.getElementById("focusReset");
    const logB = document.getElementById("focusLogBtn");
    const logM = document.getElementById("focusLogMinutes");
    const msg = document.getElementById("focusMsg");
    const presetMin = total / 60;
    const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
    const paint = () => {
      clock.textContent = fmt(left);
      if (bar) bar.style.width = `${Math.round((1 - left / total) * 100)}%`;
      document.title = left > 0 && timer ? `${fmt(left)} · Focusing` : "Focus · FiboTask";
      const elapsedMin = Math.floor((total - left) / 60);
      if (elapsedMin >= 1 && logB && logB.disabled) {
        logB.disabled = false;
        if (logM) logM.value = String(elapsedMin);
        logB.textContent = `Log ${elapsedMin} min`;
      } else if (elapsedMin >= 1 && logM && !timer) {
        logM.value = String(elapsedMin);
        if (logB) logB.textContent = `Log ${elapsedMin} min`;
      }
    };
    const stop = () => { clearInterval(timer); timer = null; startB.disabled = false; pauseB.disabled = true; paint(); };
    startB?.addEventListener("click", () => {
      if (timer || left <= 0) return;
      startB.disabled = true; pauseB.disabled = false;
      timer = setInterval(() => {
        left -= 1; paint();
        if (left <= 0) {
          stop(); clock.classList.add("done");
          if (logB) logB.disabled = false;
          if (msg) msg.textContent = "Time! Log it, then take the suggested break.";
        }
      }, 1000);
      paint();
    });
    pauseB?.addEventListener("click", stop);
    resetB?.addEventListener("click", () => {
      stop(); left = total; clock.classList.remove("done"); paint();
    });
    paint();
  }
})();
