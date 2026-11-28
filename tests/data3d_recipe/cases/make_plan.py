import json, sys
_D3 = __import__("pathlib").Path(__file__).resolve().parents[3] / "tools" / "data3d"
sys.path.insert(0, str(_D3 / "store")); sys.path.insert(0, str(_D3))
import shot_plan as SP
OUT = str(__import__("pathlib").Path(__file__).resolve().parent) + "/"
def P(name, objects, built, whole=True, held=False):
    d = {"name": name, "objects": objects, "whole": whole, "built_as": built}
    if held: d["held"] = True
    return d
def case(title, prop, props, action, consequence, shows, hands, new, says, vis, stands="beside", unseen=()):
    stills = [{"event": e, "shows": s, "hands": h, "visible": [{"prop": "data", "as": s}] + [{"prop": v, "as": s} for v in vv], "new": n}
              for e, s, h, n, vv in zip(SP.EVENTS, shows, hands, new, vis)]
    plan = {"prop": prop, "props": props, "framing": "close", "data": {"stands": stands, "side": "left", "frame_h": 0.36}, "action": action,
            "consequence": consequence, "says_still": 3, "unseen": [{"word": w, "why": "how"} for w in unseen], "stills": stills}
    return title, plan, says, ". ".join(s[0].upper() + s[1:] for s in shows) + "."
pose = lambda c: {"what": "data", "how": "pose", "cause": c}
C = [
 case("the bulb", "bulb", [P("bulb", ["bulb"], "a red glass lamp bulb with a brass cap", held=True), P("stump", ["stump"], "a sawn tree stump with bark and rings")],
      "he lifts the bulb off the stump", "the bulb comes up off the stump in his hand",
      ["he stands at the stump with the red bulb on it", "he lifts the bulb off the stump", "the bulb comes up off the stump in his hand", "he turns to us holding the bulb up"],
      ["free", "bulb", "bulb", "bulb"],
      [[], [pose("he reaches for it")], [{"what": "bulb", "how": "moves", "cause": "his hand lifts it"}, pose("he straightens")], [pose("he turns to us")]],
      "He lifts the bulb off the stump.", [["bulb", "stump"], ["bulb", "stump"], ["bulb", "stump"], ["bulb"]]),
 case("the crate", "crate", [P("crate", ["crate"], "a slatted wooden shipping crate with an iron lid")],
      "he slaps the wooden crate hard", "the iron lid jumps up off the crate",
      ["he stands beside the wooden crate", "he slaps the wooden crate hard", "the iron lid jumps up off the crate", "he turns round grinning with both arms thrown high"],
      ["free", "crate", "free", "free"],
      [[], [pose("he leans in and slaps it")], [{"what": "crate", "how": "opens", "cause": "his slap"}, pose("he steps back")], [pose("he turns to us")]],
      "He slaps the crate and the lid jumps.", [["crate"]] * 4),
 case("the shove", "crate", [P("crate", ["crate"], "a tall slatted wooden shipping crate")],
      "he shoves the tall crate", "the crate slides away over the soil",
      ["he stands beside the tall wooden crate", "he shoves the tall crate", "the crate slides away over the soil", "he turns round grinning with both arms thrown high"],
      ["free", "crate", "free", "free"],
      [[], [pose("he leans in and shoves")], [{"what": "crate", "how": "moves", "cause": "his shove"}, pose("he steps back")], [pose("he turns to us")]],
      "He shoves the crate and it slides away.", [["crate"]] * 4),
 case("the lever", "signal post", [P("signal post", ["post"], "an iron signal post with a red lever on it"), P("signal arm", ["signal arm"], "a red iron signal arm on the post")],
      "he pulls the red lever down", "the red signal arm goes up the post",
      ["he stands at the iron signal post", "he pulls the red lever down", "the red signal arm goes up the post", "he turns round grinning with both arms thrown high"],
      ["free", "signal post", "free", "free"],
      [[], [pose("he takes the lever")], [{"what": "signal arm", "how": "rises", "cause": "the lever he pulled"}, pose("he steps back")], [pose("he turns to us")]],
      "He pulls the lever and the signal arm goes up.", [["signal post", "signal arm"]] * 4),
 case("the high lever", "signal post", [P("signal post", ["post"], "an iron signal post with a red lever high on it"), P("signal arm", ["signal arm"], "a red iron signal arm on the post"), P("step", ["step"], "a wooden step of planks and nails")],
      "he pulls the high red lever down", "the red signal arm goes up the post",
      ["he stands on a wooden step at the iron signal post", "he pulls the high red lever down", "the red signal arm goes up the post", "he turns round grinning with both arms thrown high"],
      ["free", "signal post", "free", "free"],
      [[], [pose("he takes the lever")], [{"what": "signal arm", "how": "rises", "cause": "the lever he pulled"}, pose("he lets go")], [pose("he turns to us")]],
      "From a step he pulls the high lever and the signal arm goes up.", [["signal post", "signal arm", "step"], ["signal post", "signal arm"], ["signal post", "signal arm"], ["signal post", "signal arm"]]),
 case("the walk", "crate", [P("crate", ["crate"], "a small slatted wooden shipping crate")],
      "he walks the small crate across the field", "the crate stands a stride further along",
      ["he stands beside the small wooden crate", "he walks the small crate across the field", "the crate stands a stride further along", "he turns round grinning with both arms thrown high"],
      ["free", "crate", "free", "free"],
      [[], [pose("he leans into it and walks")], [{"what": "crate", "how": "moves", "cause": "his push"}, pose("he steps back")], [pose("he turns to us")]],
      "He walks the crate a stride across the field.", [["crate"]] * 4),
 case("the puddle", "puddle", [P("puddle", ["puddle", "ripple"], "a round puddle of blue water on the soil with a ripple running over it"), P("stick", ["stick"], "a long wooden walking stick", held=True)],
      "he prods the puddle with the stick", "the puddle spreads wide over the soil",
      ["he stands at the round puddle with a stick", "he prods the puddle with the stick", "the puddle spreads wide over the soil", "he turns to us holding the stick"],
      ["stick", "stick", "stick", "stick"],
      [[], [pose("he prods down")], [{"what": "puddle", "how": "grows", "cause": "his stick stirs it"}, pose("he steps back")], [pose("he turns to us")]],
      "He prods the puddle and it spreads.", [["puddle", "stick"], ["puddle", "stick"], ["puddle", "stick"], ["stick"]], stands="at the foot of"),
]
script = {"slug": "recipe_cases", "title": "recipe cases", "lines": [c[2] for c in C], "links": [],
          "storyboard": [f"{i} {c[0]} (a field; close, level with him): {c[3]}" for i, c in enumerate(C, 1)], "sets": ["field"] * len(C),
          "draft_windows": [[4.0 * i, 4.0 * i + 4.0] for i in range(len(C))]}
plan = {"shots": [c[1] for c in C]}
json.dump(script, open(OUT + "script.json", "w"), indent=1); json.dump(plan, open(OUT + "plan.json", "w"), indent=1)
bad = SP.validate(script, plan)
for w, t in bad: print(w, t[:330])
print("problems:", len(bad))
