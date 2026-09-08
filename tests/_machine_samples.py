"""One production-shaped sample per machine, shared by the tests.

Kept in one place because two tests need the same inputs and a machine
measured against different data in each is a machine nobody has actually
measured. Every entry is the kind of data the router would really hand that
machine — a ranking for the race, stages for the funnel, a percent for the
spinner — not a synthetic best case.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning.insights import Insight                # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC=Source(name="BLS",publisher="BLS",url="https://x",access_date="2026-01-01")
def mk(pairs,unit="count",topic="t",main="m",base=None):
    i=Insight(kind="scene",topic=topic,main_insight=main,
      items=[DataPoint(label=l,value=float(v)) for l,v in pairs],source=SRC,
      unit=unit,highlight_label=pairs[0][0])
    if base: i.baseline=DataPoint(label=base[0],value=float(base[1]))
    return i
YRS=[(str(2016+k), 42.0+k*7) for k in range(8)]
DOWN=[(str(2016+k), 96.0-k*7) for k in range(8)]
ZIG=[(str(2016+k), v) for k,v in enumerate([99,101,97,100,98,101,97,99])]
RANK=[("San Jose",11.3),("Los Angeles",9.7),("Miami",8.2),("Seattle",6.8),("Denver",5.4)]
STAGE=[("Applied",12000),("Screened",9800),("Interviewed",2100),("Offered",1700),("Hired",1500)]
SAMPLES = {
 "unit_figures": mk(RANK[:1],"usd"), "dot_field": mk([("Own",23.0)],"percent"),
 "balance": mk([("Rent",2400),("Wage",3100)],"usd"), "race_track": mk(RANK),
 "staircase": mk(YRS,"usd"), "elevator": mk(DOWN,"percent"),
 "burden": mk(YRS,"usd"), "gauge": mk([("Rate",22.9)],"percent"),
 "skyline": mk([("Tokyo",37.4),("Delhi",9.2),("Cairo",7.8),("Lima",4.1)],"millions"),
 "tower": mk(YRS,"usd"), "hurdle": mk([("San Jose",11.3)],"years",base=("US average",5.9)),
 "funnel": mk(STAGE), "conveyor": mk([("Parcels",1400)],"per day"),
 "pipes": mk([("Rent",34),("Food",22),("Transit",18),("Other",26)],"percent"),
 "spotlight": mk(ZIG,"index"), "road": mk([(str(2016+k),50.0+(k%2)*0.2) for k in range(8)],"percent"),
 "tape": mk([("2016",42),("2026",97)],"usd"), "bridge": mk([("Now",76)],"percent",base=("Target",100)),
 "centre": mk(RANK,"years"), "coaster": mk(ZIG,"index"),
 "thermometer": mk([("Now",88)],"percent",base=("Limit",100)),
 "wheel": mk([(str(2016+k),v) for k,v in enumerate([10,60,12,58,11,62,13,59])],"index"),
 "darts": mk([("A",100),("B",102),("C",101),("D",99),("E",100),("F",101)],"index"),
 "queue": mk([(str(2016+k), 200.0+k*180) for k in range(8)],"count"),
 "bottleneck": mk(STAGE), "leaky": mk([("Enrolled",4800),("Finished",860)]),
 "inout": mk([("Inflow",1840),("Outflow",1310)],"megalitres"),
 "sorter": mk([("Housing",4200),("Transit",2600),("Parks",1400),("Admin",900)],"usd"),
 "chain": mk([("Wafer",940),("Assembly",720),("Test",210),("Ship",880)],"k units"),
 "spinner": mk([("Rain",23.0)],"percent"), "doors": mk([("Match",4.0)],"percent"),
 "fan": mk([(str(2016+k),62+k*3.1) for k in range(8)]+[("2040",108.0)],"millions"),
 "gears": mk([("Median rent",2400),("Median wage",3100)],"usd"),
 "slider": mk([("Top speed",82),("Range",148)]),
 "density": mk([("Manila",46000),("Houston",1400)],"per sq km"),
 "nest": mk([("Alaska",1723000),("New Jersey",22600)],"sq km"),
 "chairs": mk([("Applicants",41000),("Homes",1200)]),
 "hourglass": mk([("San Jose",11.3),("Detroit",2.4)],"years"),
 "trophies": mk([("Djokovic",24),("Nadal",22),("Federer",20)]),
 "basket": mk([("1999",34),("2026",19)]),
}
