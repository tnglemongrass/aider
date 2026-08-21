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
