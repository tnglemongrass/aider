package commands

import (
	"bytes"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRegisterAndExecute(t *testing.T) {
	r := NewRegistry(&bytes.Buffer{})
	r.Register("test", "A test command", func(args string) string {
		return "result:" + args
	})

	out, found := r.Execute("/test hello")
	assert.True(t, found)
	assert.Equal(t, "result:hello", out)
}

func TestExecuteUnknown(t *testing.T) {
	r := NewRegistry(&bytes.Buffer{})
	out, found := r.Execute("/unknown")
	assert.True(t, found)
	assert.Contains(t, out, "Unknown command")
}

func TestExecuteNonCommand(t *testing.T) {
	r := NewRegistry(&bytes.Buffer{})
	out, found := r.Execute("not a command")
	assert.False(t, found)
	assert.Empty(t, out)
}

func TestIsCommand(t *testing.T) {
	assert.True(t, IsCommand("/help"))
	assert.True(t, IsCommand("  /model gpt-4"))
	assert.False(t, IsCommand("hello"))
	assert.False(t, IsCommand(""))
}

func TestRegisterDefaults(t *testing.T) {
	r := NewRegistry(&bytes.Buffer{})
	cleared := false
	RegisterDefaults(r, Callbacks{
		OnClear: func() { cleared = true },
	})

	// /help should work.
	out, found := r.Execute("/help")
	assert.True(t, found)
	assert.Contains(t, out, "/help")
	assert.Contains(t, out, "/quit")
	assert.Contains(t, out, "/model")

	// /clear should invoke callback.
	out, found = r.Execute("/clear")
	assert.True(t, found)
	assert.True(t, cleared)
	assert.Contains(t, out, "cleared")

	// /quit should return sentinel.
	out, found = r.Execute("/quit")
	assert.True(t, found)
	assert.Equal(t, "__QUIT__", out)

	// /exit should also return sentinel.
	out, found = r.Execute("/exit")
	assert.True(t, found)
	assert.Equal(t, "__QUIT__", out)
}

func TestDefaultCallbacksNil(t *testing.T) {
	r := NewRegistry(&bytes.Buffer{})
	RegisterDefaults(r, Callbacks{})

	out, _ := r.Execute("/model gpt-4")
	assert.Contains(t, out, "not configured")

	out, _ = r.Execute("/config")
	assert.Contains(t, out, "not configured")
}

func TestCommandWithNoArgs(t *testing.T) {
	r := NewRegistry(&bytes.Buffer{})
	r.Register("ping", "Ping", func(args string) string {
		return "pong:" + args
	})

	out, found := r.Execute("/ping")
	assert.True(t, found)
	assert.Equal(t, "pong:", out)
}
