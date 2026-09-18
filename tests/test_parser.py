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


def _write_skill(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: use when testing discovery\n---\nbody",
        encoding="utf-8",
    )


def test_discover_follows_symlinked_skills(make_skill, root, tmp_path_factory):
    """`npx skills add` keeps skills in a shared store and symlinks them in.

    Path.rglob does not descend into symlinked directories, so this layout
    reported one skill and called it clean. Found by running skillprobe on a
    real 21-skill directory and being told it held 1.

    The store must live OUTSIDE root: the `root` fixture is `tmp_path` itself,
    so a store under `tmp_path` is inside the scan and rglob finds it directly,
    which is how the first version of this test passed without the fix.
    """
    store = tmp_path_factory.mktemp("store")
    _write_skill(store / "linked", "linked")

    make_skill("direct")
    (root / "linked").symlink_to(store / "linked", target_is_directory=True)

    names = {p.parent.name for p in discover(root)}
    assert names == {"direct", "linked"}


def test_discover_reports_a_symlink_and_its_target_once(root: Path):
    """A scan covering both the store and the link to it counts one skill."""
    _write_skill(root / "store" / "shared", "shared")
    (root / "shared-link").symlink_to(root / "store" / "shared", target_is_directory=True)

    assert len(discover(root)) == 1
