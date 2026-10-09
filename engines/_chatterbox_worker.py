"""Runs INSIDE the Chatterbox venv (cache/venvs/chatterbox), never imported
by the pipeline. One process voices one narration: load the pinned model
once, read the reference voice once, then every line.

Job (JSON file, argv[1]):
    {"model": "full"|"turbo", "ckpt": "<dir>", "ref": "<audio>",
     "lines": [{"text": "...", "out": "<wav>", "seed": 123}, ...],
     "exaggeration": 0.6, "cfg_weight": 0.4}

Prints one JSON line per finished line ({"i": n, "ok": true}) so the caller
can see progress, then exits 0. Any failure exits non-zero; the caller
treats that as "this engine did not voice this video" and falls through.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text())
    import torch
    import torchaudio
    torch.set_num_threads(int(job.get("threads", 4)))
    ckpt = Path(job["ckpt"])
    if job["model"] == "turbo":
        from chatterbox.tts_turbo import ChatterboxTurboTTS as M
        kw = {}
    else:
        from chatterbox.tts import ChatterboxTTS as M
        kw = {"exaggeration": float(job.get("exaggeration", 0.6)),
              "cfg_weight": float(job.get("cfg_weight", 0.4))}
    m = M.from_local(ckpt, "cpu")
    if job["model"] == "turbo":
        m.prepare_conditionals(job["ref"])
    else:
        m.prepare_conditionals(job["ref"], exaggeration=kw["exaggeration"])
    for i, line in enumerate(job["lines"]):
        # A fixed seed per line: the same words in the same voice come out
        # the same, so a re-render sounds like the draft the judge passed.
        torch.manual_seed(int(line["seed"]))
        wav = m.generate(line["text"], **kw)
        torchaudio.save(line["out"], wav.cpu(), m.sr)
        print(json.dumps({"i": i, "ok": True}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
