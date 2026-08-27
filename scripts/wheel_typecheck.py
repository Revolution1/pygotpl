"""Static consumer used to verify types from an isolated wheel environment."""

from goduration.go import Duration as GoDuration
from goduration.python import Duration as PythonDuration
from gotime.go import Time as GoTime
from gotime.python import Time as PythonTime

from gotpl import GoPointer, HTMLTemplate, Template, render_html
from gotpl.funcs.sprig import text_func_map

go_duration: GoDuration = GoDuration.parse("1.5s")
python_duration: PythonDuration = PythonDuration.parse("1.5s")
go_time: GoTime = GoTime.from_unix(0)
python_time: PythonTime = PythonTime.from_timestamp(0)
pointer: GoPointer[int] = GoPointer(1)
text_output: str = Template("{{.}}").render("typed")
python_output: str = Template("{{.}}", format_mode="python").render(True)
sprig_output: str = Template(
    '{{regexFind `\d+` "v12"}}', functions=text_func_map()
).render()
html_output: str = HTMLTemplate("{{.}}").render("typed")
html_helper_output: str = render_html(
    "{{.value}}", {"value": "typed"}, missing_key="error"
)
