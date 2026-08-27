from __future__ import annotations

import base64
import re
import uuid

import pytest

from gotpl import Template, TemplateExecutionError
from gotpl.funcs.sprig import generic_func_map
from gotpl.funcs.sprout import Handler, group, registry
from gotpl.funcs.sprout.inventory import INVENTORY

from .support import TemplateRequest, run_go_oracle_many

_MAPS_SOURCE = (
    '{{$d := dict "a" 1 "nested" (dict "x" 2) "a.b" 3}}'
    '{{$d | get "a"}}|{{$d | hasKey "missing"}}|{{$d | pick "a"}}|'
    '{{$d | omit "nested"}}|{{$d | dig "nested.x"}}|{{$d | dig `a\\.b`}}|'
    '{{$d | set "z" 9}}|{{$d | unset "a"}}|'
    '{{merge (dict "a" 1) (dict "a" 2 "b" 3)}}|'
    '{{mergeOverwrite (dict "a" 1) (dict "a" 2 "b" 3)}}'
    '|{{$k := dict "a" 1}}{{keys $k}}|{{values $k}}|{{pluck "a" $k}}'
)
_NUMERIC_SOURCE = (
    "{{add 1 2 3}}|{{add 1.5 2 3}}|{{addf 0.1 0.2}}|{{add1 4}}|"
    "{{sub 10 2 3}}|{{mul 2 3 4}}|{{mulf 1.5 2}}|{{div 20 3}}|"
    "{{divf 20 4}}|{{mod 7 4}}|{{min 3 1 2}}|{{minf 3.5 1.2 2.1}}|"
    "{{max 3 8 2}}|{{maxf 3.5 8.2 2.1}}|{{floor 3.9}}|{{ceil 3.1}}|"
    "{{round 3.14159 3}}"
)
_CONVERSION_SOURCE = (
    '{{toBool "true"}}|{{toBool 0}}|{{toInt "42"}}|{{toInt64 3.9}}|'
    '{{toUint 7}}|{{toUint64 8}}|{{toFloat64 "1.25"}}|'
    '{{toOctal "755"}}|{{toString 12.5}}|{{toDuration "1h2m3s"}}|'
    '{{toDuration 1000}}|{{toDate "2006-01-02" "2024-03-02"}}|'
    '{{toLocalDate "2006-01-02 15:04" "UTC" "2024-03-02 04:05"}}'
)
_REFLECT_SOURCE = (
    '{{typeOf .}}|{{kindOf .}}|{{typeIs "map[string]interface {}" .}}|'
    '{{typeIsLike "map[string]interface {}" .}}|{{kindIs "map" .}}|'
    "{{deepEqual . .}}|{{deepCopy .}}"
)
_SLICES_SOURCE = (
    "{{$l := list 1 2 2 0 3}}{{$l | append 4}}|{{$l | prepend 9}}|"
    "{{concat (list 1 2) (list 3 4)}}|{{$l | chunk 2}}|{{$l | uniq}}|"
    "{{$l | compact}}|{{flatten (list 1 (list 2 (list 3)))}}|"
    "{{flattenDepth 1 (list 1 (list 2 (list 3)))}}|{{$l | slice 1 3}}|"
    "{{$l | has 2}}|{{$l | without 2 3}}|{{$l | rest}}|{{$l | initial}}|"
    "{{$l | first}}|{{$l | last}}|{{$l | reverse}}|"
    '{{sortAlpha (list "b" "a")}}|{{splitList "," "a,b"}}|'
    '{{strSlice (list 1 nil "x")}}|{{until -3}}|{{untilStep 5 0 -2}}'
)
_STRINGS_SOURCE = (
    '{{nospace " a\\t b"}}|{{trim "  foo  "}}|{{trimAll "-o" "-f--o-o-"}}|'
    '{{trimPrefix "-f" "-foo-"}}|{{trimSuffix "o-" "-foo-"}}|'
    '{{contains "oo" "foo"}}|{{hasPrefix "fo" "foo"}}|{{hasSuffix "oo" "foo"}}|'
    '{{toLower "FOO"}}|{{toUpper "foo"}}|{{replace "o" "a" "foo"}}|'
    '{{repeat 3 "foo"}}|{{join "-" .Items}}|{{trunc -3 "foobar"}}|'
    '{{ellipsis 6 "foooooo"}}|{{ellipsisBoth 4 9 "foooboooooo"}}|'
    '{{initials " Foo  bar"}}|{{plural "single" "many" 1}}|'
    '{{wrap 10 "This is a long string"}}|{{wrapWith 4 "/" "abcdefgh x"}}|'
    '{{quote "foo" nil "👍"}}|{{squote "foo" nil "👍"}}|'
    '{{toCamelCase "___complex__case_"}}|{{toKebabCase "HTTPServer"}}|'
    '{{toPascalCase "foo-bar_baz"}}|{{toDotCase "foo-bar_baz"}}|'
    '{{toPathCase "foo-bar_baz"}}|{{toConstantCase "HTTP20xOK"}}|'
    '{{toSnakeCase "Duration2m3s"}}|{{toTitleCase "foo-bar_baz"}}|'
    '{{untitle "Foo  Bar"}}|{{swapCase "Foo-Bar_baz"}}|'
    '{{capitalize "👍 good"}}|{{uncapitalize "123Boo_bar"}}|'
    '{{$s := split "$" "foo$bar$"}}{{$s._0}}/{{$s._1}}/{{$s._2}}|'
    '{{$n := splitn "$" 2 "foo$bar$baz"}}{{$n._0}}/{{$n._1}}|'
    '{{substr -3 -1 "foobar"}}|{{indent 3 "foo\\n bar"}}|'
    '{{nindent 3 "foo"}}|{{seq 0 3 10}}|{{escape ".:" "a.b:c\\\\d"}}|'
    '{{unescape ".:" "a\\\\.b\\\\:c\\\\\\\\d"}}'
)
_REGEX_SOURCE = (
    r"{{regexFind `(\w+)=(\w+)` .V}}|"
    r"{{regexFindAll `(\w+)=(\w+)` 1 .V}}|"
    r"{{regexMatch `^a` .V}}|{{regexSplit `\s+` -1 .V}}|"
    r'{{regexReplaceAll `(\w+)=(\w+)` "$2:$1" .V}}|'
    r'{{regexReplaceAllLiteral `\w+` "$1" .V}}|'
    r'{{regexQuoteMeta "a+b"}}|{{regexFindGroups `(\w+)=(\w+)` .V}}|'
    r"{{regexFindAllGroups `(\w+)=(\w+)` -1 .V}}|"
    r"{{regexFindNamed `(?P<key>\w+)=(?P<value>\w+)` .V}}|"
    r"{{regexFindAllNamed `(?P<key>\w+)=(?P<value>\w+)` -1 .V}}"
)
_REGEXP_SOURCE = (
    r"{{regexFind `(\w+)=(\w+)` .V}}|"
    r"{{regexFindAll `(\w+)=(\w+)` .V 1}}|"
    r"{{regexMatch `^a` .V}}|{{regexSplit `\s+` .V -1}}|"
    r'{{regexReplaceAll `(\w+)=(\w+)` .V "$2:$1"}}|'
    r'{{regexReplaceAllLiteral `\w+` .V "$1"}}|'
    r'{{regexQuoteMeta "a+b"}}|{{regexFindGroups `(\w+)=(\w+)` .V}}|'
    r"{{regexFindAllGroups `(\w+)=(\w+)` -1 .V}}|"
    r"{{regexFindNamed `(?P<key>\w+)=(?P<value>\w+)` .V}}|"
    r"{{regexFindAllNamed `(?P<key>\w+)=(?P<value>\w+)` -1 .V}}"
)
_NETWORK_SOURCE = (
    '{{parseIP "10.42.0.1"}}|{{parseIP "2001:0db8::1"}}|'
    '{{parseMAC "01-23-45-67-89-AB"}}|{{parseCIDR "10.42.1.2/16"}}|'
    '{{ipVersion "10.42.0.1"}}|{{ipVersion "2001:db8::1"}}|'
    '{{ipIsLoopback "127.0.0.1"}}|{{ipIsGlobalUnicast "8.8.8.8"}}|'
    '{{ipIsMulticast "ff02::1"}}|{{ipIsPrivate "fd00::1"}}|'
    '{{parseIP "10.42.0.255" | ipIncrement}}|'
    '{{parseIP "2001:db8::1:0" | ipDecrement}}|'
    '{{cidrContains "10.42.0.0/16" "10.42.1.1"}}|'
    '{{cidrSize "2001:db8::/120"}}|{{cidrRangeList "10.42.0.1/30"}}|'
    '{{cidrFirst "10.42.1.1/16"}}|{{cidrLast "2001:db8::1/120"}}|'
    '{{cidrOverlap "10.42.1.0/24" "10.42.0.0/16"}}'
)
_UNIQUEID_SOURCE = (
    '{{uuidv5 "dns" "python.org"}}|{{uuidv5 "DNS" "python.org"}}|'
    '{{uuidv3 "dns" "python.org"}}|{{uuidNil}}|'
    '{{isUUID "886313e1-3b8a-5372-9b90-0c9aee199e5d"}}|'
    '{{isUUID "urn:uuid:886313e1-3b8a-5372-9b90-0c9aee199e5d"}}|'
    '{{uuidVersion "0bcce080-0c83-11ef-8000-000000000000"}}|'
    '{{uuidVersion "018f5395-4e88-7000-8000-000000000000"}}|'
    '{{uuidTime "0bcce080-0c83-11ef-8000-000000000000"}}'
)
_TIME_SOURCE = (
    '{{$t := fromUnix "1715094245"}}'
    '{{$n := fromUnixMicro "1715094245123456"}}'
    '{{date "02 Jan 06 15:04 -0700" $t}}|'
    '{{dateInZone "02 Jan 06 15:04 -0700" $t "UTC"}}|'
    '{{duration "93784"}}|{{unixEpoch $t}}|{{toUnix $t}}|'
    "{{toUnixMilli $n}}|{{toUnixMicro $n}}|"
    '{{fromUnixMilli "1715094245123"}}|'
    '{{date "02 Jan 06 16:04 -0700" (dateModify "1h" $t)}}|'
    '{{durationRound "2400h5s"}}|{{htmlDate $t}}|'
    '{{htmlDateInZone $t "UTC"}}'
)
_CRYPTO_SOURCE = (
    '{{derivePassword 1 "short" "password" "user" "example.com"}}|'
    '{{encryptAES "secret" ""}}|{{decryptAES "secret" ""}}'
)
_GROUP_SOURCE = (
    '{{sha256Sum "hello"}}|{{toInt "42"}}|{{pathBase "/a/b"}}|'
    '{{regexMatch `^a` "abc"}}|{{toUpper "hello"}}|{{uuidNil}}'
)

