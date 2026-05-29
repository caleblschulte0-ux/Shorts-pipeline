"""Source catalog for the daily run.

Each entry is a confirmed-reachable source URL + hook + script + targeting
metadata. The orchestrator picks unposted entries first, then falls back
to least-recently-posted. Add more entries to expand the rotation.

To add an entry:
1. Confirm the source URL is reachable (curl -I should 200)
2. WATCH the source at --start to verify the action actually shows up
3. Write a hook that lands in the first 7-9 words. No "this is X", no
   "you are about to watch". Lead with stakes, contradiction, or a
   visceral number.
4. Pick gameplay tag ('minecraft', 'geometry', or 'random' for either).
   All horizontal/16:9 gameplay only — Subway Surfers (portrait) is
   dropped because the player character couldn't be reliably kept in
   frame.

Hook templates that have worked:
  - Mortal stakes:   "He is one twitch from being killed by a mountain."
  - Specific stat:   "318 mph. The most violent wind ever measured."
  - Contradiction:   "These drivers do not believe in brakes."
  - Public failure:  "Kobe just dunked on a 7-foot man, then found a microphone."

Hook templates that do NOT work and should not appear in this file:
  - "This is <name>..."        # biographical filler
  - "Today we are going to..."  # tutorial energy
  - "You won't believe..."      # clickbait without payoff
  - "What you are about to..."  # delay; tell us what it IS, not when
"""

