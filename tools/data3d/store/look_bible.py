"""THE LOOK BIBLE: every ruling caaleb has given on how a 3D Data short must look and play, in his own words, in ONE
place (2026-11-22, after the lightning short spent three days and seventeen judge rounds on one opening shot: "you, A,
don't even know what the fuck you're trying to go for here style-wise, and B, when you get told what you're trying to
go for, you fucking ignore it").

Until now these rulings lived in thirty-odd session notes and a dozen one-off checks, and no shot was built or judged
against all of them at once. So every round aimed at the last round's notes instead of at his look.

  RULINGS      the rules, each with the date and the words it came from. Add a ruling HERE when he gives one.
  REFERENCES   frames from the 3D short he approved and posted (self-checkout, 2026-11-12). The judge READS them
               beside every shot, so "the bar" is a picture, not a paragraph.
  brief()      the text judge3d.py puts in front of every judge; a shot that breaks a ruling is a hard OFF THE LOOK
  markdown()   the same rulings as a page for caaleb to check (python look_bible.py)

Data's design is not in here because it is not open: the rig is approved and only he changes it.
"""
import os
from pathlib import Path

# where the approved frames live: the project's shared folder (media is never committed). JUDGE3D_LOOK_REFS overrides.
REF_DIR = Path(os.environ.get("JUDGE3D_LOOK_REFS", "/mnt/project-files/data3d/look"))

REFERENCES = [
    ("approved_hook_store.jpg", "self-checkout short, hook: a real, built, lit store; Data whole in it; the machine's "
                                "result (cash) big and falling to the floor"),
    ("approved_lanes_9of10.jpg", "self-checkout short, 9 out of 10: the wide shot that SHOWS the number (nine lanes "
                                 "flipped to SELF, one CASHIER left), Data the cause at the MASTER lever"),
    ("approved_calendar.jpg", "self-checkout short, jobs gone: torn years really fall and pile on the floor; the "
                              "counter is readable on a phone"),
]

# (area, rule, date, his words)
RULINGS = [
    # ---- the look of the picture
    ("look", "Kinda real, clean and professional. Not clay, matte or cel-shaded; not glossy plastic.",
     "2026-11-05", "the style is still giving claymation ... futuristic SpongeBob"),
    ("look", "Backgrounds as real as we can make them.",
     "2026-11-06", "the realer the better ... at an 8, take it to a 10"),
    ("look", "Every object built from its real parts at real scale with real textures, one tied palette. No flat "
             "colour boxes, no cardboard backdrops, no sign clutter.",
     "2026-11-06", "the NYC render is the bar because of how it was built"),
    ("look", "The approved store is the standard of finish every new place must match.",
     "2026-11-11", "exactly how I want it"),
    ("look", "Friendly and readable: lit, eye level, never horror lighting or dark underlit night.",
     "2026-10-30", "moving the wrong way, horror movie vibes"),
    ("look", "Clean frames: no shimmer, crawl or flicker between frames.",
     "2026-11-11", "had the Dr. Katz effect"),
    # ---- the story and the world
    ("world", "A 3D short is a STORY in one believable world the viewer buys into, not a list of 2D beats.",
     "2026-11-19", "Building a world that the viewer has to believe in. And you're just being very, very lazy about it"),
    ("world", "Every beat in its own place, built fresh. Reusing a set or prop is a rare, deliberate callback.",
     "2026-11-18", "reusing stuff should be like a wow, crazy one-time and forever event"),
    ("world", "Each beat SHOWS its fact as a picture (nine of ten lanes flipping), not a number on a sign.",
     "2026-11-11", "there needs to be an ultra wide shot so they can see ... what percentage"),
    ("world", "One distinct visual idea per beat; no two beats with the same verb.",
     "2026-11-13", "All those were just varying shots of bananas getting browner"),
    ("world", "Things behave for real: pages tear and fall to the floor, coins land in the jar, what is hit reacts.",
     "2026-11-12", "props behave for real"),
    # ---- Data and the staging
    ("staging", "Data CAUSES what moves; he does the work with the tool, not beside it.",
     "2026-10-01", "he's the one that's making the water rise"),
    ("staging", "Stage for the one camera like a film director: the simplest pose that reads from THIS lens.",
     "2026-11-06", "it only makes sense if you look at it from where you're supposed to be standing"),
    ("staging", "Data whole in his world and fitting it, never his back to us, never pasted in.",
     "2026-11-12", "no awkward back-to-camera, Data must fit the scene"),
    ("staging", "No talking heads: something new happens every couple of seconds, building to the end.",
     "2026-11-19", "Half that was the Dr. Katz effect"),
    ("staging", "No stock gags: coins into a jar, piles growing, things being pumped up.",
     "2026-11-19", "Pouring coins into a fucking jar. That's in every single one of our videos"),
    ("staging", "The opening grabs in the first second or people swipe.",
     "2026-10-17", "That can't be an opening clip"),
    ("staging", "Data's face and body must read the emotion; big props carry a beat, not a subtle face.",
     "2026-11-14", "faces read as resting smile"),
]


def refs():
    """the approved frames that exist here, as absolute paths; missing ones are SAID, never skipped quietly"""
    have, missing = [], []
    for name, what in REFERENCES:
        p = REF_DIR / name
        (have if p.exists() else missing).append((p, what))
    return have, missing


def brief():
    """the section judge3d.py puts in every judge's brief"""
    have, _ = refs()
    lines = ["THE OPERATOR'S LOOK. These are his own rulings on how this channel's 3D shorts look and play. A shot that",
             "plainly breaks one FAILS with the hard defect OFF THE LOOK (name the ruling and the frames). Grade against",
             "them every time, not only against the shot's own line:"]
    for area, rule, when, said in RULINGS:
        lines.append(f"- {rule} (his words, {when}: \"{said}\")")
    if have:
        lines += ["", "THE BAR AS PICTURES. Frames from the 3D short he approved and posted. READ each with the Read tool",
                  "before grading. They show the finish, the realism and the clarity he wants (ignore their caption text):"]
        lines += [f"- {p}: {what}" for p, what in have]
    return "\n".join(lines)


def markdown():
    out = ["# The 3D look: caaleb's rulings", "",
           "Every shot is built and judged against all of these at once. Data's design is approved and not open.", ""]
    for area, title in (("look", "The picture"), ("world", "The story and the world"), ("staging", "Data and the staging")):
        out += [f"## {title}", ""]
        out += [f"- **{rule}** ({when}: \"{said}\")" for a, rule, when, said in RULINGS if a == area]
        out.append("")
    out += ["## The bar as pictures", ""] + [f"- `{n}`: {w}" for n, w in REFERENCES]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(markdown())
