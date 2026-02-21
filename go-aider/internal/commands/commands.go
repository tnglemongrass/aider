// Package commands provides slash command handling for the chat session.
package commands

import (
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

// Handler is a function that handles a slash command.
// It receives the arguments after the command name and returns output text.
type Handler func(args string) string

// Registry holds all registered slash commands.
type Registry struct {
	commands map[string]entry
	writer   io.Writer
}

type entry struct {
	handler     Handler
	description string
}

// NewRegistry creates a Registry writing output to w. If w is nil, os.Stdout is used.
func NewRegistry(w io.Writer) *Registry {
	if w == nil {
		w = os.Stdout
	}
	return &Registry{
		commands: make(map[string]entry),
		writer:   w,
	}
}

// Register adds a command to the registry.
func (r *Registry) Register(name, description string, handler Handler) {
	r.commands[name] = entry{handler: handler, description: description}
}

// Execute runs a slash command. Returns the command output and whether it was found.
func (r *Registry) Execute(input string) (string, bool) {
	input = strings.TrimSpace(input)
	if !strings.HasPrefix(input, "/") {
		return "", false
	}

	parts := strings.SplitN(input[1:], " ", 2)
	name := parts[0]
	args := ""
	if len(parts) > 1 {
		args = strings.TrimSpace(parts[1])
	}

	e, ok := r.commands[name]
	if !ok {
		return fmt.Sprintf("Unknown command: /%s. Type /help for available commands.", name), true
	}

	return e.handler(args), true
}

// IsCommand reports whether the input starts with a slash command prefix.
func IsCommand(input string) bool {
	return strings.HasPrefix(strings.TrimSpace(input), "/")
}

// RegisterDefaults registers the standard set of slash commands.
func RegisterDefaults(r *Registry, callbacks Callbacks) {
	r.Register("help", "Show available commands", func(_ string) string {
		return r.helpText()
	})
	r.Register("quit", "Exit the application", func(_ string) string {
		return "__QUIT__"
	})
	r.Register("exit", "Exit the application", func(_ string) string {
		return "__QUIT__"
	})
	r.Register("clear", "Clear chat history", func(_ string) string {
		if callbacks.OnClear != nil {
			callbacks.OnClear()
		}
		return "Chat history cleared."
	})
	r.Register("model", "Switch model or list available", func(args string) string {
		if callbacks.OnModel != nil {
			return callbacks.OnModel(args)
		}
		return "Model switching not configured."
	})
	r.Register("system", "Show or set system prompt", func(args string) string {
		if callbacks.OnSystem != nil {
			return callbacks.OnSystem(args)
		}
		return "System prompt management not configured."
	})
	r.Register("config", "Show current configuration", func(_ string) string {
		if callbacks.OnConfig != nil {
			return callbacks.OnConfig()
		}
		return "Configuration display not configured."
	})
	r.Register("add", "Add file to context", func(args string) string {
		if callbacks.OnAdd != nil {
			return callbacks.OnAdd(args)
		}
		return "File context not configured."
	})
	r.Register("drop", "Remove file from context", func(args string) string {
		if callbacks.OnDrop != nil {
			return callbacks.OnDrop(args)
		}
		return "File context not configured."
	})
	r.Register("agents", "Show loaded AGENTS.md content", func(_ string) string {
		if callbacks.OnAgents != nil {
			return callbacks.OnAgents()
		}
		return "No AGENTS.md content loaded."
	})
}

// Callbacks holds optional callbacks for default commands that need session state.
type Callbacks struct {
	OnClear  func()
	OnModel  func(args string) string
	OnSystem func(args string) string
	OnConfig func() string
	OnAdd    func(args string) string
	OnDrop   func(args string) string
	OnAgents func() string
}

func (r *Registry) helpText() string {
	var names []string
	for name := range r.commands {
		names = append(names, name)
	}
	sort.Strings(names)

	var sb strings.Builder
	sb.WriteString("Available commands:\n")
	for _, name := range names {
		sb.WriteString(fmt.Sprintf("  /%s - %s\n", name, r.commands[name].description))
	}
	return sb.String()
}
