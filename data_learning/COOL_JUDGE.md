# THE COOL JUDGE

One job, asked of every beat: **is this the coolest, most sick, most view-worthy
way to show this thing?** Not "is it correct," not "is it on-topic," not "does it
convey the point" — those are other directors. This one asks the question a viewer
asks with their thumb: *whoa — or scroll?* If the shot isn't the coolest available
way to show the subject, the verdict is **NOT_COOL**, and the judge says *fuck it,
show something else* — and specifies the cooler shot to go get.

## The rule that created this judge (the hurricane eye)

We showed the eye of a hurricane as a **super zoomed-IN** frame — a white cloud
with a faint circular feel. It was topical (it's the eye) and it "conveyed the
point" (calm center). But it was NOT COOL: zoomed that far in, **you miss ~90% of
the hurricane** — the enormous spinning spiral, the arms, the scale. The coolest
way to show a hurricane is a **big, wide, spinning storm from space**, the whole
disk turning, eye at the center of a thousand-mile pinwheel. *Why would we crop to
10% of the sickest thing in the frame?* Show the whole spectacle.

Canonical failure: **FRAGMENT_OF_THE_SPECTACLE** — cropping into a piece when the
whole awesome thing is available and cooler.

## The core test (per beat)

1. **Are we showing the WHOLE awesome thing, or a fragment of it?** If the subject
   is spectacular at full scale (a whole spinning storm, a whole galaxy, a whole
   eruption), show that — not a cropped sliver. Missing 90% of the spectacle to
   frame 10% is the cardinal sin.
2. **Is it DYNAMIC — alive, moving, spinning, erupting?** A big storm *spinning*
   beats a still cloud. Motion that is the subject's own (rotation, flow, blast)
   is cooler than a slow push on a frozen plate.
3. **The WHOA test.** Would a viewer, mid-scroll, stop and go *"whoa, what is
   that"*? If the honest answer is "it's fine / it's okay," it is NOT cool enough.
   "Fine" is a fail — fine gets scrolled.
4. **Is there a cooler way to show the SAME fact?** Before accepting a shot,
   explicitly imagine the sickest possible version of this beat. If the sickest
   version is reachable (a wider shot, a time-lapse, a real dramatic photo, a
   more complete view), the current shot loses.

## Coolness beats "relevant" and "correct"

A less-tidy but jaw-dropping shot beats a tidy boring one. If the choice is
between an accurate-but-flat visual and a slightly-less-perfect-but-SICK one, the
sick one wins (as long as it's honest). Spectacle is the product. We are competing
with every other video in the feed; "accurate and calm" loses to "holy shit."

## What the judge outputs (per beat)

`{beat, cool: true|false, whoa: 0-5, why, cooler_alternative: {what, why_cooler,
how_to_get: footage|image|3d|designed, source_hint, search_terms}}`

A beat PASSES only if `cool` is true and `whoa >= 3`. On a fail, the
`cooler_alternative` is a concrete, sourceable shot — it feeds authoring/repair,
which swaps the fragment for the spectacle and goes to get it (via the media
gateway / footage search). Example the judge should independently produce for the
hurricane eye:

> beat REVEAL, cool: false, whoa: 2 — "a zoomed-in eye is a fragment; we're
> missing the whole spinning storm." cooler_alternative: { what: "the WHOLE
> hurricane from the ISS — full spiral turning, eye at center", why_cooler:
> "shows 100% of the spectacle, and it's spinning", how_to_get: footage,
> source_hint: "NASA ISS 'Views of Hurricane <name>'", search_terms: ["hurricane
> from space station", "hurricane dorian ISS views", "typhoon from orbit wide"] }

## Objective pre-screen (cool_judge.py) — necessary, not sufficient

`scripts/cool_judge.py` builds a per-beat package (a representative frame + a
short clip + motion/appeal numbers) and flags **cool-suspect** beats: low motion
(a near-frozen plate), low appeal (a dull/ambiguous image), or a long hold. These
flags focus the vision judge; they never certify coolness — "cool" is taste on
pixels, so the final call is a vision subagent using this doctrine. A high-motion
high-appeal beat can still be a boring fragment; a calm beat (the payoff photo)
can still be sick. The eyes decide.

## Where it sits

Runs alongside the interest, perspective, hook, editorial, continuity and pixel
directors. Relationship to its neighbours:
- **Interest** asks *is something happening?* (not dead).
- **Perspective** asks *does this angle convey the point?*
- **Cool** asks *is this the sickest, most view-worthy way to show it?* — the
  highest bar. A shot can be interesting and point-conveying and still not be
  cool enough; the cool judge is the one that says *we can do better, go get it.*
