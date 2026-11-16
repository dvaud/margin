"""Runs a real view of the page in Node, with the real lib.js and the modules it imports, under a fake DOM (0.19.9).

A test writes a probe: JavaScript with several `scenario(name, async (t) => {...})` calls, each returning what a person
would notice. `run_views(probe, tmp)` runs it in one Node process and returns {name: result}; reading a result fails
when its scenario threw, logged an error or made a server call it did not expect. Inside a scenario `t` offers:

  t.answer("PUT /api/x", reply)      the server's answer to a call: an object, (body, path, method) => object, or
                                     t.fail(status, message); a key without a method matches any; a key may end in
                                     "?*" (any query) or be a RegExp. t.calls lists each call {method, path, body,
                                     headers}.
  t.state(state, {project, hash})    App.state (settings, projects…) and the location hash; t.navs: hashes set since
  await t.render(VIEW, "renderX", params, query)   imports static/<VIEW> and renders it into #view's page
  await t.module(PATH)               a module of static/, to call what it exports
  t.text(el?) / t.buttons(el?) / t.find(label) / t.field(label) / t.focused() / t.hidden(el) / t.toasts()
  await t.click(label) / t.type(label, text) / t.press(key) / t.settle(ms)   act, then let promises and timers run
  t.layout(el => rect) / t.scrolls / t.select(textNode, start, end)   where things are on the screen (and their sizes:
                                     clientWidth, offsetWidth… in the rect), scrolling, a selection
  await t.resize()                   tells every ResizeObserver its elements changed size

`text()` is what a person sees: folded <details> show only their summary, hidden elements and icons are left out.
Timers are fake: t.settle(ms) moves the clock on by ms and runs what falls due. Tests skip without Node.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "src" / "margin" / "gui" / "static"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node is not installed")

DOM = r"""
// ---- the document -------------------------------------------------------------------------------------------
const realImmediate = setImmediate;
const INLINE = new Set(["SPAN", "A", "STRONG", "EM", "B", "I", "MARK", "CODE", "SMALL", "LABEL", "TIME", "ABBR", "KBD", "SUP", "SUB", "BUTTON", "SUMMARY", "Q", "S"]);
const BOOL = ["hidden", "disabled", "checked", "open", "selected", "required", "readonly", "multiple"];
const PROPS = ["type", "name", "href", "title", "placeholder", "target", "rel", "for", "role", "download", "src", "alt", "lang", "dir", "accept", "maxlength", "min", "max", "step", "autocomplete", "spellcheck", "draggable"];
class Node {
  constructor() { this.childNodes = []; this.parentNode = null; this._ls = {}; }
  get firstChild() { return this.childNodes[0] || null; }
  get lastChild() { return this.childNodes[this.childNodes.length - 1] || null; }
  get parentElement() { return this.parentNode instanceof Element ? this.parentNode : null; }
  get nextSibling() { const p = this.parentNode; return p ? p.childNodes[p.childNodes.indexOf(this) + 1] || null : null; }
  get previousSibling() { const p = this.parentNode; return p ? p.childNodes[p.childNodes.indexOf(this) - 1] || null : null; }
  get isConnected() { let n = this; while (n.parentNode) n = n.parentNode; return n === globalThis.document; }
  get ownerDocument() { return globalThis.document; }
  _adopt(c) {
    if (c instanceof Fragment) return [...c.childNodes].map((x) => { c.removeChild(x); return x; });
    if (c.parentNode) c.parentNode.removeChild(c);
    return [c];
  }
  insertBefore(c, ref) {
    const kids = this._adopt(c);
    let i = ref ? this.childNodes.indexOf(ref) : -1;
    if (i < 0) i = this.childNodes.length;
    for (const k of kids) { k.parentNode = this; this.childNodes.splice(i++, 0, k); }
    return c;
  }
  appendChild(c) { return this.insertBefore(c, null); }
  removeChild(c) {
    this.childNodes = this.childNodes.filter((x) => x !== c); c.parentNode = null;
    if (c.contains && c.contains(document.activeElement)) document.activeElement = document.body;
    return c;
  }
  replaceChild(n, old) { this.insertBefore(n, old); this.removeChild(old); return old; }
  contains(n) { for (; n; n = n.parentNode) if (n === this) return true; return false; }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
  set textContent(v) { for (const c of [...this.childNodes]) this.removeChild(c); if (v !== "" && v != null) this.appendChild(new Text(String(v))); }
  addEventListener(t, f, o) { if (f) (this._ls[t] = this._ls[t] || []).push({ f, once: !!(o && o.once) }); }
  removeEventListener(t, f) { this._ls[t] = (this._ls[t] || []).filter((x) => x.f !== f); }
  dispatchEvent(e) {
    if (!e.target) e.target = this;
    for (let n = this; n; n = n === globalThis.document ? winTarget : n.parentNode) {
      e.currentTarget = n === winTarget ? globalThis : n;
      for (const l of [...(n._ls[e.type] || [])]) {
        if (l.once) n.removeEventListener(e.type, l.f);
        try { typeof l.f === "function" ? l.f.call(n, e) : l.f.handleEvent(e); } catch (err) { report(err); }
      }
      if (e._stop || e.bubbles === false) break;
    }
    e.currentTarget = null;
    return !e.defaultPrevented;
  }
  // the parts other nodes have in a browser: append, before, remove… and the queries
  append(...xs) { for (const x of xs) this.appendChild(typeof x === "string" ? new Text(x) : x); }
  prepend(...xs) { const first = this.firstChild; for (const x of xs) this.insertBefore(typeof x === "string" ? new Text(x) : x, first); }
  replaceChildren(...xs) { for (const c of [...this.childNodes]) this.removeChild(c); this.append(...xs); }
  before(...xs) { for (const x of xs) this.parentNode.insertBefore(typeof x === "string" ? new Text(x) : x, this); }
  after(...xs) { const next = this.nextSibling; for (const x of xs) this.parentNode.insertBefore(typeof x === "string" ? new Text(x) : x, next); }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  replaceWith(...xs) { const p = this.parentNode; if (!p) return; const next = this.nextSibling; p.removeChild(this); for (const x of xs) p.insertBefore(typeof x === "string" ? new Text(x) : x, next); }
  get children() { return this.childNodes.filter((c) => c instanceof Element); }
  get firstElementChild() { return this.children[0] || null; }
  get lastElementChild() { const k = this.children; return k[k.length - 1] || null; }
  get childElementCount() { return this.children.length; }
  *_all() { for (const c of this.children) { yield c; yield* c._all(); } }
  querySelectorAll(sel) { const s = parseSel(sel); return [...this._all()].filter((el) => matchSel(el, s, this)); }
  querySelector(sel) { const s = parseSel(sel); for (const el of this._all()) if (matchSel(el, s, this)) return el; return null; }
  getElementById(id) { for (const el of this._all()) if (el.id === id) return el; return null; }
}
class Text extends Node {
  constructor(t) { super(); this.data = String(t); }
  get textContent() { return this.data; } set textContent(v) { this.data = String(v); }
  get nodeValue() { return this.data; }
  get nodeType() { return 3; }
}
class Fragment extends Node { get nodeType() { return 11; } }
Object.assign(Node, { ELEMENT_NODE: 1, TEXT_NODE: 3, DOCUMENT_FRAGMENT_NODE: 11 });
globalThis.NodeFilter = { SHOW_ALL: 0xFFFFFFFF, SHOW_ELEMENT: 1, SHOW_TEXT: 4 };
const camel = (k) => k.replace(/-(\w)/g, (_, c) => c.toUpperCase());
const kebab = (k) => k.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
class Element extends Node {
  constructor(tag, ns) {
    super(); this.tagName = ns ? tag : tag.toUpperCase(); this.localName = tag.toLowerCase(); this.namespaceURI = ns || null; this.attributes = {};
    this.style = { setProperty(k, v) { this[k] = v; }, removeProperty(k) { delete this[k]; }, getPropertyValue(k) { return this[k] || ""; } };
    const self = this;
    this.dataset = new Proxy({}, {
      get: (_, k) => (typeof k === "string" ? self.getAttribute("data-" + kebab(k)) ?? undefined : undefined),
      set: (_, k, v) => { self.setAttribute("data-" + kebab(k), v); return true; },
      deleteProperty: (_, k) => { self.removeAttribute("data-" + kebab(k)); return true; },
      has: (_, k) => self.hasAttribute("data-" + kebab(k)),
      ownKeys: () => Object.keys(self.attributes).filter((a) => a.startsWith("data-")).map((a) => camel(a.slice(5))),
      getOwnPropertyDescriptor: (_, k) => (self.hasAttribute("data-" + kebab(k)) ? { enumerable: true, configurable: true, value: self.getAttribute("data-" + kebab(k)) } : undefined),
    });
    const words = () => (self.attributes.class || "").split(/\s+/).filter(Boolean);
    const set = (ws) => { self.attributes.class = [...new Set(ws)].join(" "); };
    this.classList = {
      add: (...c) => set([...words(), ...c]), remove: (...c) => set(words().filter((x) => !c.includes(x))),
      contains: (c) => words().includes(c),
      toggle: (c, force) => { const on = force === undefined ? !words().includes(c) : !!force; on ? set([...words(), c]) : set(words().filter((x) => x !== c)); return on; },
      replace: (a, b) => set(words().map((x) => (x === a ? b : x))),
      get length() { return words().length; }, [Symbol.iterator]: () => words()[Symbol.iterator](),
    };
    this.scrollTop = 0; this.scrollLeft = 0;
  }
  get nodeType() { return 1; }
  get className() { return this.attributes.class || ""; } set className(v) { this.attributes.class = String(v); }
  get id() { return this.attributes.id || ""; } set id(v) { this.attributes.id = String(v); }
  get tabIndex() { return this.attributes.tabindex === undefined ? (/^(BUTTON|A|INPUT|SELECT|TEXTAREA|SUMMARY)$/.test(this.tagName) ? 0 : -1) : Number(this.attributes.tabindex); }
  set tabIndex(v) { this.attributes.tabindex = String(v); }
  setAttribute(k, v) {
    k = String(k).toLowerCase();
    this.attributes[k] = String(v);
    if (k === "value" && !this._dirty) this._value = undefined;
    if (k === "checked") this._checked = undefined;
  }
  getAttribute(k) { k = String(k).toLowerCase(); return k in this.attributes ? this.attributes[k] : null; }
  hasAttribute(k) { return String(k).toLowerCase() in this.attributes; }
  removeAttribute(k) { delete this.attributes[String(k).toLowerCase()]; }
  toggleAttribute(k, force) { const on = force === undefined ? !this.hasAttribute(k) : !!force; on ? this.setAttribute(k, "") : this.removeAttribute(k); return on; }
  get value() {
    if (this.tagName === "SELECT") { const o = this.querySelectorAll("option"); const s = o.find((x) => x.selected) || o[0]; return s ? s.value : ""; }
    if (this.tagName === "OPTION") return this.getAttribute("value") ?? this.textContent;
    if (this._value !== undefined) return this._value;
    if (this.tagName === "TEXTAREA") return this.textContent;
    return this.getAttribute("value") ?? (this.getAttribute("type") === "checkbox" ? "on" : "");
  }
  set value(v) {
    if (this.tagName === "SELECT") { for (const o of this.querySelectorAll("option")) o.selected = o.value === String(v); return; }
    this._value = String(v); this._dirty = true;
  }
  get checked() { return this._checked !== undefined ? this._checked : this.hasAttribute("checked"); }
  set checked(v) { this._checked = !!v; }
  get selectedIndex() { return this.querySelectorAll("option").findIndex((o) => o.selected); }
  get options() { return this.querySelectorAll("option"); }
  get labels() { return this.id ? document.querySelectorAll(`label[for="${this.id}"]`) : []; }
  get innerText() { return seen(this); }
  set innerHTML(v) { if (v !== "") throw new Error("innerHTML is not allowed"); this.textContent = ""; }
  // sizes are 0 unless t.layout's answer for the element names them ({clientWidth: 900, offsetWidth: 120…})
  get offsetHeight() { return sized(this, "offsetHeight"); } get offsetWidth() { return sized(this, "offsetWidth"); }
  get clientHeight() { return sized(this, "clientHeight"); } get clientWidth() { return sized(this, "clientWidth"); }
  get scrollHeight() { return sized(this, "scrollHeight"); } get scrollWidth() { return sized(this, "scrollWidth"); }
  get offsetTop() { return 0; } get offsetParent() { return this.parentElement; }
  // a table's parts, as the browser offers them
  get tHead() { return this.tagName === "TABLE" ? this.children.find((c) => c.tagName === "THEAD") || null : undefined; }
  get tBodies() { return this.tagName === "TABLE" ? this.children.filter((c) => c.tagName === "TBODY") : undefined; }
  get cells() { return this.children.filter((c) => c.tagName === "TD" || c.tagName === "TH"); }
  get cellIndex() { return this.parentNode ? this.parentNode.cells.indexOf(this) : -1; }
  getBoundingClientRect() { const r = this._rect || (layout && layout(this)) || { top: 0, left: 0, width: 0, height: 0 }; return { ...r, x: r.left, y: r.top, bottom: r.top + r.height, right: r.left + r.width }; }
  getClientRects() { return [this.getBoundingClientRect()]; }
  focus(o) { if (this.disabled) return; const was = document.activeElement; document.activeElement = this; if (was !== this) this.dispatchEvent(new Event("focus", { bubbles: false })); }
  blur() { if (document.activeElement === this) document.activeElement = document.body; }
  select() { this._selected = true; }
  setSelectionRange(a, b) { this.selectionStart = a; this.selectionEnd = b; }
  scrollIntoView(o) { scrolls.push({ into: describe(this), how: o === undefined ? null : o }); }
  scrollTo(...a) { scrolls.push({ el: describe(this), to: a[0] }); }
  scrollBy() {}
  animate() { return { finished: Promise.resolve(), cancel() {}, onfinish: null }; }
  matches(sel) { return matchSel(this, parseSel(sel), null); }
  closest(sel) { const s = parseSel(sel); for (let n = this; n instanceof Element; n = n.parentNode) if (matchSel(n, s, null)) return n; return null; }
  click() {
    if (this.disabled) return;
    if (this.tagName === "INPUT" && /^(checkbox|radio)$/.test(this.getAttribute("type"))) {
      this.checked = this.getAttribute("type") === "radio" ? true : !this.checked;
    }
    const go = this.dispatchEvent(new Event("click", { bubbles: true }));
    if (go && this.tagName === "SUMMARY" && this.parentNode && this.parentNode.tagName === "DETAILS") {
      this.parentNode.open = !this.parentNode.open; this.parentNode.dispatchEvent(new Event("toggle", { bubbles: false }));
    }
    if (this.tagName === "INPUT" && /^(checkbox|radio)$/.test(this.getAttribute("type"))) {
      this.dispatchEvent(new Event("input", { bubbles: true })); this.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (go && this.tagName === "LABEL" && this.getAttribute("for")) { const c = document.getElementById(this.getAttribute("for")); if (c && c !== this) c.click(); }
    // a submit button (a button of no type, or type submit) submits its form, as in a browser
    if (go && this.tagName === "BUTTON" && (this.getAttribute("type") || "submit") === "submit") { const f = this.closest("form"); if (f) f.requestSubmit(this); }
  }
  requestSubmit(submitter) { this.dispatchEvent(new Event("submit", { bubbles: true, submitter: submitter || null })); }
  showModal() { this.open = true; dialogsOpened.push(seen(this.querySelector("h2") || this)); }
  show() { this.open = true; }
  close(v) { if (!this.open) return; this.open = false; this.returnValue = v; this.dispatchEvent(new Event("close", { bubbles: false })); }
  cloneNode(deep) {
    const c = new Element(this.localName, this.namespaceURI); Object.assign(c.attributes, this.attributes);
    if (deep) for (const k of this.childNodes) c.appendChild(k instanceof Element ? k.cloneNode(true) : new Text(k.textContent));
    return c;
  }
}
for (const b of BOOL) Object.defineProperty(Element.prototype, b, { get() { return this.hasAttribute(b); }, set(v) { this.toggleAttribute(b, !!v); }, configurable: true });
Object.defineProperty(Element.prototype, "checked", { get() { return this._checked !== undefined ? this._checked : this.hasAttribute("checked"); }, set(v) { this._checked = !!v; }, configurable: true });
for (const p of PROPS) Object.defineProperty(Element.prototype, camel(p) === "for" ? "htmlFor" : camel(p), { get() { return this.getAttribute(p) ?? ""; }, set(v) { this.setAttribute(p, v); }, configurable: true });
// rows: a textarea's height in lines; a table's (or its head's or body's) rows
Object.defineProperty(Element.prototype, "rows", { get() {
  if (this.tagName === "TABLE") return this.querySelectorAll("tr").filter((r) => r.parentNode === this || r.parentNode.parentNode === this);
  if (/^(THEAD|TBODY|TFOOT)$/.test(this.tagName)) return this.children.filter((c) => c.tagName === "TR");
  return Number(this.getAttribute("rows") || 2);
}, set(v) { this.setAttribute("rows", v); }, configurable: true });

// ---- simple selectors: tag, #id, .class, [a], [a=v], :not(…), :nth-child(n), :scope, :checked, :disabled; " ", ">", ","
function parseSel(sel) {
  return splitTop(String(sel), ",").map((part) => {
    const steps = []; let comb = " ";
    for (const tok of part.trim().replace(/\s*>\s*/g, " > ").split(/\s+(?![^\[(]*[\])])/)) {
      if (tok === ">") { comb = ">"; continue; }
      if (tok) { steps.push({ comb, c: compound(tok) }); comb = " "; }
    }
    return steps;
  });
}
function splitTop(s, ch) { const out = []; let d = 0, cur = ""; for (const c of s) { if (c === "(" || c === "[") d++; if (c === ")" || c === "]") d--; if (c === ch && !d) { out.push(cur); cur = ""; } else cur += c; } out.push(cur); return out; }
function compound(tok) {
  const c = { tag: null, ids: [], cls: [], attrs: [], nots: [], nth: null, scope: false, pseudo: [] };
  const rx = /^\*|^[a-zA-Z][\w-]*|#((?:\\.|[\w-])+)|\.((?:\\.|[\w-])+)|\[\s*([\w-]+)\s*(?:([*^$~]?=)\s*(?:"([^"]*)"|'([^']*)'|([^\]\s]*)))?\s*\]|:not\(((?:[^()]|\([^)]*\))*)\)|:nth-child\((\d+)\)|:([\w-]+)/y;
  let m; rx.lastIndex = 0;
  while (rx.lastIndex < tok.length && (m = rx.exec(tok))) {
    const unesc = (s) => s.replace(/\\(.)/g, "$1");
    if (m[0] === "*") continue;
    if (m.index === 0 && /^[a-zA-Z]/.test(m[0]) && !m[0].startsWith(":")) c.tag = m[0].toUpperCase();
    else if (m[1]) c.ids.push(unesc(m[1]));
    else if (m[2]) c.cls.push(unesc(m[2]));
    else if (m[3]) c.attrs.push([m[3].toLowerCase(), m[4] || null, m[5] ?? m[6] ?? m[7] ?? null]);
    else if (m[8] !== undefined) c.nots.push(parseSel(m[8]));
    else if (m[9]) c.nth = Number(m[9]);
    else if (m[10] === "scope") c.scope = true;
    else if (m[10]) c.pseudo.push(m[10]);
  }
  if (rx.lastIndex !== tok.length) throw new Error(`the fake DOM cannot read the selector ${JSON.stringify(tok)}`);
  return c;
}
function one(el, c, scope) {
  if (!(el instanceof Element)) return false;
  if (c.scope) return el === scope;
  if (c.tag && el.tagName.toUpperCase() !== c.tag) return false;
  for (const id of c.ids) if (el.id !== id) return false;
  for (const k of c.cls) if (!el.classList.contains(k)) return false;
  for (const [a, op, v] of c.attrs) {
    const got = el.getAttribute(a);
    if (got === null) return false;
    if (op === "=" && got !== v) return false;
    if (op === "~=" && !got.split(/\s+/).includes(v)) return false;
    if (op === "^=" && !got.startsWith(v)) return false;
    if (op === "$=" && !got.endsWith(v)) return false;
    if (op === "*=" && !got.includes(v)) return false;
  }
  for (const n of c.nots) if (matchSel(el, n, scope)) return false;
  if (c.nth && (!el.parentNode || el.parentNode.children.indexOf(el) + 1 !== c.nth)) return false;
  for (const p of c.pseudo) {
    if (p === "checked" && !el.checked) return false;
    if (p === "disabled" && !el.disabled) return false;
    if (p === "first-child" && el.parentNode && el.parentNode.children[0] !== el) return false;
  }
  return true;
}
function matchSteps(el, steps, i, scope) {
  if (!one(el, steps[i].c, scope)) return false;
  if (i === 0) return true;
  if (steps[i].comb === ">") return el.parentNode instanceof Element && matchSteps(el.parentNode, steps, i - 1, scope);
  for (let p = el.parentNode; p instanceof Element; p = p.parentNode) if (matchSteps(p, steps, i - 1, scope)) return true;
  return false;
}
function matchSel(el, list, scope) { return list.some((steps) => matchSteps(el, steps, steps.length - 1, scope)); }

class Event {
  constructor(type, o = {}) { this.type = type; this.bubbles = true; Object.assign(this, o); this.defaultPrevented = false; this.timeStamp = clock.now; }
  preventDefault() { this.defaultPrevented = true; } stopPropagation() { this._stop = true; } stopImmediatePropagation() { this._stop = true; }
}
class CustomEvent extends Event { constructor(t, o = {}) { super(t, o); this.detail = o.detail; } }
class Observer { constructor(fn) { this.fn = fn; } observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
// a ResizeObserver answers t.resize(): each one still observing is called with the elements it watches
const resizers = new Set();
class Resizer extends Observer {
  observe(el) { (this.els = this.els || []).push(el); resizers.add(this); }
  unobserve(el) { this.els = (this.els || []).filter((x) => x !== el); }
  disconnect() { resizers.delete(this); }
}

// ---- the clock: timers wait for t.settle(ms)
const clock = { now: 0, timers: [], seq: 0 };
const addTimer = (fn, ms, every) => { const id = ++clock.seq; clock.timers.push({ id, fn, at: clock.now + Math.max(0, Number(ms) || 0), every: every ? Math.max(1, Number(ms) || 1) : 0 }); return id; };
const dropTimer = (id) => { clock.timers = clock.timers.filter((x) => x.id !== id); };

// ---- what the scenario sees and records
let scrolls = [], dialogsOpened = [], errors = [], selection = null, clipboard = [], layout = null;
const sized = (el, k) => { const r = el._rect || (layout && layout(el)); return r && r[k] != null ? r[k] : 0; };
function report(e) { errors.push(String((e && e.stack) || e).split("\n").slice(0, 4).join(" | ")); }
const g = globalThis;
Object.assign(g, { Node, Element, HTMLElement: Element, SVGElement: Element, HTMLInputElement: Element, HTMLDialogElement: Element, Text, DocumentFragment: Fragment,
  Event, CustomEvent, KeyboardEvent: Event, MouseEvent: Event, FocusEvent: Event, InputEvent: Event, HashChangeEvent: Event, PopStateEvent: Event,
  IntersectionObserver: Observer, ResizeObserver: Resizer, MutationObserver: Observer,
  CSS: { escape: (s) => String(s).replace(/[^\w-]/g, (c) => "\\" + c), supports: () => true },
  setTimeout: (fn, ms) => addTimer(fn, ms, false), clearTimeout: dropTimer, setInterval: (fn, ms) => addTimer(fn, ms, true), clearInterval: dropTimer,
  requestAnimationFrame: (fn) => addTimer(() => fn(clock.now), 16, false), cancelAnimationFrame: dropTimer,
  requestIdleCallback: (fn) => addTimer(() => fn({ timeRemaining: () => 50, didTimeout: false }), 1, false), cancelIdleCallback: dropTimer,
  innerWidth: 1280, innerHeight: 800, scrollX: 0, scrollY: 0, pageYOffset: 0, devicePixelRatio: 1,
  scrollTo: (...a) => scrolls.push({ window: true, to: a.length > 1 ? a : a[0] }), scrollBy: (...a) => scrolls.push({ window: true, by: a.length > 1 ? a : a[0] }),
  getComputedStyle: () => ({ getPropertyValue: () => "", display: "block" }),
  matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }),
  getSelection: () => selection || { toString: () => "", rangeCount: 0, isCollapsed: true, removeAllRanges() {}, addRange() {}, getRangeAt() { return null; } },
  history: { replaceState() {}, pushState() {}, back() {}, state: null },
  alert() {}, confirm: () => true, open: (...a) => { opened.push(a[0]); return null; },
});
Object.defineProperty(g, "navigator", { configurable: true, writable: true, value: { userAgent: "Mozilla/5.0 (Macintosh)", platform: "MacIntel", language: "en-GB", languages: ["en-GB"], clipboard: { writeText: async (x) => { clipboard.push(x); } }, onLine: true } });
const winTarget = new Node();
g.addEventListener = (t, f, o) => winTarget.addEventListener(t, f, o);
g.removeEventListener = (t, f) => winTarget.removeEventListener(t, f);
g.dispatchEvent = (e) => { e.target = e.target || g; e.currentTarget = g; for (const l of [...(winTarget._ls[e.type] || [])]) { try { l.f(e); } catch (err) { report(err); } } return !e.defaultPrevented; };
g.window = g; g.self = g;
const opened = [];
function makeStorage() { let m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), clear: () => m.clear(), key: (i) => [...m.keys()][i] ?? null, get length() { return m.size; } }; }
Object.defineProperty(g, "sessionStorage", { configurable: true, writable: true, value: makeStorage() });
Object.defineProperty(g, "localStorage", { configurable: true, writable: true, value: makeStorage() });
let navs = [];
const loc = { _hash: "", pathname: "/", search: "", origin: "http://127.0.0.1:8766", host: "127.0.0.1:8766", protocol: "http:",
  get hash() { return this._hash; }, set hash(v) { v = String(v); if (v && !v.startsWith("#")) v = "#" + v; this._hash = v; navs.push(v); },
  get href() { return this.origin + this.pathname + this._hash; }, set href(v) { navs.push(String(v)); }, reload() { navs.push("reload"); }, assign(v) { navs.push(String(v)); }, replace(v) { navs.push(String(v)); } };
