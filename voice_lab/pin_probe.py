"""Pin what a production Chatterbox engine needs: model revisions + file
hashes, and the time each step costs on a GitHub runner, using the call
shape the pipeline will use (snapshot at a revision, from_local, one
narration of five lines per process)."""
import hashlib, json, sys, time
from pathlib import Path
t0 = time.time()
import torch, torchaudio
from huggingface_hub import HfApi, snapshot_download
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
refs = Path(sys.argv[1]); rep = {"import_s": round(time.time() - t0, 1)}
api = HfApi(); torch.set_num_threads(4)
L = json.loads((Path(__file__).parent / "lines.json").read_text())["lines"][:5]
for name, repo, pats in [("full", "ResembleAI/chatterbox",
                          ["ve.safetensors", "t3_cfg.safetensors", "s3gen.safetensors", "tokenizer.json", "conds.pt"]),
                         ("turbo", "ResembleAI/chatterbox-turbo",
                          ["*.safetensors", "*.json", "*.txt", "*.pt", "*.model"])]:
    r = {}
    info = api.model_info(repo, files_metadata=True)
    r["repo"], r["revision"] = repo, info.sha
    t = time.time()
    d = Path(snapshot_download(repo_id=repo, revision=info.sha, allow_patterns=pats))
    r["download_s"] = round(time.time() - t, 1)
    files = {}
    for f in sorted(p for p in d.rglob("*") if p.is_file()):
        files[str(f.relative_to(d))] = {"bytes": f.stat().st_size,
                                        "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    r["files"] = files
    t = time.time()
    if name == "full":
        from chatterbox.tts import ChatterboxTTS as M
    else:
        from chatterbox.tts_turbo import ChatterboxTurboTTS as M
    m = M.from_local(d, "cpu"); r["load_s"] = round(time.time() - t, 1)
    for s in ["3000", "6319"]:
        ref = refs / f"libritts_r_{s}.ogg"
        t = time.time(); wavs = []
        for i, line in enumerate(L):
            kw = dict(exaggeration=0.6, cfg_weight=0.4) if name == "full" else {}
            w = m.generate(line, audio_prompt_path=str(ref), **kw)
            p = out / f"{name}_{s}_{i}.wav"; torchaudio.save(str(p), w.cpu(), m.sr); wavs.append(p)
        r[f"five_lines_{s}_s"] = round(time.time() - t, 1)
        import subprocess
        lst = out / "l.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in wavs))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-af", "atempo=1.12,loudnorm=I=-16:LRA=11:TP=-1.5", "-b:a", "160k",
                        str(out / f"prod_{name}_{s}.mp3")], check=True)
        for p in wavs: p.unlink()
    rep[name] = r; del m
(out / "pin.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1)[:4000])
