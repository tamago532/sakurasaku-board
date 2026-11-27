(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  let mx = innerWidth / 2, my = innerHeight / 2;

  const dot = $(".cursor"), ring = $(".cursor-ring");
  let rx = mx, ry = my;
  addEventListener("pointermove", (e) => {
    mx = e.clientX;
    my = e.clientY;
    dot.style.transform = `translate(${mx}px, ${my}px)`;
  });
  const follow = () => {
    rx += (mx - rx) * .14;
    ry += (my - ry) * .14;
    ring.style.transform = `translate(${rx}px, ${ry}px)`;
    requestAnimationFrame(follow);
  };
  follow();
  $$("a, button, summary, select, input[type=checkbox], input[type=file]").forEach((el) => {
    el.addEventListener("pointerenter", () => ring.classList.add("hover"));
    el.addEventListener("pointerleave", () => ring.classList.remove("hover"));
  });

  const doc = $(".doc-card");
  if (doc) {
    addEventListener("pointermove", (e) => {
      const px = e.clientX / innerWidth - .5, py = e.clientY / innerHeight - .5;
      doc.style.setProperty("--ry", `${px * 16}deg`);
      doc.style.setProperty("--rx", `${-py * 12}deg`);
    });
  }

  $$(".spot, .cta").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    });
  });

  $$(".magnetic").forEach((el) => {
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left - r.width / 2, y = e.clientY - r.top - r.height / 2;
      el.style.transform = `translate(${x * .2}px, ${y * .3}px)`;
    });
    el.addEventListener("pointerleave", () => { el.style.transform = ""; });
  });

  const heroBg = $(".hero-bg"), heroInner = $(".hero-inner"), footer = $(".footer-big");
  const onScroll = () => {
    const y = scrollY;
    if (heroBg) heroBg.style.transform = `translateY(${y * .35}px)`;
    if (heroInner) {
      heroInner.style.transform = `translateY(${y * .15}px)`;
      heroInner.style.opacity = Math.max(0, 1 - y / 700);
    }
    if (footer) {
      const start = footer.getBoundingClientRect().top + y - innerHeight;
      const end = document.documentElement.scrollHeight - innerHeight;
      const k = end - start <= 1 ? 1 : Math.max(0, Math.min(1, (y - start) / (end - start)));
      footer.style.setProperty("--fill", `${k * 100}%`);
    }
  };
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", onScroll);
  addEventListener("load", onScroll);
  onScroll();

  const countUp = (el, delay) => {
    const target = +el.dataset.count;
    const pad = el.dataset.pad ? +el.dataset.pad : 0;
    const start = performance.now() + delay, dur = 1800;
    const fmt = (n) => String(n).padStart(pad, "0");
    el.textContent = fmt(0);
    const step = (t) => {
      const k = Math.max(0, Math.min(1, (t - start) / dur));
      el.textContent = fmt(Math.round(target * (1 - Math.pow(1 - k, 4))));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const cd = $(".countdown");
  if (cd) {
    const target = Date.parse(cd.dataset.target);
    const seg = (u) => $(`[data-unit="${u}"]`, cd);
    const d = seg("d"), h = seg("h"), m = seg("m"), s = seg("s");
    const pad = (n, w) => String(n).padStart(w, "0");
    const tickCd = () => {
      const left = Math.max(0, target - Date.now());
      const days = Math.floor(left / 86400000);
      const hours = Math.floor(left / 3600000) % 24;
      const mins = Math.floor(left / 60000) % 60;
      const secs = Math.floor((left % 60000) / 10) / 100;
      d.textContent = pad(days, 3);
      h.textContent = pad(hours, 2);
      m.textContent = pad(mins, 2);
      s.textContent = secs.toFixed(2).padStart(5, "0");
      if (left > 0) requestAnimationFrame(tickCd);
    };
    tickCd();
  }

  const glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-";
  const scramble = (el) => {
    const final = el.dataset.text || el.textContent;
    el.dataset.text = final;
    let frame = 0;
    const run = () => {
      el.textContent = [...final].map((ch, i) =>
        ch === " " || i < frame / 2 ? ch : glyphs[(Math.random() * glyphs.length) | 0]).join("");
      if (frame++ < final.length * 2) requestAnimationFrame(run);
      else el.textContent = final;
    };
    run();
  };

  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      if (e.target.classList.contains("scramble")) scramble(e.target);
      $$("[data-count]", e.target).forEach((n) => countUp(n, 200));
      io.unobserve(e.target);
    });
  }, { threshold: .12 });
  let i = 0;
  $$(".reveal, .scramble").forEach((el) => {
    if (el.classList.contains("reveal")) el.style.transitionDelay = `${(i++ % 4) * 80}ms`;
    io.observe(el);
  });

  const plusOne = (x, y) => {
    const p = document.createElement("span");
    p.className = "plus";
    p.textContent = "+1";
    p.style.left = x + "px";
    p.style.top = y + "px";
    document.body.appendChild(p);
    setTimeout(() => p.remove(), 1000);
  };
  const ripple = (x, y) => {
    const r = document.createElement("span");
    r.className = "ripple";
    r.style.left = x + "px";
    r.style.top = y + "px";
    document.body.appendChild(r);
    setTimeout(() => r.remove(), 800);
  };

  $$(".empathy-form").forEach((form) => {
    form.addEventListener("submit", (e) => {
      const btn = $("button", form);
      if (btn.disabled) return;
      e.preventDefault();
      const r = btn.getBoundingClientRect();
      plusOne(r.left + r.width / 2, r.top);
      ripple(r.left + r.width / 2, r.top + r.height / 2);
      btn.disabled = true;
      setTimeout(() => form.submit(), 600);
    });
  });

  addEventListener("pointerdown", (e) => ripple(e.clientX, e.clientY));
  addEventListener("dragstart", (e) => {
    if (!e.target.closest || !e.target.closest("input, textarea")) e.preventDefault();
  });

  const wipe = $(".wipe");
  wipe.classList.add("out");
  $$("a[href^='/']").forEach((a) => {
    a.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      wipe.classList.remove("out");
      wipe.classList.add("on");
      setTimeout(() => { location.href = a.href; }, 480);
    });
  });
  addEventListener("pageshow", (e) => {
    if (e.persisted) { wipe.classList.remove("on"); wipe.classList.add("out"); }
  });
})();
