// 16 November 2026: one person, two accounts (sync/selfsync.py). The Team page's People and settings, below the people:
// "Your other account". When the owner marked another account as this person (Use both computers), this account may
// send its private work (what it has not shared) to that account, and take that account's in, through the storage
// space only. Both accounts must turn it on, each on its own computer; either can stop at any time. The section shows
// the other account's name, when it joined and a check code (the same on both computers when each sees the other's
// real keys), so a person never turns it on for a stranger. Built on GET …/shared-folder ("self_sync") and
// PUT/DELETE …/space/self-sync (gui/api_space.py).
import { api, h, toast, showError, P, button, dialog, confirmDialog, listRow, listGroup, personMark, notice, helpMark } from "../lib.js";

const S = (project) => `/api/projects/${P(project)}/space/self-sync`;
const when = (iso) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "");
const HELP = "Your private work is what you have not shared: checks, sets of themes, codebooks, notes, research log entries and links between terms. "
  + "It goes to your other account only, sealed so that only that account can open it, and it stays private there: it is never sent to colleagues. "
  + "Either account can then share or take back what the other made (the account that made it does so at its next round). The owner’s mark that both accounts are you is not enough: each account turns this on itself.";

function section(key, title, ...children) {
  const id = `team-h-${key}`;
  return h("section", { class: `team-section team-sec-${key}`, "aria-labelledby": id, dataset: { key } },
    h("h3", { class: "team-h", id }, title), ...children.filter((c) => c !== null && c !== undefined));
}

async function turnOn(ctx, c) {
  const ok = await dialog({ title: `Send your private work to ${c.name}?`, body: h("div", {},
    h("p", {}, `${c.name} is in the team since ${when(c.since) || "an unknown day"}. Your private work goes to that account only, sealed so that only it can open it, and stays private there.`),
    h("p", {}, "Nothing goes until you turn this on there too, on your other computer. Check first that your other computer shows the same check code:"),
    h("p", { class: "mono team-self-code", id: "team-self-dlg-code" }, c.code || "—"),
    h("p", { class: "muted small" }, "A different code means it is not your other account: do not turn it on. You can stop at any time; what already arrived stays.")),
  actions: [{ text: "Cancel", value: null }, { text: "Send my private work", value: true, primary: true, id: "team-self-dlg-ok" }] });
  if (!ok) return;
  try {
    await api("PUT", S(ctx.project), { with: c.person });
    toast(`Turned on. Your private work goes to ${c.name} once that account turns it on too.`, "ok", { ttl: 9000 });
    await ctx.refresh({ force: true });
  } catch (e) { showError(e); }
}

async function turnOff(ctx, on) {
  const ok = await confirmDialog({ title: `Stop sending your private work to ${on.name}?`, confirmText: "Stop", danger: false,
    message: "Nothing more goes between the two accounts from the next round. What already arrived stays on both computers." });
  if (!ok) return;
  try {
    await api("DELETE", S(ctx.project));
    toast("Stopped. What already arrived stays.", "ok");
    await ctx.refresh({ force: true });
  } catch (e) { showError(e); }
}

function selfSyncSection(ctx) {
  const st = ctx.status || {};
  const s = st.self_sync;
  if (!s) return null;
  const title = "Your other account";
  const help = h("p", { class: "small team-help" }, helpMark("About your other account", HELP), " Your private work, on both of your computers.");
  if (s.needs_space) {
    const names = (s.linked || []).map((x) => x.name).join(", ");
    return section("self-sync", title,
      h("p", { class: "muted team-text", id: "team-self-needs-space" }, `The owner marks ${names} as you. Sending your private work to your other account needs a storage space: on a shared folder it is not offered.`));
  }
  // the roster (signed by the owner's copy) gives this account other keys than this computer's: nothing goes
  const warn = s.warning ? notice({ kind: "attention", id: "team-self-keys" }, s.warning) : null;
  if (s.on) {
    const sub = s.active
      ? [`your private work goes both ways`, s.sent_at ? ` · last sent ${when(s.sent_at)}` : null, s.received_at ? ` · last received ${when(s.received_at)}` : null, s.code ? ` · check code ${s.code}` : null]
      : (s.why || "");
    const row = listRow({ person: personMark([s.on.name]), title: s.on.name, sub, warn: !s.active,
      actions: [button({ kind: "quiet", sm: true, id: "team-self-off", onClick: () => turnOff(ctx, s.on) }, "Stop…")] });
    return section("self-sync", title, warn, h("div", { class: "team-people" }, listGroup(null, row)), help);
  }
  if (!(s.candidates || []).length) {
    return section("self-sync", title, h("p", { class: "muted team-text" }, "The owner marks another account as you, but it is not in the storage space now."));
  }
  const rows = s.candidates.map((c) => listRow({ person: personMark([c.name]), title: c.name,
    sub: [c.since ? `in the team since ${when(c.since)}` : null, c.code ? `check code ${c.code}` : null].filter(Boolean).join(" · "),
    actions: s.keys_differ ? [] : [button({ sm: true, id: `team-self-on-${c.part}`, onClick: () => turnOn(ctx, c) }, "Send my private work…")] }));
  return section("self-sync", title, warn,
    warn ? null : notice({ kind: "info" }, "The owner marks this account as yours too. Your private work can go to it, and its private work come here, once both accounts turn this on."),
    h("div", { class: "team-people" }, listGroup(null, ...rows)), help);
}

export const SELF_SYNC_SECTION = { key: "self-sync", render: selfSyncSection };
