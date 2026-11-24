#!/bin/bash
# inline the drafts into shots.py (the one file the harness and the tests read)
cd "$(dirname "$0")"
python3 - <<'PY'
parts = [open("shots_head.py").read()]
places = ["grindavik_street", "wall_works", "wall_crest", "town_crack", "harbour_dawn"]
for k, name in enumerate(["world.py", "shot1.py", "shot2.py", "shot3.py", "shot4.py", "shot5.py"]):
    try: src = open(name).read()
    except FileNotFoundError: src = f"def shot{k}():\n    raise SystemExit('{name} not built yet')\n\n\ndef place_{places[k - 1]}():\n    pass\n"
    parts.append(f"\n\n# {'=' * 100}\n# {name}\n# {'=' * 100}\n" + src)
parts.append("\n\nSHOTS = {1: shot1, 2: shot2, 3: shot3, 4: shot4, 5: shot5}\n")
open("shots.py", "w").write("".join(parts))
PY
