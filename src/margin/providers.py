"""The cloud AI providers Margin knows (stage 1 of "cloud providers other than Claude").

One table, the only source for every module: which company each provider is, where its API is, how its key is sent,
where the key is kept, and what its chat API takes (`quirks`). Anthropic covers both Claude Code and the Claude API;
the five others all speak the OpenAI chat-completions format (`llm.CloudBackend`).

Consent is per document and per provider (access.py): a document marked `cloud` may be read by the providers it
allows, Anthropic alone unless the person allowed more. A model server on another computer that is none of these is
the provider `other` (an unnamed cloud server): nothing allows it unless the person says so.

`measured`: whether Margin's routing and defaults were measured on this provider's models (only Anthropic so far).
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlparse

ANTHROPIC = "anthropic"
OTHER = "other"          # a server on another computer that is none of the providers below


@dataclass(frozen=True)
class Provider:
    id: str
    title: str                      # how the app names it
    company: str                    # who receives the text
    base_url: str = ""              # the OpenAI-compatible base address ("" for Anthropic; Azure: a template)
    auth: str = "bearer"            # "bearer" (Authorization: Bearer <key>) or "api-key" (Azure's api-key header)
    keychain: str = ""              # the name the key is kept under in the system's keychain
    lists_models: bool = True       # GET {base}/models lists the models this key may use
    hosts: tuple[str, ...] = ()     # the addresses that are this provider (a server field pointed at one of them)
    measured: bool = False
    # what its chat API takes: the name of the answer's length limit, of the seed (None: send none), and which
    # answer formats it documents (the first that works is kept)
    quirks: dict = field(default_factory=dict)
    key_hint: str = ""              # where a person gets a key
    placeholder: str = ""           # what a key looks like
    # the set-up's pages (the guided steps of Settings → AI, docs/DESIGN.md 4.28), checked on the providers' own
    # sites on 18 November 2026: where to make an account, where its keys are made, where credit is added ("" = none)
    signup: str = ""
    keys_url: str = ""
    billing_url: str = ""


TABLE: dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Anthropic (Claude)", "Anthropic", auth="x-api-key", keychain="",
             hosts=("api.anthropic.com",), measured=True),
    Provider("openai", "OpenAI", "OpenAI", "https://api.openai.com/v1", keychain="provider-key:openai",
             hosts=("api.openai.com",),
             quirks={"max_tokens": "max_completion_tokens", "seed": "seed",
                     "formats": ("json_schema", "json_object", "none")},
             key_hint="platform.openai.com → API keys", placeholder="sk-…",
             signup="https://platform.openai.com/signup", keys_url="https://platform.openai.com/api-keys",
             billing_url="https://platform.openai.com/account/billing/overview"),
    Provider("gemini", "Google Gemini", "Google", "https://generativelanguage.googleapis.com/v1beta/openai",
             keychain="provider-key:gemini", hosts=("generativelanguage.googleapis.com",),
             # Gemini's OpenAI-compatible API documents no seed
             quirks={"max_tokens": "max_tokens", "seed": None, "formats": ("json_schema", "json_object", "none"),
                     "model_prefix": "models/"},
             key_hint="aistudio.google.com → Get API key", placeholder="",
             signup="https://aistudio.google.com", keys_url="https://aistudio.google.com/apikey",
             billing_url="https://aistudio.google.com/docs/billing"),
    Provider("mistral", "Mistral", "Mistral AI", "https://api.mistral.ai/v1", keychain="provider-key:mistral",
             hosts=("api.mistral.ai",),
             # Mistral takes random_seed, not seed, and refuses fields it does not know
             quirks={"max_tokens": "max_tokens", "seed": "random_seed",
                     "formats": ("json_schema", "json_object", "none")},
             key_hint="console.mistral.ai → API keys",
             signup="https://console.mistral.ai", keys_url="https://console.mistral.ai/api-keys",
             billing_url="https://admin.mistral.ai/organization/billing"),
    Provider("azure", "Azure OpenAI", "Microsoft", "https://{resource}.openai.azure.com/openai/v1", auth="api-key",
             keychain="provider-key:azure", lists_models=False, hosts=(".openai.azure.com",),
             quirks={"max_tokens": "max_completion_tokens", "seed": "seed",
                     "formats": ("json_schema", "json_object", "none")},
             key_hint="Azure portal → your Azure OpenAI resource → Keys and Endpoint",
             signup="https://ai.azure.com", keys_url="https://portal.azure.com", billing_url=""),
    Provider("openrouter", "OpenRouter", "OpenRouter (and the model's own provider)", "https://openrouter.ai/api/v1",
             keychain="provider-key:openrouter", hosts=("openrouter.ai",),
             quirks={"max_tokens": "max_tokens", "seed": "seed", "formats": ("json_schema", "json_object", "none")},
             key_hint="openrouter.ai → Keys", placeholder="sk-or-…",
             signup="https://openrouter.ai", keys_url="https://openrouter.ai/keys",
             billing_url="https://openrouter.ai/settings/credits"),
)}

IDS = tuple(TABLE)                                   # anthropic first
CLOUD_IDS = tuple(i for i in IDS if i != ANTHROPIC)  # the ones Settings' "Another cloud provider" offers
ALLOWABLE = IDS + (OTHER,)                           # what a document may allow
DEFAULT_ALLOWED = (ANTHROPIC,)                       # a project without its own choice: as before stage 1

# the main routes (Settings' backend) whose passages leave this computer, and the provider each one is
ROUTE_PROVIDER = {"claude_code": ANTHROPIC, "anthropic": ANTHROPIC, "codex": "openai", "antigravity": "gemini"}
CLOUD_ROUTE = "cloud_api"                            # Settings' backend for another cloud provider


# -- recommended models (each provider's own advice, applied to Margin's three tiers) ---------------------------------
# Margin's work has three tiers, named after Claude's models in the routing table (routing.py): the many small tasks
# (labels, links: Haiku), judging excerpts against a hypothesis with exact quotes (the core: Sonnet), and second
# opinions and hard cases (Opus). Every other provider gets the same three tiers from its own line-up. Each tier is a
# list of candidates, best first: the first one the person's key (GET {base}/models) or the CLI (`agy models`) offers
# is used, else the first. Checked on the providers' own model pages on 18 November 2026:
#   OpenAI   developers.openai.com/api/docs/models: GPT-6.2 Astra (flagship), GPT-6.2 Sol (everyday), GPT-6 Luna
#            (high volume); the GPT-5 family shuts down on 11 December 2026
#   Google   aistudio.google.com/docs/models: "for any new projects, use Gemini 4 Hydrogen or 3.5 Flash-Lite";
#            Gemini 4 Carbon is the strongest (Ultra in Antigravity), 3.8 Flash the free plan's model
#   Mistral  docs.mistral.ai models overview: Ministral 3, Mistral Small 4, Mistral Large 4 (their -latest aliases)
#   Azure    deployment names the person chose: none is recommended, the set-up says which models to deploy
#   OpenRouter  openrouter.ai/models ids (org/model), resolved against the key's list
# A model chosen in Settings always comes first; an empty choice means "the recommendation", so a newer Margin brings
# newer recommendations by itself. Not measured with Margin yet (`measured`): Settings says so.
TIERS = ("small", "middle", "strong")
TIER_TITLES = {"small": "Small tasks (labels, links, search words)", "middle": "Judging excerpts",
               "strong": "Second opinions and hard cases"}
ALIAS_TIER = {"haiku": "small", "sonnet": "middle", "opus": "strong", "fable": "strong"}
TIER_ALIAS = {"small": "haiku", "middle": "sonnet", "strong": "opus"}

LINEUP: dict[str, dict[str, tuple[str, ...]]] = {
    "openai": {"small": ("gpt-6-luna",), "middle": ("gpt-6.2-sol", "gpt-6.1-sol"),
               "strong": ("gpt-6.2-astra", "gpt-6-astra")},
    "gemini": {"small": ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"),
               "middle": ("gemini-4-hydrogen", "gemini-3.8-flash"),
               "strong": ("gemini-4-carbon", "gemini-4-argon", "gemini-4-hydrogen")},
    # (mistral-small-latest first for the small tier: Ministral is not on Mistral's models page, so an id that may not
    # be listed is never the default; it stays the second candidate for a key that offers it)
    "mistral": {"small": ("mistral-small-latest", "ministral-8b-latest"), "middle": ("mistral-small-latest",),
                "strong": ("mistral-large-latest",)},
    # Azure: what to deploy (the names are the person's own deployments, typed in Settings)
    "azure": {"small": ("gpt-6-luna",), "middle": ("gpt-6.2-sol",), "strong": ("gpt-6.2-astra",)},
    "openrouter": {"small": ("google/gemini-3.5-flash-lite", "openai/gpt-6-luna"),
                   "middle": ("openai/gpt-6.2-sol", "google/gemini-4-hydrogen"),
                   "strong": ("openai/gpt-6.2-astra", "google/gemini-4-carbon")},
}
# reasoning effort per thought (Settings' Energy efficient / Balanced / Intelligence), for the APIs and CLIs that take
# one (OpenAI `reasoning_effort`, Codex `model_reasoning_effort`, Antigravity `--effort`); None: the model's default
EFFORT = {"efficient": "low", "balanced": None, "intelligence": "high"}


def pick(candidates, available=None, prefix: bool = False) -> str:
    """The first candidate the provider offers (`available`: the model ids its list gave; None or empty: not known,
    the first candidate). `prefix`: an offered id may add a suffix ("gemini-4-carbon-high" offers gemini-4-carbon);
    Gemini's "models/" prefix is ignored."""
    cands = [c for c in (candidates or ()) if c]
    if not cands:
        return ""
    if not available:
        return cands[0]
    have = {str(a).removeprefix("models/") for a in available}
    for c in cands:
        if c in have or (prefix and any(a.startswith(c + "-") for a in have)):
            return c
    return cands[0]


