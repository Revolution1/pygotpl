# Sprig Security and Reproducibility

## Trust Boundary

Sprig function maps add operating-system access, DNS, randomness,
computationally expensive cryptography, parsing, and mutation to the template
runtime. Registering a Sprig map is therefore a capability decision. A caller
must not treat an arbitrary template as passive text merely because the data
passed to it is read-only.

The default compatibility target follows Sprig v3.3.0 even where a newer API
would make different security choices. Applications that render untrusted
templates should construct an explicit allowlist instead of registering the
complete map.

## Registry Profiles

`generic_func_map`, `text_func_map`, and `html_func_map` expose all 211 Sprig
names. The generic, text, and HTML maps currently have identical membership;
the template engine determines escaping behavior.

The hermetic maps remove Sprig's exact 17-name upstream exclusion list:

- current-time functions and date functions with current-time fallbacks;
- cryptographic random strings, random bytes, and UUID v4;
- environment reads and expansion;
- DNS lookup.

The upstream name `Hermetic*FuncMap` does not mean deterministic, side-effect
free, bounded, or safe for untrusted templates. For compatibility it retains:

- `randInt` and `shuffle`, which use process-global pseudo-random state unless
  a selection source is injected;
- bcrypt and htpasswd, which intentionally consume significant CPU;
- AES encryption, private-key generation, and certificate generation, which
  use operating-system randomness;
- collection mutation functions such as `set`, `unset`, and merge operations;
- `fail`, which deliberately terminates template execution.

Strictly reproducible applications must additionally remove or replace these
functions. Injectable clocks, entropy sources, random selectors, environment
mappings, and DNS resolvers exist for tests and controlled embedding, but
injection does not change public map membership.

## Environment and Network Access

`env` and `expandenv` can expose any variable visible to the Python process.
Do not register them for templates supplied by tenants, users, repositories,
or packages outside the process trust boundary. Passing an explicit mapping
constrains reads to that mapping.

`getHostByName` performs a blocking system DNS lookup by default. It can leak
queried names, block a rendering worker, observe changing network state, and
return addresses influenced by local resolver configuration. Use an explicit
resolver or remove the function in network-restricted applications. Async
rendering does not make this synchronous helper non-blocking.

## Randomness and Cryptography

Secure random string, byte, UUID, AES-IV, private-key, and certificate helpers
use operating-system randomness by default. Injected entropy is intended for
deterministic tests, not production cryptography.

Sprig AES compatibility uses a zero-padded or truncated 32-byte password as an
AES-CBC key and does not authenticate ciphertext. It must not be used as a new
general-purpose encryption design. Prefer a modern AEAD construction in
application code when Sprig compatibility is not required.

`bcrypt` and `htpasswd` use Sprig's cost 10. `derivePassword` uses scrypt with
N=32768, r=8, p=2, and a 64-byte derived key. Repeated calls can exhaust CPU or
memory when template invocation counts are not bounded. RSA and DSA key
generation and certificate functions are also intentionally expensive.

The bcrypt, AES, key, and certificate backends are provided by the optional
`crypto` extra and imported only on first use. Missing backends produce an
actionable `gotpl[crypto]` installation error. Installing the extra does not
make untrusted cryptographic template calls safe.

## Regular Expressions

Go Sprig uses RE2, whose matching time is linear in the input size. pygotpl
executes accepted patterns with a pure Python ordered Thompson NFA. Ambiguous
alternation and nested repetition do not use Python's backtracking matcher. A
bounded 256-entry compilation cache avoids repeated parsing without allowing
template-controlled patterns to grow process memory without limit.

An audited fast path uses the standard-library matcher only when the complete
pattern is one non-capturing consuming atom or a greedy repetition of that one
atom, with no case-folding scope. Those shapes have no alternative path on
which to backtrack and remain linear in the input. Every other accepted shape
uses the ordered NFA. A 4,096-character adversarial ambiguous-repetition test,
structured and seeded Go differential matrices, and repeated-capture cases
exercise the safety boundary and RE2 leftmost-first priority.

The syntax layer rejects lookaround, backreferences, conditionals, and atomic
groups and normalizes ASCII Perl classes, POSIX classes, anchors, replacement
expansion, and empty-match progression. Unicode category, script, alias,
complement, and assigned-rune classes use generated Go 1.27.0 Unicode 17.0.0
tables rather than interpreter-dependent Python tables. Go's `i`, `m`, `s`,
and `U` flags, including scoped, removed, and mid-expression forms, are
translated explicitly. The extracted `goregexp.go` surface uses a
project-owned parser and does not import CPython's private parser or constants.
Explicit source-length, repeat-count, instruction-count, and capture-count
limits bound compilation work independently of the template registry.

## Serialization and Mutable Data

JSON helpers reject unsupported values, non-finite floats, unsupported map
keys, and cycles. `fromJson` follows Go's untyped float64 number semantics,
including precision loss beyond 53 integer bits. Callers that require exact
decimal or large-integer preservation should parse outside the Sprig profile.

`set`, `unset`, `merge`, `mergeOverwrite`, and their aliases mutate the
destination dictionary. Deep-copy helpers prevent ordinary nested collection
aliasing, but they do not turn arbitrary Python objects into immutable values.
Do not share mutable render data across concurrent renders without application
level synchronization.

## Operational Controls

For untrusted or multi-tenant workloads:

1. Start from an empty function map and allowlist required names.
2. Exclude environment, DNS, randomness, cryptography, and mutation by default;
   allowlist regex only when its input and pattern work are appropriate for the
   application.
3. Bound template size, input size, output size, loop work, and render time at
   the application boundary.
4. Keep secrets out of the process environment visible to rendering workers.
5. Run expensive or blocking helpers in isolated workers when compatibility
   requires them.
6. Treat `html/template` contextual escaping as a separate M5 security gate;
   text templates and Sprig do not sanitize HTML.

`SandboxPolicy.strict()` enforces the function allowlist and VM-visible source,
output, iteration, call, and associated-template-depth limits described in
`docs/sandbox.md`. It denies complete ecosystem maps by default. It does not
preempt work inside one admitted helper, so cryptography, Python `re`, eager
CIDR expansion, blocking DNS, and serializer internals still require denial or
an operating-system-limited worker.

## Sprout and Helm Ecosystem Profiles

Sprout's `all` group includes its environment, random, and network registries.
Its `hermetic` group excludes those three registries exactly, but retains
lexical filesystem path helpers; those helpers normalize strings and do not
read the filesystem. The expensive cryptographic registry is not part of
either group and must be selected separately.

`gotpl.funcs.helm` removes `env` and `expandenv`, disables DNS by default, and uses
an empty lookup result until the embedding application injects a cluster
adapter. The miniature Helm example owns chart-directory reads and dynamic
`tpl` compilation. The complete M8-to-M9 policy handoff is recorded in
`docs/reports/m8-capability-matrix.md`.
