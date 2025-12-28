---
parent: Connecting to LLMs
nav_order: 500
---

# OpenAI compatible APIs

Aider can connect to any LLM which is accessible via an OpenAI compatible API endpoint.

First, install aider:

{% include install.md %}

## Simple configuration (environment variables only)

For the simplest setup, configure your API connection using only environment variables:

```bash
# Mac/Linux:
export OPENAI_API_BASE=<endpoint>
export OPENAI_API_KEY=<key>
export MODEL=openai/<model-name>

# Windows:
setx OPENAI_API_BASE <endpoint>
setx OPENAI_API_KEY <key>
setx MODEL openai/<model-name>
# ... restart shell after setx commands
```

Then start aider in your codebase without any additional arguments:

```bash
cd /to/your/project
aider
```

## Using command line arguments

Alternatively, you can set the API endpoint via environment variables and specify the model on the command line:

```bash
# Mac/Linux:
export OPENAI_API_BASE=<endpoint>
export OPENAI_API_KEY=<key>

# Windows:
setx OPENAI_API_BASE <endpoint>
setx OPENAI_API_KEY <key>
# ... restart shell after setx commands
```

Start working with aider and your OpenAI compatible API on your codebase:

```bash
# Change directory into your codebase
cd /to/your/project

# Prefix the model name with openai/
aider --model openai/<model-name>
```

See the [model warnings](warnings.html)
section for information on warnings which will occur
when working with models that aider is not familiar with.
