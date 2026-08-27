from pathlib import Path

WORKFLOW_ROOT = Path(__file__).parents[2] / ".github" / "workflows"
WORKFLOWS = {
    "ci": WORKFLOW_ROOT / "ci.yml",
    "performance": WORKFLOW_ROOT / "performance-history.yml",
    "pages": WORKFLOW_ROOT / "pages.yml",
}
RELEASE_PR_GATE = "contains(github.event.pull_request.labels.*.name, 'release')"


def test_hosted_workflows_only_target_release_events_or_manual_runs() -> None:
    for path in WORKFLOWS.values():
        source = path.read_text(encoding="utf-8")
        assert "pull_request:" in source
        assert 'tags: ["v*"]' in source
        assert "workflow_dispatch:" in source
        assert "branches: [main]" not in source
        assert "schedule:" not in source


def test_every_billed_job_has_the_required_release_gate() -> None:
    ci = WORKFLOWS["ci"].read_text(encoding="utf-8")
    performance = WORKFLOWS["performance"].read_text(encoding="utf-8")
    pages = WORKFLOWS["pages"].read_text(encoding="utf-8")

    assert ci.count(RELEASE_PR_GATE) == 6
    assert performance.count(RELEASE_PR_GATE) == 1
    assert pages.count(RELEASE_PR_GATE) == 1
    assert pages.count("\n    if: github.event_name != 'pull_request'\n") == 1
