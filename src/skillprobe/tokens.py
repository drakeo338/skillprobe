"""Token estimation without a tokenizer dependency.

Every skill's description is loaded into the model's context on *every* turn,
so the interesting number is how much that costs. Getting it exactly right
would mean shipping a tokenizer (and, for tiktoken, downloading encoding files
on first use — a network call inside what should be an offline linter).

So this estimates. The estimate is deterministic, needs nothing installed, and
is calibrated to byte-pair encoding's actual behaviour: common short words are
one token, longer words split into roughly four-character subwords, and
punctuation is almost always its own token. Measured against tiktoken's
``cl100k_base`` on English prose it lands within about 10-15%, which is ample
for "this skill costs 800 tokens and that one costs 80".

``--tokenizer tiktoken`` switches to exact counts when the package is present.
"""

import math
import re

# Words (including underscores/digits) or a single non-space symbol. Symbols are
# separated because BPE almost always gives punctuation its own token.
_PIECE = re.compile(r"\w+|[^\w\s]")

# Average characters per sub-word token in BPE for English text.
_CHARS_PER_TOKEN = 4.0

# Words at or below this length are nearly always a single token.
_SHORT_WORD = 4


def estimate_tokens(text: str) -> int:
    """Approximate the token count of ``text``.

    Deterministic and offline. See the module docstring for accuracy.
    """
    if not text:
        return 0

    total = 0
    for piece in _PIECE.findall(text):
        is_symbol = not piece[0].isalnum() and piece[0] != "_"
        if is_symbol or len(piece) <= _SHORT_WORD:
            total += 1
        else:
            total += math.ceil(len(piece) / _CHARS_PER_TOKEN)
    return total


def count_tokens(text: str, tokenizer: str = "estimate") -> int:
    """Count tokens with the named tokenizer, falling back to the estimate.

    Args:
        text: The text to measure.
        tokenizer: ``"estimate"`` (default, offline) or ``"tiktoken"``.

    Raises:
        RuntimeError: if ``tiktoken`` is requested but not installed. Silently
            falling back would make the reported numbers a lie about their own
            precision.
    """
    if tokenizer == "estimate":
        return estimate_tokens(text)
    if tokenizer == "tiktoken":
        try:
            import tiktoken
        except ImportError as exc:
            raise RuntimeError(
                "--tokenizer tiktoken needs the tiktoken package: pip install tiktoken"
            ) from exc
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    raise ValueError(f"Unknown tokenizer {tokenizer!r}; expected 'estimate' or 'tiktoken'.")
