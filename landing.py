"""
The landing page visitors see before they sign in.

A dark wine hero with a live Three.js "routing field" (prompts flowing into
a router and splitting across three model lanes), animated counters for the
real savings so far, cards that reveal as you scroll, and brass buttons.

Everything degrades gracefully: with JavaScript off, or if Three.js can't
load, the page still shows all its content with a static background.
"""

import html

import streamlit as st

from registry import MODEL_REGISTRY
from router import ROUTING
from theme import BASE_CSS, BRASS, IVORY, logo_img, tier_meter

PROVIDER_NAMES = {"groq": "Groq", "gemini": "Google"}
TIER_EXAMPLES = {
    1: "Reformatting, extraction, lookups in provided text",
    2: "Summaries, classification, structured analysis",
    3: "Multi-step reasoning, comparisons, creative writing",
}


def _price(value: float) -> str:
    """0.075 -> "0.075", 0.3 -> "0.30", 2.5 -> "2.50"."""
    text = f"{value:.3f}"
    return text[:-1] if text.endswith("0") else text


LANE_COSTS = {1: "about $0.00004 a request", 2: "about $0.00007 a request", 3: "about $0.0018 a request"}

# Streamlit removes any style block containing a "<" character, so none appear in this CSS.
LANDING_CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding-top: 1.25rem; padding-bottom: 2rem; }
[data-testid="stHeader"] { display: none; }

