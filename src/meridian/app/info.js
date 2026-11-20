/* Info bubbles (config/glossary.yaml, injected as window.MINFO by the shell).
   A small "i" is added next to every column header, tile label, heading and control label whose text matches a
   glossary entry, or that carries data-info="<key>"; for entries marked button: true, also next to buttons with that
   label. Click (or Enter/Space) opens a short explanation with a simplified formula; Esc or a click elsewhere closes.
   The "i" is drawn with CSS, so the label's text (and any test or screen-reader text) is unchanged. */
(function(){
  const G = window.MINFO || {};
  const norm = t => String(t||'').replace(/\s+/g,' ').trim().replace(/[:：]$/,'').toLowerCase();
  const byLabel = {}, byBtn = {};
  for (const [k,e] of Object.entries(G)) for (const m of (e.match||[])) { byLabel[norm(m)] = k; if (e.button) byBtn[norm(m)] = k; }
  const css = document.createElement('style'); css.id = 'minfo-css';
  css.textContent = `.minfo{display:inline-flex;align-items:center;justify-content:center;width:15px;height:15px;min-height:0;padding:0;margin:0 0 0 5px;border-radius:50%;
    border:1px solid var(--line-strong,#c9c9c9);background:var(--surface,#fff);color:var(--muted,#666);font:italic 700 10px/1 Georgia,serif;cursor:help;vertical-align:middle;flex:none}
  .minfo::before{content:"i"}
  .minfo:hover,.minfo:focus-visible,.minfo[aria-expanded="true"]{border-color:var(--accent,#002855);color:var(--accent,#002855);outline:none;box-shadow:0 0 0 2px var(--focus,#0076CF)33}
  .minfo-pop{position:fixed;z-index:10050;max-width:min(380px,92vw);background:var(--surface,#fff);color:var(--text,#222);border:1px solid var(--line-strong,#ccc);
    border-radius:var(--radius-md,8px);box-shadow:0 8px 28px rgba(0,0,0,.18);padding:10px 12px;font:13px/1.45 var(--font,system-ui,sans-serif);text-align:left;white-space:normal;font-style:normal;font-weight:400;text-transform:none;letter-spacing:0}
  .minfo-pop h4{margin:0 0 4px;font-size:13px;color:var(--heading,var(--text,#111))}
  .minfo-pop p{margin:0}
  .minfo-pop .mf{margin-top:8px;padding:6px 8px;background:var(--surface-2,#f4f4f6);border-radius:6px;font-size:12px}
  .minfo-pop .mf b{display:block;font-size:11px;color:var(--muted,#666);font-weight:600;margin-bottom:2px}
  .minfo-pop .mx{position:absolute;top:4px;right:6px;border:0;background:none;color:var(--muted,#666);font-size:16px;cursor:pointer;min-height:0;padding:2px 4px}`;
  document.head.appendChild(css);
  let pop = null, owner = null;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  function close(){ if (pop) { pop.remove(); pop = null; } if (owner) { owner.setAttribute('aria-expanded','false'); owner = null; } }
  function open(btn){
    const e = G[btn.dataset.minfo]; if (!e) return;
    if (owner === btn) { close(); return; }
    close(); owner = btn; btn.setAttribute('aria-expanded','true');
    pop = document.createElement('div'); pop.className = 'minfo-pop'; pop.setAttribute('role','dialog'); pop.id = 'minfoPop';
    pop.setAttribute('aria-label', e.title);
    pop.innerHTML = `<button class="mx" aria-label="Close">×</button><h4>${esc(e.title)}</h4><p>${esc(e.text)}</p>${e.formula?`<div class="mf"><b>How it's calculated</b>${esc(e.formula)}</div>`:''}`;
    document.body.appendChild(pop);
    pop.querySelector('.mx').onclick = ev => { ev.stopPropagation(); const b = owner; close(); if (b) b.focus(); };
    place();
  }
  function place(){
    if (!pop || !owner) return;
    const r = owner.getBoundingClientRect();
    if (!document.contains(owner) || r.bottom < 0 || r.top > window.innerHeight) { close(); return; }
    const w = pop.offsetWidth, h = pop.offsetHeight;
    const left = Math.min(Math.max(8, r.left - 12), window.innerWidth - w - 8);
    let top = r.bottom + 6; if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    pop.style.left = left + 'px'; pop.style.top = top + 'px';
  }
  function make(key, label){
    const b = document.createElement('button'); b.type = 'button'; b.className = 'minfo'; b.dataset.minfo = key;
    b.setAttribute('aria-label', 'What is ' + (G[key].title || label) + '?'); b.setAttribute('aria-expanded','false');
    b.setAttribute('aria-haspopup','dialog');
    b.addEventListener('click', ev => { ev.preventDefault(); ev.stopPropagation(); open(b); });
    b.addEventListener('mousedown', ev => ev.stopPropagation());
    return b;
  }
  // the label text of an element, ignoring nested blocks (e.g. a sub-label under a column header)
  function label(el){
    let t = '';
    for (const n of el.childNodes) { if (n.nodeType === 3) t += n.textContent; else if (n.nodeType === 1 && /^(B|STRONG|SPAN|EM|A)$/.test(n.tagName) && !n.classList.contains('minfo')) t += n.textContent; else if (n.nodeType === 1 && n.tagName === 'BR') break; }
    return norm(t);
  }
  const SEL = 'th, .kpi .l, .kpis span.small, h2, h3, [data-info]';
  function scan(){
    document.querySelectorAll(SEL).forEach(el => {
      if (el.dataset.minfoDone || el.closest('.minfo-pop, .mpop, .mbar, #guide-toc')) return;
      const key = el.dataset.info || byLabel[label(el)];
      el.dataset.minfoDone = '1';
      if (!key || !G[key]) return;
      el.appendChild(make(key, label(el)));
    });
    document.querySelectorAll('button, a.btn').forEach(el => {
      if (el.dataset.minfoDone || el.classList.contains('minfo') || el.closest('.minfo-pop, .mpop, .mbar, .seg, .vt-tabs, nav, [role=tablist]')) return;
      el.dataset.minfoDone = '1';
      const key = byBtn[norm(el.textContent)];
      if (!key) return;
      const nx = el.nextElementSibling; if (nx && nx.classList.contains('minfo')) return;
      el.insertAdjacentElement('afterend', make(key, el.textContent));
    });
  }
  let queued = false;
  const q = () => { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; scan(); }); };
  document.addEventListener('click', ev => { if (pop && !pop.contains(ev.target)) close(); });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && pop) { const b = owner; close(); if (b && document.contains(b)) b.focus(); } });
  window.addEventListener('scroll', place, true);
  window.addEventListener('resize', place);
  function start(){ scan(); new MutationObserver(muts => { if (muts.some(m => m.addedNodes.length)) { if (owner && !document.contains(owner)) close(); q(); } }).observe(document.body, {childList:true, subtree:true}); }
  window.MINFO_scan = scan;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
