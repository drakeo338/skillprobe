"""Finding and parsing skill files."""

from pathlib import Path

import yaml

from skillprobe.model import Skill

# Agent skills are a directory containing SKILL.md, but people also keep loose
# markdown files in a skills folder, and those load the same way.
_SKILL_FILENAMES = ("SKILL.md", "skill.md")

_FRONTMATTER_FENCE = "---"


def discover(root: Path) -> list[Path]:
    """Find skill files under ``root``, sorted for deterministic output.

    A directory containing SKILL.md is a skill. A bare ``.md`` file directly
    inside the root is also treated as one, since that layout loads too.
    """
    if root.is_file():
        return [root]

    found: list[Path] = []
    for name in _SKILL_FILENAMES:
        found.extend(root.rglob(name))

    # `rglob` does not descend into symlinked directories, and the usual
    # installer (`npx skills add`) puts every skill in a shared store and
    # symlinks it into the agent's skills folder. Without this pass, pointing
    # skillprobe at a real skills directory reports one skill instead of
    # twenty-one and calls it clean — which is the exact silent failure this
    # tool exists to catch.
    for child in root.iterdir():
        if not child.is_dir():  # follows the symlink, unlike rglob
            continue
        for name in _SKILL_FILENAMES:
            candidate = child / name
            if candidate.is_file():
                found.append(candidate)

    # Loose top-level markdown, excluding anything already found and the
    # README that almost every skills folder has.
    claimed = {p.parent for p in found}
    for path in root.glob("*.md"):
        if path.parent not in claimed and path.name.lower() != "readme.md":
            found.append(path)

    # Dedupe by what each path actually points at, so a symlink and its target
    # are not both reported when the scan covers the store and the link farm.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in sorted(set(found)):
        try:
            key = path.resolve()
        except OSError:  # broken symlink, dangling mount
            key = path
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)

    return unique


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Split a document into its raw YAML frontmatter and its body.

    Returns ``(None, text)`` when there is no frontmatter block, which is
    itself a finding rather than an error here.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return None, text

    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])

    # An opening fence with no closing one: everything after it is frontmatter
    # as far as a loader is concerned, and the skill has no body at all.
    return "\n".join(lines[1:]), ""


def parse(path: Path) -> Skill:
    """Parse one skill file. Never raises — a broken skill is a finding."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return Skill(path=path, name="", description="", body="", parse_error=str(exc))

    raw, body = split_frontmatter(text)
    if raw is None:
        return Skill(path=path, name="", description="", body=body, parse_error="no frontmatter")

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        message = str(exc).split("\n")[0]
        return Skill(path=path, name="", description="", body=body, parse_error=message)

    if data is None:
        data = {}
    if not isinstance(data, dict):
        return Skill(
            path=path,
            name="",
            description="",
            body=body,
            parse_error="frontmatter is not a mapping",
        )

    return Skill(
        path=path,
        name=str(data.get("name") or ""),
        description=str(data.get("description") or ""),
        body=body,
    )
