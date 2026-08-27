package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	htmltemplate "html/template"
	"io"
	"os"
	"testing"
	texttemplate "text/template"

	sprig "github.com/Masterminds/sprig/v3"
)

type request struct {
	Engine          string `json:"engine"`
	Name            string `json:"name"`
	Template        string `json:"template"`
	Data            any    `json:"data"`
	FunctionProfile string `json:"function_profile"`
	ExecuteTemplate string `json:"execute_template"`
}

type fixture struct {
	SchemaVersion int     `json:"schema_version"`
	ID            string  `json:"id"`
	Request       request `json:"request"`
	Mode          string  `json:"mode"`
	Warmup        int     `json:"warmup"`
}

type result struct {
	Runtime          string  `json:"runtime"`
	CaseID           string  `json:"case_id"`
	Mode             string  `json:"mode"`
	Iterations       int     `json:"iterations"`
	NsPerOp          float64 `json:"ns_per_op"`
	AllocationsPerOp float64 `json:"allocations_per_op"`
	BytesPerOp       float64 `json:"bytes_per_op"`
	OutputSHA256     string  `json:"output_sha256"`
}

type executableTemplate interface {
	Execute(io.Writer, any) error
	ExecuteTemplate(io.Writer, string, any) error
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: go run benchmarks/go/main.go FIXTURE")
		os.Exit(2)
	}
	contents, err := os.ReadFile(os.Args[1])
	if err != nil {
		fail(err)
	}
	var benchmark fixture
	if err := json.Unmarshal(contents, &benchmark); err != nil {
		fail(err)
	}
	if benchmark.SchemaVersion != 1 || (benchmark.Request.Engine != "text" && benchmark.Request.Engine != "html") {
		fail(fmt.Errorf("unsupported benchmark fixture"))
	}
	if benchmark.Mode == "" {
		benchmark.Mode = "warm_render"
	}
	switch benchmark.Mode {
	case "warm_render", "cold_render", "writer_render", "named_render":
	default:
		fail(fmt.Errorf("unsupported benchmark mode: %s", benchmark.Mode))
	}
	if benchmark.Mode == "named_render" && benchmark.Request.ExecuteTemplate == "" {
		fail(fmt.Errorf("named benchmark requires execute_template"))
	}
	tmpl, err := parseBenchmarkTemplate(benchmark.Request)
	if err != nil {
		fail(err)
	}
	var output bytes.Buffer
	if err := executeBenchmarkTemplate(tmpl, &output, benchmark.Request); err != nil {
		fail(err)
	}
	outputDigest := fmt.Sprintf("%x", sha256.Sum256(output.Bytes()))
	for range benchmark.Warmup {
		output.Reset()
		current := tmpl
		if benchmark.Mode == "cold_render" {
			current, err = parseBenchmarkTemplate(benchmark.Request)
			if err != nil {
				fail(err)
			}
		}
		if err := executeBenchmarkTemplate(current, &output, benchmark.Request); err != nil {
			fail(err)
		}
	}
	benchmarkResult := testing.Benchmark(func(b *testing.B) {
		for b.Loop() {
			output.Reset()
			current := tmpl
			if benchmark.Mode == "cold_render" {
				current, err = parseBenchmarkTemplate(benchmark.Request)
				if err != nil {
					b.Fatal(err)
				}
			}
			if err := executeBenchmarkTemplate(current, &output, benchmark.Request); err != nil {
				b.Fatal(err)
			}
		}
	})
	encoded := result{
		Runtime:          "go",
		CaseID:           benchmark.ID,
		Mode:             benchmark.Mode,
		Iterations:       benchmarkResult.N,
		NsPerOp:          float64(benchmarkResult.NsPerOp()),
		AllocationsPerOp: float64(benchmarkResult.AllocsPerOp()),
		BytesPerOp:       float64(benchmarkResult.AllocedBytesPerOp()),
		OutputSHA256:     outputDigest,
	}
	if err := json.NewEncoder(os.Stdout).Encode(encoded); err != nil {
		fail(err)
	}
}

func parseBenchmarkTemplate(req request) (executableTemplate, error) {
	functions := texttemplate.FuncMap(nil)
	switch req.FunctionProfile {
	case "":
	case "sprig-v3.3.0":
		functions = sprig.TxtFuncMap()
	default:
		return nil, fmt.Errorf("unsupported function profile: %s", req.FunctionProfile)
	}
	switch req.Engine {
	case "text":
		builder := texttemplate.New(req.Name)
		if functions != nil {
			builder = builder.Funcs(functions)
		}
		return builder.Parse(req.Template)
	case "html":
		builder := htmltemplate.New(req.Name)
		if functions != nil {
			builder = builder.Funcs(functions)
		}
		return builder.Parse(req.Template)
	default:
		return nil, fmt.Errorf("unsupported benchmark engine: %s", req.Engine)
	}
}

func executeBenchmarkTemplate(tmpl executableTemplate, output io.Writer, req request) error {
	if req.ExecuteTemplate != "" {
		return tmpl.ExecuteTemplate(output, req.ExecuteTemplate, req.Data)
	}
	return tmpl.Execute(output, req.Data)
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(2)
}
