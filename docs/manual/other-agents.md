[Manual](../MANUAL.md) › Codex and Antigravity

# Codex and Antigravity, on your own plan

> **In short**
> - If you have a ChatGPT plan or a Google account, **Codex** or **Antigravity** can answer Margin's work, as Claude Code
>   does. No API key.
> - Margin installs it, opens its sign-in and adds itself to it. Then press *Start Codex* or *Start Antigravity*
>   wherever work waits.
> - Neither is tried with real accounts yet, and neither is measured with Margin: check their answers before you rely
>   on them.

## Which one

*Settings → AI → Subscription* offers three agents. Each answers on a plan you already pay for, and only the passages
inside its tasks go to its company.

| Agent | Whose | Your plan | Where the passages go |
| --- | --- | --- | --- |
| [Claude Code](claude-code.md) | Anthropic | A Claude plan (Pro, Max, Ultra, Team or Enterprise) | Anthropic |
| **Codex** | OpenAI | A ChatGPT plan (Plus, Pro, Business, Edu or Enterprise) | OpenAI |
| **Antigravity** | Google | A personal Google account, free or paid | Google |

Claude Code stays the recommendation. Antigravity is the one to take without a paid plan: on a free Google account it
offers Gemini 3.8 Flash only, so every task uses it ([Which model does what](models.md#the-recommended-models-of-each-provider)).
A ChatGPT plan pays for Codex, not for an OpenAI API key; for that, see [An API
key](settings.md#an-api-key-claude-or-another-provider).

> [!NOTE]
> Codex and Antigravity are built against stand-in programs that follow their documentation. They are **not yet tried
> with real accounts**, and **not yet measured with Margin**: its models and settings were measured with Claude only.
> Settings says so beside each, and so does the question Margin asks before you use one.

## Set it up once

Choose the agent in *Settings → AI → Subscription*. The first time, Margin asks, naming the company: *Let Codex read the
excerpts, on your ChatGPT plan?* Answer *Use Codex* and press **Set up Codex** (or *Set up Antigravity*). A window of
guided steps opens at the first step not done yet:

1. **Install.** Margin shows the maker's own installer line and runs it when you press *Install Codex*. It puts the
   program in your user folder and needs no administrator rights. Prefer to do it yourself? The step links the maker's
   page ([Codex](https://github.com/openai/codex), [Antigravity](https://antigravity.google/docs/getting-started)) and
   moves on by itself once the program is found.
2. **Sign in.** The button opens the sign-in. Codex opens your browser by itself, with no terminal
   ([its sign-in page](https://learn.chatgpt.com/docs/auth)). Antigravity opens one terminal window, as Claude Code
   does: sign in there and in the browser page it opens. Before you close that window, switch off **Enable
   Telemetry** in Antigravity's settings (under *AI credits and feedback*): while it is on, Google may use what
   Antigravity reads to improve its products. The step moves on by itself when it sees you are signed in; *I have
   signed in* checks now. While it waits, *Open the sign-in* stays pressed; after 30 seconds *Open it again* offers a
   new one, for a window closed too soon. Margin never sees your login: the agent keeps it.
3. **Add Margin.** The button adds the Margin connector (with its three queue tools), the skill and the helpers.
   For Antigravity it also writes Margin's own Antigravity settings, in a folder of Margin: Margin starts Antigravity
   with those, never with yours. Nothing else in the agent is changed. Margin 0.20.0 and 0.20.1 wrote a permission
   line and its work folder into your own Antigravity settings; this step lists them and offers **Remove them**. When
   the project has documents the agent's company may not read yet, the last step says how many and offers to allow it
   for the project.

The last step says *Start Codex wherever work waits*. A new Margin, or a moved one, writes these again by itself. The
card in *Settings → AI* shows the same three ticks (found, signed in, Margin added); the models in use, which you may
change per tier, are in *Settings › Technical › The provider's models*.

## Start it

Press an AI button, and the page says what waits, with **Start Codex** or **Start Antigravity**. It works exactly as
[Start Claude Code](claude-code.md#start-claude-code) does: Margin starts the agent's helpers in the background, each on
its own model, checks every quote, and stops them with *Stop* or when you quit. *How much thought* and *Helpers at once*
work the same, and so do the choices beside a local model (*Sharing the work* and *At your plan's usage limit*, in
*Settings → AI › Documents only a local AI may read*) ([Which model does what](models.md#how-much-thought)). On a
free Google account every task uses Gemini 3.8 Flash, so a second opinion comes from the same model; Settings says so. Nothing runs until you press it.

You can also type the run yourself in the agent, opened anywhere:

```text
$margin-run Pilot       # in Codex
/margin-run Pilot       # in Antigravity
```

## What it may read

Each document says which companies may read it. A task goes only to the agent whose company every document it names
allows: a document that allows OpenAI but not Anthropic reaches Codex and never Claude Code, and the reverse. Every
document allows Anthropic only until you tick OpenAI or Google for it ([Privacy](privacy.md#other-cloud-providers)).
*What was sent* records the company and the agent for each passage.

Which AI work ran, with which agent and model, is in the [AI log](how-the-ai-is-used.md#the-ai-log).

## How each agent is closed in

Each agent Margin starts works in a box, as far as the agent allows, so a passage that tries to give it instructions can
do nothing else.

| Agent | How it is closed in |
| --- | --- |
| **Claude Code** | An empty folder, no file, shell or web tools, only Margin's plugin ([Privacy](privacy.md#how-it-is-enforced)). |
| **Codex** | Starts in an empty folder, read-only, with your own Codex settings left out. Its command, web search and image tools are off, and only Margin's three queue tools are given to it (take a batch, send the answers, give a batch back). |
| **Antigravity** | Its own tools cannot be switched off from outside. So Margin starts it in an empty folder of its own, in its sandbox, without slash commands, and it asks before every tool except Margin's; in the background nobody answers, so it is refused. It runs with **its own home folder and settings**, which Margin writes before every run: your own Antigravity permissions, connectors and AI credits never reach it. **Margin refuses to start an Antigravity without its sandbox switch.** A tool it refused is written in the run's report ([Troubleshooting](troubleshooting.md#codex-and-antigravity)). |

These limits are built against stand-ins that follow the makers' own documentation ([Codex](https://github.com/openai/codex),
[Antigravity](https://antigravity.google/docs/getting-started)), not yet against a real account.

## If something stops

Not found, not signed in, a reached plan limit, or Antigravity refusing to start:
[Troubleshooting](troubleshooting.md#codex-and-antigravity).

---

Next: [A model on your own computer →](local-models.md)
