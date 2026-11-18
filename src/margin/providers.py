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


TABLE: dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Anthropic (Claude)", "Anthropic", auth="x-api-key", keychain="",
             hosts=("api.anthropic.com",), measured=True),
    Provider("openai", "OpenAI", "OpenAI", "https://api.openai.com/v1", keychain="provider-key:openai",
             hosts=("api.openai.com",),
             quirks={"max_tokens": "max_completion_tokens", "seed": "seed",
                     "formats": ("json_schema", "json_object", "none")},
             key_hint="platform.openai.com → API keys", placeholder="sk-…"),
    Provider("gemini", "Google Gemini", "Google", "https://generativelanguage.googleapis.com/v1beta/openai",
             keychain="provider-key:gemini", hosts=("generativelanguage.googleapis.com",),
             # Gemini's OpenAI-compatible API documents no seed
             quirks={"max_tokens": "max_tokens", "seed": None, "formats": ("json_schema", "json_object", "none"),
                     "model_prefix": "models/"},
             key_hint="aistudio.google.com → Get API key", placeholder="AIza…"),
    Provider("mistral", "Mistral", "Mistral AI", "https://api.mistral.ai/v1", keychain="provider-key:mistral",
             hosts=("api.mistral.ai",),
             # Mistral takes random_seed, not seed, and refuses fields it does not know
             quirks={"max_tokens": "max_tokens", "seed": "random_seed",
                     "formats": ("json_schema", "json_object", "none")},
             key_hint="console.mistral.ai → API keys"),
    Provider("azure", "Azure OpenAI", "Microsoft", "https://{resource}.openai.azure.com/openai/v1", auth="api-key",
             keychain="provider-key:azure", lists_models=False, hosts=(".openai.azure.com",),
             quirks={"max_tokens": "max_completion_tokens", "seed": "seed",
                     "formats": ("json_schema", "json_object", "none")},
             key_hint="Azure portal → your Azure OpenAI resource → Keys and Endpoint"),
    Provider("openrouter", "OpenRouter", "OpenRouter (and the model's own provider)", "https://openrouter.ai/api/v1",
             keychain="provider-key:openrouter", hosts=("openrouter.ai",),
             quirks={"max_tokens": "max_tokens", "seed": "seed", "formats": ("json_schema", "json_object", "none")},
             key_hint="openrouter.ai → Keys", placeholder="sk-or-…"),
)}

IDS = tuple(TABLE)                                   # anthropic first
CLOUD_IDS = tuple(i for i in IDS if i != ANTHROPIC)  # the ones Settings' "Another cloud provider" offers
ALLOWABLE = IDS + (OTHER,)                           # what a document may allow
DEFAULT_ALLOWED = (ANTHROPIC,)                       # a project without its own choice: as before stage 1

# the main routes (Settings' backend) whose passages leave this computer, and the provider each one is
ROUTE_PROVIDER = {"claude_code": ANTHROPIC, "anthropic": ANTHROPIC}
CLOUD_ROUTE = "cloud_api"                            # Settings' backend for another cloud provider


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
             "needs_address": p.id == "azure"} for p in TABLE.values()]