def recommended(pid: str, available=None, prefix: bool = False) -> dict[str, str]:
    """{tier: model id} recommended for a provider's API (or a CLI's provider), resolved against what it offers."""
    line = LINEUP.get(pid) or {}
    return {t: pick(line.get(t), available, prefix) for t in TIERS}


# -- agent CLIs on the person's own plan, like Claude Code (stage 2) -------------------------------------------------
# Each answers Margin's task queue through the Margin connector (mcp_server.py), started by Margin in the background
# ("Start Codex"), or by the person in the CLI (/margin-run, $margin-run). The route is the Settings' backend; its
# provider is the company that receives the passages. The line-up is the models the plan offers in that CLI.
@dataclass(frozen=True)
class AgentCli:
    id: str                         # Settings' backend
    title: str                      # "Codex"
    provider: str                   # providers.TABLE id
    program: str                    # the program's name on the PATH
    plan: str                       # the plans it runs on, in words
    lineup: dict = field(default_factory=dict)
    docs: str = ""                  # the CLI's own set-up page (checked 18 November 2026)
    measured: bool = False


AGENT_CLIS: dict[str, AgentCli] = {a.id: a for a in (
    AgentCli("codex", "Codex", "openai", "codex", "a ChatGPT plan (Plus, Pro, Business, Edu or Enterprise)",
             lineup={"small": ("gpt-6-luna",), "middle": ("gpt-6.2-sol", "gpt-6.1-sol"),
                     "strong": ("gpt-6.2-astra", "gpt-6-astra")},
             docs="https://learn.chatgpt.com/docs/auth"),
    AgentCli("antigravity", "Antigravity", "gemini", "agy", "a personal Google account (free, Google AI Pro or Ultra)",
             # the free plan offers Gemini 3.8 Flash only; AI Pro adds Gemini 4 Argon and Hydrogen, Ultra Carbon
             lineup={"small": ("gemini-3.8-flash",), "middle": ("gemini-4-hydrogen", "gemini-3.8-flash"),
                     "strong": ("gemini-4-carbon", "gemini-4-argon", "gemini-4-hydrogen", "gemini-3.8-flash")},
             docs="https://antigravity.google/docs/getting-started"),
)}
# the main routes that answer through the task queue (Claude Code and the agent CLIs)
AGENT_ROUTES = ("claude_code",) + tuple(AGENT_CLIS)