_CASES = (
    ("crypto", _CRYPTO_SOURCE),
    ("time", _TIME_SOURCE),
    ("uniqueid", _UNIQUEID_SOURCE),
    ("network", _NETWORK_SOURCE),
    ("regex", _REGEX_SOURCE),
    ("regexp", _REGEXP_SOURCE),
    (
        "strings",
        _STRINGS_SOURCE,
    ),
    (
        "slices",
        _SLICES_SOURCE,
    ),
    (
        "reflect",
        _REFLECT_SOURCE,
    ),
    (
        "conversion",
        _CONVERSION_SOURCE,
    ),
    (
        "numeric",
        _NUMERIC_SOURCE,
    ),
    (
        "maps",
        _MAPS_SOURCE,
    ),
    (
        "encoding",
        '{{base64Encode "Hello World"}}|'
        '{{base64Decode "SGVsbG8gV29ybGQ="}}|'
        '{{base32Encode "Hello World"}}|'
        '{{base32Decode "JBSWY3DPEBLW64TMMQ======"}}|'
        '{{fromJSON `{"foo":55}`}}|{{toJSON .}}|'
        "{{toPrettyJSON .}}|{{toRawJSON .}}",
    ),
    (
        "backward",
        '{{urlJoin (urlParse "https://example.com/a?q=x")}}',
    ),
    (
        "checksum",
        '{{sha1Sum "hello"}}|{{sha256sum "hello"}}|'
        '{{md5Sum "hello"}}|{{adler32Sum "hello"}}',
    ),
    (
        "filesystem",
        '{{pathBase "/a/b/"}}|{{pathDir "/a/b/"}}|'
        '{{pathExt "a.tar.gz"}}|{{pathClean "a//b/../c"}}|'
        '{{pathIsAbs "/a"}}',
    ),
    (
        "semver",
        '{{semverCompare ">=1.2.0 <2.0.0" "1.5.3"}}|{{semver "1.2.3-beta.1+build"}}',
    ),
    (
        "std",
        '{{hello}}|{{default "d" ""}}|{{empty 0}}|{{all 1 "x"}}|'
        '{{any 0 "x"}}|{{coalesce 0 "x"}}|'
        '{{ternary "yes" "no" true}}|{{cat "a" nil "b"}}',
    ),
)

