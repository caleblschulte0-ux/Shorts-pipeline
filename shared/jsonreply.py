"""The ONE way a model's reply is read as JSON.

Sixteen call sites read a reply with `re.search(r"\\{.*\\}")` and
`json.loads` of the match. That greedy match spans from the first brace to
the last, so a reply carrying two objects (an answer and then a corrected
one, or a fenced example plus the answer) raised "Extra data" — and on
Baller Bro that killed one to three posts every run for days
(2026-11-11..13) as "render failed: JSONDecodeError". Every caller now
goes through `one_object`, held by tests/test_model_replies_parse.py.
"""
from __future__ import annotations

import json


def one_object(text: str) -> dict:
    """The JSON object a model's reply carries: every top-level object is
    decoded on its own and the LAST is the answer (a model that writes two
    writes its correction second). Raises ValueError when none decodes."""
    dec = json.JSONDecoder()
    text = str(text or "")
    found, i = [], text.find("{")
    while i != -1:
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            found.append(obj)
        i = text.find("{", end)
    if not found:
        raise ValueError("no JSON object in the reply")
    return found[-1]
