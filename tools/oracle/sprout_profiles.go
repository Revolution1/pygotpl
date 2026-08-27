package main

import (
	"fmt"
	"io"
	"log/slog"
	"strings"
	texttemplate "text/template"

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
	stringsregistry "github.com/go-sprout/sprout/registry/strings"
	"github.com/go-sprout/sprout/registry/time"
	"github.com/go-sprout/sprout/registry/uniqueid"
)

func sproutRegistryFactories() map[string]func() sprout.Registry {
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
		"strings":    func() sprout.Registry { return stringsregistry.NewRegistry() },
		"time":       func() sprout.Registry { return time.NewRegistry() },
		"uniqueid":   func() sprout.Registry { return uniqueid.NewRegistry() },
	}
}

func sproutFunctions(profile string) (texttemplate.FuncMap, bool) {
	handler := sprout.New(sprout.WithLogger(slog.New(slog.NewTextHandler(io.Discard, nil))))
	switch profile {
	case "sprout-all":
		if err := handler.AddGroups(all.RegistryGroup()); err != nil {
			panic(err)
		}
	case "sprout-hermetic":
		if err := handler.AddGroups(hermetic.RegistryGroup()); err != nil {
			panic(err)
		}
	default:
		name, found := strings.CutPrefix(profile, "sprout-registry:")
		if !found {
			return nil, false
		}
		factory, exists := sproutRegistryFactories()[name]
		if !exists {
			return texttemplate.FuncMap{
				"__invalid_profile": func() (string, error) {
					return "", fmt.Errorf("unsupported Sprout registry %q", name)
				},
			}, true
		}
		if err := handler.AddRegistry(factory()); err != nil {
			panic(err)
		}
	}
	return handler.Build(), true
}