_SUPPLEMENTAL_EVIDENCE = {
    "crypto": frozenset(
        {
            "bcrypt",
            "htpasswd",
            "derivePassword",
            "genPrivateKey",
            "buildCustomCert",
            "genCA",
            "genCAWithKey",
            "genSelfSignedCert",
            "genSelfSignedCertWithKey",
            "genSignedCert",
            "genSignedCertWithKey",
            "encryptAES",
            "decryptAES",
        }
    ),
    "encoding": frozenset({"fromYAML", "toYAML", "toIndentYAML"}),
    "random": frozenset(
        {
            "randAlphaNum",
            "randAlpha",
            "randAscii",
            "randNumeric",
            "randBytes",
            "randInt",
        }
    ),
    "reflect": frozenset({"hasField"}),
    "strings": frozenset({"shuffle"}),
    "time": frozenset({"now", "dateAgo"}),
    "uniqueid": frozenset({"uuidv4", "uuidv7"}),
}


def _data_for(registry_name: str) -> object:
    if registry_name == "encoding":
        return {"foo": 55, "html": "<b>"}
    if registry_name == "reflect":
        return {"a": 1}
    if registry_name == "strings":
        return {"Items": ["a", None, 1, True]}
    if registry_name in {"regex", "regexp"}:
        return {"V": "a=1 b=2"}
    return None


