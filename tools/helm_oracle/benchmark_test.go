package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"sort"
	"strings"
	"testing"
	texttemplate "text/template"
)

type runtimeBenchmarkFixture struct {
	SchemaVersion int    `json:"schema_version"`
	ID            string `json:"id"`
	Reference     string `json:"reference"`
	Chart         struct {
		Name            string            `json:"name"`
		Version         string            `json:"version"`
		Templates       map[string]string `json:"templates"`
		StaticTemplates map[string]string `json:"static_templates"`
		Files           map[string]string `json:"files"`
	} `json:"chart"`
	Values       map[string]any            `json:"values"`
	CoreSources  map[string]string         `json:"core_sources"`
	CoreContexts map[string]map[string]any `json:"core_contexts"`
}

var (
	benchmarkParsedTemplate *texttemplate.Template
	benchmarkRenderedOutput map[string]string
)

func loadRuntimeBenchmarkFixture(tb testing.TB) runtimeBenchmarkFixture {
	tb.Helper()
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		tb.Fatal("cannot resolve benchmark source path")
	}
	path := filepath.Join(
		filepath.Dir(filename),
		"..", "..", "benchmarks", "helm", "fixtures", "runtime-v1.json",
	)
	data, err := os.ReadFile(path)
	if err != nil {
		tb.Fatal(err)
	}
	var fixture runtimeBenchmarkFixture
	if err := json.Unmarshal(data, &fixture); err != nil {
		tb.Fatal(err)
	}
	if fixture.SchemaVersion != 1 || fixture.ID == "" || fixture.Reference != "helm-v4.2.3" {
		tb.Fatalf("invalid runtime benchmark fixture metadata: %#v", fixture)
	}
	return fixture
}

func helmBenchmarkRequest(
	fixture runtimeBenchmarkFixture,
	templates map[string]string,
) request {
	return request{
		Name:        fixture.Chart.Name,
		Version:     fixture.Chart.Version,
		Templates:   templates,
		Files:       fixture.Chart.Files,
		Values:      fixture.Values,
		ReleaseName: "demo",
		Namespace:   "default",
	}
}

func compileCoreSources(tb testing.TB, sources map[string]string) *texttemplate.Template {
	tb.Helper()
	names := make([]string, 0, len(sources))
	for name := range sources {
		names = append(names, name)
	}
	sort.Strings(names)
	tmpl := texttemplate.New("root")
	for _, name := range names {
		var err error
		tmpl, err = tmpl.New(name).Parse(sources[name])
		if err != nil {
			tb.Fatal(err)
		}
	}
	return tmpl
}

func renderCoreBatch(
	tb testing.TB,
	tmpl *texttemplate.Template,
	contexts map[string]map[string]any,
) map[string]string {
	tb.Helper()
	names := make([]string, 0, len(contexts))
	for name := range contexts {
		names = append(names, name)
	}
	sort.Strings(names)
	output := make(map[string]string, len(names))
	for _, name := range names {
		var rendered strings.Builder
		if err := tmpl.ExecuteTemplate(&rendered, name, contexts[name]); err != nil {
			tb.Fatal(err)
		}
		output[name] = rendered.String()
	}
	return output
}

func TestRuntimeBenchmarkFixtureParity(t *testing.T) {
	fixture := loadRuntimeBenchmarkFixture(t)
	dynamic := execute(helmBenchmarkRequest(fixture, fixture.Chart.Templates))
	static := execute(helmBenchmarkRequest(fixture, fixture.Chart.StaticTemplates))
	if dynamic.Error != "" || static.Error != "" {
		t.Fatalf("fixture render failed: dynamic=%q static=%q", dynamic.Error, static.Error)
	}
	if !reflect.DeepEqual(dynamic.Output, static.Output) {
		t.Fatalf("dynamic and static output differ:\ndynamic=%#v\nstatic=%#v", dynamic.Output, static.Output)
	}
	expected := map[string]string{
		"benchmark/templates/config.txt":  "demo-benchmark|80,443,8080,8443,|abcdefghijklmnopqrstuvwxyz0123456789",
		"benchmark/templates/dynamic.txt": "demo-benchmark/example:v1",
	}
	if !reflect.DeepEqual(dynamic.Output, expected) {
		t.Fatalf("unexpected fixture output: %#v", dynamic.Output)
	}
}

func BenchmarkGoTextTemplateCompile(b *testing.B) {
	fixture := loadRuntimeBenchmarkFixture(b)
	b.ReportAllocs()
	b.ResetTimer()
	for range b.N {
		benchmarkParsedTemplate = compileCoreSources(b, fixture.CoreSources)
	}
}

func BenchmarkGoTextTemplateWarmBatch(b *testing.B) {
	fixture := loadRuntimeBenchmarkFixture(b)
	tmpl := compileCoreSources(b, fixture.CoreSources)
	b.ReportAllocs()
	b.ResetTimer()
	for range b.N {
		benchmarkRenderedOutput = renderCoreBatch(b, tmpl, fixture.CoreContexts)
	}
}

func BenchmarkHelmStaticCold(b *testing.B) {
	fixture := loadRuntimeBenchmarkFixture(b)
	req := helmBenchmarkRequest(fixture, fixture.Chart.StaticTemplates)
	b.ReportAllocs()
	b.ResetTimer()
	for range b.N {
		result := execute(req)
		if result.Error != "" {
			b.Fatal(result.Error)
		}
		benchmarkRenderedOutput = result.Output
	}
}

func BenchmarkHelmTplCold(b *testing.B) {
	fixture := loadRuntimeBenchmarkFixture(b)
	req := helmBenchmarkRequest(fixture, fixture.Chart.Templates)
	b.ReportAllocs()
	b.ResetTimer()
	for range b.N {
		result := execute(req)
		if result.Error != "" {
			b.Fatal(result.Error)
		}
		benchmarkRenderedOutput = result.Output
	}
}
