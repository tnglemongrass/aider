import argparse

import pytest

from aider import capabilities


@pytest.fixture(autouse=True)
def clear_cache():
    capabilities._checked.clear()
    yield
    capabilities._checked.clear()


def test_available_true_when_all_modules_present(monkeypatch):
    monkeypatch.setattr(
        capabilities.importlib.util, "find_spec", lambda name: object()
    )
    assert capabilities.available("voice") is True


def test_available_false_when_any_module_missing(monkeypatch):
    def find_spec(name):
        if name == "sounddevice":
            return None
        return object()

    monkeypatch.setattr(capabilities.importlib.util, "find_spec", find_spec)
    assert capabilities.available("voice") is False


def test_available_false_on_value_error(monkeypatch):
    def find_spec(name):
        raise ValueError("invalid name")

    monkeypatch.setattr(capabilities.importlib.util, "find_spec", find_spec)
    assert capabilities.available("litellm") is False


def test_available_cached(monkeypatch):
    calls = []

    def find_spec(name):
        calls.append(name)
        return object()

    monkeypatch.setattr(capabilities.importlib.util, "find_spec", find_spec)
    assert capabilities.available("lint") is True
    assert len(calls) == len(capabilities.CAPS["lint"].modules)
    assert capabilities.available("lint") is True
    assert len(calls) == len(capabilities.CAPS["lint"].modules)


def test_hint_mentions_extra():
    assert "aider-chat[voice]" in capabilities.hint("voice")
    assert "aider-chat[lint]" in capabilities.hint("repomap")


def test_all_caps_have_extra_and_modules():
    for name, cap in capabilities.CAPS.items():
        assert cap.modules, name
        assert cap.extra.startswith("aider-chat["), name


@pytest.fixture
def parser():
    from aider.args import get_parser

    return get_parser([], None)


def test_notice_silent_by_default(parser):
    args = parser.parse_args([])
    assert capabilities.explicit_notices(args, parser) == []


def test_notice_on_explicit_map_tokens(parser, monkeypatch):
    monkeypatch.setattr(capabilities, "available", lambda name: False)
    args = parser.parse_args(["--map-tokens", "2048"])
    notices = capabilities.explicit_notices(args, parser)
    assert len(notices) == 1
    assert "Repo map" in notices[0]
    assert "aider-chat[lint]" in notices[0]


def test_no_notice_for_explicit_zero(parser):
    args = parser.parse_args(["--map-tokens", "0"])
    assert capabilities.explicit_notices(args, parser) == []


def test_notice_on_nondefault_refresh(parser, monkeypatch):
    monkeypatch.setattr(capabilities, "available", lambda name: False)
    args = parser.parse_args(["--map-refresh", "always"])
    assert capabilities.explicit_notices(args, parser)


def test_no_notice_when_available(parser, monkeypatch):
    monkeypatch.setattr(capabilities, "available", lambda name: True)
    args = parser.parse_args(["--map-tokens", "2048"])
    assert capabilities.explicit_notices(args, parser) == []
