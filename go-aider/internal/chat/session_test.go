package chat

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/tnglemongrass/aider/go-aider/internal/config"
	"github.com/tnglemongrass/aider/go-aider/internal/llm"
)

func fakeServer(t *testing.T) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/v1/chat/completions":
			var req llm.ChatCompletionRequest
			json.NewDecoder(r.Body).Decode(&req)
			if req.Stream {
				w.Header().Set("Content-Type", "text/event-stream")
				fmt.Fprint(w, "data: {\"id\":\"1\",\"object\":\"chat.completion.chunk\",\"choices\":[{\"index\":0,\"delta\":{\"content\":\"Hi!\"}}]}\n")
				fmt.Fprint(w, "data: [DONE]\n")
			} else {
				resp := llm.ChatCompletionResponse{
					ID:      "1",
					Choices: []llm.ChatCompletionChoice{{Message: llm.ChatMessage{Role: "assistant", Content: "Hello!"}}},
				}
				json.NewEncoder(w).Encode(resp)
			}
		case "/v1/models":
			resp := llm.ModelListResponse{Data: []llm.ModelInfo{{ID: "test-model"}}}
			json.NewEncoder(w).Encode(resp)
		}
	}))
}

func testConfig(serverURL string) *config.Config {
	return &config.Config{
		Model:       "test-model",
		APIKey:      "test-key",
		APIBase:     serverURL,
		MaxTokens:   100,
		Temperature: 0.5,
		Stream:      false,
		EditFormat:   "diff",
		Language:    "English",
	}
}

func TestNewSession(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)
	assert.NotNil(t, s)
	assert.Empty(t, s.Messages())
}

func TestRunQuit(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	inputs := []string{"/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
}

func TestRunEOF(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	reader := func(_ string) (string, error) {
		return "", io.EOF
	}

	err = s.Run(reader)
	require.NoError(t, err)
}

func TestRunChatNonStreaming(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	cfg := testConfig(srv.URL)
	cfg.Stream = false
	s, err := NewSession(cfg, &buf)
	require.NoError(t, err)

	inputs := []string{"Hello", "/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
	assert.Len(t, s.Messages(), 2) // user + assistant
}

func TestRunChatStreaming(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	cfg := testConfig(srv.URL)
	cfg.Stream = true
	s, err := NewSession(cfg, &buf)
	require.NoError(t, err)

	inputs := []string{"Hello", "/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
	assert.Len(t, s.Messages(), 2)
}

func TestClearHistory(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	inputs := []string{"Hello", "/clear", "/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
	assert.Empty(t, s.Messages())
}

func TestAddDropFile(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	dir := t.TempDir()
	testFile := filepath.Join(dir, "test.go")
	require.NoError(t, os.WriteFile(testFile, []byte("package main"), 0644))

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	inputs := []string{"/add " + testFile, "/drop " + testFile, "/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
	assert.Contains(t, buf.String(), "Added")
	assert.Contains(t, buf.String(), "Removed")
	assert.Empty(t, s.Files())
}

func TestSwitchModel(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	inputs := []string{"/model new-model", "/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
	assert.Contains(t, buf.String(), "Switched to model: new-model")
}

func TestBuildMessagesIncludesSystem(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	msgs := s.buildMessages("test")
	assert.True(t, len(msgs) >= 2) // system + user
	assert.Equal(t, "system", msgs[0].Role)
	assert.Contains(t, msgs[0].Content, "expert software developer")
	assert.Equal(t, "user", msgs[len(msgs)-1].Role)
}

func TestEmptyInput(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	inputs := []string{"", "  ", "/quit"}
	idx := 0
	reader := func(_ string) (string, error) {
		if idx >= len(inputs) {
			return "", io.EOF
		}
		line := inputs[idx]
		idx++
		return line, nil
	}

	err = s.Run(reader)
	require.NoError(t, err)
	assert.Empty(t, s.Messages())
}

func TestShowConfig(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	output := s.showConfig()
	assert.Contains(t, output, "test-model")
	assert.Contains(t, output, "English")
}

func TestDropFileNotInContext(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	result := s.dropFile("nonexistent.go")
	assert.Contains(t, result, "not in context")
}

func TestDropFileNoArgs(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	result := s.dropFile("")
	assert.Contains(t, result, "No files")
}

func TestListModels(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	result := s.switchModel("")
	assert.Contains(t, result, "test-model")
}

func TestBuildMessagesWithFiles(t *testing.T) {
	srv := fakeServer(t)
	defer srv.Close()

	var buf bytes.Buffer
	s, err := NewSession(testConfig(srv.URL), &buf)
	require.NoError(t, err)

	s.files["main.go"] = "package main"
	msgs := s.buildMessages("test")
	// system + file context system + user
	found := false
	for _, m := range msgs {
		if m.Role == "system" && strings.Contains(m.Content, "main.go") {
			found = true
		}
	}
	assert.True(t, found, "should include file context in messages")
}
