"""The checks themselves.

Three questions, in the order they cost you:

1. Is it broken? Malformed frontmatter or a missing referenced file means the
   skill does nothing, loudly or quietly.
2. Will it trigger? A description the model cannot match against is the most
   common failure and the most invisible one — the skill simply never fires
   and you conclude it did not help.
3. What does it cost? Descriptions are in context on every turn, for the whole
   session, whether or not the skill is ever used.
"""

import re
from pathlib import Path

from skillprobe.model import Finding, Severity, Skill
from skillprobe.tokens import count_tokens

# Descriptions much shorter than this rarely carry enough signal to match on.
MIN_DESCRIPTION_CHARS = 40
# Past this, the tail of a description stops reliably influencing selection.
MAX_DESCRIPTION_CHARS = 1024
# A description costing more than this is worth a second look on its own.
DESCRIPTION_TOKEN_BUDGET = 200
# Jaccard overlap above which two descriptions are ambiguous to select between.
COLLISION_THRESHOLD = 0.45

# Phrases that fill space without telling the model when to fire.
_VAGUE = (
    "helps with",
    "various",
    "and more",
    "etc.",
    "as needed",
    "if necessary",
    "general purpose",
    "all kinds of",
    "anything related",
)

# A description should say *when* to use the skill, not only what it is.
_TRIGGER_CUES = ("use when", "use this", "when the user", "triggers on", "for when", "invoke")

# Concrete things a model can match against: extensions, paths, CamelCase or
# snake_case identifiers, quoted literals, commands.
_CONCRETE = re.compile(
    r"\.\w{1,5}\b|/\w+|`[^`]+`|\"[^\"]+\"|'[^']+'|\b[a-z]+_[a-z]+\b|\b[A-Z][a-z]+[A-Z]\w+\b"
)

# Only a markdown link claims that a file exists next to the skill. Everything
# looser was tried first and was wrong in practice: a bare filename is usually
# prose about another package ("every package has `examples/example.py`"), a
# leading slash is an HTTP route ("GET /openapi.json"), and even an explicit
# ./path is normally the *user's* working directory, not the skill's — the two
# real skills that tripped this were `cognee-cli remember ./docs` and a config
# written to "./.env in the cwd". Fixture tests never surface that; running it
# against a real repository did.
_REFERENCE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Fenced code blocks are examples, not references — a shell snippet naming a
# file is not a claim that the file ships with the skill.
_CODE_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "use",
        "used",
        "user",
        "using",
        "when",
        "with",
        "your",
        "you",
    ]
)


def check_skill(skill: Skill, tokenizer: str = "estimate") -> None:
    """Run every single-skill check, appending findings in place."""
    if skill.parse_error:
        skill.findings.append(
            Finding("broken", Severity.ERROR, f"cannot be loaded: {skill.parse_error}")
        )
        return

    _check_identity(skill)
    _check_description(skill, tokenizer)
    _check_references(skill)


def _check_identity(skill: Skill) -> None:
    if not skill.name:
        skill.findings.append(Finding("no-name", Severity.ERROR, "frontmatter has no `name`"))
    elif skill.path.name.lower() in ("skill.md",) and skill.name != skill.path.parent.name:
        skill.findings.append(
            Finding(
                "name-mismatch",
                Severity.INFO,
                f"name `{skill.name}` differs from its directory `{skill.path.parent.name}`",
            )
        )


def _check_description(skill: Skill, tokenizer: str) -> None:
    description = skill.description.strip()

    if not description:
        skill.findings.append(
            Finding("no-description", Severity.ERROR, "frontmatter has no `description`")
        )
        return

    if len(description) < MIN_DESCRIPTION_CHARS:
        skill.findings.append(
            Finding(
                "thin-description",
                Severity.WARN,
                f"description is {len(description)} chars; too thin to match against reliably",
            )
        )

    if len(description) > MAX_DESCRIPTION_CHARS:
        skill.findings.append(
            Finding(
                "bloated-description",
                Severity.WARN,
                f"description is {len(description)} chars; the tail stops influencing selection",
            )
        )

    lowered = description.lower()

    if not any(cue in lowered for cue in _TRIGGER_CUES):
        skill.findings.append(
            Finding(
                "no-trigger",
                Severity.WARN,
                "says what it is but never says when to use it — add a 'use when ...' clause",
            )
        )

    if not _CONCRETE.search(description):
        skill.findings.append(
            Finding(
                "abstract",
                Severity.WARN,
                "no concrete anchors (file types, commands, identifiers, quoted phrases)",
            )
        )

    vague = [phrase for phrase in _VAGUE if phrase in lowered]
    if vague:
        skill.findings.append(
            Finding("vague", Severity.INFO, "filler phrasing: " + ", ".join(repr(v) for v in vague))
        )

    cost = count_tokens(description, tokenizer)
    if cost > DESCRIPTION_TOKEN_BUDGET:
        skill.findings.append(
            Finding(
                "expensive",
                Severity.WARN,
                f"description costs ~{cost} tokens on every turn of every session",
            )
        )


def _check_references(skill: Skill) -> None:
    """Flag referenced sibling files that are not there."""
    base = skill.path.parent
    prose = _CODE_FENCE.sub("", skill.body)
    missing: list[str] = []
    for match in _REFERENCE.finditer(prose):
        target = match.group(1) or ""
        target = target.strip()
        if not target or target.startswith(("http://", "https://", "#", "mailto:", "/")):
            continue
        # Strip a markdown link's title and any anchor: `file.md#section "Title"`.
        target = target.split("#", 1)[0].split(" ", 1)[0].strip()
        if not target:
            continue
        if not (base / target).exists():
            missing.append(target)

    for target in sorted(set(missing))[:5]:
        skill.findings.append(
            Finding("missing-file", Severity.ERROR, f"references `{target}`, which does not exist")
        )


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2}


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of the meaningful words in two descriptions."""
    a, b = _keywords(left), _keywords(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_collisions(skills: list[Skill]) -> list[tuple[Skill, Skill, float]]:
    """Find description pairs so similar that selection between them is a coin flip."""
    collisions = []
    usable = [s for s in skills if not s.parse_error and s.description.strip()]
    for i, left in enumerate(usable):
        for right in usable[i + 1 :]:
            score = similarity(left.description, right.description)
            if score >= COLLISION_THRESHOLD:
                collisions.append((left, right, score))
                note = f"{int(score * 100)}% description overlap with `{right.slug}`"
                left.findings.append(Finding("collision", Severity.WARN, note, other=right.slug))
                note = f"{int(score * 100)}% description overlap with `{left.slug}`"
                right.findings.append(Finding("collision", Severity.WARN, note, other=left.slug))
    return sorted(collisions, key=lambda c: c[2], reverse=True)


def always_on_cost(skills: list[Skill], tokenizer: str = "estimate") -> int:
    """Total tokens these skills spend on every single turn."""
    return sum(count_tokens(s.description, tokenizer) for s in skills if not s.parse_error)


def on_demand_cost(skills: list[Skill], tokenizer: str = "estimate") -> int:
    """Total tokens the bodies cost, but only when a skill actually fires."""
    return sum(count_tokens(s.body, tokenizer) for s in skills if not s.parse_error)


def analyze(root: Path, tokenizer: str = "estimate") -> list[Skill]:
    """Parse and check everything under ``root``."""
    from skillprobe.parser import discover, parse

    skills = [parse(path) for path in discover(root)]
    for skill in skills:
        check_skill(skill, tokenizer)
    check_collisions(skills)
    return skills
