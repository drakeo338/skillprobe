from pathlib import Path

from skillprobe.parser import discover, parse, split_frontmatter


def test_split_frontmatter_extracts_block_and_body():
    raw, body = split_frontmatter("---\nname: a\n---\nbody text")
    assert raw == "name: a"
    assert body == "body text"


def test_split_frontmatter_without_a_block_returns_all_body():
    raw, body = split_frontmatter("just a document")
    assert raw is None
    assert body == "just a document"


def test_unterminated_frontmatter_leaves_no_body():
    raw, body = split_frontmatter("---\nname: a\nstill going")
    assert "still going" in raw
    assert body == ""


def test_parse_reads_name_and_description(make_skill):
    path = make_skill("alpha", description="Does a thing", body="Body here.")
    skill = parse(path)
    assert skill.name == "alpha"
    assert skill.description == "Does a thing"
    assert "Body here." in skill.body
    assert skill.parse_error is None


def test_parse_reports_malformed_yaml_instead_of_raising(make_skill):
    path = make_skill("broken", frontmatter="name: [unclosed")
    skill = parse(path)
    assert skill.parse_error is not None


def test_parse_reports_missing_frontmatter(tmp_path):
    path = tmp_path / "loose.md"
    path.write_text("no frontmatter at all", encoding="utf-8")
    assert parse(path).parse_error == "no frontmatter"


def test_parse_reports_non_mapping_frontmatter(make_skill):
    path = make_skill("listy", frontmatter="- one\n- two")
    assert parse(path).parse_error == "frontmatter is not a mapping"


def test_parse_handles_an_unreadable_file(tmp_path):
    missing = tmp_path / "gone.md"
    assert parse(missing).parse_error is not None


def test_discover_finds_skill_directories(make_skill, root):
    make_skill("one")
    make_skill("two")
    assert len(discover(root)) == 2


def test_discover_accepts_a_single_file(make_skill):
    path = make_skill("solo")
    assert discover(path) == [path]


def test_discover_skips_readme_but_keeps_loose_markdown(root: Path):
    (root / "README.md").write_text("docs", encoding="utf-8")
    (root / "loose.md").write_text("---\nname: loose\n---\n", encoding="utf-8")
    names = {p.name for p in discover(root)}
    assert names == {"loose.md"}


def test_discover_is_sorted_for_stable_output(make_skill, root):
    make_skill("zeta")
    make_skill("alpha")
    found = discover(root)
    assert found == sorted(found)
