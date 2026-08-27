"""Construction of isolated Sprig-compatible function registries."""

from collections.abc import Callable, Mapping
from functools import partial
from types import MappingProxyType

from . import (
    crypto,
    dates,
    defaults,
    dicts,
    environment,
    flow,
    lists,
    network,
    numeric,
    randoms,
    reflect,
    regex,
    semver,
    strings,
    url,
)

_NONHERMETIC_NAMES = frozenset(
    {
        "date",
        "dateInZone",
        "dateModify",
        "date_in_zone",
        "date_modify",
        "env",
        "expandenv",
        "getHostByName",
        "htmlDate",
        "htmlDateInZone",
        "now",
        "randAlpha",
        "randAlphaNum",
        "randAscii",
        "randBytes",
        "randNumeric",
        "uuidv4",
    }
)

_IMPLEMENTED_FUNCTIONS: Mapping[str, Callable[..., object]] = MappingProxyType(
    {
        "adler32sum": strings.adler32sum,
        "add": numeric.add,
        "add1": numeric.add1,
        "add1f": numeric.add1f,
        "addf": numeric.addf,
        "append": lists.append,
        "bcrypt": crypto.bcrypt_hash,
        "b32dec": strings.b32dec,
        "b32enc": strings.b32enc,
        "b64dec": strings.b64dec,
        "b64enc": strings.b64enc,
        "base": strings.path_base,
        "biggest": numeric.maximum,
        "atoi": numeric.atoi,
        "ceil": numeric.ceil,
        "clean": strings.path_clean,
        "coalesce": defaults.coalesce,
        "chunk": lists.chunk,
        "buildCustomCert": crypto.build_custom_certificate_result,
        "compact": lists.compact,
        "concat": lists.concat,
        "contains": strings.contains,
        "date": dates.date,
        "dateInZone": dates.date_in_zone,
        "dateModify": dates.date_modify,
        "date_in_zone": dates.date_in_zone,
        "date_modify": dates.date_modify,
        "default": defaults.default,
        "deepCopy": dicts.deep_copy,
        "deepEqual": reflect.deep_equal,
        "dict": dicts.make_dict,
        "dig": dicts.dig,
        "div": numeric.div,
        "divf": numeric.divf,
        "decryptAES": crypto.decrypt_aes_result,
        "derivePassword": crypto.derive_password_go,
        "duration": dates.duration,
        "durationRound": dates.duration_round,
        "dir": strings.path_dir,
        "ext": strings.path_ext,
        "float64": numeric.to_float64,
        "floor": numeric.floor,
        "first": lists.first,
        "fail": flow.fail,
        "fromJson": defaults.from_json,
        "get": dicts.get,
        "getHostByName": network.get_host_by_name,
        "genCA": crypto.generate_ca_result,
        "genCAWithKey": crypto.generate_ca_with_key_result,
        "genPrivateKey": crypto.generate_private_key,
        "genSelfSignedCert": crypto.generate_self_signed_certificate_result,
        "genSelfSignedCertWithKey": (
            crypto.generate_self_signed_certificate_with_key_result
        ),
        "genSignedCert": crypto.generate_signed_certificate_result,
        "genSignedCertWithKey": crypto.generate_signed_certificate_with_key_result,
        "all": defaults.all_values,
        "any": defaults.any_value,
        "empty": defaults.empty,
        "encryptAES": crypto.encrypt_aes_result,
        "env": environment.env,
        "expandenv": environment.expand_env,
        "hasPrefix": strings.has_prefix,
        "hasSuffix": strings.has_suffix,
        "hasKey": dicts.has_key,
        "hello": strings.hello,
        "htmlDate": dates.html_date,
        "htmlDateInZone": dates.html_date_in_zone,
        "htpasswd": crypto.htpasswd,
        "indent": strings.indent,
        "initial": lists.initial,
        "int": numeric.to_int,
        "int64": numeric.to_int,
        "isAbs": strings.path_is_abs,
        "join": strings.join,
        "last": lists.last,
        "list": lists.make_list,
        "lower": strings.lower,
        "max": numeric.maximum,
        "maxf": numeric.maxf,
        "min": numeric.minimum,
        "minf": numeric.minf,
        "mod": numeric.mod,
        "merge": dicts.merge,
        "mergeOverwrite": dicts.merge_overwrite,
        "mul": numeric.mul,
        "mulf": numeric.mulf,
        "mustAppend": lists.must_append,
        "mustChunk": lists.must_chunk,
        "mustCompact": lists.must_compact,
        "mustDateModify": dates.must_date_modify,
        "mustFirst": lists.must_first,
        "mustFromJson": defaults.must_from_json,
        "mustMerge": dicts.must_merge,
        "mustMergeOverwrite": dicts.must_merge_overwrite,
        "mustHas": lists.must_has,
        "mustInitial": lists.must_initial,
        "mustLast": lists.must_last,
        "mustPrepend": lists.must_prepend,
        "mustPush": lists.must_append,
        "mustRest": lists.must_rest,
        "mustRegexFind": regex.must_regex_find,
        "mustRegexFindAll": regex.must_regex_find_all,
        "mustRegexMatch": regex.must_regex_match,
        "mustRegexReplaceAll": regex.must_regex_replace_all,
        "mustRegexReplaceAllLiteral": regex.must_regex_replace_all_literal,
        "mustRegexSplit": regex.must_regex_split,
        "mustReverse": lists.must_reverse,
        "mustSlice": lists.must_slice,
        "mustUniq": lists.must_uniq,
        "mustWithout": lists.must_without,
        "mustToJson": defaults.must_to_json,
        "mustToDate": dates.must_to_date,
        "mustToPrettyJson": defaults.must_to_pretty_json,
        "mustToRawJson": defaults.must_to_raw_json,
        "must_date_modify": dates.must_date_modify,
        "nindent": strings.nindent,
        "now": dates.now,
        "omit": dicts.omit,
        "pick": dicts.pick,
        "pluck": dicts.pluck,
        "plural": strings.plural,
        "prepend": lists.prepend,
        "push": lists.append,
        "repeat": strings.repeat,
        "replace": strings.replace,
        "regexFind": regex.regex_find,
        "regexFindAll": regex.regex_find_all,
        "regexMatch": regex.regex_match,
        "regexQuoteMeta": regex.regex_quote_meta,
        "regexReplaceAll": regex.regex_replace_all,
        "regexReplaceAllLiteral": regex.regex_replace_all_literal,
        "regexSplit": regex.regex_split,
        "round": numeric.round_number,
        "sha1sum": strings.sha1sum,
        "sha256sum": strings.sha256sum,
        "sha512sum": strings.sha512sum,
        "seq": numeric.seq,
        "semver": semver.semver_result,
        "semverCompare": semver.semver_compare_result,
        "set": dicts.set_value,
        "slice": lists.slice_list,
        "sortAlpha": strings.sort_alpha,
        "sub": numeric.sub,
        "subf": numeric.subf,
        "trim": strings.trim,
        "trimAll": strings.trim_all,
        "trimPrefix": strings.trim_prefix,
        "trimSuffix": strings.trim_suffix,
        "trimall": strings.trim_all,
        "ternary": defaults.ternary,
        "toJson": defaults.to_json,
        "toPrettyJson": defaults.to_pretty_json,
        "toRawJson": defaults.to_raw_json,
        "toString": strings.to_string,
        "toStrings": strings.to_strings,
        "toDecimal": numeric.to_decimal,
        "toDate": dates.to_date,
        "until": numeric.until,
        "untilStep": numeric.until_step,
        "unixEpoch": dates.unix_epoch,
        "unset": dicts.unset,
        "upper": strings.upper,
        "uniq": lists.uniq,
        "values": dicts.values,
        "without": lists.without,
        "has": lists.has,
        "rest": lists.rest,
        "reverse": lists.reverse,
        "tuple": lists.make_list,
        "keys": dicts.keys,
        "kindIs": reflect.kind_is,
        "kindOf": reflect.kind_of,
        "mustDeepCopy": dicts.must_deep_copy,
        "typeIs": reflect.type_is,
        "typeIsLike": reflect.type_is_like,
        "typeOf": reflect.type_of,
        "urlJoin": url.url_join,
        "urlParse": url.url_parse,
        "osBase": strings.os_path_base,
        "osClean": strings.os_path_clean,
        "osDir": strings.os_path_dir,
        "osExt": strings.os_path_ext,
        "osIsAbs": strings.os_path_is_abs,
        "abbrev": strings.abbrev,
        "abbrevboth": strings.abbrevboth,
        "camelcase": strings.camelcase,
        "cat": strings.cat,
        "initials": strings.initials,
        "kebabcase": strings.kebabcase,
        "nospace": strings.nospace,
        "quote": strings.quote,
        "randAlpha": randoms.rand_alpha,
        "randAlphaNum": randoms.rand_alpha_numeric,
        "randAscii": randoms.rand_ascii,
        "randBytes": randoms.rand_bytes_result,
        "randInt": randoms.rand_int,
        "randNumeric": randoms.rand_numeric,
        "snakecase": strings.snakecase,
        "split": strings.split,
        "splitList": strings.split_list,
        "splitn": strings.splitn,
        "squote": strings.squote,
        "substr": strings.substring,
        "swapcase": strings.swapcase,
        "title": strings.title,
        "trunc": strings.trunc,
        "untitle": strings.untitle,
        "wrap": strings.wrap,
        "wrapWith": strings.wrap_with,
        "ago": dates.ago,
        "shuffle": randoms.shuffle,
        "uuidv4": randoms.uuid_v4,
    }
)


