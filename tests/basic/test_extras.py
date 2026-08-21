"""Guard against drift between the capability registry and package metadata."""

import importlib.metadata

import pytest

from aider.capabilities import CAPS


def extras_of_installed_package():
    return set(importlib.metadata.metadata("aider-chat").get_all("Provides-Extra") or [])


def test_registry_extras_exist_in_package_metadata():
    installed_extras = extras_of_installed_package()
    for name, cap in CAPS.items():
        extra = cap.extra.split("[", 1)[1].rstrip("]")
        assert extra in installed_extras, (
            f"capability '{name}' points at extra '{extra}' "
            f"which is not declared in pyproject.toml"
        )


def test_all_extra_exists():
    assert "all" in extras_of_installed_package()


@pytest.mark.parametrize("expected", ["dev", "help", "browser", "playwright"])
def test_legacy_extras_still_declared(expected):
    assert expected in extras_of_installed_package()