def cli_recommended(route: str, available=None) -> dict[str, str]:
    """{tier: model id} recommended for an agent CLI, resolved against the models it lists (`agy models`)."""
    a = AGENT_CLIS.get(route)
    return {t: pick((a.lineup if a else {}).get(t), available, prefix=True) for t in TIERS}


def get(pid: str | None) -> Provider | None:
    return TABLE.get(pid or "")


def title(pid: str | None) -> str:
    if pid == OTHER:
        return "a server on another computer"
    p = TABLE.get(pid or "")
    return p.title if p else str(pid or "")


def company(pid: str | None) -> str:
    if pid == OTHER:
        return "the owner of that server"
    p = TABLE.get(pid or "")
    return p.company if p else str(pid or "")


def on_this_computer(url: str) -> bool:
    """Whether an address is this computer (localhost, 127.x, ::1)."""
    u = (url or "").strip()
    if not u:
        return False
    if "://" not in u:
        u = "http://" + u
    try:
        host = (urlparse(u).hostname or "").strip("[]").lower()
    except ValueError:
        return False
    if host in ("localhost", "localhost.localdomain") or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def of_url(url: str) -> str | None:
    """The provider a model server's address is: None on this computer, a provider of the table by its host (an
    OpenAI address typed into the local server field is OpenAI), else `other`."""
    if on_this_computer(url):
        return None
    u = (url or "").strip()
    if "://" not in u:
        u = "https://" + u
    try:
        host = (urlparse(u).hostname or "").lower()
    except ValueError:
        return OTHER
    for p in TABLE.values():
        for h in p.hosts:
            if host == h or (h.startswith(".") and host.endswith(h)):
                return p.id
    return OTHER


