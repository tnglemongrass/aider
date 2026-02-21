// Package chat manages the interactive chat session with the LLM.
package chat

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/tnglemongrass/aider/go-aider/internal/agents"
	"github.com/tnglemongrass/aider/go-aider/internal/commands"
	"github.com/tnglemongrass/aider/go-aider/internal/config"
	"github.com/tnglemongrass/aider/go-aider/internal/llm"
	"github.com/tnglemongrass/aider/go-aider/internal/models"
	"github.com/tnglemongrass/aider/go-aider/internal/prompts"
	"github.com/tnglemongrass/aider/go-aider/internal/render"
)

// InputReader reads a line of user input. Returns the line and any error (io.EOF on end).
type InputReader func(prompt string) (string, error)

// Session manages the state of a single chat conversation.
type Session struct {
	cfg      *config.Config
	client   *llm.Client
	renderer *render.Renderer
	cmdReg   *commands.Registry
	modelMgr *models.Manager
	agents   *agents.Agents

	history []llm.ChatMessage
	files   map[string]string // filename -> content
	writer  io.Writer
}

// NewSession creates a new chat session from the given configuration.
func NewSession(cfg *config.Config, w io.Writer) (*Session, error) {
	if w == nil {
		w = os.Stdout
	}
	r, err := render.NewRenderer(w)
	if err != nil {
		return nil, fmt.Errorf("create renderer: %w", err)
	}

	client := llm.NewClient(cfg.APIBase, cfg.APIKey, cfg.Model)
	modelMgr := models.NewManager(cfg.APIBase, cfg.APIKey)
	ag := agents.Load()

	s := &Session{
		cfg:      cfg,
		client:   client,
		renderer: r,
		modelMgr: modelMgr,
		agents:   ag,
		history:  nil,
		files:    make(map[string]string),
		writer:   w,
	}

	reg := commands.NewRegistry(w)
	commands.RegisterDefaults(reg, commands.Callbacks{
		OnClear:  s.clearHistory,
		OnModel:  s.switchModel,
		OnSystem: s.systemPrompt,
		OnConfig: s.showConfig,
		OnAdd:    s.addFile,
		OnDrop:   s.dropFile,
		OnAgents: s.showAgents,
	})
	s.cmdReg = reg

	return s, nil
}

// Run starts the main chat loop using the provided input reader.
func (s *Session) Run(readInput InputReader) error {
	for {
		input, err := readInput("aider> ")
		if err != nil {
			if err == io.EOF {
				return nil
			}
			return err
		}
		input = strings.TrimSpace(input)
		if input == "" {
			continue
		}

		if output, isCmd := s.cmdReg.Execute(input); isCmd {
			if output == "__QUIT__" {
				return nil
			}
			fmt.Fprintln(s.writer, output)
			continue
		}

		if err := s.sendMessage(input); err != nil {
			fmt.Fprintf(s.writer, "Error: %v\n", err)
		}
	}
}

// Messages returns the current message history (read-only copy).
func (s *Session) Messages() []llm.ChatMessage {
	out := make([]llm.ChatMessage, len(s.history))
	copy(out, s.history)
	return out
}

// Files returns the current file context map.
func (s *Session) Files() map[string]string {
	out := make(map[string]string, len(s.files))
	for k, v := range s.files {
		out[k] = v
	}
	return out
}

func (s *Session) buildMessages(userMsg string) []llm.ChatMessage {
	var msgs []llm.ChatMessage

	// System prompt.
	sys := prompts.MainSystemPrompt(s.cfg.Language)
	if s.agents.HasContent() {
		sys += "\n\n" + s.agents.SystemContext()
	}
	msgs = append(msgs, llm.ChatMessage{Role: "system", Content: sys})

	// File context.
	if len(s.files) > 0 {
		var ctx strings.Builder
		ctx.WriteString("Files in context:\n")
		for name, content := range s.files {
			ctx.WriteString(fmt.Sprintf("\n--- %s ---\n%s\n", name, content))
		}
		msgs = append(msgs, llm.ChatMessage{Role: "system", Content: ctx.String()})
	}

	// History.
	msgs = append(msgs, s.history...)

	// Current message.
	msgs = append(msgs, llm.ChatMessage{Role: "user", Content: userMsg})

	return msgs
}

