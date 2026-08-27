from __future__ import annotations

from gotpl.funcs.sprout import INVENTORY


def test_inventory_identifies_the_pinned_sprout_release() -> None:
    assert INVENTORY.schema_version == 1
    assert INVENTORY.reference == "github.com/go-sprout/sprout"
    assert INVENTORY.version == "v1.1.1"


def test_inventory_preserves_registry_and_group_boundaries() -> None:
    assert set(INVENTORY.registries) == {
        "backward",
        "checksum",
        "conversion",
        "crypto",
        "encoding",
        "env",
        "filesystem",
        "maps",
        "network",
        "numeric",
        "random",
        "reflect",
        "regex",
        "regexp",
        "semver",
        "slices",
        "std",
        "strings",
        "time",
        "uniqueid",
    }
    assert "go-sprout/sprout.env" in INVENTORY.groups["all"].registries
    assert "go-sprout/sprout.env" not in INVENTORY.groups["hermetic"].registries
    assert "go-sprout/sprout.random" not in INVENTORY.groups["hermetic"].registries
    assert "go-sprout/sprout.network" not in INVENTORY.groups["hermetic"].registries


def test_inventory_distinguishes_raw_functions_aliases_and_notices() -> None:
    checksum = INVENTORY.registries["checksum"]
    assert "sha256Sum" in checksum.functions
    assert checksum.aliases["sha256Sum"] == ("sha256sum",)
    assert any(
        notice.kind.value == "deprecated" and notice.functions == ("sha256sum",)
        for notice in checksum.notices
    )

    regexp = INVENTORY.registries["regexp"]
    assert "mustRegexMatch" not in regexp.functions
    assert regexp.aliases["regexMatch"] == ("mustRegexMatch",)
    assert any(notice.kind.value == "info" for notice in regexp.notices)