def clean_list(value) -> list[str]:
    """A list of providers a document or a project allows, checked and in the table's order. Raises ValueError."""
    if value is None:
        raise ValueError("Give the providers as a list.")
    if isinstance(value, str):
        value = [v for v in value.replace(";", ",").split(",") if v.strip()]
    if not isinstance(value, (list, tuple)):
        raise ValueError("Give the providers as a list.")
    got = {str(v).strip().lower() for v in value}
    unknown = sorted(got - set(ALLOWABLE))
    if unknown:
        raise ValueError(f"Unknown AI provider {unknown[0]!r}: choose from {', '.join(ALLOWABLE)}.")
    if not got:
        raise ValueError("Allow at least one provider, or mark the documents Only a local AI.")
    return [p for p in ALLOWABLE if p in got]


def base_url(pid: str, azure_url: str = "") -> str:
    """The OpenAI-compatible base address of a provider (Azure: from the resource's address the person gives).
    Raises ValueError when Azure's address is missing or not one."""
    p = TABLE[pid]
    if pid != "azure":
        return p.base_url
    a = (azure_url or "").strip().rstrip("/")
    if not a:
        raise ValueError("Give your Azure OpenAI resource's address (Settings → AI), for example "
                         "https://my-resource.openai.azure.com.")
    if "://" not in a:
        a = (f"https://{a}.openai.azure.com" if "." not in a else "https://" + a)
    if not a.lower().startswith("https://"):
        raise ValueError("The Azure OpenAI address must start with https://.")
    # the resource's address is enough: a deployment's address copied from the portal
    # (…/openai/deployments/<name>/chat/completions?api-version=…) gives the same base
    try:
        host = urlparse(a).netloc
    except ValueError:
        host = ""
    if not host or any(c in host for c in "/?#@"):
        raise ValueError("Give your Azure OpenAI resource's address, for example https://my-resource.openai.azure.com.")
    return f"https://{host}/openai/v1"


def summary() -> list[dict]:
    """The table as the app shows it (no key: whether one is stored is asked separately)."""
    return [{"id": p.id, "title": p.title, "company": p.company, "lists_models": p.lists_models,
             "measured": p.measured, "key_hint": p.key_hint, "placeholder": p.placeholder,
             "needs_address": p.id == "azure", "signup": p.signup, "keys_url": p.keys_url,
             "billing_url": p.billing_url,
             "recommended": recommended(p.id) if p.id in LINEUP else {}} for p in TABLE.values()]


def clis_summary() -> list[dict]:
    """The agent CLIs as the app shows them (whether each is set up is asked separately, agentcli.status)."""
    return [{"id": a.id, "title": a.title, "provider": a.provider, "company": company(a.provider),
             "program": a.program, "plan": a.plan, "docs": a.docs, "measured": a.measured,
             "recommended": cli_recommended(a.id)} for a in AGENT_CLIS.values()]