def generic_func_map(
    *,
    clock: dates.Clock | None = None,
    entropy: randoms.Entropy | None = None,
    randbelow: randoms.RandBelow | None = None,
    environ: Mapping[str, str] | None = None,
    resolver: network.Resolver | None = None,
) -> dict[str, Callable[..., object]]:
    """Return a mutable copy of the implemented Sprig generic function map."""

    functions = dict(_IMPLEMENTED_FUNCTIONS)
    if clock is not None:
        for name in {
            "ago",
            "date",
            "dateInZone",
            "date_in_zone",
            "durationRound",
            "htmlDate",
            "htmlDateInZone",
            "now",
            "genCA",
            "genCAWithKey",
            "genSelfSignedCert",
            "genSelfSignedCertWithKey",
            "genSignedCert",
            "genSignedCertWithKey",
        }:
            functions[name] = partial(functions[name], clock=clock)
    if entropy is not None:
        for name in {
            "randAlpha",
            "randAlphaNum",
            "randAscii",
            "randBytes",
            "randNumeric",
            "uuidv4",
            "encryptAES",
        }:
            functions[name] = partial(functions[name], entropy=entropy)
    if randbelow is not None:
        for name in {"randInt", "shuffle"}:
            functions[name] = partial(functions[name], randbelow=randbelow)
    if environ is not None:
        functions["env"] = partial(functions["env"], environ=environ)
        functions["expandenv"] = partial(functions["expandenv"], environ=environ)
    if resolver is not None or randbelow is not None:
        functions["getHostByName"] = partial(
            functions["getHostByName"], resolver=resolver, randbelow=randbelow
        )
    return functions


