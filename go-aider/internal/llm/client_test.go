package llm

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestComplete(t *testing.T) {
	expected := ChatCompletionResponse{
		ID:     "chatcmpl-1",
		Object: "chat.completion",
		Choices: []ChatCompletionChoice{
			{Index: 0, Message: ChatMessage{Role: "assistant", Content: "Hello!"}, FinishReason: "stop"},
		},
		Usage: Usage{PromptTokens: 5, CompletionTokens: 2, TotalTokens: 7},
	}

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/v1/chat/completions", r.URL.Path)
		assert.Equal(t, "Bearer test-key", r.Header.Get("Authorization"))
		assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

		var req ChatCompletionRequest
		require.NoError(t, json.NewDecoder(r.Body).Decode(&req))
		assert.Equal(t, "my-model", req.Model)
		assert.False(t, req.Stream)

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expected)
	}))
	defer srv.Close()

	client := NewClient(srv.URL, "test-key", "my-model")
	msgs := []ChatMessage{{Role: "user", Content: "Hi"}}
	resp, err := client.Complete(msgs, 100, 0.5)
	require.NoError(t, err)
	assert.Equal(t, "Hello!", resp.Choices[0].Message.Content)
	assert.Equal(t, 7, resp.Usage.TotalTokens)
}

func TestCompleteAPIError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		fmt.Fprint(w, `{"error":"invalid key"}`)
	}))
	defer srv.Close()

	client := NewClient(srv.URL, "bad-key", "m")
	_, err := client.Complete(nil, 0, 0)
	require.Error(t, err)
	assert.Contains(t, err.Error(), "401")
}

func TestCompleteStream(t *testing.T) {
	sseData := strings.Join([]string{
		`data: {"id":"1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"Hel"},"finish_reason":null}]}`,
		`data: {"id":"1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"lo!"},"finish_reason":null}]}`,
		`data: [DONE]`,
		"",
	}, "\n")

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req ChatCompletionRequest
		json.NewDecoder(r.Body).Decode(&req)
		assert.True(t, req.Stream)

		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, sseData)
	}))
	defer srv.Close()

	client := NewClient(srv.URL, "k", "m")
	var deltas []string
	full, err := client.CompleteStream(
		[]ChatMessage{{Role: "user", Content: "Hi"}},
		100, 0.5,
		func(d string) { deltas = append(deltas, d) },
	)
	require.NoError(t, err)
	assert.Equal(t, "Hello!", full)
	assert.Equal(t, []string{"Hel", "lo!"}, deltas)
}

func TestNewClientTrimsTrailingSlash(t *testing.T) {
	c := NewClient("https://api.example.com/", "k", "m")
	assert.Equal(t, "https://api.example.com", c.BaseURL)
}
