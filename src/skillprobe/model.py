"""Data types shared across the checks."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Severity(StrEnum):
    """How much a finding matters.

    ``ERROR`` means the skill is broken — malformed, or pointing at files that
    do not exist. ``WARN`` means it works but will not behave as intended, and
    is where most of the value is: a skill that never triggers fails silently.
    ``INFO`` is worth knowing but costs nothing.
    """

    ERROR = "error"
    WARN = "warn"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 2, "warn": 1, "info": 0}[self.value]


@dataclass(frozen=True)
class Finding:
    """One problem with one skill."""

    code: str
    severity: Severity
    message: str
    # Populated for findings about a pair of skills (a collision).
    other: str | None = None


@dataclass
class Skill:
    """A parsed skill: its frontmatter, its body, and where it came from."""

    path: Path
    name: str
    description: str
    body: str
    # Set when the frontmatter could not be read at all.
    parse_error: str | None = None
    findings: list[Finding] = field(default_factory=list)

    @property
    def slug(self) -> str:
        """The name to show — the declared name, else the directory it lives in."""
        return self.name or self.path.parent.name

    @property
    def grade(self) -> str:
        """A letter grade, driven by the worst findings present."""
        if any(f.severity is Severity.ERROR for f in self.findings):
            return "F"
        warnings = sum(1 for f in self.findings if f.severity is Severity.WARN)
        if warnings >= 3:
            return "D"
        if warnings == 2:
            return "C"
        if warnings == 1:
            return "B"
        return "A"

    @property
    def worst(self) -> Severity:
        return max((f.severity for f in self.findings), key=lambda s: s.rank, default=Severity.INFO)
