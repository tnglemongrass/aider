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

# Global flag to control whether to use SimpleLLM or LiteLLM
USE_LITELLM = os.environ.get("AIDER_USE_LITELLM", "").lower() == "true"


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


class LLMProxy:
    """Proxy that delegates to either SimpleLLM or LiteLLM based on USE_LITELLM flag"""
    
    _lazy_litellm = None
    _simple_llm = None
    
    def _load_litellm(self):
        """Compatibility method for tests that patch this"""
        if self._lazy_litellm is None:
            self._lazy_litellm = LazyLiteLLM()
        return self._lazy_litellm._load_litellm()
    
    def __getattr__(self, name):
        # Special handling for _lazy_module check
        if name == "_lazy_module":
            if USE_LITELLM:
                if self._lazy_litellm is None:
                    self._lazy_litellm = LazyLiteLLM()
                return self._lazy_litellm._lazy_module
            else:
                # SimpleLLM doesn't have _lazy_module, return None
                return None
        
        if USE_LITELLM:
            if self._lazy_litellm is None:
                self._lazy_litellm = LazyLiteLLM()
            return getattr(self._lazy_litellm, name)
        else:
            if self._simple_llm is None:
                from aider import simple_llm
                self._simple_llm = simple_llm
            return getattr(self._simple_llm, name)


litellm = LLMProxy()

__all__ = ['litellm']
