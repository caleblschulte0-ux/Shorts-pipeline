# Bottom-game rules — relevance, reskin, creativity (STANDING REQUIREMENTS)

These are hard requirements for the bottom-half game. They exist because bottoms
kept shipping generic/irrelevant even after routing was "correct":

- A **stolen-backhoe** ATM heist → shown as plain `pursuit` cars (should be a
  backhoe being chased).
- A **tortoise escape** and **Merlín the duck** → both shown as the same generic
  `runner` critter (should be a tortoise / a duck).
- An **Iran warship strike in Hormuz** → shown as `plinko` balls (should be a
  naval battle).
- A **fireworks** story → generic theme (should be a fireworks duel).

The operator should NEVER have to hand-pick this. It must be automatic.

## 1. The bottom must match the story's SUBJECT, visually — not just its category
Routing to the right theme is not enough. The on-screen character/object must BE
the story's subject:
- tortoise escapes → runner themed as a **tortoise**
- Merlín the duck → runner themed as a **duck**
- stolen backhoe / police chase → pursuit where the fleeing vehicle is a **backhoe**
- goats on a road → runner/pursuit themed as a **goat**

**"Reskin" means swap the sprite/object to the subject — NOT just recolor the
frame.** (Today `config_from_story()` only color-grades; that is the core miss.)

## 2. Reuse is rare: at most ~1 base game per 3 videos
Most bottoms in a batch must be a DIFFERENT base game, or the same base game with
a genuinely different character. Two near-identical runners in one batch is a
fail. If two stories share a base game, they must at least have different
characters (duck vs tortoise), and prefer spreading across base games.

## 3. When no game fits, BUILD a new one — be creative
If a story has no fitting game, invent one instead of dumping it on plinko:
- naval / warship / Hormuz strike → ships trading fire across water
- fireworks / July 4 / festival → two sides launching fireworks at each other
plinko is the LAST resort, only for stories with genuinely no visual hook.

## 4. The subject is extracted automatically
The router pulls the hero noun (tortoise, duck, backhoe, warship, fireworks) from
the story and passes it to the theme as the character/object.

---

## Where it currently misfires (code)
- `themed_bottom.config_from_story()` — returns only a color grade (tint +
  saturation). No character/object swap → duck/tortoise/backhoe never appear.
  **Biggest gap.**
- Theme classes (`_Runner`, `_Pursuit`, …) — draw a HARDCODED sprite; there is no
  `character` parameter to swap in the story's subject.
- `_THEME_CLASSES` — fixed ~15 themes; no naval / fireworks → novel stories fall
  to plinko or the closest-but-wrong theme.
- The batch allocator — reuses a base theme for same-type batches (animal-heavy →
  multiple runners) and the shallow color reskin makes them look identical.

## The fix to build
1. Add a `character`/`sprite` parameter to themes that have a protagonist
   (runner: critter/duck/tortoise/dog/bird/goat…; pursuit: car/backhoe/truck/bike
   as the fleeing vehicle). Router picks it from the story's hero noun.
2. Expand the library with missing common types (naval battle, fireworks duel),
   and keep adding when a story type recurs with no fit.
3. Enforce reuse ≤ 1 base game / 3 videos; a reused base game ALWAYS gets a
   different character.
