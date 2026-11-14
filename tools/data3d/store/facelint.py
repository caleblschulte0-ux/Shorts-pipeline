"""THE FACE LINT: a face that is not a smile never turns into one (2026-11-14, saffron shot 4: a worried face's release
keyed his RESTING face 0.15 s after 'alarmed' began, so the alarm was overwritten and he ended the shot on a contented
smile; the judge called it "the opposite emotion"). character.expression() now clears an older face's keys out of a
new face's window (_clear_face); this check catches the whole class, whatever keyed the smile back in.

shots.py runs check() on every shot beside twitch, after data.finish(), on what renders. For every expression in
Data.NOT_SMILING (worried, alarmed, surprised, sad, wry, determined) it takes the frames that face OWNS and HOLDS (from
SETTLE_F frames after it arrives to its t1, or the end of the shot; frames a later expression() took over are that
one's) and fails the shot when, on any of them:
  - the 'smile' or 'grin' shape key is above SMILE_MAX, or
  - the mouth's SMILE READ is above READ_MAX. Data's resting mouth is itself a small closed smile (the corners turned
    up), so a face keyed back to rest smiles with every smile key at 0; that is exactly tonight's defect. The smile
    read is how far the mouth corners turn up over the middle of the lip, in units of the resting smile (rest = 1.0),
    measured from the lip shapes themselves (character._mouth_paths): shape keys blend linearly, so it is exact.
Under STAGING=strict a failed lint fails the shot. Lines start with FACE so proof_loop picks them up."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from clock import FPS, F   # the one clock

SMILE_MAX = 0.25     # the 'smile' / 'grin' key itself
READ_MAX = 0.5       # the corners may turn up at most half as much as his resting smile does
SETTLE_F = 4         # frames a new face takes to arrive (its blend, then the twitch filter's tail)


def upturn(path):
    """how far a lip outline's corners sit above the middle of its top edge (the first half of the path is the top lip,
    left to right, for every shape _mouth_paths builds)"""
    n = len(path) // 2
    return (path[0][2] + path[n - 1][2]) / 2 - path[n // 2][2]


def coeffs(paths, keys):
    """(rest upturn, {key: change in upturn at value 1}) from the lip shapes"""
    r = upturn(paths['rest'])
    return r, {k: upturn(paths[k]) - r for k in keys}


def smile_read(state, co):
    """the mouth's upturn for a face state ({key: value}), in units of the resting smile"""
    r, c = co
    side = state.get('side', 0.0)
    vals = dict(state, side_R=max(0.0, side), side_L=max(0.0, -side))
    return (r + sum(vals.get(k, 0.0) * d for k, d in c.items())) / r


def owned(log, nf):
    """[(i, name, frames)]: the frames each logged expression owns and holds. log entries are (name, start of its blend,
    t0, t1 or None, blend) in call order; a later call owns the frames it covers (it cleared the older keys there)."""
    owner = [None] * (nf + 2)
    for i, (name, ta, t0, t1, blend) in enumerate(log):
        end = nf if t1 is None else min(nf, F(t1 + blend))
        for f in range(max(1, F(ta)), end + 1):
            owner[f] = i
    out = []
    for i, (name, ta, t0, t1, blend) in enumerate(log):
        last = nf if t1 is None else min(nf, F(t1))
        out.append((i, name, [f for f in range(max(1, F(t0) + SETTLE_F), last + 1) if owner[f] == i]))
    return out


def lint(log, states, not_smiling, co, nf=None):
    """states[f - 1] is the face state on frame f. Returns (per-window report rows, failures):
    rows (name, t0, t1, worst smile key, worst smile read, frames); failures (name, frame, what, value)"""
    nf = nf or len(states)
    rows, bad = [], []
    for i, name, frames in owned(log, nf):
        if name not in not_smiling or not frames: continue
        wk = wr = -9.0
        for f in frames:
            s = states[f - 1]
            k = max(s.get('smile', 0.0), s.get('grin', 0.0)); r = smile_read(s, co)
            wk = max(wk, k); wr = max(wr, r)
            if k > SMILE_MAX: bad.append((name, f, 'smile key', k))
            if r > READ_MAX: bad.append((name, f, 'smile read', r))
        rows.append((name, (frames[0] - 1) / FPS, (frames[-1] - 1) / FPS, wk, wr, len(frames)))
    return rows, bad


def check(data, nf, name="shot"):
    import bpy
    import character as CH
    co = coeffs(CH._mouth_paths(), CH.MOUTH_KEYS)
    sc = bpy.context.scene; states = []
    for f in range(1, nf + 1):
        sc.frame_set(f); states.append(data._face_state())
    rows, bad = lint(data.face_log, states, set(CH.Data.NOT_SMILING), co, nf)
    for nm, a, b, wk, wr, n in rows:
        print(f"FACE {name}: '{nm}' held {a:.2f}-{b:.2f}s: smile key worst {wk:.2f} (max {SMILE_MAX}), smile read worst "
              f"{wr:.2f} of his resting smile (max {READ_MAX})", flush=True)
    seen = set()
    for nm, f, what, v in bad:
        if (nm, what, f // 6) in seen: continue
        seen.add((nm, what, f // 6))
        print(f"FACE {name} f{f} t={(f - 1) / FPS:.2f}s: '{nm}' is set but the {what} is {v:.2f}: the face turned into a smile", flush=True)
    ok = not bad
    print(f"FACE {name}: {len(rows)} non-smiling faces checked, {len(bad)} smiling frames inside them -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok
