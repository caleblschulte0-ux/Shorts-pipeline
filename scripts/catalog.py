"""Source catalog for the daily run.

Each entry is a confirmed-reachable source URL + hook + script + targeting
metadata. The orchestrator picks unposted entries first, then falls back
to least-recently-posted. Add more entries to expand the rotation.

To add an entry:
1. Confirm the source URL is reachable (curl -I should 200)
2. Pick a strong hook (first 1.5s must grab — see writing_notes below)
3. Set --start to skip any intro card
4. Pick gameplay tag ('subway' or 'minecraft') for variety

writing_notes:
  - First sentence must NOT be "hey what's up" — start with stakes,
    specificity, contradiction, or impossibility.
  - 50-70 words total. ~25s of TTS at edge-tts default speed.
  - Lean into present tense and second person where possible.
  - Tags help YouTube classify; keep ≤8, all lowercase.
"""

CATALOG: list[dict] = [
    {
        "id": "nba_dunks_v1",
        "topic": "basketball",
        "source_url": "https://archive.org/download/youtube-k7VifslDIv0/k7VifslDIv0.mp4",
        "start": 8, "duration": 22, "gameplay": "subway",
        "title": "Every Dunk Here Deleted Somebody's Confidence #shorts",
        "script": (
            "Every dunk you are about to watch ended a defender's confidence on live "
            "television. These men weigh two hundred pounds and they treat gravity "
            "like a polite suggestion. The cameras zoom in just to catch the dignity "
            "leaving their bodies. Pure unfiltered physical violence. Set to a rim."
        ),
        "tags": ["shorts","nba","basketball","dunks","highlights","sports","athleticism"],
    },
    {
        "id": "ufc_kos_v1",
        "topic": "combat",
        "source_url": "https://archive.org/download/youtube-rrxamKa5mpk/rrxamKa5mpk.webm",
        "start": 45, "duration": 22, "gameplay": "minecraft",
        "title": "Knocked Out In Three Seconds Flat #shorts",
        "script": (
            "Imagine training your entire adult life and getting put to sleep in three "
            "seconds. Every knockout in here ended faster than the walkout song. The "
            "hands move faster than the brain can compute danger. The referee barely "
            "has time to wave it off. This is the highest level of legal violence on the "
            "planet and it is over before it starts."
        ),
        "tags": ["shorts","ufc","mma","knockout","highlights","combat"],
    },
    {
        "id": "lioness_hunt_v1",
        "topic": "wildlife",
        "source_url": "https://archive.org/download/youtube-mVyteSLfdgY/mVyteSLfdgY.webm",
        "start": 5, "duration": 22, "gameplay": "minecraft",
        "title": "She Has 90 Seconds Before She Starves #shorts",
        "script": (
            "This lioness has not eaten in nine days. She has about ninety seconds to "
            "fix that. The antelope sleeping at the bottom of your screen does not yet "
            "know it is the solution to her problem. Every step she takes is a math "
            "equation. One loud snap and she starves."
        ),
        "tags": ["shorts","wildlife","lion","nature","predator","africa","hunt"],
    },
    {
        "id": "wingsuit_cave_v1",
        "topic": "stunts",
        "source_url": "https://archive.org/download/UnbelievableWingsuitCaveFlightBatmanCaveAlexanderPolli/Unbelievable_Wingsuit_Cave_Flight__Batman_Cave__Alexander_Polli.mp4",
        "start": 8, "duration": 22, "gameplay": "subway",
        "title": "He Flew Through A Hole In A Mountain #shorts",
        "script": (
            "This man is about to fly through a hole in a solid mountain. At one hundred "
            "and fifty miles per hour. With about three feet of clearance on each side. "
            "One twitch from his shoulder and he becomes a stain on the rock. He did it "
            "on purpose. He did it twice for the camera. Then he kept going."
        ),
        "tags": ["shorts","wingsuit","extreme sports","flying","stunts","basejump"],
    },
    {
        "id": "rally_v1",
        "topic": "motorsport",
        "source_url": "https://archive.org/download/youtube-Ni2zSq5maY4/Ni2zSq5maY4.webm",
        "start": 15, "duration": 22, "gameplay": "minecraft",
        "title": "Braking Is For Cowards — Rally Driving #shorts",
        "script": (
            "This is rallying. There is no track. The walls are made of actual trees. The "
            "trees are real. Every driver in here has accepted death as a reasonable "
            "Tuesday outcome of doing their job. They are not braking, because braking is "
            "for cowards. The car is sideways because forward is too slow."
        ),
        "tags": ["shorts","rally","wrc","cars","motorsport","driving","extreme"],
    },
    {
        "id": "f4_tornado_vanwert_v1",
        "topic": "weather",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/b/b9/2002_Van_Wert_Tornado_Dashcam.webm",
        "start": 0, "duration": 21, "gameplay": "minecraft",
        "title": "F4 Dashcam — He Drove Toward The Tornado #shorts",
        "script": (
            "This is a real dashcam from October two thousand two. A driver near Van Wert "
            "Ohio is filming straight into an F-four tornado crossing the highway. Three "
            "minutes later this same storm hit a movie theater. Fifty people inside "
            "survived by diving behind their seats. The roof landed two miles away."
        ),
        "tags": ["shorts","tornado","dashcam","weather","storm","ohio"],
    },
    {
        "id": "f5_tornado_bridgecreek_v1",
        "topic": "weather",
        "source_url": "https://archive.org/download/youtube-l6LCUCzoeUU/l6LCUCzoeUU.mp4",
        "start": 25, "duration": 22, "gameplay": "subway",
        "title": "Strongest Tornado Ever Recorded — 318 MPH #shorts",
        "script": (
            "This is the most powerful tornado ever measured on planet Earth. Wind speeds "
            "inside the funnel hit three hundred and eighteen miles per hour. That is fast "
            "enough to strip asphalt from the road and erase entire neighborhoods in "
            "seconds. Watching this footage feels like watching the atmosphere itself go "
            "completely insane."
        ),
        "tags": ["shorts","tornado","weather","oklahoma","f5","storm","extreme weather"],
    },
    {
        "id": "parkour_pov_rennes_v1",
        "topic": "stunts",
        "source_url": "https://archive.org/download/youtube-S6YVK7BMiEU/S6YVK7BMiEU.mp4",
        "start": 30, "duration": 22, "gameplay": "subway",
        "title": "He Treats The Entire City As A Playground #shorts",
        "script": (
            "Bro just rewrote the laws of physics. Watch his feet barely touch the rooftops "
            "as he flies between buildings. Most people couldn't even climb a fence. This "
            "guy treats the whole city like a playground. Pure athleticism. Zero hesitation. "
            "Reads gaps and commits before his brain catches up."
        ),
        "tags": ["shorts","parkour","freerunning","stunts","rooftop","pov"],
    },
    {
        "id": "power_slap_v1",
        "topic": "combat",
        "source_url": "https://archive.org/download/youtube-DDQaq0_cqAg/DDQaq0_cqAg.webm",
        "start": 4, "duration": 22, "gameplay": "minecraft",
        "title": "One Open Hand. Lights Out. #shorts",
        "script": (
            "There are no gloves. There is no defense. Two grown men take turns slapping "
            "each other in the face as hard as humanly possible until one of them shuts off "
            "like a lamp. Every slap in here registered higher than a car crash. The brain "
            "rattles inside the skull. Then the body just folds."
        ),
        "tags": ["shorts","power slap","slap","knockout","combat","viral"],
    },
    {
        "id": "f1_champions_v1",
        "topic": "motorsport",
        "source_url": "https://archive.org/download/youtube-KjFJ__q2vgE/KjFJ__q2vgE.webm",
        "start": 8, "duration": 22, "gameplay": "subway",
        "title": "Every F1 World Champion Since 1950 #shorts",
        "script": (
            "These are every single Formula One world champion since nineteen fifty. "
            "Seventy years of the most expensive sport on Earth. Each one of them was the "
            "fastest human alive in their year. Some died chasing it. Some retired billionaires. "
            "All of them drove cars that wanted to kill them."
        ),
        "tags": ["shorts","formula1","f1","motorsport","racing","cars","history"],
    },
    {
        "id": "f1_safety_car_v1",
        "topic": "motorsport",
        "source_url": "https://archive.org/download/youtube-3SHJIZ2-REU/3SHJIZ2-REU.webm",
        "start": 5, "duration": 22, "gameplay": "minecraft",
        "title": "What Happens When The Safety Car Stays Out #shorts",
        "script": (
            "In Formula One, the safety car is the only thing slowing twenty cars worth two "
            "hundred million dollars from racing at full speed. When it does not come in, "
            "the drivers go feral. The pit wall starts screaming. Strategists rewrite races "
            "in twenty seconds. This is what controlled chaos at three hundred kilometers an "
            "hour looks like."
        ),
        "tags": ["shorts","formula1","f1","motorsport","racing","safety car"],
    },
    {
        "id": "iceland_volcano_2023_v1",
        "topic": "weather",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/5/53/007_Volcano_eruption_of_Litli-Hr%C3%BAtur_in_Iceland_in_2023_Video_by_Giles_Laurent.webm",
        "start": 6, "duration": 22, "gameplay": "minecraft",
        "title": "Watching New Earth Get Born In Real Time #shorts",
        "script": (
            "What you are watching is fresh planet Earth being born in real time. This is "
            "the Litli-Hrutur eruption in Iceland from twenty twenty three. That orange is "
            "rock so hot it forgot it was solid, flowing at over two thousand degrees "
            "Fahrenheit. Iceland sits on top of two plates pulling apart. Every few years, "
            "the country tears open and bleeds lava."
        ),
        "tags": ["shorts","volcano","iceland","lava","eruption","nature","2023"],
    },
    {
        "id": "kobe_dwight_v1",
        "topic": "basketball",
        "source_url": "https://archive.org/download/youtube-szmYKrZtwW4/szmYKrZtwW4.webm",
        "start": 0, "duration": 22, "gameplay": "subway",
        "title": "\"I Baptized Dwight\" — Kobe On Killing Souls #shorts",
        "script": (
            "Kobe Bryant just dunked on Dwight Howard, who is seven feet tall and weighs "
            "two hundred sixty five pounds of muscle. Then he found a microphone. Then he "
            "said something so disrespectful the entire NBA paused. This is what Mamba "
            "Mentality sounds like out loud. Pure surgical confidence with the receipts to "
            "back it up."
        ),
        "tags": ["shorts","kobe","nba","basketball","dwight howard","mamba","dunk"],
    },
    {
        "id": "hawaii_bigwave_v1",
        "topic": "extreme",
        "source_url": "https://archive.org/download/XcorpsSpecialHawaiiBigWavesWithFilter/XcorpsHawaiiSpecialFilterWEB.mp4",
        "start": 180, "duration": 22, "gameplay": "subway",
        "title": "This Wave Has Killed World Champions #shorts",
        "script": (
            "That wave has the energy of a four story building falling on you. The riders "
            "you are watching paddle into water that has killed world champions. One mistake "
            "and the ocean drags you to the bottom and pins you there. They are smiling "
            "while doing it. Pure madness in a wetsuit."
        ),
        "tags": ["shorts","surfing","big wave","hawaii","extreme sports","ocean"],
    },
]


def by_id(entry_id: str) -> dict | None:
    for c in CATALOG:
        if c["id"] == entry_id:
            return c
    return None
