# skillprobe

Lint your agent skills before they quietly cost you something: will they
trigger, what do they charge you on every turn, and do they collide with each
other?

Installing a skill is currently an act of faith. You drop a markdown file into
a directory and hope. Three things go wrong, all of them silently.

```
$ skillprobe ~/.claude/skills

   skill                per turn  on demand  issues
B  cognee-docker              67      1,144  1 warn
B  cognee-install             53      1,328  1 warn
B  cognee-server              62        855  1 warn
A  cognee-cli                 52      2,118  clean
A  cognee-community          134      1,406  clean
A  cognee-integrations        87      1,335  clean
A  cognee-permissions         84      2,819  clean

cognee-docker
  ! no concrete anchors (file types, commands, identifiers, quoted phrases)
cognee-install
  ! no concrete anchors (file types, commands, identifiers, quoted phrases)
cognee-server
  ! no concrete anchors (file types, commands, identifiers, quoted phrases)

7 skills  539 tokens on every turn, 11,005 more when they fire
```

That run is reproducible — it is [cognee](https://github.com/topoteretes/cognee)'s
own shipped skills:

```bash
git clone --depth 1 https://github.com/topoteretes/cognee
skillprobe cognee/.claude/skills
```

## The three silent failures

**It never triggers.** The description is abstract — "helps with data tasks" —
so the model never selects it. The skill does nothing and you conclude it
wasn't useful. skillprobe flags descriptions with no concrete anchors, no
"use when" clause, or too little text to match against.

**It charges you rent.** Every skill's description sits in context on *every
turn of every session*, used or not. The summary line is the number nobody
measures. A directory of nine skills costing 1,600 tokens a turn is a real
bill you're paying before you type anything.

**It collides.** Two skills with overlapping descriptions make selection a coin
flip, and the winner isn't the one you meant. skillprobe scores every pair and
flags the ambiguous ones.

## Install

```bash
uv tool install skillprobe     # or: pipx install skillprobe
```

No API key, no config file, no network. It reads files and prints a table.

## Usage

```bash
skillprobe                       # defaults to ~/.claude/skills
skillprobe path/to/skills        # any directory, or a single SKILL.md
skillprobe --json                # machine-readable, for scripts
skillprobe --fail-on warn        # stricter gate
skillprobe --tokenizer tiktoken  # exact counts instead of the estimate
```

Exit codes make it usable as a CI gate: `0` clean, `1` findings at or above
`--fail-on` (default `error`), `2` for a bad invocation.

```yaml
- run: pipx install skillprobe && skillprobe .claude/skills --fail-on warn
```

## What it checks

| Code | Severity | Meaning |
|---|---|---|
| `broken` | error | Frontmatter won't parse |
| `no-name` / `no-description` | error | Required field missing |
| `missing-file` | error | A markdown link points at a file that isn't there |
| `thin-description` | warn | Too short to match against reliably |
| `bloated-description` | warn | Past the length where the tail stops mattering |
| `no-trigger` | warn | Says what it is, never says *when* to use it |
| `abstract` | warn | No file types, commands, identifiers or quoted phrases |
| `expensive` | warn | Description costs more than 200 tokens, every turn |
| `collision` | warn | Description overlaps another skill's past 45% |
| `vague` | info | Filler phrasing — "and more", "various", "etc." |
| `name-mismatch` | info | Declared name differs from its directory |

## On the token numbers

Counting exactly would mean shipping a tokenizer, and tiktoken downloads
encoding files on first use — a network call inside what should be an offline
linter. So the default is an estimate: deterministic, offline, calibrated to
how byte-pair encoding actually behaves (short words are one token, longer ones
split into ~4-character pieces, punctuation stands alone). It lands within
about 10-15% of `cl100k_base` on English prose, which is plenty for comparing
one skill against another.

If you want exact numbers, `pip install skillprobe[exact]` and pass
`--tokenizer tiktoken`. Asking for tiktoken without it installed is an error
rather than a silent fallback — a number that lies about its own precision is
worse than no number.

## What it deliberately doesn't do

**Security.** [SkillSpector](https://github.com/NVIDIA/SkillSpector) scans
skills for prompt injection, exfiltration and supply-chain risk. That's a
different question and it owns it. skillprobe asks whether a skill *works* and
what it *costs*; run both.

**Live trigger testing.** Telling you whether a model really selects a skill
means calling one. That needs a key and makes results nondeterministic. The
heuristics here catch the common failures offline.

**Fixing your prose.** It reports. Rewriting someone's description for them is
presumptuous, and the judgement about what a skill is *for* is yours.

## Development

```bash
uv sync
pytest
ruff check . && ruff format --check .
```

## License

MIT
