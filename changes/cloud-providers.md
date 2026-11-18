### New

- **Another cloud provider, with an API key.** *Settings → AI* has a new main choice, *Another cloud provider (API
  key)*: OpenAI, Google Gemini, Mistral, Azure OpenAI or OpenRouter, each through its OpenAI-compatible chat API over
  HTTPS. It needs *Allow cloud models* and is refused on a local-only installation. The key is kept in the system's
  keychain (or a file only you can read), never in settings, a log, an error message, the record of how an answer was
  made or a *Move Margin to another computer* file. You pick the model from the provider's list (for Azure you type
  the deployment name and give the resource address), and may add a smaller model for labels and links. These
  providers are marked *not yet measured*: Margin's default models and routing were measured on Claude only.
- **Consent per document and per provider.** A document marked *Claude may read it* now lists which cloud providers
  may read it, **by default only Anthropic**, so every existing project means what it did. Set it for the project
  (on the Documents page) or per document (its AI setting), as tick boxes. Once another provider is set up, the page says *Cloud AI
  may read it*. A document that does not allow the main route's provider is read by the local model for restricted
  documents, or waits for your judgement. The ledger, the Documents page and the CSV (a new *Provider* column) say
  which provider read what. In a shared project only Anthropic may read such documents for now, and the app says why.

### Changes that can alter your results

- **A model server on another computer no longer reads *Claude may read it* documents until you allow it.** It counts
  as a cloud provider now (a known one by its address, otherwise *a server on another computer*). If you used one,
  its documents wait for the local model for restricted documents or for your judgement, until you allow it. Settings
  → AI and the Documents page say so in one line, with *Allow it for this project*. A server on this computer is
  unchanged. An embedding server on another computer embeds only the documents that allow it, in the same way.

### Fixed

- **A model server on another computer could read *Claude may read it* documents.** An address typed into the local
  server field that was not this computer (an OpenAI address, a lab's GPU server) was read as a local model and got
  every such document. It is now a cloud provider that each document must allow.

### Tests

- `tests/test_providers.py`: the hole above, existing projects unchanged, the work split per provider, relabelling,
  shared projects, the cloud backend's fields, keys and errors against an OpenAI-compatible stand-in in
  `tests/fake_servers.py`, and settings. `tests/test_providers_fixes.py`: a team merge keeps the stored settings, a
  remote embedder, the working-document floor, no redirect carries the key, labels follow a change of route. Node
  view tests for the wording switch, the provider tick boxes and the line about a server on another computer.

### Not yet done

- Codex CLI and Antigravity CLI through the task queue.
- Routing ladders and *Energy efficient / Balanced / Intelligence* per provider; measured defaults for other
  providers.
- The allowance does not travel with a team: shared projects allow Anthropic only.
- Tried only against stand-ins, not the real providers' APIs.
