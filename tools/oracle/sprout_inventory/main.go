package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"slices"

	"github.com/go-sprout/sprout"
	"github.com/go-sprout/sprout/group/all"
	"github.com/go-sprout/sprout/group/hermetic"
	"github.com/go-sprout/sprout/registry/backward"
	"github.com/go-sprout/sprout/registry/checksum"
	"github.com/go-sprout/sprout/registry/conversion"
	"github.com/go-sprout/sprout/registry/crypto"
	"github.com/go-sprout/sprout/registry/encoding"
	"github.com/go-sprout/sprout/registry/env"
	"github.com/go-sprout/sprout/registry/filesystem"
	"github.com/go-sprout/sprout/registry/maps"
	"github.com/go-sprout/sprout/registry/network"
	"github.com/go-sprout/sprout/registry/numeric"
	"github.com/go-sprout/sprout/registry/random"
	"github.com/go-sprout/sprout/registry/reflect"
	"github.com/go-sprout/sprout/registry/regex"
	"github.com/go-sprout/sprout/registry/regexp"
	"github.com/go-sprout/sprout/registry/semver"
	slicesregistry "github.com/go-sprout/sprout/registry/slices"
	"github.com/go-sprout/sprout/registry/std"
	"github.com/go-sprout/sprout/registry/strings"
	"github.com/go-sprout/sprout/registry/time"
	"github.com/go-sprout/sprout/registry/uniqueid"
)

type noticeInventory struct {
	Functions []string `json:"functions"`
	Kind      string   `json:"kind"`
	Message   string   `json:"message"`
}

type registryInventory struct {
	UID       string              `json:"uid"`
	Functions []string            `json:"functions"`
	Aliases   map[string][]string `json:"aliases"`
	Notices   []noticeInventory   `json:"notices"`
}

type groupInventory struct {
	Registries []string `json:"registries"`
	Functions  []string `json:"functions"`
}

type inventory struct {
	Reference  string                       `json:"reference"`
	Version    string                       `json:"version"`
	Registries map[string]registryInventory `json:"registries"`
	Groups     map[string]groupInventory    `json:"groups"`
}

func registryFactories() map[string]func() sprout.Registry {
	return map[string]func() sprout.Registry{
		"backward":   func() sprout.Registry { return backward.NewRegistry() },
		"checksum":   func() sprout.Registry { return checksum.NewRegistry() },
		"conversion": func() sprout.Registry { return conversion.NewRegistry() },
		"crypto":     func() sprout.Registry { return crypto.NewRegistry() },
		"encoding":   func() sprout.Registry { return encoding.NewRegistry() },
		"env":        func() sprout.Registry { return env.NewRegistry() },
		"filesystem": func() sprout.Registry { return filesystem.NewRegistry() },
		"maps":       func() sprout.Registry { return maps.NewRegistry() },
		"network":    func() sprout.Registry { return network.NewRegistry() },
		"numeric":    func() sprout.Registry { return numeric.NewRegistry() },
		"random":     func() sprout.Registry { return random.NewRegistry() },
		"reflect":    func() sprout.Registry { return reflect.NewRegistry() },
		"regex":      func() sprout.Registry { return regex.NewRegistry() },
		"regexp":     func() sprout.Registry { return regexp.NewRegistry() },
		"semver":     func() sprout.Registry { return semver.NewRegistry() },
		"slices":     func() sprout.Registry { return slicesregistry.NewRegistry() },
		"std":        func() sprout.Registry { return std.NewRegistry() },
		"strings":    func() sprout.Registry { return strings.NewRegistry() },
		"time":       func() sprout.Registry { return time.NewRegistry() },
		"uniqueid":   func() sprout.Registry { return uniqueid.NewRegistry() },
	}
}

func sortedKeys[V any](values map[string]V) []string {
	keys := make([]string, 0, len(values))
	for key := range values {
		keys = append(keys, key)
	}
	slices.Sort(keys)
	return keys
}

func noticeKind(kind sprout.NoticeKind) string {
	switch kind {
	case sprout.NoticeKindDeprecated:
		return "deprecated"
	case sprout.NoticeKindInfo:
		return "info"
	case sprout.NoticeKindDebug:
		return "debug"
	default:
		return fmt.Sprintf("unknown:%d", kind)
	}
}

func inspectRegistry(registry sprout.Registry) registryInventory {
	handler := sprout.New()
	if err := handler.AddRegistry(registry); err != nil {
		panic(err)
	}

	functions := sortedKeys(handler.RawFunctions())
	aliases := make(map[string][]string, len(handler.RawAliases()))
	for original, names := range handler.RawAliases() {
		aliases[original] = slices.Clone(names)
		slices.Sort(aliases[original])
	}

	notices := make([]noticeInventory, 0, len(handler.Notices()))
	for _, notice := range handler.Notices() {
		functions := slices.Clone(notice.FunctionNames)
		slices.Sort(functions)
		notices = append(notices, noticeInventory{
			Functions: functions,
			Kind:      noticeKind(notice.Kind),
			Message:   notice.Message,
		})
	}

	return registryInventory{
		UID:       registry.UID(),
		Functions: functions,
		Aliases:   aliases,
		Notices:   notices,
	}
}

func inspectGroup(group *sprout.RegistryGroup) groupInventory {
	handler := sprout.New()
	if err := handler.AddGroups(group); err != nil {
		panic(err)
	}
	registryUIDs := make([]string, 0, len(group.Registries))
	for _, registry := range group.Registries {
		registryUIDs = append(registryUIDs, registry.UID())
	}
	return groupInventory{
		Registries: registryUIDs,
		Functions:  sortedKeys(handler.Build()),
	}
}

func main() {
	outputPath := flag.String("output", "", "write the inventory to this file")
	flag.Parse()

	registries := make(map[string]registryInventory)
	for name, factory := range registryFactories() {
		registries[name] = inspectRegistry(factory())
	}

	output := inventory{
		Reference:  "github.com/go-sprout/sprout",
		Version:    "v1.1.1",
		Registries: registries,
		Groups: map[string]groupInventory{
			"all":      inspectGroup(all.RegistryGroup()),
			"hermetic": inspectGroup(hermetic.RegistryGroup()),
		},
	}

	var writer io.Writer = os.Stdout
	if *outputPath != "" {
		file, err := os.Create(*outputPath)
		if err != nil {
			panic(err)
		}
		defer file.Close()
		writer = file
	}

	encoder := json.NewEncoder(writer)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(output); err != nil {
		panic(err)
	}
}
