from examples.helm_runtime import HelmFiles


def test_helm_files_match_get_glob_config_secret_and_lines_contracts() -> None:
    files = HelmFiles(
        {
            "ship/captain.txt": b"The Captain",
            "ship/stowaway.txt": "Legatt",
            "story/author.txt": "Joseph Conrad",
            "multiline/test.txt": "bar\nfoo\n",
        }
    )

    assert files.GetBytes("ship/captain.txt") == b"The Captain"
    assert files.Get("missing") == ""
    assert files.Glob("story/**").Get("story/author.txt") == "Joseph Conrad"
    assert files.Glob("ship/**").AsConfig() == (
        "captain.txt: The Captain\nstowaway.txt: Legatt"
    )
    assert files.Glob("ship/**").AsSecrets() == (
        "captain.txt: VGhlIENhcHRhaW4=\nstowaway.txt: TGVnYXR0"
    )
    assert files.Lines("multiline/test.txt") == ("bar", "foo")
    assert files.Lines("missing") == ()


def test_helm_files_are_immutable_and_expose_python_aliases() -> None:
    files = HelmFiles({"a.txt": "a"})

    assert files.get_text("a.txt") == "a"
    assert files.glob("*.txt").as_config() == "a.txt: a"
    assert dict(files) == {"a.txt": b"a"}