g.location = loc;
class Doc extends Node {
  constructor() {
    super(); this.documentElement = new Element("html"); this.appendChild(this.documentElement);
    this.head = new Element("head"); this.body = new Element("body"); this.documentElement.append(this.head, this.body);
    this.activeElement = this.body; this.title = ""; this.hidden = false; this.visibilityState = "visible"; this.readyState = "complete";
  }
  createElement(t) { return new Element(t); }
  createElementNS(ns, t) { return new Element(t, ns); }
  createTextNode(t) { return new Text(t); }
  createDocumentFragment() { return new Fragment(); }
  createRange() { return { setStart() {}, setEnd() {}, selectNodeContents() {}, collapse() {}, getBoundingClientRect: () => ({ top: 0, left: 0, width: 0, height: 0, bottom: 0, right: 0 }), getClientRects: () => [] }; }
  createTreeWalker(root, what) {
    const nodes = []; const walk = (n) => { for (const c of n.childNodes) { if (c instanceof Text) nodes.push(c); else walk(c); } }; walk(root);
    let i = -1; return { currentNode: root, nextNode() { i++; this.currentNode = nodes[i] || null; return this.currentNode; } };
  }
  get defaultView() { return g; }
  hasFocus() { return true; }
  elementFromPoint() { return null; }
  execCommand() { return true; }
}
g.document = new Doc();
g.Document = Doc;

