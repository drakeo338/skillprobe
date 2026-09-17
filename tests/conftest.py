import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def make_skill(tmp_path):
    """Write a skill directory and return its root, so checks see a real tree."""

    def _make(name: str, description: str = "", body: str = "", frontmatter: str | None = None):
        directory = tmp_path / name
        directory.mkdir(parents=True, exist_ok=True)
        if frontmatter is None:
            frontmatter = f"name: {name}\ndescription: {description}"
        (directory / "SKILL.md").write_text(
            f"---\n{frontmatter}\n---\n{textwrap.dedent(body)}", encoding="utf-8"
        )
        return directory / "SKILL.md"

    return _make


@pytest.fixture
def root(tmp_path) -> Path:
    return tmp_path
