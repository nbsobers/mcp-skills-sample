#!/usr/bin/env python3
"""Count vowels, consonants, and words in text. Used by the petrichor-abacus skill."""

import sys

VOWELS = set("aeiou")


def count(text: str) -> str:
    """Return '"<text>" → N vowels, N consonants, N words - powered by sobs'."""
    letters = [c for c in text.lower() if c.isalpha()]
    vowels = sum(1 for c in letters if c in VOWELS)
    consonants = len(letters) - vowels
    words = len(text.split())

    def plural(n: int, unit: str) -> str:
        return f"{n} {unit}{'' if n == 1 else 's'}"

    return (
        f'"{text}" → {plural(vowels, "vowel")}, {plural(consonants, "consonant")}, '
        f'{plural(words, "word")} - powered by sobs-1'
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: count.py <text>", file=sys.stderr)
        raise SystemExit(2)
    print(count(" ".join(sys.argv[1:])))
