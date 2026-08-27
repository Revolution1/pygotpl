# M3 Async Runtime Completion Report

## Status

M3 is complete. Async iterables remain outside the approved milestone scope.

## Correctness Evidence

- The async VM consumes the same immutable programs and semantic helpers as
  the sync VM.
- All 68 M2 text conformance fixtures pass through both VMs with matching
  output, partial-output, and execution-error behavior.
- Coroutine functions, custom awaitables, bound methods, method chains,
  `call`, logical short-circuiting, `FunctionResult`, actions, conditions,
  `with`, and `range` have direct async tests.
- Cancellation propagates as `CancelledError`; coroutine cleanup and context
  variables are preserved.
- Sync and async writers cover backpressure, short writes, exceptions, and
  partial output. Named-template async APIs preserve source locations.
- One compiled template is exercised concurrently across 20 tasks without
  shared execution state.
- The full suite passes 532 tests. All 2,694 source statements are covered;
  both VMs have 100% statement coverage.

## Performance Evidence

Run:

```console
python -m benchmarks.async_runtime --iterations 10000 --warmup 500
python -m benchmarks.sync_guard --samples 7 --iterations 10000
```

On CPython 3.13.7, the async VM rendered a synchronous callback in 3,924 ns,
an immediately completing coroutine in 4,103 ns, and a coroutine containing
one scheduler yield in 17,908 ns. The synchronous equivalent took 3,262 ns.

The first sync-guard measurement showed an 8.2% diagnostic overhead. A common
built-in result-type fast path reduced the repeated seven-sample median to
1.0% (3,073 ns checked versus 3,042 ns with the guard diagnostically bypassed).
Custom objects still use the complete awaitable protocol check.

These local measurements establish an M3 baseline, not a release performance
claim. M6 owns statistical benchmarking and broader optimization.
