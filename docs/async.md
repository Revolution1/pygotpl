# Async Rendering

Async rendering is a Python extension to Go templates. The template language is
unchanged: gotpl awaits results at callable boundaries before continuing a
pipeline.

| Task | Entry point |
| --- | --- |
| Render one text source | `await gotpl.render_async(...)` |
| Reuse a compiled root | `await template.render_async(...)` |
| Render an associated name | `await template.render_template_async(...)` |
| Stream with backpressure | `await template.render_async_to(...)` |
| Render dynamic associated source | `await template.render_source_async(...)` |

`HTMLTemplate` and the `render_html_async*` helpers provide the same choices
with contextual HTML escaping.

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

```python
import asyncio

from gotpl import AsyncRequiredError, Template


def decorate(value: str) -> str:
    return f"[{value}]"


async def load(value: str) -> str:
    await asyncio.sleep(0)
    return value.upper()


template = Template(
    "{{load . | decorate}}",
    functions={"decorate": decorate, "load": load},
)

assert asyncio.run(template.render_async("mixed")) == "[MIXED]"

try:
    template.render("mixed")
except AsyncRequiredError as error:
    assert "render_async" in str(error)
else:
    raise AssertionError("sync rendering unexpectedly accepted an awaitable")
```

## Writers

`render_async_to()` accepts a writer whose `write(str)` method returns an
integer either immediately or awaitably. Each write completes before template
execution continues, so ordering is deterministic and backpressure is
preserved.

```python
import asyncio

from gotpl import Template


class AsyncWriter:
    def __init__(self) -> None:
        self.parts: list[str] = []

    async def write(self, value: str) -> int:
        await asyncio.sleep(0)
        self.parts.append(value)
        return len(value)


async def main() -> None:
    writer = AsyncWriter()
    template = Template("{{.Greeting}}, {{.Name}}!")

    await template.render_async_to(
        writer,
        {"Greeting": "Hello", "Name": "Ada"},
    )

    assert "".join(writer.parts) == "Hello, Ada!"


asyncio.run(main())
```

A writer must report the full number of characters accepted. A short count or
writer exception stops rendering instead of silently dropping output.

## Cancellation and concurrency

Cancellation propagates unchanged; gotpl does not convert it into a template
execution error. A compiled template stores no per-render mutable state, so one
instance can serve concurrent tasks. Application callbacks and data objects
must still be safe for the concurrency pattern in which they are used.

```python
import asyncio

from gotpl import Template


async def identify(value: int) -> str:
    await asyncio.sleep(0)
    return f"item-{value}"


async def main() -> None:
    template = Template("{{identify .}}", functions={"identify": identify})
    output = await asyncio.gather(*(template.render_async(value) for value in range(3)))
    assert output == ["item-0", "item-1", "item-2"]


asyncio.run(main())
```

Cancelling a render raises `asyncio.CancelledError` to the caller. gotpl does
not wrap cancellation in `TemplateExecutionError` or continue rendering after
the cancelled awaitable.

Async iterables are not currently consumed by `range`. Async support applies to
registered functions, called methods, `call` targets, and writers.
