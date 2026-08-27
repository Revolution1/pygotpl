# Async Rendering

Async rendering is a Python extension to Go templates. The template language is
unchanged: gotpl awaits results at callable boundaries before continuing a
pipeline.

```python
import asyncio

from gotpl import Template


async def load_name(user_id: int) -> str:
    await asyncio.sleep(0)
    return f"user-{user_id}"


async def main() -> None:
    template = Template(
        "Hello {{load_name .UserID}}",
        functions={"load_name": load_name},
    )
    assert await template.render_async({"UserID": 42}) == "Hello user-42"


asyncio.run(main())
```

## Sync and async functions may be mixed

`render_async()` calls ordinary functions directly and awaits only awaitable
results. `render()` never starts an event loop. If a sync render encounters an
awaitable result, it raises `AsyncRequiredError` with the relevant template
location.

## Writers

`render_async_to()` accepts a writer whose `write(str)` method returns an
integer either immediately or awaitably. Each write completes before template
execution continues, so ordering is deterministic and backpressure is
preserved.

```python
class AsyncWriter:
    def __init__(self) -> None:
        self.parts: list[str] = []

    async def write(self, value: str) -> int:
        self.parts.append(value)
        return len(value)
```

## Cancellation and concurrency

Cancellation propagates unchanged; gotpl does not convert it into a template
execution error. A compiled template stores no per-render mutable state, so one
instance can serve concurrent tasks. Application callbacks and data objects
must still be safe for the concurrency pattern in which they are used.

Async iterables are not currently consumed by `range`. Async support applies to
registered functions, called methods, `call` targets, and writers.
