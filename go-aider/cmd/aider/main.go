// go-aider is an AI-powered coding assistant compatible with any OpenAI-compatible API.
package main

import (
	"fmt"
	"io"
	"os"

	"github.com/chzyer/readline"
	"github.com/tnglemongrass/aider/go-aider/internal/chat"
	"github.com/tnglemongrass/aider/go-aider/internal/config"
)

func main() {
	cfg, err := config.Load(os.Args[1:])
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}

	if cfg.APIKey == "" {
		fmt.Fprintln(os.Stderr, "Warning: No API key configured. Set OPENAI_API_KEY or use --api-key.")
	}

	session, err := chat.NewSession(cfg, os.Stdout)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error creating session: %v\n", err)
		os.Exit(1)
	}

	rl, err := readline.NewEx(&readline.Config{
		Prompt:          "aider> ",
		HistoryFile:     historyPath(),
		InterruptPrompt: "^C",
		EOFPrompt:       "exit",
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error initializing readline: %v\n", err)
		os.Exit(1)
	}
	defer rl.Close()

	fmt.Println("go-aider - AI coding assistant")
	fmt.Printf("Model: %s | API: %s\n", cfg.Model, cfg.APIBase)
	fmt.Println("Type /help for commands, /quit to exit.")

	readInput := func(_ string) (string, error) {
		line, err := rl.Readline()
		if err == readline.ErrInterrupt {
			return "", io.EOF
		}
		return line, err
	}

	if err := session.Run(readInput); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

func historyPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	dir := home + "/.aider"
	_ = os.MkdirAll(dir, 0755)
	return dir + "/history"
}
