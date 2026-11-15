### New

- **Team and Research log are places in the sidebar.** The sidebar now reads *Overview*, then *Project* (*Documents*,
  *Research log*, *Team*), *Explore* and *Check*. *Team* opens the Team page from anywhere, also in a project that has
  no team yet; in a project with one, its entry says the team's state at its end (*synced 15:44*, *3 new*, *offline*).
  The research log is no longer a tab of the Overview, and the Team is no longer a tab behind the *Research log*
  button: the panel beside the page holds the research log only, and its button is now called *Write in the log*. The
  project menu no longer has *Manage the team*. Changes no results.
- **The Team page says what you came to do.** Without a team it has three cards: *Start a team for this project*,
  *Join a colleague's team* and *Send it once, as a file*. Where the team's shared work is kept is four choices named
  by what they are (*A storage space at Backblaze*, recommended; *Your institution's drive*; *A storage space at
  Cloudflare*; *A folder you already share*), with one button that says what it starts (*Set up at Backblaze…*). A
  colleague's shared folder that is already on your computer is offered first. Joining from the Team page asks where
  the team's project goes: a new project (the usual answer) or this one.
- **A storage space is set up one step at a time.** The dialog shows the whole way as numbered steps, opens one at a
  time, and each goes on in your own words (*I have an account*, *I see the key*). What cannot be changed later
  (Backblaze's region) and what an app password opens are notices, not small print. The main button waits for the last
  step and says so. Escape or a click beside the dialog asks before it closes once you have begun, and the dialog opens
  again at the step you left (never with what you pasted). After a Backblaze set-up a last step says how to cancel the
  key you pasted.
- **With a team, the Team page has two views.** *Activity*: what waits for your word, the sync state with *Sync now*
  and *Pause*, what came in, what you shared; while you are the only one, a card with *Invite a colleague…*.
  *People and settings*: the people with the invites not used yet and *Invite a colleague…*, where the shared work is
  kept, the owner, the switches, the downloads and leaving.
- **A calmer Research log page.** A one-line box to write an entry, one *Show* list in place of the row of filter
  buttons, the downloads at the top right, entries in a readable column. What can be done to an entry (*Say why*,
  *Edit*, *Share*, *Compare with before*, *Remove…*) is in one menu at the end of its row, not in buttons under it.

### Fixed

- **A colleague's shared entry is no longer listed under *Your own entries*.** The research log's *Show* list has
  *Your own entries* (yours only) and *Your colleagues' entries*; in the Excel download both are *Entry*, and *Who*
  says whose. Changes no results.
- **The sidebar no longer says *no round yet* for a team that was in step before Margin started.** Until the first
  round it says when the next one comes (*round in 2 min*).

### For developers

- `guidedSteps()` (lib.js, docs/DESIGN.md 4.28): a task done one step at a time. `dialog({ onDismiss })`: asked before
  a dialog is dismissed without an answer. `menu({ iconOnly })`: the more icon alone, for a list where every row has a
  menu. `teamEntry()` replaces `teamLine()`; the window event `margin-drawer` is gone (`#/team?at=<section>` brings a
  section of the Team page into view). `GET …/log` has the group `colleagues` beside `entries`.
- The Team page's set-up is `views/team-setup.js`; `views/team-entry.js` keeps the sidebar's Team entry.

### Not yet done

- The set-up at Backblaze, Cloudflare and an institution's drive was walked with stand-in answers and against a
  storage space kept in a folder, not with real accounts at the services.
- The words *Sync* and *round* are still both used for the same thing, and *Keep documents … out of the shared folder*
  says "folder" in a team that uses a storage space.
- *Say why* is one press further away than before (in the entry's menu).
