"""Central registry of optional features and their dependencies.

Each entry maps a feature name to the modules it requires and the pip
extra that provides them. UX surfaces (CLI help, slash commands, startup
notices) consult this registry so unavailable features are invisible
instead of advertised and broken.
"""

import importlib.util


class Capability:
    def __init__(self, modules, extra, title):
        self.modules = tuple(modules)
        self.extra = extra
        self.title = title


CAPS = {
    "voice": Capability(
        modules=("pydub", "sounddevice", "soundfile"),
        extra="aider-chat[voice]",
        title="Voice",
    ),
    "repomap": Capability(
        modules=("grep_ast", "networkx"),
        extra="aider-chat[lint]",
        title="Repo map",
    ),
    "lint": Capability(
        modules=("grep_ast", "flake8"),
        extra="aider-chat[lint]",
        title="Linting",
    ),
    "litellm": Capability(
        modules=("litellm",),
        extra="aider-chat[litellm]",
        title="Multi-provider LLM support",
    ),
}

_checked = {}


def available(name):
    """True if all modules for the feature are installed. Cached."""
    if name not in _checked:
        try:
            _checked[name] = all(
                importlib.util.find_spec(mod) is not None for mod in CAPS[name].modules
            )
        except ValueError:
            _checked[name] = False
    return _checked[name]


def hint(name):
    """Canonical install hint for a missing feature."""
    return f"Install with: pip install '{CAPS[name].extra}'"


def reset():
    """Forget cached probe results (e.g. after a runtime pip install)."""
    _checked.clear()


# Command-line args whose non-default values signal that the user
# explicitly wants a feature, even though it may not be installed.
EXPLICIT_ARGS = {
    "repomap": ("map_tokens", "map_refresh", "map_multiplier_no_files"),
}


def explicit_notices(args, parser):
    """Warnings for features the user explicitly requested but which are unavailable.

    A feature counts as requested only when one of its args was set to a
    meaningful non-default value via command line / env / config file.
    """
    notices = []
    for cap, attr_names in EXPLICIT_ARGS.items():
        if available(cap):
            continue
        for attr in attr_names:
            value = getattr(args, attr, None)
            if not value:  # None/0/"" never signal an explicit request
                continue
            if value == parser.get_default(attr):
                continue
            notices.append(
                f"{CAPS[cap].title} requested but its dependencies are not installed."
                f" {hint(cap)}"
            )
            break
    return notices