@pytest.mark.parametrize(("registry_name", "source"), _CASES)
def test_implemented_sprout_registries_match_the_pinned_oracle(
    registry_name: str, source: str
) -> None:
    expected = run_go_oracle_many(
        [
            TemplateRequest(
                engine="text",
                name=registry_name,
                template=source,
                data=_data_for(registry_name),
                function_profile=f"sprout-registry:{registry_name}",
            )
        ]
    )[0]
    functions = Handler(registry(registry_name)).build()

    data = _data_for(registry_name)
    assert expected == {
        "output": Template(source, name=registry_name, functions=functions).render(
            data
        ),
        "error": None,
    }


def test_sprout_environment_registry_matches_the_pinned_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYGOTPL_SPROUT_TEST", "hello world")
    source = '{{env "PYGOTPL_SPROUT_TEST"}}|{{expandEnv "$PYGOTPL_SPROUT_TEST/x"}}'
    request = TemplateRequest(
        engine="text",
        name="env",
        template=source,
        data=None,
        function_profile="sprout-registry:env",
    )
    expected = run_go_oracle_many([request])[0]
    functions = Handler(registry("env")).build()

    assert expected == {
        "output": Template(source, name="env", functions=functions).render(),
        "error": None,
    }


def test_sprout_random_and_generated_uuid_shapes_match_upstream_contracts() -> None:
    requests = [
        TemplateRequest(
            engine="text",
            name=name,
            template=source,
            data=None,
            function_profile=f"sprout-registry:{profile}",
        )
        for name, profile, source in (
            ("alpha-numeric", "random", "{{randAlphaNum 64}}"),
            ("alpha", "random", "{{randAlpha 64}}"),
            ("numeric", "random", "{{randNumeric 64}}"),
            ("ascii", "random", "{{randAscii 64}}"),
            ("bytes", "random", "{{randBytes 32}}"),
            ("integer", "random", "{{randInt -10 20}}"),
            ("shuffle", "strings", '{{shuffle "foo 👍 bar"}}'),
            ("uuid-v4", "uniqueid", "{{uuidv4}}"),
            ("uuid-v7", "uniqueid", "{{uuidv7}}"),
        )
    ]
    upstream = run_go_oracle_many(requests)
    random_functions = Handler(registry("random")).build()
    string_functions = Handler(registry("strings")).build()
    uniqueid_functions = Handler(registry("uniqueid")).build()
    functions_by_profile = {
        "sprout-registry:random": random_functions,
        "sprout-registry:strings": string_functions,
        "sprout-registry:uniqueid": uniqueid_functions,
    }
    local = [
        Template(
            request["template"],
            functions=functions_by_profile[request.get("function_profile", "")],
        ).render()
        for request in requests
    ]

    for results in ([item["output"] for item in upstream], local):
        (
            alpha_numeric,
            alpha,
            numeric,
            ascii_text,
            encoded,
            integer,
            shuffled,
            uuid_v4,
            uuid_v7,
        ) = results
        assert alpha_numeric is not None and len(alpha_numeric) == 64
        assert all(
            character.isascii() and character.isalnum() for character in alpha_numeric
        )
        assert (
            alpha is not None
            and len(alpha) == 64
            and alpha.isascii()
            and alpha.isalpha()
        )
        assert (
            numeric is not None
            and len(numeric) == 64
            and numeric.isascii()
            and numeric.isdigit()
        )
        assert ascii_text is not None and len(ascii_text) == 64
        assert all(32 <= ord(character) <= 126 for character in ascii_text)
        assert encoded is not None and len(base64.b64decode(encoded)) == 32
        assert integer is not None and -10 <= int(integer) < 20
        assert shuffled is not None
        assert sorted(shuffled) == sorted("foo 👍 bar")
        assert uuid_v4 is not None and uuid.UUID(uuid_v4).version == 4
        assert uuid_v7 is not None and uuid.UUID(uuid_v7).version == 7


