"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from skillprobe.checks import always_on_cost, analyze, on_demand_cost
from skillprobe.model import Severity, Skill
from skillprobe.tokens import count_tokens

DEFAULT_ROOT = Path.home() / ".claude" / "skills"

_GRADE_STYLE = {"A": "bold green", "B": "green", "C": "yellow", "D": "dark_orange", "F": "bold red"}
_SEVERITY_STYLE = {Severity.ERROR: "bold red", Severity.WARN: "yellow", Severity.INFO: "dim"}
_SEVERITY_MARK = {Severity.ERROR: "x", Severity.WARN: "!", Severity.INFO: "-"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillprobe",
        description="Lint agent skills: will they trigger, what do they cost, do they collide?",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"skills directory or a single skill file (default: {DEFAULT_ROOT})",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--tokenizer",
        choices=("estimate", "tiktoken"),
        default="estimate",
        help="estimate (default, offline) or exact counts via tiktoken",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warn", "never"),
        default="error",
        help="exit non-zero at this severity or worse (default: error)",
    )
    return parser


def _as_dict(skill: Skill, tokenizer: str) -> dict:
    return {
        "name": skill.slug,
        "path": str(skill.path),
        "grade": skill.grade,
        "always_on_tokens": count_tokens(skill.description, tokenizer),
        "on_demand_tokens": count_tokens(skill.body, tokenizer),
        "findings": [
            {"code": f.code, "severity": f.severity.value, "message": f.message}
            for f in skill.findings
        ],
    }


def render(console: Console, skills: list[Skill], tokenizer: str) -> None:
    table = Table(box=None, pad_edge=False, header_style="bold")
    table.add_column("", width=1)
    table.add_column("skill", style="bold", no_wrap=True)
    table.add_column("per turn", justify="right")
    table.add_column("on demand", justify="right")
    table.add_column("issues")

    for skill in sorted(skills, key=lambda s: (-s.worst.rank, s.grade, s.slug)):
        grade = skill.grade
        issues = Text()
        if not skill.findings:
            issues.append("clean", style="dim green")
        else:
            counts: dict[Severity, int] = {}
            for finding in skill.findings:
                counts[finding.severity] = counts.get(finding.severity, 0) + 1
            parts = [
                f"{count} {severity.value}"
                for severity, count in sorted(counts.items(), key=lambda kv: -kv[0].rank)
            ]
            issues.append(", ".join(parts), style=_SEVERITY_STYLE[skill.worst])

        table.add_row(
            Text(grade, style=_GRADE_STYLE[grade]),
            skill.slug,
            f"{count_tokens(skill.description, tokenizer):,}",
            f"{count_tokens(skill.body, tokenizer):,}",
            issues,
        )

    console.print(table)

    flagged = [s for s in skills if s.findings]
    if flagged:
        console.print()
        for skill in sorted(flagged, key=lambda s: -s.worst.rank):
            console.print(Text(skill.slug, style="bold"))
            for finding in sorted(skill.findings, key=lambda f: -f.severity.rank):
                mark = _SEVERITY_MARK[finding.severity]
                console.print(
                    Text(f"  {mark} ", style=_SEVERITY_STYLE[finding.severity])
                    + Text(finding.message, style="default")
                )

    always = always_on_cost(skills, tokenizer)
    demand = on_demand_cost(skills, tokenizer)
    console.print()
    summary = Text()
    summary.append(f"{len(skills)} skills  ", style="bold")
    summary.append(f"{always:,} tokens", style="bold yellow" if always > 2000 else "bold")
    summary.append(" on every turn, ", style="dim")
    summary.append(f"{demand:,}", style="bold")
    summary.append(" more when they fire", style="dim")
    console.print(summary)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console()

    if not args.path.exists():
        console.print(f"[bold red]no such path:[/] {args.path}", highlight=False)
        return 2

    try:
        skills = analyze(args.path, args.tokenizer)
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/]", highlight=False)
        return 2

    if not skills:
        console.print(f"[yellow]no skills found under[/] {args.path}", highlight=False)
        return 0

    if args.json:
        payload = {
            "skills": [_as_dict(s, args.tokenizer) for s in skills],
            "always_on_tokens": always_on_cost(skills, args.tokenizer),
            "on_demand_tokens": on_demand_cost(skills, args.tokenizer),
        }
        print(json.dumps(payload, indent=2))
    else:
        render(console, skills, args.tokenizer)

    if args.fail_on == "never":
        return 0
    threshold = Severity.ERROR if args.fail_on == "error" else Severity.WARN
    hit = any(f.severity.rank >= threshold.rank for s in skills for f in s.findings)
    return 1 if hit else 0


if __name__ == "__main__":
    sys.exit(main())