// ---- reading the page as a person does --------------------------------------------------------------------
function hiddenEl(el) {
  for (let n = el; n instanceof Element; n = n.parentNode) {
    if (n.hidden || (n.style && n.style.display === "none") || n.getAttribute("aria-hidden") === "true" && n.tagName === "svg") return true;
    const p = n.parentNode;
    if (p instanceof Element && p.tagName === "DETAILS" && !p.open && n.tagName !== "SUMMARY") return true;
    if (n.tagName === "DIALOG" && !n.open) return true;
  }
  return !el.isConnected;
}
function seenParts(n, out, all) {
  if (n instanceof Text) { out.push(n.data); return; }
  if (!(n instanceof Element)) { for (const c of n.childNodes) seenParts(c, out, all); return; }
  if (n.namespaceURI || n.tagName === "STYLE" || n.tagName === "SCRIPT") return;
  if (!all && (n.hidden || (n.style && n.style.display === "none"))) return;
  if (n.tagName === "INPUT" || n.tagName === "TEXTAREA" || n.tagName === "SELECT") { return; }
  const block = !INLINE.has(n.tagName), gap = block ? "\n" : n.tagName === "MARK" ? "" : " ";
  out.push(gap);
  for (const c of n.childNodes) {
    if (!all && n.tagName === "DETAILS" && !n.open && !(c instanceof Element && c.tagName === "SUMMARY")) continue;
    seenParts(c, out, all);
  }
  out.push(gap);
}
function seen(el, all = false) {
  const out = []; seenParts(el, out, all);
  return out.join("").split("\n").map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean).join("\n");
}
const flat1 = (s) => String(s || "").replace(/\s+/g, " ").trim();
function labelOf(el) {
  if (!el) return null;
  const aria = el.getAttribute("aria-label");
  if (aria) return flat1(aria);
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) {
    const l = el.labels[0] || el.closest("label");
    return l ? flat1(seen(l, true)) : flat1(el.getAttribute("placeholder") || el.getAttribute("title") || "");
  }
  return flat1(seen(el, true));
}
function describe(el) {
  if (!el || el === document.body) return null;
  return { tag: el.tagName.toLowerCase(), label: labelOf(el), cls: el.className || undefined };
}
const ACTIONS = "button, a, summary, [role=button], [role=radio], [role=tab], [role=menuitem], [role=checkbox], [role=switch], input[type=checkbox], input[type=radio]";
function controls(root, sel = ACTIONS) { return root.querySelectorAll(sel).filter((el) => !hiddenEl(el)); }
"""

HARNESS = r"""
// ---- the scenarios ----------------------------------------------------------------------------------------
const LIB = await import(new URL("lib.js", STATIC).href);
const results = {};
let current = null;
process.on("unhandledRejection", (e) => report(e));
process.on("uncaughtException", (e) => report(e));
console.error = (...a) => errors.push(a.map((x) => (x && x.stack) ? x.stack.split("\n").slice(0, 3).join(" | ") : String(x)).join(" "));

