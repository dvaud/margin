### New

- **Codex and Antigravity answer the queue on your own plan, as Claude Code does.** *Settings → AI → Subscription*
  now offers three agents: Claude Code (your Claude plan, still the recommendation), Codex (OpenAI, on a ChatGPT plan)
  and Antigravity (Google, on a personal Google account, free or paid: the recommendation without a paid plan). Margin
  installs the one you choose with its maker's own installer (after showing you the command), opens its sign-in (Codex
  signs in through your browser without a terminal; Antigravity opens one window, as Claude Code does), and adds Margin
  to it. Then *Start Codex* or *Start Antigravity* wherever work waits works like *Start Claude Code*: Margin starts
  the helpers in the background, each on its model, checks every quote, and stops them with *Stop* or when you quit.
  You can also type `$margin-run <project>` in Codex or `/margin-run <project>` in Antigravity yourself. Neither is
  measured with Margin yet, nor tried with real accounts: Settings says so. The first-run page offers them too.
- **Every set-up of something outside Margin works the same way.** The API keys (OpenAI, Google Gemini, Mistral, Azure
  OpenAI, OpenRouter and the Claude API) and the three agents are set up step by step in a dialog, like the storage
  space: one thing at a time, the address to open with a Copy button, the button waiting for the last step. A key the
  provider refuses is said so at once and not kept; the done step lists the models Margin applied and switches the
  route on in one press.
- **Work a provider may not read says so, and goes on once you allow it.** With Codex (or another provider) as the AI
  and documents that allow Anthropic only, a check no longer waits silently: it says "Codex reads only documents that
  allow OpenAI: 0 of 3 do", with *Allow OpenAI for this project*, and the same check continues after the press.
- **Recommended models, applied by themselves.** Every provider now gets Margin's three tiers (small tasks such as
  labels and links; judging excerpts; second opinions and hard cases) from its own current line-up: for example
  GPT-6 Luna, GPT-6.2 Sol and GPT-6.2 Astra on OpenAI, Gemini 3.5 Flash-Lite, Gemini 4 Hydrogen and Gemini 4 Carbon on
  Google's API, Mistral Small and Mistral Large on Mistral. The one in use follows the route you chose and
  the models your key or plan offers; a model you pick for a tier comes first. *How much thought* (Energy efficient,
  Balanced, Intelligence) now works for every provider: one tier lower or higher, and less or more reasoning effort
  where the model takes it. On a free Google account Antigravity offers Gemini 3.8 Flash only, so every task uses it.

### Changes that can alter your results

- **Another cloud provider no longer uses one model for everything.** Labels and links go to the provider's smaller
  model, second opinions and hard cases to its strongest, as on Claude. Can change results for projects that used
  *Another cloud provider (API key)* in 0.19.19.

### Privacy

- **The queue hands passages only to the company of the agent that takes them.** A document that allows OpenAI but
  not Anthropic reaches Codex and never Claude Code, and the reverse; *What was sent* records the provider and the
  agent for every passage. Choosing Codex or Antigravity asks you first, naming the company, as Claude Code did.
- **Each agent is closed in as far as it allows.** Codex runs read-only, without its command, web search and image
  tools, with only Margin's three queue tools and none of your own Codex settings. Antigravity's own tools cannot be
  switched off from outside: Margin starts it in an empty folder of its own, in its sandbox, adds one permission line
  (`mcp(margin/*)`, after keeping a copy of your settings), marks its own empty work folder as trusted, and refuses
  to start it while it is set to run every tool without asking.
- **Each agent's consent says what its maker does with the text on that kind of account:** ChatGPT Plus and Pro may
  be used to train OpenAI's models unless *Improve the model for everyone* is off; Antigravity on a personal Google
  account while its *Enable Telemetry* setting is on. In a shared project only Anthropic reads, as before.

### Tests

- `tests/test_agent_cli.py`: the provider-gated queue both ways and after a change of route, set-up, sign-in and
  repair of both agents, the runner (start, stop, a reached limit, Antigravity's always-proceed refusal, stopping
  every run at quit), and the API, against stand-in `codex` and `agy` programs (`tests/fake_codex_cli.py`,
  `tests/fake_agy_cli.py`). `tests/test_providers.py`: the three tiers and the recommendations per provider, a
  refused key. `tests/test_provider_allow.py`: a held check waits with its reason and continues once OpenAI is
  allowed; a shared project ends with the reason. `tests/test_outside_setup_views.py`: the set-up dialogs in Node.

### Not yet done

- Codex and Antigravity are built against stand-ins that follow their documentation; neither has been tried with a
  real account (see the roadmap's *Left to try with real accounts*).
