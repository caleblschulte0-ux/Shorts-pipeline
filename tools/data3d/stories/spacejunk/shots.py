"""space junk through a roof: the first daily-pipeline short, staged with store/director.py"""
import director as D


def shot_test():
    s = D.Shot(globals(), "living_room")
    s.sky("day"); s.ground("grass")
    s.hero(u=0.3, height=0.42)
    sofa = s.model("barrel_03", u=0.72, depth=3.2)
    rock = s.model("boulder_01", u=0.7, depth=3.0, scale=0.3)
    top = s.air(0.75, 1.15, 3.0)
    s.fall(rock, top, s.at(0.7, 3.0, 0.1), 0.3, 0.42, spin=(200, 90, 0), bounce=0.15)
    s.dust(s.at(0.7, 3.0), 0.42); s.shake(0.42); s.flash(s.at(0.7, 3.0, 0.3), 0.42)
    s.act([(0.05, "look", "lens"), (0.3, "look", top), (0.44, "alarmed"), (0.46, "step", (-0.25, 0.0)), (0.6, "look", rock), (0.8, "look", "lens"), (0.82, "shrug")])
    s.happens("a rock falls from the sky and lands beside him", [rock], 0.3, 0.6, moves=[rock])
    return s.done()


SHOTS = {1: shot_test, 2: shot_test, 3: shot_test, 4: shot_test, 5: shot_test}
