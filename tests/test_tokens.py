import pytest

from skillprobe.tokens import count_tokens, estimate_tokens


def test_empty_text_costs_nothing():
    assert estimate_tokens("") == 0


def test_short_words_are_one_token_each():
    assert estimate_tokens("the cat sat") == 3


def test_long_words_split_into_subwords():
    # "extraordinary" is 13 chars: BPE gives it several tokens, not one.
    assert estimate_tokens("extraordinary") > 1


def test_punctuation_counts_separately():
    assert estimate_tokens("hi, there") > estimate_tokens("hi there")


def test_estimate_is_in_the_right_ballpark():
    # English prose runs roughly four characters per token; assert we are within
    # a sane band rather than pinning an exact number the heuristic may tune.
    text = "The quick brown fox jumps over the lazy dog near the river bank today."
    ratio = len(text) / estimate_tokens(text)
    assert 3.0 < ratio < 6.0


def test_estimate_is_deterministic():
    text = "some description of a skill"
    assert estimate_tokens(text) == estimate_tokens(text)


def test_count_tokens_defaults_to_the_estimator():
    assert count_tokens("hello world") == estimate_tokens("hello world")


def test_unknown_tokenizer_is_rejected():
    with pytest.raises(ValueError, match="Unknown tokenizer"):
        count_tokens("x", tokenizer="gpt9")


def test_missing_tiktoken_raises_rather_than_silently_estimating():
    try:
        import tiktoken  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="tiktoken"):
            count_tokens("x", tokenizer="tiktoken")
    else:
        assert count_tokens("hello world", tokenizer="tiktoken") > 0
