package main

import (
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"time"
)

type parseCase struct {
	Text        string `json:"text"`
	Nanoseconds int64  `json:"nanoseconds"`
	Formatted   string `json:"formatted"`
}

type operationInput struct {
	Operation string
	Value     int64
	Multiple  int64
}

type operationCase struct {
	Operation string `json:"operation"`
	Value     int64  `json:"value"`
	Multiple  int64  `json:"multiple"`
	Result    int64  `json:"result"`
}

type invalidCase struct {
	Text  string `json:"text"`
	Error string `json:"error"`
}

type fixture struct {
	SchemaVersion int             `json:"schema_version"`
	GoVersion     string          `json:"go_version"`
	Parse         []parseCase     `json:"parse"`
	Invalid       []invalidCase   `json:"invalid"`
	Operations    []operationCase `json:"operations"`
}

func main() {
	result, err := buildFixture()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func buildFixture() (fixture, error) {
	parseInputs := []string{
		"0",
		"+5s",
		"-2m3.4s",
		".5ms",
		"12us",
		"12µs",
		"12μs",
		"1h2m3s4ms5us6ns",
		"0.3333333333333333333h",
		"9007199254740993ns",
		"9223372036854775807ns",
		"-9223372036854775808ns",
	}
	parsed := make([]parseCase, 0, len(parseInputs))
	for _, input := range parseInputs {
		duration, err := time.ParseDuration(input)
		if err != nil {
			return fixture{}, fmt.Errorf("parse %q: %w", input, err)
		}
		parsed = append(parsed, parseCase{
			Text:        input,
			Nanoseconds: duration.Nanoseconds(),
			Formatted:   duration.String(),
		})
	}
	operationInputs := []operationInput{
		{"round", int64(2*time.Minute + 30*time.Second), int64(time.Minute)},
		{"round", -int64(2*time.Minute + 30*time.Second), int64(time.Minute)},
		{"round", 9_000_000_000_000_000_000, 5_000_000_000_000_000_000},
		{"round", -9_000_000_000_000_000_000, 5_000_000_000_000_000_000},
		{"truncate", int64(10*time.Minute + 10*time.Second), int64(3 * time.Minute)},
		{"truncate", -int64(10*time.Minute + 10*time.Second), int64(3 * time.Minute)},
		{"truncate", int64(time.Minute), -int64(time.Second)},
		{"add", 1<<63 - 1, 1},
		{"subtract", -1 << 63, 1},
		{"negate", -1 << 63, 0},
		{"multiply", 1<<63 - 1, 2},
		{"divide", int64(5 * time.Second), int64(2 * time.Second)},
		{"divide", -1 << 63, -1},
		{"modulo", int64(5 * time.Second), int64(2 * time.Second)},
	}
	operations := make([]operationCase, 0, len(operationInputs))
	for _, input := range operationInputs {
		value := time.Duration(input.Value)
		multiple := time.Duration(input.Multiple)
		var result time.Duration
		switch input.Operation {
		case "round":
			result = value.Round(multiple)
		case "truncate":
			result = value.Truncate(multiple)
		case "add":
			result = value + multiple
		case "subtract":
			result = value - multiple
		case "negate":
			result = -value
		case "multiply":
			result = value * multiple
		case "divide":
			result = value / multiple
		case "modulo":
			result = value % multiple
		default:
			return fixture{}, fmt.Errorf("unsupported operation %q", input.Operation)
		}
		operations = append(operations, operationCase{
			Operation: input.Operation,
			Value:     input.Value,
			Multiple:  input.Multiple,
			Result:    int64(result),
		})
	}
	invalidInputs := []string{
		"",
		"3",
		".s",
		"1d",
		"1h!",
		"1..s",
		"1h+2s",
		"1h2x3s",
		"9223372036854775808ns",
		"-9223372036854775809ns",
	}
	invalid := make([]invalidCase, 0, len(invalidInputs))
	for _, input := range invalidInputs {
		_, err := time.ParseDuration(input)
		if err == nil {
			return fixture{}, fmt.Errorf("expected parse failure for %q", input)
		}
		invalid = append(invalid, invalidCase{Text: input, Error: err.Error()})
	}
	return fixture{
		SchemaVersion: 2,
		GoVersion:     runtime.Version(),
		Parse:         parsed,
		Invalid:       invalid,
		Operations:    operations,
	}, nil
}
