# M3: Async Runtime

## Outcome

Allow template pipelines to call asynchronous Python functions while preserving
the behavior and speed of the synchronous path.

## Deliverables

- [x] Async VM consuming the shared instruction stream.
- [x] Public `render_async` API.
- [x] Async string and writer rendering.
- [x] Mixed synchronous and asynchronous pipelines.
- [x] `AsyncRequiredError` in the sync VM.
- [x] Cancellation, exception, partial-output, and backpressure semantics.
- [x] Task-sharing and concurrency tests.
- [x] Async latency and throughput benchmarks.

## Acceptance Gates

- [x] Sync and async VMs have full parity when no awaitable is produced.
- [x] Awaitables work in action, condition, `with`, and `range` pipelines.
- [x] Cancellation propagates without conversion or leakage.
- [x] The sync benchmark baseline shows no material async-related regression.
- [x] Both VMs reach 100% statement coverage.

## Non-Goals

- Async iterable support unless separately approved.
- Parallel evaluation of pipeline stages.
- Implicit event-loop management in synchronous APIs.

The [M3 async-runtime report](../reports/m3-async-runtime.md) owns parity,
cancellation, writer, concurrency, and benchmark evidence.
