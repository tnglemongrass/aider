"""Platform and language detection utilities for Coder."""

import locale
import os
import platform
from datetime import datetime

# Optional dependency: used to convert locale codes (eg ``en_US``)
# into human-readable language names (eg ``English``).
try:
    from babel import Locale  # type: ignore
except ImportError:  # Babel not installed – we will fall back to a small mapping
    Locale = None


class PlatformDetector:
    """Detects platform and language information for the user."""

    def __init__(self, chat_language=None):
        """Initialize PlatformDetector.

        Args:
            chat_language: Optional explicit language override
        """
        self.chat_language = chat_language

    def normalize_language(self, lang_code):
        """Convert a locale code to a readable language name.

        Args:
            lang_code: Locale code like 'en_US' or 'fr'

        Returns:
            Human-readable language name like 'English' or 'French', or None
        """
        if not lang_code:
            return None

        if lang_code.upper() in ("C", "POSIX"):
            return None

        # Probably already a language name
        if (
            len(lang_code) > 3
            and "_" not in lang_code
            and "-" not in lang_code
            and lang_code[0].isupper()
        ):
            return lang_code

        # Preferred: Babel
        if Locale is not None:
            try:
                loc = Locale.parse(lang_code.replace("-", "_"))
                return loc.get_display_name("en").capitalize()
            except Exception:
                pass  # Fall back to manual mapping

        # Simple fallback for common languages
        fallback = {
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ru": "Russian",
        }
        primary_lang_code = lang_code.replace("-", "_").split("_")[0].lower()
        return fallback.get(primary_lang_code, lang_code)

    def get_user_language(self):
        """Detect the user's language preference.

        Detection order:
        1. self.chat_language if explicitly set
        2. locale.getlocale()
        3. LANG / LANGUAGE / LC_ALL / LC_MESSAGES environment variables

        Returns:
            Human-readable language name like 'English', or None
        """
        # Explicit override
        if self.chat_language:
            return self.normalize_language(self.chat_language)

        # System locale
        try:
            lang = locale.getlocale()[0]
            if lang:
                lang = self.normalize_language(lang)
            if lang:
                return lang
        except Exception:
            pass

        # Environment variables
        for env_var in ("LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES"):
            lang = os.environ.get(env_var)
            if lang:
                lang = lang.split(".")[0]  # Strip encoding if present
                return self.normalize_language(lang)

        return None

    def get_platform_info(
        self, repo=None, lint_cmds=None, auto_lint=True,
        test_cmd=None, auto_test=False
    ):
        """Get platform information text.

        Args:
            repo: GitRepo instance or None
            lint_cmds: Dict of lint commands
            auto_lint: Whether auto-linting is enabled
            test_cmd: Test command string
            auto_test: Whether auto-testing is enabled

        Returns:
            Formatted platform information text
        """
        platform_text = ""
        try:
            platform_text = f"- Platform: {platform.platform()}\n"
        except KeyError:
            # Skip platform info if it can't be retrieved
            platform_text = "- Platform information unavailable\n"

        shell_var = "COMSPEC" if os.name == "nt" else "SHELL"
        shell_val = os.getenv(shell_var)
        platform_text += f"- Shell: {shell_var}={shell_val}\n"

        user_lang = self.get_user_language()
        if user_lang:
            platform_text += f"- Language: {user_lang}\n"

        dt = datetime.now().astimezone().strftime("%Y-%m-%d")
        platform_text += f"- Current date: {dt}\n"

        if repo:
            platform_text += "- The user is operating inside a git repository\n"

        if lint_cmds:
            if auto_lint:
                platform_text += (
                    "- The user's pre-commit runs these lint commands, don't suggest running"
                    " them:\n"
                )
            else:
                platform_text += "- The user prefers these lint commands:\n"
            for lang, cmd in lint_cmds.items():
                if lang is None:
                    platform_text += f"  - {cmd}\n"
                else:
                    platform_text += f"  - {lang}: {cmd}\n"

        if test_cmd:
            if auto_test:
                platform_text += (
                    "- The user's pre-commit runs this test command, don't suggest running them: "
                )
            else:
                platform_text += "- The user prefers this test command: "
            platform_text += test_cmd + "\n"

        return platform_text
