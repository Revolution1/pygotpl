# Built-in Functions

Every text and HTML template starts with the following Go-compatible built-in
functions. They do not need a function registry and are not Python callables
exported from `gotpl`; use them inside template actions.

Pipeline values become the final argument of the next function. For example,
`{{.Items | len}}` is equivalent to `{{len .Items}}`.

## Logic

| Function | Result |
| --- | --- |
| `and arg0 arg1 ...` | Evaluate left to right and return the first empty argument, or the last argument. Evaluation stops as soon as the result is known. |
| `or arg0 arg1 ...` | Evaluate left to right and return the first non-empty argument, or the last argument. Evaluation stops as soon as the result is known. |
| `not arg` | Return the Boolean negation of Go template truth. |

`and` and `or` return an operand rather than coercing it to `bool`:

```python
from gotpl import render

assert render('{{or .Primary "fallback"}}', {"Primary": ""}) == "fallback"
assert render('{{and .Enabled "ready"}}', {"Enabled": True}) == "ready"
```

## Comparisons

| Function | Result |
| --- | --- |
| `eq arg1 arg2 [arg...]` | Whether `arg1` equals any following argument. Requires at least two arguments. |
| `ne arg1 arg2` | Whether the two arguments are not equal. |
| `lt arg1 arg2` | Whether `arg1` is less than `arg2`. |
| `le arg1 arg2` | Whether `arg1` is less than or equal to `arg2`. |
| `gt arg1 arg2` | Whether `arg1` is greater than `arg2`. |
| `ge arg1 arg2` | Whether `arg1` is greater than or equal to `arg2`. |

Ordered comparisons accept compatible integers, floats, or strings. Equality
follows Go comparability rules rather than arbitrary Python coercion; mappings,
sequences, sets, and byte containers are not directly comparable.

```python
from gotpl import render

assert render("{{eq . 1 2 3}}", 2) == "true"
assert render("{{lt .Left .Right}}", {"Left": "a", "Right": "b"}) == "true"
```

## Collections and Calls

| Function | Result |
| --- | --- |
| `len value` | Length of a supported value. String length is its UTF-8 byte length, matching Go. |
| `index value index [index...]` | Repeatedly index a mapping, list, tuple, string, or bytes value. |
| `slice value [low [high [max]]]` | Slice a list, tuple, string, or bytes value with Go bounds. Strings do not accept the three-index form. |
| `call function [arg...]` | Invoke a callable stored in template data. An opt-in sandbox removes this built-in. |

Missing mapping keys produce the template missing value. A `TypedMap` supplies
an explicit element zero. Sequence indexes and slice bounds are non-negative
Go-style indexes; Python negative indexing is deliberately not accepted.

```python
from gotpl import TypedMap, render

assert render("{{len .}}", "é") == "2"
assert render("{{index . 1}}", ["zero", "one"]) == "one"
assert render("{{slice . 1 3}}", [0, 1, 2, 3]) == "[1 2]"
assert render('{{index . "missing"}}', TypedMap({}, zero=0)) == "0"
```

For `call`, place the callable and its arguments in template data:

```python
from gotpl import render

data = {"Transform": str.upper, "Value": "gopher"}
assert render("{{call .Transform .Value}}", data) == "GOPHER"
```

## Formatting

| Function | Result |
| --- | --- |
| `print arg...` | Format arguments like Go `fmt.Sprint`; adjacent non-string operands receive a separating space. |
| `printf format arg...` | Apply Go `fmt`-compatible formatting. |
| `println arg...` | Format operands separated by spaces and append a newline. |

`format_mode="go"` is the default. Select `format_mode="python"` explicitly
when Python-native value formatting is desired; the format string still uses
the documented template formatting surface.

```python
from gotpl import render

assert render('{{printf "%04d" .}}', 7) == "0007"
assert render('{{println "left" 2}}') == "left 2\n"
```

## Escaping Helpers

| Function | Result |
| --- | --- |
| `html arg...` | Escape text for a basic HTML text context. |
| `js arg...` | Escape text using Go's legacy JavaScript string helper. |
| `urlquery arg...` | Percent-encode text for a URL query component, using `+` for spaces. |

These are Go `text/template` compatibility helpers. For complete HTML
documents, use `HTMLTemplate` or `render_html()` so escaping is selected from
the actual HTML, attribute, URL, CSS, and JavaScript context.

```python
from gotpl import render

assert render("{{html .}}", "<&") == "&lt;&amp;"
assert render("{{urlquery .}}", "a b&c") == "a+b%26c"
assert render("{{js .}}", "</script>") == r"\u003C/script\u003E"
```

## Implementation

- Semantic name validation is defined in
  `src/gotpl/parse/semantic.py` as `BUILTIN_FUNCTIONS`.
- Ordinary implementations and registration live in
  `src/gotpl/runtime/sync_vm.py`, beginning with `_builtin_functions()`.
- `and` and `or` use dedicated short-circuit execution in both
  `src/gotpl/runtime/sync_vm.py` and `src/gotpl/runtime/async_vm.py`.
- Contextual HTML rewriting and its private escapers live under
  `src/gotpl/html/`; they are separate from the three legacy helpers above.

The underscored implementation functions are internal and are not supported as
Python imports. The stable interface is the template-language behavior recorded
on this page and in the compatibility fixtures.
