import importlib
import os
import warnings

from aider.dump import dump  # noqa: F401

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

AIDER_SITE_URL = "https://aider.chat"
AIDER_APP_NAME = "Aider"

os.environ["OR_SITE_URL"] = AIDER_SITE_URL
os.environ["OR_APP_NAME"] = AIDER_APP_NAME
os.environ["LITELLM_MODE"] = "PRODUCTION"

# `import litellm` takes 1.5 seconds, defer it!

VERBOSE = False


class LazyLiteLLM:
    _lazy_module = None

    def __getattr__(self, name):
        if name == "_lazy_module":
            return super()
        self._load_litellm()
        return getattr(self._lazy_module, name)

    def _load_litellm(self):
        if self._lazy_module is not None:
            return

        if VERBOSE:
            print("Loading litellm...")

        self._lazy_module = importlib.import_module("litellm")

        self._lazy_module.suppress_debug_info = True
        self._lazy_module.set_verbose = False
        self._lazy_module.drop_params = True
        self._lazy_module._logging._disable_debugging()


litellm = LazyLiteLLM()


def has_litellm():
    """True if the litellm package is installed, without importing it."""
    from aider.capabilities import available

    return available("litellm")


def use_openai_client(model=None):
    """Use the built-in OpenAI-compatible client instead of litellm.

    Without litellm installed we always use it. With litellm installed we
    prefer it, unless the user points at an OpenAI-compatible endpoint via
    OPENAI_API_BASE / OPENAI_API_HOST.
    """
    if not has_litellm():
        return True
    if os.environ.get("OPENAI_API_TYPE", "").lower() == "azure":
        return False
    if os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_API_HOST"):
        return True
    return False


__all__ = [litellm]
