### New

- **Each person chooses their own cloud provider in a shared project.** Until now a shared project let Anthropic read
  only. Now a member's own Codex, Antigravity or API key reads the project's documents marked for cloud AI on their
  copy, for the providers they tick there. Those ticks are their own consent: they stay in their copy and never reach a
  colleague's (a colleague's new document or project file arrives without them). Which documents may go to cloud AI
  at all stays the team's, as before; the research log tells the team which providers a person allowed.
- **The owner may limit the providers the team may use.** Team › People and settings › *AI providers*: off by default;
  on, the owner ticks the providers (Anthropic only, say). The limit travels with the owner's other settings; a
  provider outside it reads none of the project's documents in anyone's copy, and work waiting for it says *The team
  uses Anthropic only (set by Anna): OpenAI reads none of this project's documents.* The app offers it to the owner
  alone; it is not signed yet, so a change in the owner's name that came in someone else's file is named as such in
  the research log.
- **The AI log.** From the research log's line under its title: one row each time AI work sent excerpts to a cloud
  provider, saying who sent them, to which provider, through which route and on which model, what kind of task, when,
  how many excerpts from how many documents, and what it was about (a link to the hypothesis, codebook, themes or
  document). Filter by person and provider. A colleague's rows arrive with the sync.

### Changes that can alter your results

- **Provider ticks a shared project brought from colleagues are cleared once.** In 0.19.19 and 0.20.0 a member's copy
  kept the ticks of whoever sent the project; they now count as consent, so on the first opening after the update
  Margin clears, once, the ticks in a shared project that you did not set yourself, and the Documents page says so:
  tick again what you allow. A colleague still on an older Margin allows Anthropic only in a shared project.

### Fixed

- **The connector chose excerpts for Anthropic whatever agent asked.** When Codex or Antigravity used Margin's
  connector in a chat (`open_check`, `more_passages`), the excerpts were chosen for Anthropic, so a document that
  allows Anthropic only could reach OpenAI or Google that way. They are now chosen for the agent's own company, and the
  ledger names it.

### Privacy

- **The ledger of what was sent now names who sent it and on which model**, so a team can trace AI results. A row a
  colleague's file says you sent, which your copy does not hold, is kept as read but names nobody. A colleague's work
  they have not shared shows only as *work not shared with the team*.

### For developers

- `teamproviders.py` (the owner's limit, key `team_providers` in `team_settings`), `ailog.py` (the AI log), new
  columns `ai_sent.person_id` and `ai_sent.model`; `GET/PUT …/owner/providers` and `GET …/ai-log` (docs/API.md).
  `access._Allow` applies the owner's limit where it applied the shared-project rule.

### Not yet done

- Not tried with a real team on two providers, nor through a real storage space or shared folder: only with two copies
  exchanging files on one computer.
