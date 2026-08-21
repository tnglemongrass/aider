"""Central registry of optional features and their dependencies.

Each entry maps a feature name to the modules it requires and the pip
extra that provides them. UX surfaces (CLI help, slash commands, startup
notices) consult this registry so unavailable features are invisible
instead of advertised and broken.
"""

import importlib.util


class Capability:
    def __init__(self, modules, extra):
        self.modules = tuple(modules)
        self.extra = extra


CAPS = {
    "voice": Capability(
        modules=("pydub", "sounddevice", "soundfile"),
        extra="aider-chat[voice]",
    ),
    "repomap": Capability(
        modules=("grep_ast", "networkx"),
        extra="aider-chat[lint]",
    ),
    "lint": Capability(
        modules=("grep_ast", "flake8"),
        extra="aider-chat[lint]",
    ),
    "litellm": Capability(
        modules=("litellm",),
        extra="aider-chat[litellm]",
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