def test_sprout_yaml_functions_match_the_pinned_oracle() -> None:
    pytest.importorskip("yaml")
    source = "{{fromYAML .Input}}|{{toYAML .Mapping}}|{{toIndentYAML 8 .Nested}}"
    data = {
        "Input": "foo: 55\nbar:\n  baz: 1\n",
        "Mapping": {"foo": 55, "bar": "baz"},
        "Nested": {"foo": {"baz": "bar", "bar": "baz"}, "bar": "baz"},
    }
    request = TemplateRequest(
        engine="text",
        name="encoding-yaml",
        template=source,
        data=data,
        function_profile="sprout-registry:encoding",
    )
    expected = run_go_oracle_many([request])[0]
    functions = Handler(registry("encoding")).build()

    assert expected == {
        "output": Template(source, name="encoding-yaml", functions=functions).render(
            data
        ),
        "error": None,
    }


def test_sprout_now_and_date_ago_match_the_pinned_wall_clock_contract() -> None:
    source = "{{dateAgo (now)}}"
    request = TemplateRequest(
        engine="text",
        name="time-wall-clock",
        template=source,
        data=None,
        function_profile="sprout-registry:time",
    )
    expected = run_go_oracle_many([request])[0]
    actual = Template(
        source,
        functions=Handler(registry("time")).build(),
    ).render()

    assert expected["error"] is None
    assert expected["output"] in {"0s", "1s"}
    assert actual in {"0s", "1s"}


def test_sprout_has_field_failure_matches_the_pinned_non_struct_contract() -> None:
    source = '{{hasField "x" .}}'
    data = {"x": 1}
    expected = run_go_oracle_many(
        [
            TemplateRequest(
                engine="text",
                name="reflect-has-field-error",
                template=source,
                data=data,
                function_profile="sprout-registry:reflect",
            )
        ]
    )[0]

    error = expected["error"]
    assert error is not None
    assert "last argument must be a struct" in error.get("message", "")
    functions = Handler(registry("reflect")).build()
    with pytest.raises(TemplateExecutionError, match="last argument must be a struct"):
        Template(source, functions=functions).render(data)


def test_every_exposed_sprout_function_has_an_evidence_route() -> None:
    sprig_function_ids = {id(function) for function in generic_func_map().values()}
    sources = dict(_CASES)
    missing: dict[str, list[str]] = {}
    route_counts = {"sprig": 0, "direct": 0, "supplemental": 0}

    for registry_name, inventory in INVENTORY.registries.items():
        implementation = registry(registry_name)
        evidenced_originals: set[str] = set()
        source = sources.get(registry_name, "")
        supplemental = _SUPPLEMENTAL_EVIDENCE.get(registry_name, frozenset())
        for name, function in implementation.functions.items():
            if id(function) in sprig_function_ids:
                route_counts["sprig"] += 1
            elif re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                source,
            ):
                route_counts["direct"] += 1
            elif name in supplemental:
                route_counts["supplemental"] += 1
            else:
                missing.setdefault(registry_name, []).append(name)
                continue
            evidenced_originals.add(name)

        for original, aliases in inventory.aliases.items():
            if original not in evidenced_originals:
                missing.setdefault(registry_name, []).extend(aliases)

    assert missing == {}
    assert route_counts == {"sprig": 50, "direct": 159, "supplemental": 25}


@pytest.mark.parametrize("profile", ["all", "hermetic"])
def test_sprout_groups_match_the_pinned_oracle(profile: str) -> None:
    expected = run_go_oracle_many(
        [
            TemplateRequest(
                engine="text",
                name=f"sprout-{profile}",
                template=_GROUP_SOURCE,
                data=None,
                function_profile=f"sprout-{profile}",
            )
        ]
    )[0]
    registry_group = group(profile)
    functions = Handler(*registry_group.registries).build()

    assert expected == {
        "output": Template(_GROUP_SOURCE, functions=functions).render(),
        "error": None,
    }