def text_func_map(
    *,
    clock: dates.Clock | None = None,
    entropy: randoms.Entropy | None = None,
    randbelow: randoms.RandBelow | None = None,
    environ: Mapping[str, str] | None = None,
    resolver: network.Resolver | None = None,
) -> dict[str, Callable[..., object]]:
    """Return the Sprig function map for text templates."""

    return generic_func_map(
        clock=clock,
        entropy=entropy,
        randbelow=randbelow,
        environ=environ,
        resolver=resolver,
    )


def html_func_map(
    *,
    clock: dates.Clock | None = None,
    entropy: randoms.Entropy | None = None,
    randbelow: randoms.RandBelow | None = None,
    environ: Mapping[str, str] | None = None,
    resolver: network.Resolver | None = None,
) -> dict[str, Callable[..., object]]:
    """Return the Sprig function map for HTML templates."""

    return generic_func_map(
        clock=clock,
        entropy=entropy,
        randbelow=randbelow,
        environ=environ,
        resolver=resolver,
    )


def hermetic_text_func_map(
    *,
    clock: dates.Clock | None = None,
    entropy: randoms.Entropy | None = None,
    randbelow: randoms.RandBelow | None = None,
) -> dict[str, Callable[..., object]]:
    """Return deterministic Sprig functions for text templates."""

    return {
        name: function
        for name, function in generic_func_map(
            clock=clock, entropy=entropy, randbelow=randbelow
        ).items()
        if name not in _NONHERMETIC_NAMES
    }


def hermetic_html_func_map(
    *,
    clock: dates.Clock | None = None,
    entropy: randoms.Entropy | None = None,
    randbelow: randoms.RandBelow | None = None,
) -> dict[str, Callable[..., object]]:
    """Return deterministic Sprig functions for HTML templates."""

    return hermetic_text_func_map(clock=clock, entropy=entropy, randbelow=randbelow)