async function drain(n = 6) { for (let i = 0; i < n; i++) await new Promise((r) => realImmediate(r)); }
async function settle(ms = 0) {
  const until = clock.now + ms;
  for (let guard = 0; guard < 5000; guard++) {
    await drain();
    const due = clock.timers.filter((x) => x.at <= until).sort((a, b) => a.at - b.at || a.id - b.id)[0];
    if (!due) break;
    clock.now = Math.max(clock.now, due.at);
    if (due.every) due.at = clock.now + due.every; else dropTimer(due.id);
    try { due.fn(); } catch (e) { report(e); }
  }
  clock.now = Math.max(clock.now, until);
  await drain();
}

function newTest(name) {
  const table = [], calls = [], unexpected = [];
  const t = {
    name, calls, unexpected, LIB, get navs() { return navs; }, get scrolls() { return scrolls; }, get dialogsOpened() { return dialogsOpened; },
    get clipboard() { return clipboard; }, get errors() { return errors; }, clock,
    view: null,
    fail: (status, message, extra = {}) => ({ __fail: true, status, body: { error: message, ...extra } }),
    answer(key, reply) { table.unshift({ key, reply }); return t; },
    state(state = {}, o = {}) {
      LIB.App.state = { projects: [{ name: o.project || "Study" }], project: o.project || "Study", settings: {}, statuses: [], ...state };
      LIB.App.project = o.project === undefined ? (LIB.App.state.project) : o.project;
      if (o.hash !== undefined) loc._hash = o.hash;
      return t;
    },
    module: (path) => import(new URL(path, STATIC).href),
    async render(view, fn, params = [], query = {}) {
      const mod = await import(new URL(view, STATIC).href);
      if (typeof mod[fn] !== "function") throw new Error(`${view} has no export ${fn}`);
      const page = mk("div", { class: "page" }); document.getElementById("view").appendChild(page);
      t.view = page;
      const r = mod[fn](page, params, query);
      t.cleanup = await r;
      await settle();
      return page;
    },
    settle,
    text: (el) => seen(el || document.body),
    allText: (el) => seen(el || document.body, true),
    buttons: (el) => controls(el || document.body).map((b) => ({ label: labelOf(b), disabled: !!b.disabled || b.getAttribute("aria-disabled") === "true" })),
    labels: (el) => controls(el || document.body).map(labelOf),
    find(label, o = {}) {
      const root = o.within || document.body;
      const pool = o.sel ? root.querySelectorAll(o.sel) : controls(root);
      const match = (el) => (label instanceof RegExp ? label.test(labelOf(el)) : labelOf(el) === label);
      const hits = pool.filter((el) => (o.hidden || !hiddenEl(el)) && match(el));
      return hits[o.nth || 0] || null;
    },
    field(label, o = {}) {
      const root = o.within || document.body;
      const hits = root.querySelectorAll("input, textarea, select").filter((el) => !hiddenEl(el) && (label instanceof RegExp ? label.test(labelOf(el)) : labelOf(el) === label));
      return hits[o.nth || 0] || null;
    },
    async click(label, o = {}) {
      const el = typeof label === "object" && !(label instanceof RegExp) ? label : t.find(label, o);
      if (!el) throw new Error(`no control labelled ${label} in view; there are: ${JSON.stringify(t.labels(o.within))}`);
      if (el.disabled) throw new Error(`${labelOf(el)} is disabled`);
      if (el.focus) el.focus();
      el.click();
      await settle(o.wait || 0);
      return el;
    },
    async type(label, text, o = {}) {
      const el = typeof label === "object" && !(label instanceof RegExp) ? label : t.field(label, o);
      if (!el) throw new Error(`no field labelled ${label}`);
      el.focus();
      if (el.tagName === "SELECT") el.value = text; else { el.value = text; }
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      await settle(o.wait || 0);
      return el;
    },
    async press(key, el = document.activeElement, o = {}) {
      const ev = new Event("keydown", { key, bubbles: true, shiftKey: !!o.shift, metaKey: !!o.meta, ctrlKey: !!o.ctrl });
      const go = el.dispatchEvent(ev);
      // Escape in a modal <dialog>: the browser fires "cancel" on it, and closes it unless that is prevented
      const dlg = key === "Escape" && go && document.querySelectorAll("dialog").filter((d) => d.open && d.isConnected).pop();
      if (dlg) { const c = new Event("cancel", { bubbles: false }); if (dlg.dispatchEvent(c)) dlg.close(); }
      await settle(o.wait || 0);
    },
    focused: () => describe(document.activeElement),
    layout(fn) { layout = fn; },   // fn(el) -> {top, left, width, height, clientWidth…} or null: where elements are on the screen
    // the window or an element changed size: every ResizeObserver still observing is told, then timers run
    async resize(o = {}) { for (const r of [...resizers]) { try { r.fn((r.els || []).map((target) => ({ target })), r); } catch (e) { report(e); } } await settle(o.wait || 0); },
    hidden: (el) => !el || hiddenEl(el),
    dialogs: () => document.querySelectorAll("dialog").filter((d) => d.open && d.isConnected),
    dialog() { const d = t.dialogs().pop(); return d || null; },
    toasts: () => document.getElementById("toasts").children.map((x) => seen(x, true)),
    // a selection of the characters start..end of a text node, as a person drags over them
    select(node, start = 0, end = node.data.length) {
      const text = node.data.slice(start, end);
      selection = { toString: () => text, rangeCount: 1, isCollapsed: start === end, anchorNode: node, focusNode: node, removeAllRanges() { selection = null; }, addRange() {},
        getRangeAt: () => ({ getBoundingClientRect: () => ({ top: 100, left: 100, width: 50, height: 16, bottom: 116, right: 150 }), commonAncestorContainer: node,
          startContainer: node, endContainer: node, startOffset: start, endOffset: end, cloneContents: () => new Fragment() }) };
      return text;
    },
  };
  g.fetch = async (path, opts = {}) => {
    const method = (opts.method || "GET").toUpperCase();
    let body = opts.body;
    if (typeof body === "string") { try { body = JSON.parse(body); } catch (_) { /* text */ } }
    calls.push({ method, path, body: body === undefined ? null : body, headers: { ...(opts.headers || {}) } });
    const bare = path.split("?")[0];
    const hit = table.find(({ key }) => {
      if (key instanceof RegExp) return key.test(`${method} ${path}`);
      const [m, p] = key.includes(" ") ? key.split(" ") : [null, key];
      if (m && m !== method) return false;
      return p === path || (p.endsWith("?*") && p.slice(0, -2) === bare) || (!p.includes("?") && p === bare && !path.includes("?"));
    });
    let reply;
    if (hit) reply = typeof hit.reply === "function" ? await hit.reply(body, path, method) : hit.reply;
    else if (method === "GET" && bare === "/api/state") reply = LIB.App.state;
    else if (method === "GET" && bare === "/api/jobs") reply = { jobs: [] };
    else { unexpected.push(`${method} ${path}`); reply = { __fail: true, status: 599, body: { error: `the test did not expect ${method} ${path}` } }; }
    const fail = reply && reply.__fail;
    const status = fail ? reply.status : 200;
    const text = JSON.stringify(fail ? reply.body : (reply === undefined ? {} : reply));
    return { ok: !fail, status, statusText: String(status), headers: { get: () => null }, text: async () => text, json: async () => JSON.parse(text), blob: async () => new Blob([text]) };
  };
  return t;
}
const mk = (tag, attrs = {}, ...kids) => { const el = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v); el.append(...kids); return el; };

