package models

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/tnglemongrass/aider/go-aider/internal/llm"
)

func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	resp := llm.ModelListResponse{
		Data: []llm.ModelInfo{
			{ID: "gpt-4o", Object: "model", OwnedBy: "openai"},
			{ID: "gpt-3.5-turbo", Object: "model", OwnedBy: "openai"},
		},
	}
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/v1/models", r.URL.Path)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}))
}

func TestList(t *testing.T) {
	srv := newTestServer(t)
	defer srv.Close()

	mgr := NewManager(srv.URL, "key")
	models, err := mgr.List()
	require.NoError(t, err)
	assert.Len(t, models, 2)
	assert.Equal(t, "gpt-4o", models[0].ID)
}

func TestListCaches(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		resp := llm.ModelListResponse{Data: []llm.ModelInfo{{ID: "m1"}}}
		json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	mgr := NewManager(srv.URL, "")
	_, _ = mgr.List()
	_, _ = mgr.List()
	assert.Equal(t, 1, calls)
}

func TestInvalidate(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		resp := llm.ModelListResponse{Data: []llm.ModelInfo{{ID: "m1"}}}
		json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	mgr := NewManager(srv.URL, "")
	_, _ = mgr.List()
	mgr.Invalidate()
	_, _ = mgr.List()
	assert.Equal(t, 2, calls)
}

func TestHas(t *testing.T) {
	srv := newTestServer(t)
	defer srv.Close()

	mgr := NewManager(srv.URL, "key")
	ok, err := mgr.Has("gpt-4o")
	require.NoError(t, err)
	assert.True(t, ok)

	ok, err = mgr.Has("nonexistent")
	require.NoError(t, err)
	assert.False(t, ok)
}
