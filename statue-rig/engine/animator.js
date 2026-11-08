/*
 * Statue Animator — deterministic, timeline-driven cut-out animation for the
 * statue character, built to reproduce the motion grammar of the reference
 * channels (pose-swap holds, pops, push-ins, phrase-by-phrase text builds).
 *
 *   const anim = new StatueAnimator(document.getElementById('stage'), scene);
 *   await anim.ready;
 *   anim.renderAt(3.25);          // draw the frame at t = 3.25 s (pure function of t)
 *
 * Scene format: see README.md ("Scene reference").  Coordinates are fractions of
 * the frame (0..1) unless noted; sizes in px are relative to a 1080-px-tall frame.
 */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const TAU = Math.PI * 2;

  // ---------- easing ----------
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const EASE = {
    linear: t => t,
    in: t => t * t * t,
    out: t => 1 - Math.pow(1 - t, 3),
    inOut: t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    back: t => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
    bounce: t => {
      const n1 = 7.5625, d1 = 2.75;
      if (t < 1 / d1) return n1 * t * t;
      if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
      if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
      return n1 * (t -= 2.625 / d1) * t + 0.984375;
    },
  };
  const ease = (name, t) => (EASE[name] || EASE.inOut)(clamp(t));
  // deterministic noise in [-1,1]
  const hash = n => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return (s - Math.floor(s)) * 2 - 1; };
  const noise1 = x => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u); };

  const FONTS = {
    marker: { family: 'Permanent Marker', weight: 400 },
    caps: { family: 'Bebas Neue', weight: 400 },
    impact: { family: 'Anton', weight: 400 },
    roman: { family: 'Cinzel', weight: 700 },
  };

  function el(tag, attrs = {}, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  class StatueAnimator {
    constructor(container, scene, library = window.STATUE) {
      this.lib = library;
      this.scene = Object.assign({ width: 1920, height: 1080, fps: 30, duration: 10, events: [] }, scene);
      this.W = this.scene.width; this.H = this.scene.height; this.k = this.H / 1080;
      this.events = this.scene.events.map((e, i) => Object.assign({ _i: i }, e)).sort((a, b) => a.t - b.t || a._i - b._i);
      this.container = container;
      this.ready = this._build();
    }

    // ---------- construction ----------
    async _build() {
      const { W, H } = this;
      const svg = this.svg = el('svg', { xmlns: NS, viewBox: `0 0 ${W} ${H}`, width: '100%', height: '100%', preserveAspectRatio: 'xMidYMid meet' });
      svg.style.display = 'block';
      this.container.innerHTML = '';
      this.container.appendChild(svg);

      // palette (editable) + symbols
      const pal = Object.assign({}, this.lib.palette, this.scene.palette || {});
      const css = Object.entries(pal).map(([r, c]) => `.${r}{fill:${c};stroke:${c}}`).join('\n') +
        '\nsymbol path{stroke-width:0.8;stroke-linejoin:round}' +
        '\n.ink-stroke{fill:none;stroke-linecap:round;stroke-linejoin:round}';
      el('style', {}, svg).textContent = css;
      const defs = this.defs = el('defs', {}, svg);
      const tmp = new DOMParser().parseFromString(`<svg xmlns="${NS}">${this.lib.symbols}</svg>`, 'image/svg+xml');
      for (const s of Array.from(tmp.documentElement.children)) defs.appendChild(document.importNode(s, true));

      // background
      const bg = this.scene.background || {};
      this.bgRect = el('rect', { x: 0, y: 0, width: W, height: H, fill: bg.color || '#ECE4D6' }, svg);
      this.world = el('g', { id: 'world' }, svg);
      this.groundShadowLayer = el('g', {}, this.world);
      this.actorLayer = el('g', { id: 'actors' }, this.world);
      this.propLayer = el('g', { id: 'props' }, this.world);
      this.textLayer = el('g', { id: 'texts' }, this.world);
      this.closeLayer = el('g', { id: 'closeup' }, svg);
      this.screenLayer = el('g', { id: 'screen' }, svg); // texts/props with "screen":true ignore camera
      this.fxLayer = el('g', { id: 'fx', 'pointer-events': 'none' }, svg);
      this._buildFx(bg);

      await this._loadFonts();
      this._prepare();
      this.renderAt(0);
      return this;
    }

    async _loadFonts() {
      if (!document.fonts) return;
      const loads = Object.values(FONTS).map(f => document.fonts.load(`${f.weight} 64px "${f.family}"`).catch(() => null));
      await Promise.all(loads);
      await document.fonts.ready;
    }

    _buildFx(bg) {
      const { W, H } = this;
      // film grain: a seeded noise tile rasterised once (cheap per frame)
      const grain = bg.grain === undefined ? 0 : bg.grain; // off by default: grain + video compression reads as dirt
      if (grain > 0) {
        const c = document.createElement('canvas'); c.width = c.height = 256;
        const g = c.getContext('2d'), id = g.createImageData(256, 256);
        let seed = 1337;
        const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
        for (let i = 0; i < id.data.length; i += 4) {
          const v = 110 + rnd() * 145; id.data[i] = id.data[i + 1] = id.data[i + 2] = v; id.data[i + 3] = 255;
        }
        g.putImageData(id, 0, 0);
        const pat = el('pattern', { id: 'grainPat', width: 256, height: 256, patternUnits: 'userSpaceOnUse' }, this.defs);
        el('image', { href: c.toDataURL(), width: 256, height: 256 }, pat);
        const r = el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#grainPat)', opacity: grain * 0.35 }, this.fxLayer);
        r.style.mixBlendMode = 'multiply';
      }
      const vig = bg.vignette === undefined ? 0.35 : bg.vignette;
      if (vig > 0) {
        const rg = el('radialGradient', { id: 'vig', cx: '50%', cy: '50%', r: '75%' }, this.defs);
        el('stop', { offset: '55%', 'stop-color': '#000', 'stop-opacity': 0 }, rg);
        el('stop', { offset: '100%', 'stop-color': '#000', 'stop-opacity': vig }, rg);
        el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#vig)' }, this.fxLayer);
      }
      this.flashRect = el('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff', opacity: 0 }, this.fxLayer);
    }

    // ---------- pre-pass: group events per layer and pre-build text/prop DOM ----------
    _prepare() {
      this.actors = {};      // id -> {events, node, use, shadow}
      this.texts = [];       // {ev, offT, exit, node, words[]}
      this.props = [];
      this.closeEvents = [];
      this.camEvents = [];
      this.shakeEvents = [];
      this.nudges = [];
      this.bgEvents = [];
      this.flashes = [];
      this.talk = this.scene.talk || [];
      const textById = {}, propById = {};
      for (const ev of this.events) {
        switch (ev.type) {
          case 'pose': {
            const id = ev.actor || 'hero';
            const a = this.actors[id] || (this.actors[id] = this._makeActor(id));
            a.events.push(ev);
            break;
          }
          case 'nudge': this.nudges.push(ev); break;
          case 'closeup': this.closeEvents.push(ev); break;
          case 'camera': this.camEvents.push(ev); break;
          case 'shake': this.shakeEvents.push(ev); break;
          case 'bg': this.bgEvents.push(ev); break;
          case 'flash': this.flashes.push(ev); break;
          case 'text':
            if (ev.off) { const tx = textById[ev.id]; if (tx) { tx.offT = ev.t; tx.exit = ev.exit || 'cut'; } }
            else { const tx = this._makeText(ev); this.texts.push(tx); if (ev.id) textById[ev.id] = tx; }
            break;
          case 'prop':
            if (ev.off) { const p = propById[ev.id]; if (p) { p.offT = ev.t; p.exit = ev.exit || 'cut'; for (const tx of p.linked) { tx.offT = ev.t; tx.exit = p.exit === 'cut' ? 'cut' : 'fade'; } } }
            else { const p = this._makeProp(ev); this.props.push(p); if (ev.id) propById[ev.id] = p; }
            break;
          default: console.warn('unknown event type', ev.type);
        }
      }
      this._makeCloseup();
    }

    _makeActor(id) {
      const shadow = el('ellipse', { rx: 1, ry: 1, fill: '#000', opacity: 0 }, this.groundShadowLayer);
      const g = el('g', { 'data-actor': id }, this.actorLayer);
      const inner = el('g', {}, g);
      const use = el('use', {}, inner);
      return { id, events: [], g, inner, use, shadow, cur: null };
    }

    // ---------- per-frame ----------
    renderAt(t) {
      this.t = t;
      this._renderBg(t);
      for (const id in this.actors) this._renderActor(this.actors[id], t);
      for (const tx of this.texts) this._renderText(tx, t);
      for (const p of this.props) this._renderProp(p, t);
      this._renderCloseup(t);
      this._renderCamera(t);
      this._renderFlash(t);
    }

    _renderBg(t) {
      let color = (this.scene.background || {}).color || '#ECE4D6';
      let prev = color;
      for (const e of this.bgEvents) {
        if (e.t > t) break;
        const p = e.dur ? clamp((t - e.t) / e.dur) : 1;
        prev = color; color = p >= 1 ? e.color : mixHex(prev, e.color, p);
      }
      this.bgRect.setAttribute('fill', color);
      this.bgColor = color;
    }

    _renderFlash(t) {
      let o = 0;
      for (const f of this.flashes) {
        const d = f.dur || 0.25, p = (t - f.t) / d;
        if (p >= 0 && p < 1) { o = Math.max(o, (f.opacity || 0.8) * (1 - p)); this.flashRect.setAttribute('fill', f.color || '#fff'); }
      }
      this.flashRect.setAttribute('opacity', o);
    }

    // --- actors ---
    _poseTransform(ev, part) {
      const { W, H } = this;
      const height = (ev.height ?? 0.78) * H;
      const s = (height / part.unit) * (ev.scale ?? 1);
      const x = (ev.x ?? 0.5) * W, y = (ev.ground ?? 0.93) * H;
      return { x, y, s, flip: !!ev.flip };
    }

    _renderActor(a, t) {
      // current = last pose event at or before t
      let cur = null, prev = null;
      for (const e of a.events) { if (e.t <= t) { prev = cur; cur = e; } else break; }
      if (!cur) { a.g.setAttribute('visibility', 'hidden'); a.shadow.setAttribute('opacity', 0); return; }
      let ev = cur, phase = 'in', p = 1;
      const isOff = !cur.name;
      if (isOff) {
        if (!prev || !prev.name || !cur.exit || cur.exit === 'cut') { a.g.setAttribute('visibility', 'hidden'); a.shadow.setAttribute('opacity', 0); return; }
        // inherit placement from the previous pose for the exit animation
        ev = Object.assign({}, prev, { t: cur.t }); phase = 'out';
        p = clamp((t - cur.t) / (cur.dur || 0.22));
        if (p >= 1) { a.g.setAttribute('visibility', 'hidden'); a.shadow.setAttribute('opacity', 0); return; }
      }
      const part = this.lib.parts[ev.name];
      if (!part) { console.warn('unknown part', ev.name); return; }
      // placement may be inherited from the previous pose if omitted ("swap in place")
      const placeFrom = (key, dflt) => (ev[key] !== undefined ? ev[key] : this._inheritPlace(a, ev, key, dflt));
      const pe = { x: placeFrom('x', 0.5), ground: placeFrom('ground', 0.93), height: placeFrom('height', 0.78), scale: placeFrom('scale', 1), flip: placeFrom('flip', false) };
      let { x, y, s, flip } = this._poseTransform(pe, part);
      const { W, H } = this;
      let ox = 0, oy = 0, sx = 1, sy = 1, rot = 0, op = 1;
      const enter = phase === 'in' ? (ev.enter || 'cut') : 'cut';
      const dur = ev.dur || ({ pop: 0.32, slide: 0.45, 'slide-left': 0.45, 'slide-right': 0.45, drop: 0.55, fade: 0.35, rise: 0.4 })[enter] || 0;
      if (phase === 'in' && dur > 0) {
        p = clamp((t - ev.t) / dur);
        if (enter === 'pop') { const k = lerp(0.55, 1, ease('back', p)); sx *= k; sy *= k; op = clamp(p * 6); }
        else if (enter === 'slide-left' || enter === 'slide') ox = lerp(-0.7 * W, 0, ease('out', p));
        else if (enter === 'slide-right') ox = lerp(0.7 * W, 0, ease('out', p));
        else if (enter === 'drop') { oy = lerp(-1.1 * H, 0, ease('bounce', p)); }
        else if (enter === 'rise') { oy = lerp(0.6 * H, 0, ease('out', p)); }
        else if (enter === 'fade') op = p;
      }
      if (phase === 'out') {
        const ex = cur.exit;
        if (ex === 'pop') { const k = lerp(1, 0.2, ease('in', p)); sx *= k; sy *= k; op = 1 - clamp((p - 0.7) / 0.3); }
        else if (ex === 'slide-left') ox = lerp(0, -0.8 * W, ease('in', p));
        else if (ex === 'slide-right') ox = lerp(0, 0.8 * W, ease('in', p));
        else if (ex === 'fade') op = 1 - p;
        else if (ex === 'fall') { rot = lerp(0, 85, ease('in', p)); oy = lerp(0, 0.05 * H, p); }
      }
      // idle life: breathing + sway (pivot at the feet)
      const idle = ev.idle !== false;
      const seed = (a.id.length * 7.3) % 5;
      if (idle) {
        const br = Math.sin(TAU * (t / 3.1) + seed);
        sy *= 1 + 0.011 * br; sx *= 1 - 0.003 * br;
        rot += 0.35 * Math.sin(TAU * (t / 5.7) + seed * 1.7);
      }
      // nudges (hop / squash / shake / lean) addressed to this actor
      for (const n of this.nudges) {
        if ((n.actor || 'hero') !== a.id) continue;
        const nd = n.dur || 0.4, q = (t - n.t) / nd;
        if (q < 0 || q > 1) continue;
        const amp = n.amp ?? 1;
        if (n.kind === 'hop') { oy -= Math.sin(Math.PI * q) * 0.06 * H * amp; const sq = q < 0.15 ? 1 - q / 0.15 * 0.1 : 1; sy *= sq; sx *= 2 - sq; }
        else if (n.kind === 'squash') { const v = Math.sin(Math.PI * q) * (1 - q); sy *= 1 - 0.12 * v * amp; sx *= 1 + 0.08 * v * amp; }
        else if (n.kind === 'shake') ox += noise1(t * 40 + 3) * 0.012 * W * amp * (1 - q);
        else if (n.kind === 'lean') rot += Math.sin(Math.PI * q) * 6 * amp * (n.dir === 'left' ? -1 : 1);
        else if (n.kind === 'grow') { const k = 1 + 0.08 * amp * Math.sin(Math.PI * q); sx *= k; sy *= k; }
      }
      const fs = flip ? -1 : 1;
      a.g.setAttribute('visibility', 'visible');
      a.g.setAttribute('opacity', op);
      a.g.setAttribute('transform', `translate(${x + ox},${y + oy}) rotate(${rot}) scale(${s * sx * fs},${s * sy})`);
      a.inner.setAttribute('transform', `translate(${-part.footX},${-part.groundY})`);
      if (a.cur !== ev.name) { a.use.setAttribute('href', '#' + ev.name); a.use.setAttribute('width', part.w); a.use.setAttribute('height', part.h); a.cur = ev.name; }
      // soft contact shadow
      const sh = this.scene.groundShadow === false ? 0 : 0.18 * op;
      a.shadow.setAttribute('cx', x + ox); a.shadow.setAttribute('cy', y + oy * 0.0 + 2 * this.k);
      a.shadow.setAttribute('rx', part.unit * s * 0.17 * sx); a.shadow.setAttribute('ry', part.unit * s * 0.022);
      a.shadow.setAttribute('opacity', oy < -5 ? sh * 0.5 : sh);
    }

    _inheritPlace(a, ev, key, dflt) {
      let v = dflt;
      for (const e of a.events) { if (e === ev) break; if (e[key] !== undefined) v = e[key]; }
      return v;
    }

    // --- close-up (full-screen bust shot) ---
    _makeCloseup() {
      this.close = { g: el('g', { visibility: 'hidden' }, this.closeLayer) };
      this.close.bg = el('rect', { x: 0, y: 0, width: this.W, height: this.H }, this.close.g);
      this.close.head = el('g', {}, this.close.g);
      this.close.inner = el('g', {}, this.close.head);
      this.close.use = el('use', {}, this.close.inner);
    }

    _renderCloseup(t) {
      let cur = null, prev = null;
      for (const e of this.closeEvents) { if (e.t <= t) { prev = cur; cur = e; } else break; }
      const C = this.close;
      if (!cur || !cur.name) { C.g.setAttribute('visibility', 'hidden'); this.closeActive = false; return; }
      this.closeActive = true;
      const part = this.lib.parts[cur.name];
      const { W, H } = this;
      // fit the bust: its height fills `fill` of the frame, bottom-anchored
      const [bx0, by0, bx1, by1] = part.bbox;
      const fill = cur.fill ?? 0.98;
      const s = (fill * H) / (by1 - by0 + 1);
      const side = cur.side || 'center';
      const cx = cur.x !== undefined ? cur.x * W : side === 'left' ? 0.3 * W : side === 'right' ? 0.7 * W : 0.5 * W;
      let ox = 0, oy = 0, k = 1, rot = 0;
      // was the previous closeup event contiguous? then this is an expression swap -> punch
      const swap = prev && prev.name && cur.enter === undefined;
      const enter = cur.enter || (swap ? 'punch' : 'cut');
      const p = clamp((t - cur.t) / (cur.dur || 0.2));
      if (enter === 'punch') k *= lerp(1.07, 1, ease('out', p));
      else if (enter === 'pop') k *= lerp(0.7, 1, ease('back', p));
      else if (enter === 'rise') oy = lerp(0.5 * H, 0, ease('out', p));
      // breathing + talk bob
      rot += 0.4 * Math.sin(TAU * t / 4.3);
      oy += 0.004 * H * Math.sin(TAU * t / 3.1);
      if (this._talking(t)) { oy += 0.009 * H * Math.abs(noise1(t * 7.5)); rot += 0.8 * noise1(t * 3.1 + 9); }
      if (cur.shake) { ox += noise1(t * 45) * 0.008 * W; oy += noise1(t * 45 + 50) * 0.006 * H; }
      const fs = cur.flip ? -1 : 1;
      C.bg.setAttribute('fill', cur.bg || this.bgColor);
      C.g.setAttribute('visibility', 'visible');
      C.head.setAttribute('transform', `translate(${cx + ox},${H + oy}) rotate(${rot}) scale(${s * k * fs},${s * k})`);
      C.inner.setAttribute('transform', `translate(${-(bx0 + bx1) / 2},${-by1 - 1})`);
      if (C.cur !== cur.name) { C.use.setAttribute('href', '#' + cur.name); C.use.setAttribute('width', part.w); C.use.setAttribute('height', part.h); C.cur = cur.name; }
    }

    _talking(t) { return this.talk.some(([a, b]) => t >= a && t <= b); }

    // --- camera ---
    _renderCamera(t) {
      let z = 1, fx = 0.5, fy = 0.5, rot = 0;
      for (const c of this.camEvents) {
        if (c.t > t) break;
        const p = c.dur ? ease(c.ease || 'inOut', (t - c.t) / c.dur) : 1;
        const tz = c.zoom ?? z, tx = c.x ?? fx, ty = c.y ?? fy, tr = c.rotate ?? rot;
        z = lerp(z, tz, p); fx = lerp(fx, tx, p); fy = lerp(fy, ty, p); rot = lerp(rot, tr, p);
      }
      let sx = 0, sy = 0;
      for (const s of this.shakeEvents) {
        const d = s.dur || 0.35, q = (t - s.t) / d;
        if (q < 0 || q > 1) continue;
        const amp = (s.amp ?? 14) * this.k * (1 - q);
        sx += noise1(t * 38 + s.t) * amp; sy += noise1(t * 38 + s.t + 77) * amp;
      }
      const { W, H } = this;
      // keep the focus point centred, but never show outside the frame when zoom >= 1
      let cx = fx * W, cy = fy * H;
      if (z >= 1) { cx = clamp(cx, W / (2 * z), W - W / (2 * z)); cy = clamp(cy, H / (2 * z), H - H / (2 * z)); }
      this.world.setAttribute('transform', `translate(${W / 2 + sx},${H / 2 + sy}) rotate(${rot}) scale(${z}) translate(${-cx},${-cy})`);
      // close-ups get the shake too
      this.closeLayer.setAttribute('transform', `translate(${sx},${sy})`);
    }

    // --- text ---
    _measure(fontKey, sizePx) {
      const f = FONTS[fontKey] || FONTS.marker;
      const ctx = (this._mctx ||= document.createElement('canvas').getContext('2d'));
      ctx.font = `${f.weight} ${sizePx}px "${f.family}"`;
      return ctx;
    }

    _wrapCount(text, fontKey, sizePx, maxW) {
      const ctx = this._measure(fontKey, sizePx), space = ctx.measureText(' ').width;
      let lines = 1, lw = 0;
      for (const w of String(text).split(/\s+/).filter(Boolean)) {
        if (w === '\n') { lines++; lw = 0; continue; }
        const ww = ctx.measureText(w).width;
        if (lw && lw + space + ww > maxW) { lines++; lw = ww; } else lw += (lw ? space : 0) + ww;
      }
      return lines;
    }

    // largest font size (1080p px) whose wrapped text fits inside maxW x maxH (screen px)
    _fitSize(text, fontKey, maxW, maxH, lineHeight) {
      let lo = 10, hi = 260;
      for (let i = 0; i < 18; i++) {
        const mid = (lo + hi) / 2, px = mid * this.k;
        const n = this._wrapCount(text, fontKey, px, maxW);
        const widest = Math.max(...String(text).split(/\s+/).map(w => this._measure(fontKey, px).measureText(w).width));
        if (n * px * lineHeight <= maxH && widest <= maxW) lo = mid; else hi = mid;
      }
      return Math.floor(lo);
    }

    _makeText(ev) {
      const f = FONTS[ev.font || 'marker'] || FONTS.marker;
      const size = (ev.size || 84) * this.k;
      const layer = ev.screen ? this.screenLayer : this.textLayer;
      const g = el('g', { visibility: 'hidden' }, layer);
      const words = (ev.words || String(ev.text || '').split(/\s+/)).filter(Boolean);
      const ctx = (this._mctx ||= document.createElement('canvas').getContext('2d'));
      ctx.font = `${f.weight} ${size}px "${f.family}"`;
      const space = ctx.measureText(' ').width;
      const maxW = (ev.maxWidth || 0.9) * this.W;
      const lh = size * (ev.lineHeight || 1.08);
      // greedy line wrap
      const lines = [[]]; let lw = 0;
      for (const w of words) {
        if (w === '\n') { lines.push([]); lw = 0; continue; }
        const ww = ctx.measureText(ev.upper ? w.toUpperCase() : w).width;
        if (lines[lines.length - 1].length && lw + space + ww > maxW) { lines.push([]); lw = 0; }
        lines[lines.length - 1].push({ w, ww }); lw += (lw ? space : 0) + ww;
      }
      const anchor = ev.anchor || 'middle';
      const X = (ev.x ?? 0.5) * this.W, Y = (ev.y ?? 0.2) * this.H;
      const out = [];
      lines.forEach((line, li) => {
        const total = line.reduce((s, o, i) => s + o.ww + (i ? space : 0), 0);
        let x = anchor === 'start' ? X : anchor === 'end' ? X - total : X - total / 2;
        const y = Y + li * lh;
        for (const o of line) {
          const wg = el('g', { transform: `translate(${x + o.ww / 2},${y})` }, g);
          const inner = el('g', {}, wg);
          const attrs = { x: 0, y: 0, 'text-anchor': 'middle', 'dominant-baseline': 'middle', 'font-family': `'${f.family}'`, 'font-weight': f.weight, 'font-size': size, fill: ev.color || '#141010' };
          if (ev.stroke) Object.assign(attrs, { stroke: ev.stroke, 'stroke-width': (ev.strokeWidth || size * 0.12), 'paint-order': 'stroke', 'stroke-linejoin': 'round' });
          el('text', attrs, inner).textContent = ev.upper ? o.w.toUpperCase() : o.w;
          out.push({ inner, wg, x: x + o.ww / 2, y });
          x += o.ww + space;
        }
      });
      if (ev.rotate) g.setAttribute('transform', `rotate(${ev.rotate},${X},${Y})`);
      return { ev, g, words: out, offT: Infinity, exit: 'cut' };
    }

    _renderText(tx, t) {
      const { ev } = tx;
      if (t < ev.t || t >= tx.offT + (tx.exit === 'cut' ? 0 : 0.25)) { tx.g.setAttribute('visibility', 'hidden'); return; }
      tx.g.setAttribute('visibility', 'visible');
      const every = ev.every ?? 0.28, enter = ev.enter || 'pop';
      const exitP = t >= tx.offT ? clamp((t - tx.offT) / 0.25) : 0;
      tx.words.forEach((w, i) => {
        const t0 = ev.t + i * every, p = (t - t0) / 0.2;
        if (p < 0) { w.inner.setAttribute('opacity', 0); return; }
        let k = 1, op = 1, dy = 0;
        if (enter === 'pop') { k = lerp(0.4, 1, ease('back', p)); op = clamp(p * 4); }
        else if (enter === 'fade') op = clamp(p);
        else if (enter === 'rise') { dy = lerp(20 * this.k, 0, ease('out', p)); op = clamp(p * 2); }
        if (exitP) { if (tx.exit === 'pop') { k *= 1 - ease('in', exitP); } else op *= 1 - exitP; }
        if (ev.wobble) dy += Math.sin(TAU * (t * 0.7) + i) * 2 * this.k;
        w.inner.setAttribute('opacity', op);
        w.inner.setAttribute('transform', `translate(0,${dy}) scale(${k})`);
      });
    }

    // --- props (hand-drawn marks) ---
    _makeProp(ev) {
      const { W, H, k } = this;
      const layer = ev.screen ? this.screenLayer : this.propLayer;
      const g = el('g', { visibility: 'hidden' }, layer);
      const color = ev.color || '#B3121C';
      const sw = (ev.width || 9) * k;
      const P = ([x, y]) => [x * W, y * H];
      const strokes = [];
      const linked = []; // text events generated by this prop (board writing)
      const stroke = (d) => { const p = el('path', { d, class: 'ink-stroke', stroke: color, 'stroke-width': sw, pathLength: 1, 'stroke-dasharray': 1 }, g); strokes.push(p); return p; };
      let pivot = [0, 0];
      switch (ev.kind) {
        case 'arrow': {
          const [x0, y0] = P(ev.from), [x1, y1] = P(ev.to);
          const bend = ev.bend ?? 0.18, mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
          const nx = -(y1 - y0) * bend, ny = (x1 - x0) * bend;
          stroke(`M${x0},${y0} Q${mx + nx},${my + ny} ${x1},${y1}`);
          const ang = Math.atan2(y1 - (my + ny), x1 - (mx + nx)), hl = (ev.head || 38) * k;
          stroke(`M${x1 - hl * Math.cos(ang - 0.5)},${y1 - hl * Math.sin(ang - 0.5)} L${x1},${y1} L${x1 - hl * Math.cos(ang + 0.5)},${y1 - hl * Math.sin(ang + 0.5)}`);
          pivot = [x1, y1];
          break;
        }
        case 'circle': {
          const [cx, cy] = P(ev.at), rx = (ev.rx || 0.08) * W, ry = (ev.ry || ev.rx || 0.08) * W * (ev.ry ? 1 : 0.62);
          let d = ''; const n = 48, turns = 1.12;
          for (let i = 0; i <= n; i++) {
            const a = -2.2 + TAU * turns * (i / n), wob = 1 + 0.04 * Math.sin(i * 0.9);
            d += (i ? 'L' : 'M') + (cx + Math.cos(a) * rx * wob * (1 + 0.05 * i / n)) + ',' + (cy + Math.sin(a) * ry * wob);
          }
          stroke(d); pivot = [cx, cy];
          break;
        }
        case 'x': {
          const [cx, cy] = P(ev.at), r = (ev.size || 0.06) * H;
          stroke(`M${cx - r},${cy - r} L${cx + r},${cy + r}`); stroke(`M${cx + r},${cy - r} L${cx - r},${cy + r}`);
          pivot = [cx, cy];
          break;
        }
        case 'check': {
          const [cx, cy] = P(ev.at), r = (ev.size || 0.06) * H;
          stroke(`M${cx - r},${cy} L${cx - r * 0.25},${cy + r * 0.75} L${cx + r * 1.1},${cy - r * 0.9}`);
          pivot = [cx, cy];
          break;
        }
        case 'underline': {
          const [x0, y0] = P(ev.from), [x1] = P(ev.to);
          stroke(`M${x0},${y0} Q${(x0 + x1) / 2},${y0 + 10 * k} ${x1},${y0 - 4 * k}`);
          pivot = [(x0 + x1) / 2, y0];
          break;
        }
        case 'svg': { // arbitrary inline SVG markup (icons, logos) placed at `at`, `size` = height fraction
          const [cx, cy] = P(ev.at), hh = (ev.size || 0.2) * H;
          const wrap = el('g', { transform: `translate(${cx},${cy})` }, g);
          const inner = el('g', {}, wrap);
          const doc = new DOMParser().parseFromString(ev.markup, 'image/svg+xml').documentElement;
          const vb = (doc.getAttribute('viewBox') || '0 0 100 100').split(/[ ,]+/).map(Number);
          const sc = hh / vb[3];
          const holder = el('g', { transform: `scale(${sc}) translate(${-vb[0] - vb[2] / 2},${-vb[1] - vb[3] / 2})` }, inner);
          for (const c of Array.from(doc.childNodes)) holder.appendChild(document.importNode(c, true));
          pivot = [cx, cy];
          break;
        }
        case 'part': { // any library part: props (prop_*), or a head/pose used as an icon
          const part = this.lib.parts[ev.name];
          if (!part) { console.warn('unknown part', ev.name); break; }
          const [bx0, by0, bx1, by1] = part.bbox;
          const bw = bx1 - bx0 + 1, bh = by1 - by0 + 1;
          const [cx, cy] = P(ev.at || [0.5, 0.5]);
          // size = height of the visible drawing as a fraction of the frame; or width = fraction of frame width
          const sc = ev.width ? (ev.width * W) / bw : ((ev.size || 0.3) * H) / bh;
          const fl = ev.flip ? -1 : 1;
          const wrap = el('g', { transform: `translate(${cx},${cy}) rotate(${ev.rotate || 0}) scale(${sc * fl},${sc}) translate(${-(bx0 + bx1) / 2},${-(by0 + by1) / 2})` }, g);
          el('use', { href: '#' + ev.name, width: part.w, height: part.h }, wrap);
          pivot = [cx, cy];
          // writing on boards: fit text inside the part's detected surface
          if (ev.text && part.surface && !ev.rotate) {
            const [sx0, sy0, sx1, sy1] = part.surface; // fractions of the bbox
            const pad = ev.padding ?? 0.08;
            const toX = f => cx + fl * (bx0 + f * bw - (bx0 + bx1) / 2) * sc;
            const toY = f => cy + (by0 + f * bh - (by0 + by1) / 2) * sc;
            const X0 = Math.min(toX(sx0), toX(sx1)), X1 = Math.max(toX(sx0), toX(sx1));
            const Y0 = toY(sy0), Y1 = toY(sy1);
            const iw = (X1 - X0) * (1 - 2 * pad), ih = (Y1 - Y0) * (1 - 2 * pad);
            const fontKey = ev.font || 'marker';
            const size = ev.textSize || this._fitSize(ev.text, fontKey, iw, ih, ev.lineHeight || 1.12);
            const nLines = this._wrapCount(ev.text, fontKey, size * this.k, iw);
            const lh = size * this.k * (ev.lineHeight || 1.12);
            const top = (Y0 + Y1) / 2 - ((nLines - 1) * lh) / 2;
            linked.push({
              type: 'text', t: ev.t + (ev.textDelay ?? 0.3), text: ev.text, font: fontKey, size,
              color: ev.textColor || (part.surfaceDark ? '#ECE4D6' : '#141010'),
              x: ((X0 + X1) / 2) / W, y: top / H, maxWidth: iw / W, lineHeight: ev.lineHeight || 1.12,
              every: ev.every ?? 0.22, enter: ev.textEnter || 'pop', screen: ev.screen,
            });
          }
          break;
        }
        case 'panel': { // flat rectangle / card (split-screen backgrounds, whiteboard cards)
          const [x0, y0] = P(ev.from), [x1, y1] = P(ev.to);
          el('rect', { x: x0, y: y0, width: x1 - x0, height: y1 - y0, rx: (ev.radius || 0) * k, fill: ev.fill || '#fff', stroke: ev.stroke || 'none', 'stroke-width': sw }, g);
          pivot = [(x0 + x1) / 2, (y0 + y1) / 2];
          break;
        }
        default: console.warn('unknown prop kind', ev.kind);
      }
      if (ev.layer === 'back') this.actorLayer.parentNode.insertBefore(g, this.actorLayer);
      return { ev, g, strokes, pivot, offT: Infinity, exit: 'cut', linked: linked.map(te => { const tx = this._makeText(te); this.texts.push(tx); return tx; }) };
    }

    _renderProp(pr, t) {
      const { ev } = pr;
      if (t < ev.t || t >= pr.offT + (pr.exit === 'cut' ? 0 : 0.25)) { pr.g.setAttribute('visibility', 'hidden'); return; }
      pr.g.setAttribute('visibility', 'visible');
      const enter = ev.enter || (pr.strokes.length ? 'draw' : 'pop');
      const dur = ev.dur || (enter === 'draw' ? 0.35 : 0.25);
      const p = clamp((t - ev.t) / dur);
      let k = 1, op = 1;
      if (enter === 'draw') {
        const n = pr.strokes.length;
        pr.strokes.forEach((s, i) => { const q = clamp(p * n - i); s.setAttribute('stroke-dashoffset', 1 - q); });
      } else {
        pr.strokes.forEach(s => s.setAttribute('stroke-dashoffset', 0));
        if (enter === 'pop') { k = lerp(0.3, 1, ease('back', p)); op = clamp(p * 5); }
        else if (enter === 'fade') op = p;
      }
      if (t >= pr.offT) { const q = clamp((t - pr.offT) / 0.25); if (pr.exit === 'pop') k *= 1 - ease('in', q); else op *= 1 - q; }
      if (ev.float) k *= 1 + 0.02 * Math.sin(TAU * t * 0.8);
      const [px, py] = pr.pivot;
      pr.g.setAttribute('opacity', op);
      pr.g.setAttribute('transform', `translate(${px},${py}) scale(${k}) translate(${-px},${-py})`);
    }
  }

  function mixHex(a, b, t) {
    const pa = [1, 3, 5].map(i => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map(i => parseInt(b.slice(i, i + 2), 16));
    return '#' + pa.map((v, i) => Math.round(lerp(v, pb[i], t)).toString(16).padStart(2, '0')).join('');
  }

  window.StatueAnimator = StatueAnimator;
  window.StatueAnimator.EASE = EASE;
  window.StatueAnimator.FONTS = FONTS;
})();
