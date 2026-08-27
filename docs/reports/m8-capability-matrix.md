# M8 Ecosystem Capability Matrix

## Purpose

This matrix identified the capabilities consumed by the completed M9 strict
policy and remains its ecosystem audit input. Registry membership alone is not
a safety claim.

| Layer | Capability | Default state | Strict-policy requirement |
| --- | --- | --- | --- |
| Core `Template` / `TemplateEngine` | Parser, execution, caller data | enabled | size, work, output, and recursion budgets |
| Sprout `all` | Process environment | enabled through `env` and `expandEnv` | deny by default or inject a mapping |
| Sprout `all` | Randomness | enabled | deny or inject a bounded deterministic source |
| Sprout `all` | IP/CIDR computation | enabled | budget eager `cidrRangeList` by address count |
| Sprout `hermetic` | Environment, random, network registries | absent | preserve exact exclusion set |
| Sprout filesystem registry | Lexical path manipulation | enabled | no filesystem grant required |
| Sprout crypto registry | CPU, memory, and OS entropy | separately opt-in | deny by default; bound calls and isolate expensive work |
| Helm function map | Environment | absent | must not be reintroduced implicitly |
| Helm function map | DNS | disabled by default | explicit `enable_dns` grant |
| Helm function map | Cluster lookup | empty by default | explicit application adapter and authorization |
| Helm serializers | YAML/TOML parsing and allocation | optional | input and object-size budgets |
| Helm example | Chart-directory reads | application-owned | filesystem roots and file-size limits |
| Helm `tpl` example | Dynamic parsing and compilation | enabled for compatibility | compilation count and source-size budgets |

## Executable Evidence

`tests/security/test_ecosystem_capabilities.py` proves registry separation,
path-only filesystem helpers, disabled Helm DNS, empty default lookup, explicit
lookup injection, and the capability-free core engine. Crypto, environment,
network, and optional dependency behavior also retain their direct unit and
oracle-backed suites.