/* ---- Hero ---- */
.st-key-hero { position: relative; overflow: hidden; border-radius: 24px; padding: 26px 40px 0;
  background: radial-gradient(70% 90% at 88% -10%, rgba(123, 30, 52, 0.75), rgba(123, 30, 52, 0) 62%),
              radial-gradient(50% 60% at 0% 100%, rgba(227, 178, 97, 0.10), rgba(227, 178, 97, 0) 70%), #150A0E; }
.st-key-hero .ca { color: #F7F2EC; }
.ca-nav { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px 28px; }
.ca-links { display: flex; flex-wrap: wrap; gap: 6px 26px; font-size: 15px; font-weight: 500; }
.ca-links a { position: relative; color: #E6DBDD; text-decoration: none; padding: 6px 0; }
.ca-links a::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1.5px; background: #E3B261;
  transform: scaleX(0); transform-origin: left; transition: transform 250ms ease; }
.ca-links a:hover { color: #FFFFFF; }
.ca-links a:hover::after, .ca-links a:focus-visible::after { transform: scaleX(1); }
.ca-h1 { margin: 14px 0 18px; font-weight: 700; font-size: clamp(34px, 4.2vw, 54px); line-height: 1.05;
  letter-spacing: -0.03em; text-wrap: balance; animation: ca-rise 700ms cubic-bezier(.2, .7, .2, 1) both; }
.ca-h1 em { font-style: normal; color: #E3B261; }
.ca-lead { margin: 0 0 8px; font-size: 19px; line-height: 1.6; color: #DCCFD2; max-width: 44ch;
  animation: ca-rise 700ms cubic-bezier(.2, .7, .2, 1) 120ms both; }
.ca-note { margin: 0; font-size: 14px; color: #BFB0B4; }

/* Buttons: brass primary with a light sweep, and quiet outline buttons */
.st-key-hero_sign_in button, .st-key-cta_sign_in button {
  position: relative; overflow: hidden; min-height: 52px; padding: 0 26px !important; border: none !important;
  border-radius: 12px !important; background: #E3B261 !important; color: #150A0E !important;
  box-shadow: 0 14px 34px -14px rgba(227, 178, 97, 0.75);
  transition: transform 200ms ease, box-shadow 200ms ease, background 200ms ease; }
.st-key-hero_sign_in button p, .st-key-cta_sign_in button p { font-weight: 600; font-size: 16px; color: #150A0E !important; }
.st-key-hero_sign_in button span, .st-key-cta_sign_in button span { color: #150A0E !important; }
.st-key-hero_sign_in button::after, .st-key-cta_sign_in button::after { content: ""; position: absolute; inset: 0;
  background: linear-gradient(110deg, rgba(255, 255, 255, 0) 30%, rgba(255, 255, 255, 0.6) 50%, rgba(255, 255, 255, 0) 70%);
  transform: translateX(-130%); transition: transform 650ms ease; pointer-events: none; }
.st-key-hero_sign_in button:hover, .st-key-cta_sign_in button:hover { transform: translateY(-2px);
  background: #EDC27A !important; box-shadow: 0 20px 40px -14px rgba(227, 178, 97, 0.9); }
.st-key-hero_sign_in button:hover::after, .st-key-cta_sign_in button:hover::after { transform: translateX(130%); }
.st-key-hero_sign_in button:active, .st-key-cta_sign_in button:active { transform: translateY(0) scale(0.98); }
.st-key-hero_sign_in button:focus-visible, .st-key-cta_sign_in button:focus-visible,
.st-key-nav_sign_in button:focus-visible, .st-key-hero_source a:focus-visible { outline: 2px solid #F7F2EC; outline-offset: 3px; }
.st-key-nav_sign_in button, .st-key-hero_source a {
  min-height: 44px; border-radius: 10px !important; background: rgba(247, 242, 236, 0.04) !important;
  border: 1px solid rgba(247, 242, 236, 0.32) !important; color: #F7F2EC !important;
  transition: background 200ms ease, border-color 200ms ease, transform 200ms ease; }
.st-key-nav_sign_in button p, .st-key-hero_source a p { color: #F7F2EC !important; font-weight: 600; }
.st-key-nav_sign_in button:hover, .st-key-hero_source a:hover { background: rgba(247, 242, 236, 0.12) !important;
  border-color: rgba(247, 242, 236, 0.6) !important; transform: translateY(-1px); }
.st-key-hero_source a { min-height: 52px; padding: 0 22px !important; border-radius: 12px !important; }

/* Example request card */
.ca-card { margin: 0; border-radius: 16px; overflow: hidden; background: rgba(247, 242, 236, 0.05);
  border: 1px solid rgba(247, 242, 236, 0.14); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 30px 60px -30px rgba(0, 0, 0, 0.7); animation: ca-rise 800ms cubic-bezier(.2, .7, .2, 1) 200ms both; }
.ca-card-head { display: flex; justify-content: space-between; gap: 12px; padding: 12px 18px; font-size: 13px;
  border-bottom: 1px solid rgba(247, 242, 236, 0.12); background: rgba(247, 242, 236, 0.04); }
.ca-code { margin: 0; padding: 14px 20px; font-size: 14px; line-height: 1.75; white-space: pre-wrap; color: #F7F2EC; }
.ca-line { display: block; animation: ca-fade 300ms ease-out both; }
.ca-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px solid rgba(247, 242, 236, 0.12); }
.ca-stat { padding: 14px 18px; display: flex; flex-direction: column; gap: 2px; border-right: 1px solid rgba(247, 242, 236, 0.12); }
.ca-stat:last-child { border-right: none; background: rgba(227, 178, 97, 0.10); }
.ca-stat small { font-size: 13px; color: #BFB0B4; }
.ca-stat b { font-family: 'IBM Plex Mono', monospace; font-size: 16px; font-weight: 500; }

/* Routing field (Three.js canvas with labels on top) */
.ca-field { position: relative; height: 270px; margin: 18px -40px 0; border-top: 1px solid rgba(247, 242, 236, 0.10); }
.ca-field canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
.ca-field-label { position: absolute; font-size: 13px; color: #BFB0B4; }
.ca-lane-label { position: absolute; right: 40px; transform: translateY(-50%); display: flex; flex-direction: column;
  gap: 2px; min-width: 190px; padding: 8px 12px; border-radius: 10px; font-size: 13px;
  background: rgba(21, 10, 14, 0.72); border: 1px solid rgba(247, 242, 236, 0.14); }
.ca-lane-label b { display: flex; align-items: center; gap: 8px; font-weight: 600; color: #F7F2EC; }
.ca-lane-label span.ca-sub { color: #BFB0B4; font-size: 12px; }
.ca-field-static { background: repeating-linear-gradient(90deg, rgba(247, 242, 236, 0.05) 0 1px, rgba(0, 0, 0, 0) 1px 46px); }

/* ---- Numbers strip ---- */
.ca-numbers { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: 16px; margin: 28px 0 0; }
.ca-number { padding: 22px 24px; border-radius: 16px; background: #FFFFFF; border: 1px solid #DCD8D4;
  transition: transform 250ms ease, box-shadow 250ms ease, border-color 250ms ease; }
.ca-number:hover { transform: translateY(-3px); border-color: #7B1E34; box-shadow: 0 18px 36px -24px rgba(123, 30, 52, 0.55); }
.ca-number b { display: block; font-size: 40px; line-height: 1.1; font-weight: 700; letter-spacing: -0.02em; color: #7B1E34;
  font-variant-numeric: tabular-nums; }
.ca-number span { color: #66625F; font-size: 15px; }
.ca-live { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #7B1E34; }
.ca-live i { width: 8px; height: 8px; border-radius: 999px; background: #7B1E34; animation: ca-pulse 2s ease-in-out infinite; }

/* ---- Sections ---- */
.ca-h2 { margin: 0 0 10px; font-weight: 700; font-size: clamp(28px, 3vw, 38px); line-height: 1.12; letter-spacing: -0.02em; }
.ca-steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(280px, 100%), 1fr)); gap: 18px;
  margin: 28px 0 0 !important; padding: 0 !important; list-style: none; }
.ca-steps li { margin: 0 !important; list-style: none; }
.ca-step { position: relative; overflow: hidden; padding: 26px 24px 24px; border-radius: 16px; background: #FFFFFF;
  border: 1px solid #DCD8D4; transition: transform 250ms ease, box-shadow 250ms ease, border-color 250ms ease; }
.ca-step::before { content: ""; position: absolute; left: 0; top: 0; height: 3px; width: 100%; background: #7B1E34;
  transform: scaleX(0.18); transform-origin: left; transition: transform 350ms cubic-bezier(.2, .7, .2, 1); }
.ca-step:hover { transform: translateY(-4px); border-color: #C9BEC0; box-shadow: 0 22px 40px -28px rgba(38, 37, 36, 0.55); }
.ca-step:hover::before { transform: scaleX(1); }
.ca-step h3 { margin: 10px 0 8px; font-size: 21px; font-weight: 600; }
.ca-step p { margin: 0; color: #66625F; }
.ca-scroll { overflow-x: auto; margin-top: 22px; background: #FFFFFF; border: 1px solid #DCD8D4; border-radius: 16px; }
.ca-table { width: 100%; min-width: 720px; border-collapse: collapse; font-size: 15px; }
.ca-table th { text-align: left; padding: 14px 20px; background: #F4F2F0; color: #66625F; font-size: 13px; font-weight: 600; }
.ca-table td { padding: 16px 20px; border-top: 1px solid #E6E2DE; transition: background 200ms ease; }
.ca-table tbody tr:hover td { background: #FAF3F4; }

/* ---- Call to action ---- */
.st-key-cta { position: relative; overflow: hidden; border-radius: 24px; padding: 44px 40px;
  background: linear-gradient(120deg, #7B1E34 0%, #5C1627 55%, #7B1E34 100%); background-size: 220% 100%;
  animation: ca-drift 14s ease-in-out infinite alternate; }
.st-key-cta .ca { color: #FFFFFF; }
.ca-footer { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(340px, 100%), 1fr)); gap: 28px;
  font-size: 15px; color: #66625F; padding: 12px 0 28px; }
.ca-footer h4 { margin: 0 0 6px; font-size: 15px; color: #262524; }
.ca-footer a { color: #7B1E34; }

/* ---- Motion ---- */
.ca-js .ca-reveal { opacity: 0; transform: translateY(20px);
  transition: opacity 650ms ease, transform 650ms cubic-bezier(.2, .7, .2, 1); transition-delay: var(--d, 0ms); }
.ca-js .ca-reveal.ca-in { opacity: 1; transform: none; }
@keyframes ca-rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes ca-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes ca-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
@keyframes ca-drift { from { background-position: 0% 0; } to { background-position: 100% 0; } }
@media (max-width: 720px) {
  .st-key-hero { padding: 22px 20px 0; border-radius: 18px; }
  .ca-field { margin: 14px -20px 0; height: 300px; }
  .ca-lane-label { right: 12px; min-width: 0; padding: 6px 9px; }
  .ca-lane-label span.ca-sub, .ca-lane-label b span.ca-mono { display: none; }
  .ca-stat { padding: 10px 12px; }
  .ca-stat b { font-size: 12.5px; }
  .st-key-cta { padding: 32px 22px; }
}
@media (prefers-reduced-motion: reduce) {
  .ca, .ca *, .st-key-cta, .st-key-hero button, .st-key-cta button { animation: none !important; transition: none !important; }
  .ca-js .ca-reveal { opacity: 1; transform: none; }
}
</style>
"""

# Runs in the page (not an iframe). It waits for Streamlit to render the markup, then starts
# the scroll reveals, the counters, and the Three.js routing field.
LANDING_JS = """
<script>
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initReveal() {
    document.documentElement.classList.add('ca-js');
    var items = document.querySelectorAll('.ca-reveal:not(.ca-in)');
    if (!('IntersectionObserver' in window) || reduce) { items.forEach(function (el) { el.classList.add('ca-in'); }); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('ca-in'); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    items.forEach(function (el) { io.observe(el); });
  }

  function initCounters() {
    document.querySelectorAll('[data-ca-count]').forEach(function (el) {
      if (el.dataset.caDone) return;
      el.dataset.caDone = '1';
      var to = parseFloat(el.dataset.caCount), decimals = parseInt(el.dataset.caDecimals || '0', 10);
      var prefix = el.dataset.caPrefix || '', suffix = el.dataset.caSuffix || '';
      var show = function (v) { el.textContent = prefix + v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix; };
      if (reduce || !('IntersectionObserver' in window)) { show(to); return; }
      show(0);
      var io = new IntersectionObserver(function (entries) {
        if (!entries[0].isIntersecting) return;
        io.disconnect();
        var start = performance.now(), delay = parseInt(el.dataset.caDelay || '0', 10);
        var tick = function (now) {
          var t = Math.min(1, Math.max(0, (now - start - delay) / 1100));
          show(to * (1 - Math.pow(1 - t, 3)));
          if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      }, { threshold: 0.4 });
      io.observe(el);
    });
  }

  function initField(THREE, field) {
    var canvas = field.querySelector('canvas');
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true }); }
    catch (e) { field.classList.add('ca-field-static'); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    var scene = new THREE.Scene();
    var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
    camera.position.z = 5;

    // The world is [-aspect, aspect] wide and [-1, 1] tall
    var aspect = 2, xStart, xRouter, xEnd;
    var LANE_Y = [0.62, 0, -0.62];              // Matches the label positions (18%, 50%, 82%)
    var LANE_SHARE = [0.55, 0.85, 1.0];         // Most prompts are simple, so most take the top lane
    var COLORS = [new THREE.Color('#E3B261'), new THREE.Color('#E77F93'), new THREE.Color('#F7F2EC')];
    var ROUTE_AT = 0.38;                        // Fraction of the journey spent reaching the router
    var smooth = function (u) { u = Math.min(1, Math.max(0, u)); return u * u * (3 - 2 * u); };

    function place(t, y0, lane, out) {
      if (t < ROUTE_AT) {
        var u = t / ROUTE_AT;
        out.x = xStart + (xRouter - xStart) * u;
        out.y = y0 * (1 - smooth(u));
      } else {
        var v = (t - ROUTE_AT) / (1 - ROUTE_AT);
        out.x = xRouter + (xEnd - xRouter) * v;
        out.y = LANE_Y[lane] * smooth(v * 1.7);
      }
    }

    // Soft round sprite for each particle
    var dot = document.createElement('canvas'); dot.width = dot.height = 64;
    var g = dot.getContext('2d'), grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, 'rgba(255,255,255,1)'); grad.addColorStop(0.35, 'rgba(255,255,255,0.55)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
    var sprite = new THREE.CanvasTexture(dot);

    var COUNT = 380;
    var positions = new Float32Array(COUNT * 3), colors = new Float32Array(COUNT * 3);
    var parts = [];
    for (var i = 0; i < COUNT; i++) {
      var r = Math.random();
      parts.push({ t: Math.random(), speed: 0.05 + Math.random() * 0.07, y0: (Math.random() * 2 - 1) * 0.86,
                   lane: r < LANE_SHARE[0] ? 0 : (r < LANE_SHARE[1] ? 1 : 2), z: Math.random() * 0.6 - 0.3,
                   wobble: Math.random() * 6.28 });
    }
    var geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    var points = new THREE.Points(geometry, new THREE.PointsMaterial({
      size: 9, sizeAttenuation: false, map: sprite, vertexColors: true, transparent: true,
      depthWrite: false, blending: THREE.AdditiveBlending }));
    scene.add(points);

    // Faint guide lines for the three lanes, and a ring where the router sits
    var guides = new THREE.Group(); scene.add(guides);
    var ring = new THREE.Mesh(new THREE.RingGeometry(0.105, 0.125, 64),
      new THREE.MeshBasicMaterial({ color: '#E3B261', transparent: true, opacity: 0.9 }));
    var core = new THREE.Mesh(new THREE.CircleGeometry(0.045, 32), new THREE.MeshBasicMaterial({ color: '#E3B261' }));
    scene.add(ring); scene.add(core);

    function buildGuides() {
      while (guides.children.length) { var c = guides.children.pop(); c.geometry.dispose(); c.material.dispose(); }
      var p = { x: 0, y: 0 };
      for (var lane = 0; lane < 3; lane++) {
        var pts = [];
        for (var s = 0; s <= 40; s++) { place(ROUTE_AT + (1 - ROUTE_AT) * s / 40, 0, lane, p); pts.push(new THREE.Vector3(p.x, p.y, -0.5)); }
        guides.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({ color: COLORS[lane], transparent: true, opacity: 0.22 })));
      }
      ring.position.set(xRouter, 0, 0); core.position.set(xRouter, 0, 0);
    }

    function resize() {
      var w = field.clientWidth, h = field.clientHeight;
      if (!w || !h) return;
      aspect = w / h;
      renderer.setSize(w, h, false);
      camera.left = -aspect; camera.right = aspect; camera.updateProjectionMatrix();
      xStart = -aspect - 0.05;
      xRouter = -aspect + 2 * aspect * 0.34;
      // Stop the lanes just before the labels on the right
      xEnd = -aspect + 2 * aspect * (w < 720 ? 0.68 : 0.74);
      buildGuides();
    }

    var tmp = { x: 0, y: 0 }, clock = 0;
    function update(dt) {
      clock += dt;
      for (var i = 0; i < COUNT; i++) {
        var p = parts[i];
        p.t += p.speed * dt;
        if (p.t > 1) { p.t = 0; p.y0 = (Math.random() * 2 - 1) * 0.86; }
        place(p.t, p.y0, p.lane, tmp);
        var k = i * 3;
        positions[k] = tmp.x;
        positions[k + 1] = tmp.y + Math.sin(clock * 1.6 + p.wobble) * 0.012;
        positions[k + 2] = p.z;
        // Fade in at the left edge and out at the end of the lane; before the router, prompts are a neutral ivory
        var fade = smooth(p.t / 0.07) * (1 - smooth((p.t - 0.9) / 0.1)) * 0.85;
        var c = p.t < ROUTE_AT ? COLORS[2] : COLORS[p.lane];
        colors[k] = c.r * fade; colors[k + 1] = c.g * fade; colors[k + 2] = c.b * fade;
      }
      geometry.attributes.position.needsUpdate = true;
      geometry.attributes.color.needsUpdate = true;
      var pulse = 1 + Math.sin(clock * 2.2) * 0.07;
      ring.scale.set(pulse, pulse, 1);
    }

    // Gentle parallax as the pointer moves over the hero
    var targetX = 0, targetY = 0;
    var hero = field.closest('.st-key-hero') || field;
    hero.addEventListener('pointermove', function (e) {
      var b = hero.getBoundingClientRect();
      targetX = ((e.clientX - b.left) / b.width - 0.5) * 0.08;
      targetY = ((e.clientY - b.top) / b.height - 0.5) * -0.06;
    });

    resize();
    window.addEventListener('resize', resize);
    update(0);
    renderer.render(scene, camera);
    if (reduce) return;   // One still frame for people who prefer less motion

    var visible = true;
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; }).observe(field);
    }
    var last = performance.now();
    function frame(now) {
      if (!canvas.isConnected) { renderer.dispose(); window.removeEventListener('resize', resize); return; }
      var dt = Math.min(0.05, (now - last) / 1000); last = now;
      if (visible && !document.hidden) {
        update(dt);
        scene.position.x += (targetX - scene.position.x) * 0.05;
        scene.position.y += (targetY - scene.position.y) * 0.05;
        renderer.render(scene, camera);
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function start() {
    var field = document.querySelector('.ca-field');
    if (!field) return false;
    initReveal();
    initCounters();
    if (field.dataset.caReady) return true;
    field.dataset.caReady = '1';
    import('https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js')
      .then(function (THREE) { initField(THREE, field); })
      .catch(function () { field.classList.add('ca-field-static'); });
    return true;
  }

  // Streamlit may add the page's markup after this script runs, so keep checking for a few seconds
  var tries = 0;
  var timer = setInterval(function () { if (start() && tries > 12) clearInterval(timer); if (++tries > 80) clearInterval(timer); }, 150);
})();
</script>
"""


def _hero_card() -> str:
    lines = [
        "{", '  "answer": "72°F is about 22.2°C.",', '  "model": "openai/gpt-oss-20b",',
        '  "tier": 1,', f'  "cost_usd": <b style="color:{BRASS}">0.000045</b>,',
        '  "escalated": false', "}",
    ]
    response = "".join(
        f'<span class="ca-line" style="animation-delay:{900 + i * 150}ms">{line}</span>'
        for i, line in enumerate(lines)
    )
    return (
        '<figure class="ca ca-card" aria-label="Example API request and response">'
        f'<div class="ca-card-head ca-mono"><span><b style="color:{BRASS}">POST</b> /route</span>'
        '<span style="color:#BFB0B4">200 OK in 0.8 s</span></div>'
        '<pre class="ca-code ca-mono" style="padding-bottom:4px;color:#BFB0B4">'
        '<span class="ca-line" style="animation-delay:600ms">{ "prompt": "Convert 72°F to Celsius." }</span></pre>'
        f'<pre class="ca-code ca-mono" style="border-top:1px dashed rgba(247,242,236,0.16)">{response}</pre>'
        '<div class="ca-stats"><div class="ca-stat"><small>This request</small><b>$0.000045</b></div>'
        '<div class="ca-stat"><small>On the top model</small><b style="color:#BFB0B4"><s>$0.000584</s></b></div>'
        f'<div class="ca-stat"><small style="color:{IVORY}">Saved</small>'
        f'<b style="font-size:22px;font-weight:600;color:{BRASS}" data-ca-count="92" data-ca-suffix="%" '
        'data-ca-delay="1900">92%</b></div></div></figure>'
    )


def _routing_field() -> str:
    labels = "".join(
        f'<div class="ca-lane-label" style="top:{top}%"><b>{tier_meter(tier, on=color, off="rgba(247,242,236,0.25)")}'
        f'Tier {tier}<span class="ca-mono" style="font-weight:400">{html.escape(ROUTING["tiers"][tier])}</span></b>'
        f'<span class="ca-sub">{LANE_COSTS[tier]}</span></div>'
        for tier, top, color in ((1, 19, "#E3B261"), (2, 50, "#E77F93"), (3, 81, "#F7F2EC"))
    )
    return (
        '<div class="ca ca-field" role="img" aria-label="Animation: prompts flow into the router and split '
        'across three model lanes. Most take the cheapest lane.">'
        '<canvas></canvas>'
        '<span class="ca-field-label ca-mono" style="left:40px;top:14px">incoming prompts</span>'
        '<span class="ca-field-label ca-mono" style="left:34%;bottom:14px;transform:translateX(-50%)">classifier + router</span>'
        f'{labels}</div>'
    )


def render_landing(sign_in, totals: dict, top_model_name: str, daily_limit: int,
                   github_url: str, built_by: str) -> None:
    st.set_page_config(page_title="Cost Autopilot", page_icon=":material/alt_route:",
                       layout="wide", initial_sidebar_state="collapsed")
    st.html(BASE_CSS + LANDING_CSS)

    with st.container(key="hero"):
        nav_left, nav_right = st.columns([6, 1], vertical_alignment="center")
        nav_left.html(
            f'<div class="ca ca-nav"><div class="ca-logo">{logo_img(IVORY, BRASS)}Cost Autopilot</div>'
            '<nav class="ca-links" aria-label="Main"><a href="#how-it-works">How it works</a>'
            f'<a href="#models-and-pricing">Models and pricing</a><a href="{github_url}">GitHub</a></nav></div>'
        )
        nav_right.button("Sign in", key="nav_sign_in", on_click=sign_in, width="stretch")

        if st.session_state.get("auth_missing"):
            st.warning("Google sign-in isn't set up yet: add your credentials to `.streamlit/secrets.toml`. "
                       "To try the chat without it on your own machine, run "
                       "`AUTOPILOT_DEV_USER=\"Your Name\" streamlit run app.py`.")

        hero_text, hero_card = st.columns([1.08, 1], gap="large", vertical_alignment="center")
        with hero_text:
            st.html(
                '<div class="ca"><h1 class="ca-h1">Route each prompt to the <em>cheapest model</em> '
                'that can answer it.</h1><p class="ca-lead">A classifier scores how complex a prompt is, '
                'a router sends it to a matching model, and a background verifier checks a sample of '
                'responses against a stronger model. Every response shows what it cost.</p></div>'
            )
            primary, secondary, _ = st.columns([1.55, 1, 0.25], vertical_alignment="center")
            primary.button("Continue with Google", key="hero_sign_in", icon=":material/login:",
                           on_click=sign_in, width="stretch")
            secondary.link_button("View the source", github_url, width="stretch", key="hero_source")
            st.html(f'<p class="ca ca-note">Free demo, {daily_limit} requests per account per day. '
                    'Your first sign-in creates your account.</p>')
        with hero_card:
            st.html(_hero_card())

        st.html(_routing_field())

    # Real numbers from the app's own database
    if totals["requests"]:
        people = "person has" if totals["users"] == 1 else "people have"
        numbers = (
            f'<div class="ca-number ca-reveal"><b data-ca-count="{totals["saved_pct"]}" data-ca-suffix="%">'
            f'{totals["saved_pct"]}%</b><span>lower cost than sending everything to {html.escape(top_model_name)}, '
            'verification included</span></div>'
            f'<div class="ca-number ca-reveal" style="--d:90ms"><b data-ca-count="{totals["requests"]}">'
            f'{totals["requests"]:,}</b><span>requests routed so far</span></div>'
            f'<div class="ca-number ca-reveal" style="--d:180ms"><b data-ca-count="{totals["users"]}">'
            f'{totals["users"]:,}</b><span>{people} tried it</span></div>'
        )
    else:
        numbers = ('<div class="ca-number ca-reveal"><b>0</b><span>requests so far. Sign in and send the first one.'
                   '</span></div>')
    st.html(
        '<section class="ca" aria-label="Results so far"><p class="ca-live" style="margin:26px 0 0"><i></i>Live from '
        f'the app\'s request log</p><div class="ca-numbers" style="margin-top:12px">{numbers}</div></section>'
    )

    st.html(
        '<section id="how-it-works" class="ca" style="padding-top:64px">'
        '<h2 class="ca-h2 ca-reveal">How a request is handled</h2>'
        '<p class="ca-muted ca-reveal" style="margin:0;--d:80ms">Three stages, each one a separate module you can '
        'read on GitHub.</p><ol class="ca-steps">'
        '<li class="ca-step ca-reveal"><span class="ca-mono ca-muted" style="font-size:13px">1  router.py</span>'
        '<h3>Classify</h3><p>Seven features, including length, instruction verbs, constraints and output format, '
        'feed a logistic regression model. It scored 86% on held-out prompts.</p></li>'
        '<li class="ca-step ca-reveal" style="--d:110ms"><span class="ca-mono ca-muted" style="font-size:13px">'
        '2  routing.yaml</span><h3>Route</h3><p>Each tier maps to a model in config. If a provider fails or '
        'exceeds 30 seconds, the request falls back to a model on a different provider.</p></li>'
        '<li class="ca-step ca-reveal" style="--d:220ms"><span class="ca-mono ca-muted" style="font-size:13px">'
        '3  verifier.py</span><h3>Verify</h3><p>About 1 in 3 responses is compared with the tier 3 model, using '
        'rule-based checks or an LLM judge. Weak responses are escalated to a stronger model.</p></li></ol></section>'
    )

    rows = "".join(
        f'<tr><td><b style="display:inline-flex;align-items:center;gap:8px">{tier_meter(tier)}{tier}</b></td>'
        f'<td>{TIER_EXAMPLES[tier]}</td><td class="ca-mono">{html.escape(name)}</td>'
        f'<td>{PROVIDER_NAMES.get(MODEL_REGISTRY[name].provider, MODEL_REGISTRY[name].provider)}</td>'
        f'<td class="ca-mono" style="text-align:right">{_price(MODEL_REGISTRY[name].input_cost_per_million)} / '
        f'{_price(MODEL_REGISTRY[name].output_cost_per_million)}</td></tr>'
        for tier, name in sorted(ROUTING["tiers"].items())
    )
    st.html(
        '<section id="models-and-pricing" class="ca" style="padding:64px 0 36px">'
        '<h2 class="ca-h2 ca-reveal">Models and pricing</h2>'
        '<div class="ca-scroll ca-reveal" style="--d:100ms"><table class="ca-table"><thead><tr><th>Tier</th>'
        '<th>Typical prompts</th><th>Model</th><th>Provider</th><th style="text-align:right">'
        f'USD per 1M tokens, in / out</th></tr></thead><tbody>{rows}</tbody></table></div>'
        '<p class="ca-muted" style="font-size:14px;margin:12px 0 0">Paid list prices as of November 2026. '
        'Thinking tokens are billed as output and included in every cost shown.</p></section>'
    )

    with st.container(key="cta"):
        cta_text, cta_button = st.columns([3, 1], vertical_alignment="center")
        cta_text.html(
            '<div class="ca"><h2 class="ca-h2" style="color:#FFFFFF">Send your own prompts</h2>'
            '<p style="margin:0;color:#F1DFE3">Sign-in is only used to enforce the per-account rate limit. '
            'Your password is never shared with this app.</p></div>'
        )
        cta_button.button("Continue with Google", key="cta_sign_in", icon=":material/login:",
                          on_click=sign_in, width="stretch")

    st.html(
        '<footer class="ca ca-footer" style="margin-top:28px"><div><h4>Data handling</h4>Prompts are sent to Groq '
        'and Google for inference, and their free tiers may use them for model training. Don\'t submit personal '
        'or sensitive data. Logs store a fingerprint of each prompt and account, never the text, name or email.'
        f'</div><div><h4>Source</h4>Code, load-test results and the case study are on <a href="{github_url}">'
        f'GitHub</a>. Built by {html.escape(built_by)}.</div></footer>'
    )

    st.html(LANDING_JS, unsafe_allow_javascript=True)
