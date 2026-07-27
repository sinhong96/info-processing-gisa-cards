#!/usr/bin/env python3
"""Validate that a subject's cards are fully and correctly classified.

kind and hook are authored by hand in cards.json. This module does not
author them; it only reports what is missing or malformed.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
VALID_KINDS = {"diagram", "mnemonic"}
MAX_HOOK = 30


def validate(cards, subject):
    problems = []
    for c in cards:
        if c.get("subject") != subject:
            continue
        cid = c.get("id", "???")
        kind = c.get("kind")
        if kind is None:
            problems.append(f"{cid}: kind is not set")
        elif kind not in VALID_KINDS:
            problems.append(f"{cid}: kind {kind!r} is not one of {sorted(VALID_KINDS)}")
        hook = (c.get("hook") or "").strip()
        if not hook:
            problems.append(f"{cid}: hook is empty")
        elif len(hook) > MAX_HOOK:
            problems.append(f"{cid}: hook is {len(hook)} chars, max is {MAX_HOOK}")
    return problems


def main():
    subject = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cards = json.load(open(os.path.join(HERE, "cards.json"), encoding="utf-8"))
    problems = validate(cards, subject)
    if problems:
        print(f"{len(problems)} problem(s) in {subject}과목:")
        for p in problems:
            print("  -", p)
        return 1
    n = len([c for c in cards if c["subject"] == subject])
    kinds = {}
    for c in cards:
        if c["subject"] == subject:
            kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(f"{subject}과목: all {n} cards classified — {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
