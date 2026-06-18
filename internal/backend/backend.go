// Backend abstraction for OLX CLI.
// Supports Crawl4AI (default) and Firecrawl scrapers.
package backend

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

// Type defines the scraping backend.
type Type string

const (
	Crawl4AI  Type = "crawl4ai"
	Firecrawl Type = "firecrawl"
)

// DefaultBaseURL returns the default base URL for a backend.
func (t Type) DefaultBaseURL() string {
	switch t {
	case Firecrawl:
		return "http://localhost:3002"
	default:
		return "https://crawl4ai:8000"
	}
}

// ParseType parses a backend type string, case-insensitive.
func ParseType(s string) (Type, error) {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "firecrawl":
		return Firecrawl, nil
	case "", "crawl4ai":
		return Crawl4AI, nil
	default:
		return "", fmt.Errorf("unknown backend %q: must be 'crawl4ai' or 'firecrawl'", s)
	}
}

// HTTPClient is the interface backends need to make HTTP requests.
type HTTPClient interface {
	Do(req *http.Request) (*http.Response, error)
}

// Scrape sends a URL to the configured backend and returns normalized JSON.
// The response is always normalized to Crawl4AI's format internally:
//
//	{"success":true,"results":[{"html":"...","markdown":{"raw_markdown":"..."}}]}
//
// so the rest of the CLI doesn't need to care about which backend is running.
func Scrape(ctx context.Context, client HTTPClient, baseURL string, backendType Type, olxURL string, priority int) (json.RawMessage, error) {
	switch backendType {
	case Firecrawl:
		return firecrawlScrape(ctx, client, baseURL, olxURL)
	default:
		return crawl4aiScrape(ctx, client, baseURL, olxURL, priority)
	}
}

// ── Crawl4AI ──────────────────────────────────────────────────────────────

func crawl4aiScrape(ctx context.Context, client HTTPClient, baseURL, olxURL string, priority int) (json.RawMessage, error) {
	body := map[string]any{
		"urls":     []string{olxURL},
		"priority": priority,
	}
	return doPost(ctx, client, baseURL+"/crawl", body)
}

// ── Firecrawl ─────────────────────────────────────────────────────────────

func firecrawlScrape(ctx context.Context, client HTTPClient, baseURL, olxURL string) (json.RawMessage, error) {
	body := map[string]any{
		"url":              olxURL,
		"formats":          []string{"markdown", "html"},
		"onlyMainContent":  false,
	}
	raw, err := doPost(ctx, client, baseURL+"/v1/scrape", body)
	if err != nil {
		return nil, err
	}
	return normalizeFirecrawlResponse(raw)
}

// normalizeFirecrawlResponse transforms Firecrawl's JSON into Crawl4AI format.
func normalizeFirecrawlResponse(raw json.RawMessage) (json.RawMessage, error) {
	var resp struct {
		Success bool `json:"success"`
		Data    *struct {
			Markdown string `json:"markdown"`
			HTML     string `json:"html"`
			Metadata *struct {
				Title       string `json:"title"`
				Description string `json:"description"`
				Language    string `json:"language"`
				SourceURL   string `json:"sourceURL"`
				StatusCode  int    `json:"statusCode"`
			} `json:"metadata"`
		} `json:"data"`
		Error string `json:"error"`
	}
	if err := json.Unmarshal(raw, &resp); err != nil {
		return nil, fmt.Errorf("firecrawl: parse response: %w", err)
	}
	if !resp.Success || resp.Data == nil {
		msg := resp.Error
		if msg == "" {
			msg = "unknown error"
		}
		return nil, fmt.Errorf("firecrawl: %s", msg)
	}

	statusCode := 200
	sourceURL := ""
	if resp.Data.Metadata != nil {
		statusCode = resp.Data.Metadata.StatusCode
		sourceURL = resp.Data.Metadata.SourceURL
	}

	normalized := map[string]any{
		"success": true,
		"results": []map[string]any{
			{
				"html":          resp.Data.HTML,
				"cleaned_html":  resp.Data.HTML,
				"markdown": map[string]string{
					"raw_markdown": resp.Data.Markdown,
				},
				"status_code":    statusCode,
				"redirected_url": sourceURL,
				"url":            sourceURL,
				"metadata": map[string]string{
					"title":       safeStr(resp.Data.Metadata, func(m *struct {
						Title       string `json:"title"`
						Description string `json:"description"`
						Language    string `json:"language"`
						SourceURL   string `json:"sourceURL"`
						StatusCode  int    `json:"statusCode"`
					}) string { return m.Title }),
					"description": safeStr(resp.Data.Metadata, func(m *struct {
						Title       string `json:"title"`
						Description string `json:"description"`
						Language    string `json:"language"`
						SourceURL   string `json:"sourceURL"`
						StatusCode  int    `json:"statusCode"`
					}) string { return m.Description }),
				},
				"links": map[string]any{
					"internal": []any{},
					"external": []any{},
				},
			},
		},
	}
	return json.Marshal(normalized)
}

func safeStr[T any](ptr *T, fn func(*T) string) string {
	if ptr == nil {
		return ""
	}
	return fn(ptr)
}

// ── HTTP helper ───────────────────────────────────────────────────────────

func doPost(ctx context.Context, client HTTPClient, url string, body any) (json.RawMessage, error) {
	b, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("backend: marshal body: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("backend: create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("backend: %s: %w", url, err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("backend: read response: %w", err)
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("backend: POST %s returned HTTP %d: %s", url, resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	return json.RawMessage(respBody), nil
}
