"""Checks, and the false positives that shaped them.

The reference check in particular was wrong twice before it was right. Running
the first version against a real repository produced four confident errors,
every one of them bogus. Those cases are pinned below as regressions, because
fixture tests written from my own assumptions are exactly what failed to catch
them.
"""

from skillprobe.checks import (
    COLLISION_THRESHOLD,
    analyze,
    check_collisions,
    check_skill,
    similarity,
)
from skillprobe.model import Severity
from skillprobe.parser import parse

GOOD = "Use when the user asks to convert a `.csv` file into a chart or summary table."


def codes(skill) -> set[str]:
    return {f.code for f in skill.findings}


# ---------------------------------------------------------------------------
# Identity and structure
# ---------------------------------------------------------------------------


def test_a_well_formed_skill_is_clean(make_skill):
    skill = parse(make_skill("charter", description=GOOD, body="Steps here."))
    check_skill(skill)
    assert skill.findings == []
    assert skill.grade == "A"


def test_missing_description_is_an_error(make_skill):
    skill = parse(make_skill("nodesc", frontmatter="name: nodesc"))
    check_skill(skill)
    assert "no-description" in codes(skill)
    assert skill.grade == "F"


def test_missing_name_is_an_error(make_skill):
    skill = parse(make_skill("noname", frontmatter=f"description: {GOOD}"))
    check_skill(skill)
    assert "no-name" in codes(skill)


def test_unparseable_skill_reports_once_and_stops(make_skill):
    skill = parse(make_skill("bad", frontmatter="name: [unclosed"))
    check_skill(skill)
    assert codes(skill) == {"broken"}


def test_name_differing_from_directory_is_only_informational(make_skill):
    skill = parse(make_skill("dirname", frontmatter=f"name: other\ndescription: {GOOD}"))
    check_skill(skill)
    assert "name-mismatch" in codes(skill)
    assert skill.worst is Severity.INFO


# ---------------------------------------------------------------------------
# Trigger quality
# ---------------------------------------------------------------------------


def test_thin_description_is_flagged(make_skill):
    skill = parse(make_skill("thin", description="Does stuff"))
    check_skill(skill)
    assert "thin-description" in codes(skill)


def test_bloated_description_is_flagged(make_skill):
    skill = parse(make_skill("fat", description="Use when " + "word " * 400))
    check_skill(skill)
    assert "bloated-description" in codes(skill)


def test_description_without_a_trigger_clause_is_flagged(make_skill):
    skill = parse(make_skill("what", description="A helper for `.pdf` document conversion tasks."))
    check_skill(skill)
    assert "no-trigger" in codes(skill)


def test_abstract_description_without_anchors_is_flagged(make_skill):
    skill = parse(
        make_skill("vapor", description="Use when the user needs help with their work somehow.")
    )
    check_skill(skill)
    assert "abstract" in codes(skill)


def test_filler_phrasing_is_noted(make_skill):
    skill = parse(
        make_skill("filler", description="Use when the user wants `.csv` handling and more, etc.")
    )
    check_skill(skill)
    assert "vague" in codes(skill)


def test_expensive_description_is_flagged(make_skill):
    long_but_concrete = "Use when the user edits a `.xlsx` file. " * 30
    skill = parse(make_skill("costly", description=long_but_concrete))
    check_skill(skill)
    assert "expensive" in codes(skill)


# ---------------------------------------------------------------------------
# References — the regressions
# ---------------------------------------------------------------------------


def test_markdown_link_to_a_missing_file_is_an_error(make_skill):
    skill = parse(make_skill("linky", description=GOOD, body="See [the guide](guide.md)."))
    check_skill(skill)
    assert "missing-file" in codes(skill)


def test_markdown_link_to_a_present_file_is_fine(make_skill):
    path = make_skill("linky", description=GOOD, body="See [the guide](guide.md).")
    (path.parent / "guide.md").write_text("hi", encoding="utf-8")
    skill = parse(path)
    check_skill(skill)
    assert "missing-file" not in codes(skill)


def test_bare_filename_in_prose_is_not_a_reference(make_skill):
    # Regression: "Every package has `examples/example.py`" is prose about other
    # packages, not a claim that the file sits beside this skill.
    skill = parse(
        make_skill("prose", description=GOOD, body="Every package has `examples/example.py` too.")
    )
    check_skill(skill)
    assert "missing-file" not in codes(skill)


def test_http_route_is_not_a_reference(make_skill):
    # Regression: "GET /openapi.json" is an endpoint, not a file.
    skill = parse(make_skill("route", description=GOOD, body="Check `GET /openapi.json` on it."))
    check_skill(skill)
    assert "missing-file" not in codes(skill)


def test_relative_path_in_a_shell_example_is_not_a_reference(make_skill):
    # Regression: `cognee-cli remember ./docs` is the user's cwd, not ours.
    body = "Run it:\n\n```bash\ncognee-cli remember ./docs\ncat ./.env\n```\n"
    skill = parse(make_skill("shell", description=GOOD, body=body))
    check_skill(skill)
    assert "missing-file" not in codes(skill)


def test_external_link_is_not_checked(make_skill):
    skill = parse(make_skill("ext", description=GOOD, body="See [docs](https://example.com/a.md)."))
    check_skill(skill)
    assert "missing-file" not in codes(skill)


def test_anchor_is_stripped_before_resolving(make_skill):
    path = make_skill("anchored", description=GOOD, body="See [part](guide.md#section).")
    (path.parent / "guide.md").write_text("hi", encoding="utf-8")
    skill = parse(path)
    check_skill(skill)
    assert "missing-file" not in codes(skill)


# ---------------------------------------------------------------------------
# Collisions
# ---------------------------------------------------------------------------


def test_identical_descriptions_collide():
    assert similarity(GOOD, GOOD) == 1.0


def test_unrelated_descriptions_do_not_collide():
    assert similarity("convert csv files to charts", "deploy the server to production") < 0.2


def test_stopwords_do_not_manufacture_overlap():
    # Two descriptions sharing only filler must not read as a collision.
    left = "Use this when the user is working with a database"
    right = "Use this when the user is working with a keyboard"
    assert similarity(left, right) < COLLISION_THRESHOLD


def test_colliding_skills_are_flagged_on_both_sides(make_skill, root):
    make_skill("csv1", description="Use when the user converts a `.csv` file into a chart.")
    make_skill("csv2", description="Use when the user converts a `.csv` file into a chart now.")
    skills = analyze(root)
    assert all("collision" in codes(s) for s in skills)


def test_collision_report_is_ordered_by_strength(make_skill, root):
    make_skill("a", description="Use when the user converts a `.csv` file into a chart.")
    make_skill("b", description="Use when the user converts a `.csv` file into a chart.")
    skills = [parse(p) for p in sorted(root.glob("*/SKILL.md"))]
    collisions = check_collisions(skills)
    assert collisions and collisions[0][2] == 1.0


def test_skills_without_descriptions_are_excluded_from_collisions(make_skill, root):
    make_skill("empty1", frontmatter="name: empty1")
    make_skill("empty2", frontmatter="name: empty2")
    skills = analyze(root)
    assert all("collision" not in codes(s) for s in skills)


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def test_grade_degrades_with_warning_count(make_skill):
    clean = parse(make_skill("clean", description=GOOD))
    check_skill(clean)
    assert clean.grade == "A"

    worse = parse(make_skill("worse", description="Does stuff"))
    check_skill(worse)
    assert worse.grade in ("C", "D")


def test_any_error_grades_f(make_skill):
    skill = parse(make_skill("err", frontmatter="name: err"))
    check_skill(skill)
    assert skill.grade == "F"
