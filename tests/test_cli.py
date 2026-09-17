import json

from skillprobe.cli import main

GOOD = "Use when the user asks to convert a `.csv` file into a chart or summary table."


def test_clean_skills_exit_zero(make_skill, root, capsys):
    make_skill("clean", description=GOOD)
    assert main([str(root)]) == 0


def test_errors_exit_one_by_default(make_skill, root, capsys):
    make_skill("broken", frontmatter="name: broken")
    assert main([str(root)]) == 1


def test_warnings_alone_do_not_fail_by_default(make_skill, root, capsys):
    make_skill("warny", description="Does stuff")
    assert main([str(root)]) == 0


def test_fail_on_warn_catches_warnings(make_skill, root, capsys):
    make_skill("warny", description="Does stuff")
    assert main([str(root), "--fail-on", "warn"]) == 1


def test_fail_on_never_always_exits_zero(make_skill, root, capsys):
    make_skill("broken", frontmatter="name: broken")
    assert main([str(root), "--fail-on", "never"]) == 0


def test_missing_path_exits_two(tmp_path, capsys):
    assert main([str(tmp_path / "nope")]) == 2
    assert "no such path" in capsys.readouterr().out


def test_empty_directory_is_not_an_error(root, capsys):
    assert main([str(root)]) == 0
    assert "no skills found" in capsys.readouterr().out


def test_json_output_is_valid_and_complete(make_skill, root, capsys):
    make_skill("alpha", description=GOOD, body="Body.")
    main([str(root), "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["always_on_tokens"] > 0
    assert payload["on_demand_tokens"] > 0
    entry = payload["skills"][0]
    assert entry["name"] == "alpha"
    assert entry["grade"] == "A"
    assert entry["findings"] == []


def test_json_reports_findings_with_codes(make_skill, root, capsys):
    make_skill("thin", description="Does stuff")
    main([str(root), "--json"])

    payload = json.loads(capsys.readouterr().out)
    codes = {f["code"] for f in payload["skills"][0]["findings"]}
    assert "thin-description" in codes


def test_table_output_shows_the_always_on_total(make_skill, root, capsys):
    make_skill("alpha", description=GOOD)
    main([str(root)])
    assert "on every turn" in capsys.readouterr().out


def test_unavailable_tokenizer_exits_two_rather_than_lying(make_skill, root, capsys):
    make_skill("alpha", description=GOOD)
    try:
        import tiktoken  # noqa: F401
    except ImportError:
        assert main([str(root), "--tokenizer", "tiktoken"]) == 2
    else:
        assert main([str(root), "--tokenizer", "tiktoken"]) == 0
