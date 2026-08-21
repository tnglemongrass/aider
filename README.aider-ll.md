## Lite vs full install

This fork defaults to a **lite** install (~100 MB instead of ~650 MB):
chat, code editing and git commits against any OpenAI-compatible API.
Model names can be listed/fuzzy-matched directly from your endpoint's
`/models` route.

Not included by default:
- repository map + tree-sitter linting (grep-ast/networkx/scipy)
- multi-provider LLM support (Anthropic, Gemini, Bedrock, ...) via litellm
- voice input

Unavailable features are simply hidden from `--help` and the command
menu; if you explicitly request one, aider prints the exact command
to enable it. Basic Python syntax checking remains built in.

Add only what you need:

    pip install aider-chat[lint]      # repo map + tree-sitter linting
    pip install aider-chat[litellm]   # all LLM providers
    pip install aider-chat[voice]     # voice input
    pip install aider-chat[all]       # everything, as before the split

Known as **aider-ll** ("local lite").

## Quickstart

From a checkout of this fork:

    python -m pip install -e .

Point aider at any OpenAI-compatible endpoint:

    export OPENAI_API_BASE=https://opencode.ai/zen/v1
    export OPENAI_API_KEY=public      # or your real key

    cd /path/to/your/project
    aider --model x-preview-f-free

Model ids come straight from the endpoint (`GET /models`) — no need to
know litellm's naming. Inside aider, `/models <prefix>` fuzzy-matches
them for you.

## Usage

- `--model <id>` selects the model; without `[litellm]` only
  OpenAI-compatible endpoints are supported (auth via `OPENAI_API_KEY`,
  endpoint via `OPENAI_API_BASE`).
- Chat, file edits and git commits work exactly like upstream aider.
- Missing features don't appear in `--help`, tab completion or `/help`;
  invoking one anyway (or setting its flag, e.g. `--map-tokens 2048`)
  prints the exact `pip install aider-chat[...]` command that enables it.
- Voice transcription uses your endpoint's `/audio/transcriptions`
  route (OpenAI-compatible), so no separate service is needed.
- Cost/context-window reporting is limited in lite (no litellm model
  database); token counts use tiktoken with a size-based fallback.

## Dev

Development setup:

    python -m pip install -e ".[dev]"       # pytest, build, pre-commit, uv, ...
    python -m pip install ".[lint,litellm]" # what CI installs for the test suite

Running tests (feature-dependent tests skip themselves automatically):

    python -m pytest tests/basic            # in a lite venv: only core deps

Verifying both modes before committing (branch convention):

    python3 -m venv /tmp/lite && /tmp/lite/bin/pip install -e . pytest
    python3 -m venv /tmp/all && /tmp/all/bin/pip install -e ".[all]" pytest
    /tmp/lite/bin/python -m pytest tests/basic      # lite
    /tmp/all/bin/python -m pytest tests/basic       # all

Rebuilding the pinned requirement files (requires [uv](https://docs.astral.sh/uv/)):

    scripts/pip-compile.sh

Building a (local) release:

    python -m build                         # sdist + wheel into dist/
    pip install dist/aider_chat-*.whl       # sanity-check the wheel