CATALOG: list[dict] = [
    # -------- already posted on the channel (kept for reference and
    # in case the rotation has to fall back to them) ----------------

    {
        "id": "f4_tornado_vanwert_v1",
        "topic": "weather",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/b/b9/2002_Van_Wert_Tornado_Dashcam.webm",
        "start": 0, "duration": 21, "gameplay": "random",
        "title": "F4 Dashcam — He Drove Toward The Tornado #shorts",
        "script": (
            "This dashcam is pointed at a real F4 tornado. October 24th, 2002. Six "
            "minutes after this footage ends, that storm hit a movie theater in Van "
            "Wert Ohio. Fifty people inside survived by diving behind their seats. "
            "The roof landed two miles away."
        ),
        "tags": ["shorts","tornado","dashcam","weather","storm","ohio"],
    },
    {
        "id": "nba_dunks_v1",
        "topic": "basketball",
        "source_url": "https://archive.org/download/youtube-k7VifslDIv0/k7VifslDIv0.mp4",
        "start": 8, "duration": 22, "gameplay": "random",
        "title": "These Men Treat Gravity Like A Suggestion #shorts",
        "script": (
            "These men treat gravity like a polite suggestion. Every dunk you are "
            "about to see ended a defender's career on live television. The cameras "
            "zoom in just to catch the dignity leaving their bodies. Two hundred "
            "pounds of pure physical violence, set to a rim."
        ),
        "tags": ["shorts","nba","basketball","dunks","highlights","sports"],
    },
    {
        "id": "ufc_kos_v1",
        "topic": "combat",
        "source_url": "https://archive.org/download/youtube-rrxamKa5mpk/rrxamKa5mpk.webm",
        "start": 45, "duration": 22, "gameplay": "random",
        "title": "Three Seconds. Career Over. #shorts",
        "script": (
            "Three seconds. That is how long it took to end his career on Saturday. "
            "Every knockout in here landed faster than the brain can compute danger. "
            "The referee barely has time to wave it off. This is the highest level "
            "of legal violence on the planet and it is over before it starts."
        ),
        "tags": ["shorts","ufc","mma","knockout","highlights","combat"],
    },

    # -------- v2 entries (timing + hook fixes from day 1 feedback) -----

    {
        "id": "wingsuit_cave_v2",
        "topic": "stunts",
        "source_url": "https://archive.org/download/UnbelievableWingsuitCaveFlightBatmanCaveAlexanderPolli/Unbelievable_Wingsuit_Cave_Flight__Batman_Cave__Alexander_Polli.mp4",
        # Verified frame-by-frame: 0-75s is intro + "First Test Jump" /
        # "Second Test Jump" / "Final Jump" title cards. Real helmet-POV
        # flight footage starts at ~78s.
        "start": 80, "duration": 22, "gameplay": "random",
        "title": "One Twitch From Being Killed By A Mountain #shorts",
        "script": (
            "This man is one shoulder twitch from being killed by a mountain. He is "
            "wearing a helmet camera. He is flying at one hundred and fifty miles per "
            "hour through a six foot wide hole in solid rock. Watch his hands. They "
            "do not move."
        ),
        "tags": ["shorts","wingsuit","extreme sports","flying","stunts","basejump"],
    },
    {
        "id": "lioness_hunt_v2",
        "topic": "wildlife",
        "source_url": "https://archive.org/download/youtube-mVyteSLfdgY/mVyteSLfdgY.webm",
        # Verified: actual pounce + kill is at t=35-65. First 30s is
        # the antelope sleeping which kills any hunt script.
        "start": 35, "duration": 22, "gameplay": "random",
        "title": "That Antelope Has Twelve Seconds To Live #shorts",
        "script": (
            "This lioness has not eaten in six days. That antelope has approximately "
            "twelve seconds to live. Watch how she disappears into the grass. Watch "
            "how she reappears on the other side. The antelope will not see her "
            "until the teeth are already in its neck."
        ),
        "tags": ["shorts","wildlife","lion","nature","predator","africa","hunt"],
    },

    # -------- unposted (ready to fire when PAUSED is removed) ----------

    {
        "id": "hindenburg_v1",
        "topic": "disasters",
        "source_url": "https://archive.org/download/HindenburgDisasterRealFootage1937hd/HindenburgDisasterRealFootage1937hd.mp4",
        # Verified: zeppelin approach + explosion at t=200. --start 180
        # gives 2s of the airship still flying before the iconic frame
        # collapse and people running.
        "start": 180, "duration": 22, "gameplay": "random",
        "title": "36 People Died In 32 Seconds — Hindenburg, 1937 #shorts",
        "script": (
            "Thirty six people died in thirty two seconds. The Hindenburg was the "
            "largest object ever to fly. It was filled with seven million cubic feet "
            "of hydrogen. The fire reached two thousand degrees before the frame even "
            "touched the ground. The radio reporter on scene started crying live on "
            "air. This footage is from May sixth, nineteen thirty seven."
        ),
        "tags": ["shorts","hindenburg","disaster","1937","history","zeppelin","explosion"],
    },
    {
        "id": "maradona_hand_of_god_v1",
        "topic": "sports_history",
        "source_url": "https://archive.org/download/2358076-wk-1986-de-hand-van-god-van-maradona-tegen-engeland/2358076-wk-1986-de-hand-van-god-van-maradona-tegen-engeland.mp4",
        # Verified: 58s clip of real 1986 World Cup England vs Argentina
        # footage. The "Hand of God" goal happens early; --start 5 catches
        # the buildup and the punch.
        "start": 5, "duration": 22, "gameplay": "random",
        "title": "The Most Famous Cheat In Sports History — Maradona 1986 #shorts",
        "script": (
            "Diego Maradona just punched a soccer ball into the net with his fist. "
            "The referee did not see it. England did not see it. The world saw it on "
            "replay and Argentina won the World Cup anyway. Maradona called it the "
            "Hand of God. England has never forgiven him."
        ),
        "tags": ["shorts","maradona","soccer","football","world cup","1986","argentina"],
    },
    {
        "id": "f5_tornado_bridgecreek_v2",
        "topic": "weather",
        "source_url": "https://archive.org/download/youtube-l6LCUCzoeUU/l6LCUCzoeUU.mp4",
        "start": 25, "duration": 22, "gameplay": "random",
        "title": "318 MPH — The Most Violent Wind Ever Measured #shorts",
        "script": (
            "Three hundred and eighteen miles per hour. That is the wind speed inside "
            "the most violent tornado ever measured. Fast enough to peel asphalt off "
            "the road like wet paper. It killed thirty six people. Entire neighborhoods "
            "stopped existing in under sixty seconds."
        ),
        "tags": ["shorts","tornado","weather","oklahoma","f5","extreme weather"],
    },
    {
        "id": "parkour_pov_rennes_v2",
        "topic": "stunts",
        "source_url": "https://archive.org/download/youtube-S6YVK7BMiEU/S6YVK7BMiEU.mp4",
        "start": 30, "duration": 22, "gameplay": "random",
        "title": "Thirty Feet Of Falling Between Him And A Closed Casket #shorts",
        "script": (
            "He has thirty feet of falling between him and a sidewalk. He does not "
            "look down. He does not slow down. He treats every rooftop in this city "
            "like it is made of foam. One missed step is a closed casket."
        ),
        "tags": ["shorts","parkour","freerunning","stunts","rooftop","pov"],
    },
    {
        "id": "power_slap_v2",
        "topic": "combat",
        "source_url": "https://archive.org/download/youtube-DDQaq0_cqAg/DDQaq0_cqAg.webm",
        "start": 4, "duration": 22, "gameplay": "random",
        "title": "He Is About To Slap His Soul Out Of His Body #shorts",
        "script": (
            "He is about to slap his soul out of his body. There are no gloves. There "
            "is no defense. Two grown men take turns hitting each other in the face "
            "as hard as humanly possible until one of them shuts off like a lamp."
        ),
        "tags": ["shorts","power slap","slap","knockout","combat","viral"],
    },
    {
        "id": "f1_safety_car_v2",
        "topic": "motorsport",
        "source_url": "https://archive.org/download/youtube-3SHJIZ2-REU/3SHJIZ2-REU.webm",
        "start": 5, "duration": 22, "gameplay": "random",
        "title": "Twenty F1 Cars Just Went Feral On Live TV #shorts",
        "script": (
            "Twenty Formula One cars worth two hundred million dollars are about to "
            "go feral on live television. The safety car stayed out. The strategists "
            "are screaming into headsets. Every driver is doing math at three hundred "
            "kilometers per hour. One mistake here and somebody dies."
        ),
        "tags": ["shorts","formula1","f1","motorsport","racing","safety car"],
    },
    {
        "id": "f1_champions_v2",
        "topic": "motorsport",
        "source_url": "https://archive.org/download/youtube-KjFJ__q2vgE/KjFJ__q2vgE.webm",
        "start": 8, "duration": 22, "gameplay": "random",
        "title": "Every F1 Champion Since 1950 — Some Died Chasing It #shorts",
        "script": (
            "Every Formula One world champion since nineteen fifty. Some retired "
            "billionaires. Some died chasing it. All of them drove cars that wanted "
            "to kill them, on tracks designed for cars half as fast. The fastest "
            "humans alive in their year, every year, for seventy years."
        ),
        "tags": ["shorts","formula1","f1","motorsport","racing","history"],
    },
    {
        "id": "iceland_volcano_2023_v2",
        "topic": "weather",
        "source_url": "https://upload.wikimedia.org/wikipedia/commons/5/53/007_Volcano_eruption_of_Litli-Hr%C3%BAtur_in_Iceland_in_2023_Video_by_Giles_Laurent.webm",
        "start": 6, "duration": 22, "gameplay": "random",
        "title": "The Earth Is Literally Bleeding In Real Time #shorts",
        "script": (
            "The Earth is literally bleeding in real time. That orange is rock heated "
            "to two thousand degrees Fahrenheit, flowing across Iceland because two "
            "tectonic plates are pulling apart underneath it. The locals stopped "
            "evacuating years ago. They just bring hot dogs to grill."
        ),
        "tags": ["shorts","volcano","iceland","lava","eruption","nature","2023"],
    },
    {
        "id": "kobe_dwight_v2",
        "topic": "basketball",
        "source_url": "https://archive.org/download/youtube-szmYKrZtwW4/szmYKrZtwW4.webm",
        "start": 0, "duration": 22, "gameplay": "random",
        "title": "Kobe Just Dunked On A 7-Foot Man Then Found A Microphone #shorts",
        "script": (
            "Kobe Bryant just dunked on a seven foot man. Then he found a microphone. "
            "Then he said something so disrespectful the entire NBA paused for a "
            "second. This is what Mamba Mentality sounds like out loud, with the "
            "receipts to back it up."
        ),
        "tags": ["shorts","kobe","nba","basketball","dwight howard","mamba","dunk"],
    },
    {
        "id": "hawaii_bigwave_v2",
        "topic": "extreme",
        "source_url": "https://archive.org/download/XcorpsSpecialHawaiiBigWavesWithFilter/XcorpsHawaiiSpecialFilterWEB.mp4",
        "start": 180, "duration": 22, "gameplay": "random",
        "title": "That Wave Has Killed World Champions #shorts",
        "script": (
            "That wave has the energy of a four story building falling on you. World "
            "champions have died paddling into water exactly like this. One mistake "
            "and the ocean takes you to the bottom and pins you there until you "
            "drown. They smile while doing it. Pure madness in a wetsuit."
        ),
        "tags": ["shorts","surfing","big wave","hawaii","extreme sports","ocean"],
    },
    {
        "id": "rally_v2",
        "topic": "motorsport",
        "source_url": "https://archive.org/download/youtube-Ni2zSq5maY4/Ni2zSq5maY4.webm",
        "start": 15, "duration": 22, "gameplay": "random",
        "title": "These Drivers Do Not Believe In Brakes #shorts",
        "script": (
            "These drivers do not believe in brakes. There is no track. The walls are "
            "made of actual trees. The trees do not move. Every driver in here has "
            "fully accepted death as a reasonable Tuesday outcome. The car is sideways "
            "because forward is too slow."
        ),
        "tags": ["shorts","rally","wrc","cars","motorsport","driving","extreme"],
    },
]


def by_id(entry_id: str) -> dict | None:
    for c in CATALOG:
        if c["id"] == entry_id:
            return c
    return None
