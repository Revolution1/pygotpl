package main

import (
	"encoding/json"
	"fmt"
	"os"
	"testing"
	"text/template"
)

type parserRequest struct {
	Engine   string `json:"engine"`
	Name     string `json:"name"`
	Template string `json:"template"`
}

type parserFixture struct {
	SchemaVersion int           `json:"schema_version"`
	ID            string        `json:"id"`
	Request       parserRequest `json:"request"`
}

type parserResult struct {
	Runtime          string  `json:"runtime"`
	CaseID           string  `json:"case_id"`
	Mode             string  `json:"mode"`
	Iterations       int     `json:"iterations"`
	NsPerOp          float64 `json:"ns_per_op"`
	AllocationsPerOp float64 `json:"allocations_per_op"`
	BytesPerOp       float64 `json:"bytes_per_op"`
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: go run benchmarks/go/parser.go FIXTURE")
		os.Exit(2)
	}
	contents, err := os.ReadFile(os.Args[1])
	if err != nil {
		parserFail(err)
	}
	var fixture parserFixture
	if err := json.Unmarshal(contents, &fixture); err != nil {
		parserFail(err)
	}
	if fixture.SchemaVersion != 1 || fixture.Request.Engine != "text" {
		parserFail(fmt.Errorf("unsupported benchmark fixture"))
	}
	benchmarkResult := testing.Benchmark(func(b *testing.B) {
		for b.Loop() {
			if _, err := template.New(fixture.Request.Name).Parse(fixture.Request.Template); err != nil {
				b.Fatal(err)
			}
		}
	})
	result := parserResult{
		Runtime:          "go",
		CaseID:           fixture.ID,
		Mode:             "parse",
		Iterations:       benchmarkResult.N,
		NsPerOp:          float64(benchmarkResult.NsPerOp()),
		AllocationsPerOp: float64(benchmarkResult.AllocsPerOp()),
		BytesPerOp:       float64(benchmarkResult.AllocedBytesPerOp()),
	}
	if err := json.NewEncoder(os.Stdout).Encode(result); err != nil {
		parserFail(err)
	}
}

func parserFail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(2)
}