func (s *Session) sendMessage(userMsg string) error {
	s.history = append(s.history, llm.ChatMessage{Role: "user", Content: userMsg})
	msgs := s.buildMessages(userMsg)

	if s.cfg.Stream {
		var acc string
		full, err := s.client.CompleteStream(msgs, s.cfg.MaxTokens, s.cfg.Temperature, func(delta string) {
			var renderErr error
			acc, renderErr = s.renderer.RenderStream(acc, delta, false)
			if renderErr != nil {
				fmt.Fprintf(s.writer, "\nRender error: %v\n", renderErr)
			}
		})
		if err != nil {
			return err
		}
		// Flush remaining content.
		if acc != "" {
			if _, renderErr := s.renderer.RenderStream(acc, "", true); renderErr != nil {
				fmt.Fprintf(s.writer, "\nRender error: %v\n", renderErr)
			}
		}
		s.history = append(s.history, llm.ChatMessage{Role: "assistant", Content: full})
	} else {
		resp, err := s.client.Complete(msgs, s.cfg.MaxTokens, s.cfg.Temperature)
		if err != nil {
			return err
		}
		if len(resp.Choices) > 0 {
			content := resp.Choices[0].Message.Content
			s.history = append(s.history, llm.ChatMessage{Role: "assistant", Content: content})
			if err := s.renderer.Render(content); err != nil {
				return err
			}
		}
	}
	return nil
}

func (s *Session) clearHistory() {
	s.history = nil
}

func (s *Session) switchModel(args string) string {
	if args == "" {
		modelList, err := s.modelMgr.List()
		if err != nil {
			return fmt.Sprintf("Error listing models: %v", err)
		}
		var sb strings.Builder
		sb.WriteString("Available models:\n")
		for _, m := range modelList {
			marker := "  "
			if m.ID == s.client.Model {
				marker = "* "
			}
			sb.WriteString(fmt.Sprintf("%s%s\n", marker, m.ID))
		}
		return sb.String()
	}
	s.client.Model = args
	s.cfg.Model = args
	return fmt.Sprintf("Switched to model: %s", args)
}

func (s *Session) systemPrompt(args string) string {
	if args == "" {
		return prompts.MainSystemPrompt(s.cfg.Language)
	}
	s.cfg.Language = args
	return fmt.Sprintf("Language set to: %s", args)
}

func (s *Session) showConfig() string {
	return fmt.Sprintf("Model: %s\nAPI Base: %s\nMax Tokens: %d\nTemperature: %.1f\nStream: %v\nEdit Format: %s\nLanguage: %s",
		s.cfg.Model, s.cfg.APIBase, s.cfg.MaxTokens, s.cfg.Temperature, s.cfg.Stream, s.cfg.EditFormat, s.cfg.Language)
}

func (s *Session) addFile(args string) string {
	if args == "" {
		return "Usage: /add <filename>"
	}
	data, err := os.ReadFile(args)
	if err != nil {
		return fmt.Sprintf("Error reading %s: %v", args, err)
	}
	s.files[args] = string(data)
	return fmt.Sprintf("Added %s to context.", args)
}

func (s *Session) dropFile(args string) string {
	if args == "" {
		if len(s.files) == 0 {
			return "No files in context."
		}
		var sb strings.Builder
		sb.WriteString("Files in context:\n")
		for name := range s.files {
			sb.WriteString(fmt.Sprintf("  %s\n", name))
		}
		return sb.String()
	}
	if _, ok := s.files[args]; !ok {
		return fmt.Sprintf("File %s is not in context.", args)
	}
	delete(s.files, args)
	return fmt.Sprintf("Removed %s from context.", args)
}

func (s *Session) showAgents() string {
	if !s.agents.HasContent() {
		return "No AGENTS.md content loaded."
	}
	return fmt.Sprintf("Sources: %s\n\n%s", strings.Join(s.agents.Sources, ", "), s.agents.Content)
}