async function scenario(name, fn) {
  // a fresh page: the shell's three boxes, empty storage, the clock's timers dropped
  document.body.replaceChildren(mk("main", { id: "view" }), mk("div", { id: "dialogs" }), mk("div", { id: "toasts" }));
  document.activeElement = document.body;
  sessionStorage.clear(); localStorage.clear();
  clock.timers = []; resizers.clear(); navs = []; scrolls = []; dialogsOpened = []; errors = []; selection = null; clipboard = []; layout = null; loc._hash = "";
  const t = newTest(name);
  t.state();
  let value = null, threw = null;
  try { value = await fn(t); } catch (e) { threw = String((e && e.stack) || e).split("\n").slice(0, 5).join(" | "); }
  try { if (typeof t.cleanup === "function") t.cleanup(); } catch (_) { /* gone with the page */ }
  await drain();
  results[name] = { value: value === undefined ? null : value, threw, unexpected: t.unexpected, errors: [...errors] };
}
"""

END = r"""
process.stdout.write(JSON.stringify(results));
process.exit(0);
"""


class Scenarios(dict):
    """{scenario: what it returned}. Reading a scenario fails the test that reads it when that scenario threw, logged an
    error or made a server call it gave no answer for, so a broken view fails the tests of that scenario only."""

    def __init__(self, raw: dict, allow_errors: tuple[str, ...]):
        super().__init__({name: res["value"] for name, res in raw.items()})
        self.problems = {}
        for name, res in raw.items():
            said = []
            if res["threw"]:
                said.append(f"threw {res['threw']}")
            if res["unexpected"]:
                said.append(f"calls the test did not expect: {res['unexpected']}")
            errs = [e for e in res["errors"] if not any(a in e for a in allow_errors)]
            if errs:
                said.append(f"errors {errs}")
            if said:
                self.problems[name] = said

    def __getitem__(self, name):
        assert name not in self.problems, f"scenario {name!r}: " + "; ".join(self.problems[name])
        return super().__getitem__(name)


def run_views(probe: str, tmp: Path, *, allow_errors: tuple[str, ...] = ()) -> Scenarios:
    """Run a probe of scenarios in one Node process; returns {scenario: its value} (see Scenarios). An error whose text
    holds one of `allow_errors` is let through."""
    f = tmp / "views_probe.mjs"
    f.write_text(DOM + f"const STATIC = {json.dumps(STATIC.as_uri() + '/')};\n" + HARNESS + probe + END, encoding="utf-8")
    r = subprocess.run([NODE, str(f)], capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0, r.stderr[-4000:]
    return Scenarios(json.loads(r.stdout), allow_errors)
