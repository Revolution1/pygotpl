from concurrent.futures import ThreadPoolExecutor

import gotpl


def test_compiled_template_supports_concurrent_warm_renders() -> None:
    template = gotpl.Template("{{.index}}={{.value}}")
    inputs = [{"index": index, "value": index * index} for index in range(100)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(template.render, inputs))

    assert outputs == [f"{item['index']}={item['value']}" for item in inputs]


def test_compiled_html_template_supports_concurrent_contextual_renders() -> None:
    template = gotpl.HTMLTemplate('<p title="{{.}}">{{.}}</p>')
    inputs = [f"<item-{index}&>" for index in range(100)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(template.render, inputs))

    assert outputs == [
        f'<p title="&lt;item-{index}&amp;&gt;">&lt;item-{index}&amp;&gt;</p>'
        for index in range(100)
    ]


def test_mapping_range_uses_numeric_order_for_homogeneous_integer_keys() -> None:
    template = gotpl.Template("{{range $key, $value := .}}{{$key}}={{$value}};{{end}}")
    assert template.render({10: "ten", 2: "two", 1: "one"}) == ("1=one;2=two;10=ten;")


def test_mapping_range_has_stable_fallback_order_for_mixed_python_keys() -> None:
    template = gotpl.Template("{{range $key, $value := .}}{{$value}};{{end}}")
    assert template.render({2: "integer", "1": "string"}) == "integer;string;"
