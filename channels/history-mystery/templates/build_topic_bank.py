#!/usr/bin/env python3
"""Source-of-truth generator for templates/topic_bank.json.

The bank is the channel's anti-exhaustion inventory (OPERATING_MANUAL §0, §8;
CONTENT_ENGINE §1-2). Every topic here is a REAL, verifiable event/person/object
— we never pad the bank with fabrications, because credibility IS the brand.
Grow the bank by appending real topics to TOPICS and re-running this file:

    python3 channels/history-mystery/templates/build_topic_bank.py

It re-computes the weighted total + episode numbers and rewrites topic_bank.json.

Scores are 1-10 first-pass heuristics; the analytics loop (winning_patterns.json)
refines them over time. Weighted total (max 130):
    3*hook + 2*mystery + 2*share + 2*visual + 2*cred + 1*search + 1*series
Greenlight >= 85. Hard floors: cred < 6 -> graveyard; visual < 7 -> long-form only.
"""
from __future__ import annotations

import json
from pathlib import Path

SERIES = {
    "weird-wars": "Weird Wars",
    "disappearances": "Historical Disappearances",
    "impossible-artifacts": "Impossible Artifacts",
    "ancient-engineering": "Ancient Engineering",
    "made-up-humans": "Humans That Sound Made Up",
    "forgotten-disasters": "Forgotten Disasters",
    "medical-history": "Strange Medical History",
    "lost-expeditions": "Lost Expeditions",
}

# (slug, title, hook, series_id, fact/theory note, source_confidence,
#   hook, mystery, share, visual, cred, search, series)
TOPICS = [
    # ---------------- Weird Wars ----------------
    ("emu-war", "Australia Lost a War to Birds in 1932", "Soldiers vs. 20,000 emus with machine guns — the birds won.", "weird-wars", "FACT: real 1932 military operation in WA; emus 'won'. Casualty/round figures well documented.", "high", 10, 8, 10, 8, 9, 9, 8),
    ("anglo-zanzibar-war", "The War That Lasted 38 Minutes", "The shortest war in history was over before lunch.", "weird-wars", "FACT: 27 Aug 1896, ~38 min, Britain vs Zanzibar.", "high", 9, 7, 9, 7, 9, 8, 7),
    ("war-of-bucket", "Two Cities Went to War Over a Stolen Bucket", "Thousands died over a wooden pail in 1325.", "weird-wars", "FACT: 1325 Modena vs Bologna; the bucket is still displayed. Death toll figures vary.", "medium", 9, 8, 9, 7, 8, 7, 7),
    ("pig-war", "A Dead Pig Almost Started a US-UK War", "One shot pig nearly triggered an international war in 1859.", "weird-wars", "FACT: 1859 San Juan Islands standoff; only casualty was a pig.", "high", 8, 7, 8, 7, 9, 7, 7),
    ("football-war", "A Soccer Match Started a Real War", "Two nations went to war after a World Cup qualifier.", "weird-wars", "FACT: 1969 El Salvador-Honduras; football was a flashpoint, not sole cause (note tensions).", "high", 8, 7, 8, 6, 8, 7, 7),
    ("kettle-war", "A War Ended After One Cannonball Hit a Soup Pot", "The only shot of the war struck a kettle.", "weird-wars", "FACT: 1784 Kettle War, Dutch vs Austrian Netherlands; near-bloodless.", "medium", 9, 7, 9, 6, 8, 6, 7),
    ("christmas-truce", "Enemies Played Soccer Together in No Man's Land", "On Christmas 1914, the shooting just stopped.", "weird-wars", "FACT: 1914 Christmas Truce; football matches attested in some sectors.", "high", 8, 6, 8, 8, 9, 8, 7),
    ("paraguay-war", "A War That Killed Most of a Country's Men", "Paraguay lost up to 70% of its adult men in one war.", "weird-wars", "FACT/THEORY: War of the Triple Alliance 1864-70; mortality estimates debated.", "medium", 7, 8, 7, 6, 8, 5, 6),
    ("cod-wars", "Britain and Iceland Fought Wars Over Fish", "NATO allies rammed each other's ships over cod.", "weird-wars", "FACT: Cod Wars, mid-20th c.; ship ramming and net-cutting documented.", "high", 7, 6, 7, 7, 9, 6, 7),
    ("war-of-jenkins-ear", "A War Named After a Severed Ear", "A captain's pickled ear helped start a war.", "weird-wars", "FACT/THEORY: War of Jenkins' Ear, 1739; the ear-in-Parliament story is partly legend.", "medium", 9, 7, 9, 6, 7, 7, 7),
    ("toledo-war", "Ohio and Michigan Went to War Over Toledo", "Two US states nearly fought over a strip of mud.", "weird-wars", "FACT: Toledo War 1835-36, essentially bloodless.", "high", 7, 6, 7, 6, 8, 6, 7),
    ("pastry-war", "France Invaded Mexico Over a Pastry Bill", "A baker's unpaid debt led to a French invasion.", "weird-wars", "FACT/THEORY: 'Pastry War' 1838; the pastry claim was one pretext among debts.", "medium", 8, 7, 8, 6, 7, 6, 7),
    ("lijar-100-years", "A Spanish Town Was 'At War' With France for 100 Years", "Lijar declared war on France and forgot to stop.", "weird-wars", "FACT: Lijar 'declared war' 1883, symbolically ended 1981.", "medium", 8, 7, 8, 5, 7, 6, 6),
    ("battle-karansebes", "An Army Attacked Itself and Lost Thousands", "The Austrian army panicked and fought... itself.", "weird-wars", "THEORY: 1788 Battle of Karansebes; casualty figures and details are disputed/possibly exaggerated.", "low", 9, 8, 9, 6, 5, 6, 7),
    ("whisky-war", "Two Nations Fought 50 Years by Swapping Bottles", "Canada and Denmark 'attacked' an island with liquor.", "weird-wars", "FACT: Whisky War over Hans Island; resolved 2022.", "high", 8, 6, 8, 6, 9, 7, 7),
    ("aroostook-war", "The Bloodless War Over a Forest", "Two armies massed over trees — nobody died in battle.", "weird-wars", "FACT: Aroostook War 1838-39, no combat deaths.", "medium", 6, 6, 6, 5, 8, 5, 6),
    ("war-stray-dog", "A Runaway Dog Started a War Between Nations", "A soldier chasing his dog sparked an invasion.", "weird-wars", "FACT/THEORY: 1925 War of the Stray Dog, Greece-Bulgaria; the dog anecdote is traditional.", "medium", 9, 7, 9, 5, 7, 6, 7),
    ("golden-stool-war", "A War Fought Over a Sacred Golden Throne", "A British demand to sit on a stool sparked rebellion.", "weird-wars", "FACT: War of the Golden Stool, 1900, Ashanti vs Britain.", "high", 7, 7, 7, 7, 9, 6, 6),
    ("utah-war", "The War Almost Nobody Died In", "An entire US army marched on Utah — and barely fought.", "weird-wars", "FACT: Utah War 1857-58, largely bloodless (but note Mountain Meadows separately).", "medium", 6, 6, 6, 6, 8, 5, 6),

    # ---------------- Historical Disappearances ----------------
    ("roanoke", "An Entire Colony Vanished, Leaving One Word", "120 settlers gone — only 'CROATOAN' carved in wood.", "disappearances", "FACT: Roanoke colonists missing by 1590; 'CROATOAN' carving documented; fate is THEORY.", "high", 10, 10, 10, 8, 9, 9, 9),
    ("flannan-isles", "Three Lighthouse Keepers Vanished Without a Trace", "The lamp was out, the door locked, the men gone.", "disappearances", "FACT: 1900 Flannan Isles keepers vanished; cause is THEORY (rogue wave leading).", "high", 10, 10, 10, 8, 9, 8, 9),
    ("mary-celeste", "A Ghost Ship Found With Everyone Gone", "Hot food, full cargo, not a soul aboard.", "disappearances", "FACT: Mary Celeste found adrift 1872, crew never found; cause THEORY.", "high", 10, 10, 10, 8, 9, 9, 9),
    ("flight-19", "Five Bombers Vanished, Then So Did the Rescue Plane", "A whole squadron disappeared off Florida in 1945.", "disappearances", "FACT: Flight 19 lost 1945; 'Bermuda Triangle' framing is THEORY — likely navigation error.", "high", 9, 9, 9, 7, 8, 9, 8),
    ("amelia-earhart", "She Was Miles From Land When She Vanished", "The most famous pilot on Earth simply disappeared.", "disappearances", "FACT: Earhart/Noonan lost 1937; resting place THEORY (Nikumaroro leading).", "high", 9, 8, 9, 7, 9, 9, 8),
    ("db-cooper", "A Hijacker Parachuted Into the Night and Vanished", "He took the cash, jumped, and was never seen again.", "disappearances", "FACT: 1971 D.B. Cooper hijacking; identity unsolved.", "high", 9, 9, 9, 7, 8, 9, 8),
    ("percy-fawcett", "An Explorer Vanished Hunting a Lost City", "He walked into the Amazon for 'Z' and never returned.", "disappearances", "FACT: Fawcett vanished 1925; fate THEORY.", "high", 9, 9, 9, 7, 8, 7, 8),
    ("louis-le-prince", "The Father of Film Vanished Off a Moving Train", "He made the first movie, then disappeared days before fame.", "disappearances", "FACT: Le Prince vanished 1890; cause unsolved.", "high", 9, 9, 9, 7, 8, 6, 8),
    ("ambrose-bierce", "A Famous Writer Rode Into a War and Vanished", "He wrote his own ending: 'to be a gringo in Mexico...'", "disappearances", "FACT: Bierce disappeared ~1913-14 in Mexico; fate unknown.", "high", 8, 8, 8, 6, 8, 6, 8),
    ("carroll-deering", "A Schooner Ran Aground With No Crew and a Pot of Food", "The ghost ship's entire crew was simply gone.", "disappearances", "FACT: Carroll A. Deering found 1921; crew never found; cause THEORY.", "high", 9, 9, 9, 7, 8, 6, 8),
    ("sodder-children", "Five Kids Vanished in a Fire That Left No Bones", "The house burned — but the children were never found.", "disappearances", "FACT: 1945 Sodder case; no remains recovered; fate unsolved/contested.", "medium", 9, 9, 9, 6, 7, 6, 8),
    ("frederick-valentich", "A Pilot Reported a Strange Object, Then Went Silent", "'It's not an aircraft' — then he and his plane vanished.", "disappearances", "FACT: Valentich vanished 1978; UFO framing is THEORY, likely spatial disorientation.", "medium", 9, 9, 9, 5, 7, 7, 8),
    ("theodosia-burr", "A Vice President's Daughter Vanished at Sea", "She boarded a ship in 1813 and was never seen again.", "disappearances", "FACT: Theodosia Burr Alston lost at sea 1813; fate THEORY.", "medium", 7, 8, 7, 6, 7, 5, 8),
    ("ninth-legion", "A Roman Legion of 5,000 Men Disappeared From History", "Rome's 9th Legion marched north and stopped existing.", "disappearances", "THEORY: Legio IX Hispana's fate debated; 'lost in Britain' is popular but contested by historians.", "medium", 9, 9, 9, 7, 6, 7, 8),
    ("bennington-triangle", "People Kept Vanishing on the Same Mountain", "Several disappeared on Glastenbury — some never found.", "disappearances", "FACT: real 1940s Vermont disappearances; 'triangle' link is THEORY/folklore.", "medium", 8, 8, 8, 6, 7, 6, 8),
    ("benjamin-bathurst", "A Diplomat Walked Around His Horses and Vanished", "He stepped behind a coach in 1809 and was gone.", "disappearances", "FACT/THEORY: Bathurst disappeared 1809; details embellished over time.", "low", 9, 8, 9, 5, 6, 5, 8),
    ("bobby-dunbar", "A 'Found' Missing Boy Wasn't Who Everyone Thought", "DNA a century later revealed the wrong child grew up in his place.", "disappearances", "FACT: 1912 case; 2004 DNA showed misidentification.", "high", 8, 9, 8, 5, 9, 5, 7),

    # ---------------- Impossible Artifacts ----------------
    ("antikythera-mechanism", "A 2,000-Year-Old Computer Found in a Shipwreck", "Ancient Greeks built a gear computer we couldn't match for 1,000 years.", "impossible-artifacts", "FACT: Antikythera mechanism, ~2nd c. BCE analog computer; function reconstructed.", "high", 10, 9, 10, 9, 10, 9, 9),
    ("voynich-manuscript", "A Book No One Has Ever Been Able to Read", "600 years old, fully illustrated, in a language that doesn't exist.", "impossible-artifacts", "FACT: Voynich manuscript undeciphered; carbon-dated ~15th c.", "high", 10, 10, 10, 9, 9, 9, 9),
    ("roman-dodecahedra", "Romans Made These and We Still Don't Know Why", "Hundreds of bronze objects, zero written explanation.", "impossible-artifacts", "FACT: Roman dodecahedra exist; purpose unknown (THEORY).", "high", 9, 10, 9, 9, 9, 7, 9),
    ("baghdad-battery", "A 2,000-Year-Old Jar That Looks Like a Battery", "Did ancient people have electricity?", "impossible-artifacts", "FACT: the artifacts exist; the 'battery' function is THEORY and widely doubted.", "medium", 9, 9, 9, 8, 6, 8, 8),
    ("phaistos-disc", "A Clay Disc Stamped With Symbols No One Can Decode", "The world's first 'typed' document is still unreadable.", "impossible-artifacts", "FACT: Phaistos Disc undeciphered; authenticity occasionally questioned (note).", "medium", 8, 9, 8, 8, 7, 6, 8),
    ("nebra-sky-disc", "The Oldest Map of the Sky Ever Found", "A Bronze Age disc showing real stars, 3,600 years old.", "impossible-artifacts", "FACT: Nebra sky disc, ~Bronze Age; dating debated by some but broadly accepted.", "medium", 8, 8, 8, 9, 8, 6, 8),
    ("piri-reis-map", "A 1513 Map That Seems to Show Too Much", "A 500-year-old map drawn with strange accuracy.", "impossible-artifacts", "FACT: Piri Reis map real, 1513; 'shows Antarctica' claims are THEORY/overstated.", "medium", 8, 8, 8, 8, 6, 7, 8),
    ("lycurgus-cup", "A Roman Cup That Changes Color Like Nanotech", "1,600 years ago, Romans used nanoparticles in glass.", "impossible-artifacts", "FACT: Lycurgus Cup uses colloidal gold/silver nanoparticles; dichroic effect real.", "high", 9, 8, 9, 9, 9, 6, 8),
    ("iron-pillar-delhi", "A 1,600-Year-Old Iron Pillar That Won't Rust", "Open-air iron that refuses to corrode.", "impossible-artifacts", "FACT: Iron Pillar of Delhi; corrosion resistance explained by passive film.", "high", 8, 7, 8, 8, 9, 6, 7),
    ("ulfberht-swords", "Viking Swords Made of Steel Too Advanced for Their Time", "Crucible steel that shouldn't have existed in Europe yet.", "impossible-artifacts", "FACT: +VLFBERH+T swords used high-purity crucible steel; sourcing debated (THEORY).", "high", 9, 8, 9, 8, 8, 6, 8),
    ("costa-rica-spheres", "Hundreds of Perfect Stone Balls in the Jungle", "Who carved them, and why nearly perfect spheres?", "impossible-artifacts", "FACT: Diquis spheres real; makers known (Diquis), exact purpose THEORY.", "high", 8, 8, 8, 9, 8, 6, 7),
    ("maine-penny", "A Viking Coin Found in Native American Ruins", "An 11th-century Norse coin, thousands of miles from home.", "impossible-artifacts", "FACT: Maine penny is a genuine Norse coin; how it arrived is THEORY (trade vs. hoax).", "medium", 8, 9, 8, 6, 7, 5, 7),
    ("saqqara-bird", "An Ancient Egyptian Object Shaped Like a Plane", "Did Egyptians understand flight?", "impossible-artifacts", "FACT: artifact exists; 'glider' interpretation is THEORY, rejected by most experts.", "low", 8, 8, 8, 7, 5, 7, 7),
    ("shroud-of-turin", "The Cloth That Science Still Argues About", "A faint image no one can fully explain.", "impossible-artifacts", "CONTESTED: 1988 C-14 dated it medieval; debates continue. Frame as disputed, not proof.", "medium", 8, 9, 8, 7, 6, 9, 7),

    # ---------------- Ancient Engineering ----------------
    ("roman-concrete", "Roman Concrete Heals Itself — Ours Crumbles", "2,000-year-old harbors are still standing.", "ancient-engineering", "FACT: Roman concrete's longevity and self-healing (lime clasts) studied/published.", "high", 9, 8, 9, 8, 9, 8, 8),
    ("greek-fire", "A Weapon That Burned on Water and We Lost the Recipe", "The formula was so secret it died with the empire.", "ancient-engineering", "FACT: Greek fire real Byzantine weapon; exact recipe lost (THEORY on composition).", "high", 10, 9, 10, 8, 8, 8, 8),
    ("derinkuyu", "A City for 20,000 People Hidden Underground", "An entire town carved beneath the earth.", "ancient-engineering", "FACT: Derinkuyu underground city, Cappadocia; capacity estimates vary.", "high", 9, 8, 9, 9, 9, 7, 8),
    ("qanat-systems", "Ancient Tunnels That Carried Water Across Deserts", "Persians moved water 50 miles underground by hand.", "ancient-engineering", "FACT: qanat/karez systems, millennia old, still used.", "high", 7, 6, 7, 8, 9, 6, 7),
    ("nan-madol", "A Stone City Built on a Coral Reef in the Pacific", "Massive basalt 'logs' stacked in the ocean.", "ancient-engineering", "FACT: Nan Madol real; how stones were moved is THEORY.", "high", 9, 9, 9, 9, 8, 6, 7),
    ("heron-aeolipile", "Ancient Greeks Built a Steam Engine — for Fun", "A working steam device, 1,700 years before the Industrial Revolution.", "ancient-engineering", "FACT: Hero of Alexandria's aeolipile and devices described in his works.", "high", 9, 7, 9, 7, 8, 6, 8),
    ("saksaywaman", "Stones So Tight You Can't Fit a Blade Between Them", "Giant boulders fitted without mortar.", "ancient-engineering", "FACT: Inca ashlar masonry at Saksaywaman; techniques partly understood.", "high", 8, 8, 8, 9, 8, 6, 7),
    ("pantheon-dome", "The Largest Concrete Dome Stood for 1,900 Years", "Unreinforced concrete that still holds the record.", "ancient-engineering", "FACT: Pantheon's dome is the largest unreinforced concrete dome.", "high", 7, 6, 7, 9, 9, 7, 7),
    ("baiae-underwater", "A Roman Resort Town Sank Beneath the Sea", "Marble villas now sit on the seafloor.", "ancient-engineering", "FACT: Baiae partly submerged by volcanic bradyseism; underwater park exists.", "high", 8, 7, 8, 9, 8, 6, 7),
    ("stepwells-india", "Upside-Down Temples Dug Hundreds of Feet Down", "Stairways descending into the earth for water.", "ancient-engineering", "FACT: Indian stepwells (e.g., Chand Baori) real and ancient.", "high", 8, 7, 8, 9, 9, 6, 7),
    ("pharos-alexandria", "A 100m Lighthouse Stood for 1,600 Years", "One of the Seven Wonders guided ships with fire and mirrors.", "ancient-engineering", "FACT: Lighthouse of Alexandria real; exact height/mirror details THEORY.", "high", 7, 7, 7, 8, 8, 7, 7),
    ("archimedes-claw", "A Giant Claw That Lifted Roman Ships Out of the Water", "Archimedes built a war machine that flipped warships.", "ancient-engineering", "FACT/THEORY: Claw of Archimedes described by ancient sources; tested as plausible.", "medium", 9, 8, 9, 7, 7, 6, 7),
    ("puma-punku", "Stone Blocks Cut Like They Were Machined", "Precise H-blocks that puzzle engineers.", "ancient-engineering", "FACT: Puma Punku real Tiwanaku site; 'machined' framing exaggerated — note carefully.", "medium", 8, 8, 8, 9, 7, 6, 7),

    # ---------------- Humans That Sound Made Up ----------------
    ("tarrare", "A Man Who Could Eat Almost Anything and Never Get Full", "He ate live animals, corks, and a whole meal for 15.", "made-up-humans", "FACT/THEORY: Tarrare documented by military surgeons; some accounts likely exaggerated.", "medium", 10, 9, 10, 6, 7, 7, 8),
    ("wojtek-bear", "A Bear Was an Official Soldier in WWII", "He carried artillery shells and had a rank.", "made-up-humans", "FACT: Wojtek enlisted in the Polish II Corps; carried supplies.", "high", 10, 8, 10, 8, 9, 8, 8),
    ("emperor-norton", "A Broke Man Declared Himself Emperor — and a City Played Along", "San Francisco printed his money and obeyed his decrees.", "made-up-humans", "FACT: Joshua Norton, 'Emperor of the United States', 1859-1880.", "high", 9, 8, 9, 7, 9, 6, 8),
    ("jack-churchill", "He Fought WWII With a Longbow and a Sword", "'Mad Jack' brought a claymore to a world war.", "made-up-humans", "FACT: Jack Churchill carried bow and sword; one longbow kill attested.", "high", 10, 7, 10, 7, 8, 7, 8),
    ("hugh-glass", "Mauled by a Bear and Left for Dead, He Crawled 200 Miles", "Half-dead, he dragged himself across the wilderness for revenge.", "made-up-humans", "FACT/THEORY: Glass's 1823 ordeal real; distance/details embellished over time.", "medium", 9, 8, 9, 7, 7, 8, 8),
    ("rasputin", "The Man Who Was Poisoned, Shot, and Still Wouldn't Die", "His murder reads like a horror movie.", "made-up-humans", "FACT/THEORY: Rasputin killed 1916; the 'unkillable' details are partly legend.", "medium", 10, 8, 10, 7, 7, 9, 8),
    ("ching-shih", "A Pirate Queen Who Commanded 80,000 Men", "She ran the largest pirate fleet in history — and retired rich.", "made-up-humans", "FACT: Zheng Yi Sao / Ching Shih led a vast Chinese pirate confederation.", "high", 9, 8, 9, 7, 8, 7, 8),
    ("incitatus", "A Roman Emperor Tried to Make His Horse a Senator", "Caligula gave his horse a house and servants.", "made-up-humans", "THEORY: Incitatus 'consul' story from hostile sources; likely satire/exaggeration — frame as claim.", "medium", 9, 8, 9, 6, 6, 8, 7),
    ("juan-pujol-garbo", "A Spy Who Tricked the Nazis With a Fake Army", "He invented agents who never existed and won medals from both sides.", "made-up-humans", "FACT: Juan Pujol Garcia ('Garbo'), double agent, D-Day deception.", "high", 9, 8, 9, 6, 9, 6, 8),
    ("daniel-lambert", "A Man So Beloved People Paid Just to Meet Him", "Britain's gentle giant became a folk hero.", "made-up-humans", "FACT: Daniel Lambert, early 1800s; treat with dignity.", "medium", 6, 6, 6, 6, 8, 4, 7),
    ("peter-wild-boy", "A Feral Boy Was Raised in a Royal Court", "A child found in the woods became a king's pet curiosity.", "made-up-humans", "FACT/THEORY: Peter the Wild Boy real; modern view: likely Pitt-Hopkins syndrome.", "medium", 8, 8, 8, 6, 7, 5, 7),
    ("william-buckland", "A Scientist Who Tried to Eat Every Animal on Earth", "He claimed to have eaten a king's preserved heart.", "made-up-humans", "FACT/THEORY: Buckland's 'zoophagy' attested; the royal-heart anecdote is traditional.", "medium", 9, 7, 9, 6, 7, 5, 7),
    ("old-tom-orca", "Killer Whales That Teamed Up With Human Whalers", "Orcas herded whales to hunters — for a share of the kill.", "made-up-humans", "FACT: 'Law of the Tongue' at Eden, Australia; Old Tom's skeleton displayed.", "high", 9, 8, 9, 7, 8, 6, 7),
    ("saint-guinefort", "A Dog Was Worshipped as a Saint", "Medieval villagers prayed to a greyhound.", "made-up-humans", "FACT: cult of Saint Guinefort recorded by Inquisitor Stephen of Bourbon.", "medium", 9, 8, 9, 6, 7, 6, 7),
    ("collyer-brothers", "Two Brothers Buried Alive in Their Own Hoard", "Booby-trapped tunnels of junk filled their mansion.", "made-up-humans", "FACT: Collyer brothers, 1947; ~140 tons removed.", "high", 8, 8, 8, 6, 8, 5, 7),

    # ---------------- Forgotten Disasters ----------------
    ("dancing-plague-1518", "In 1518, a Town Danced Itself to Death", "Hundreds danced for days — some until they died.", "forgotten-disasters", "FACT: Dancing Plague of 1518 in city records; cause THEORY (ergot vs mass hysteria).", "high", 10, 9, 9, 8, 9, 8, 8),
    ("boston-molasses-flood", "A Wave of Molasses Killed 21 People", "A 25-foot wall of syrup tore through Boston at 35 mph.", "forgotten-disasters", "FACT: 1919 Boston Molasses Flood; 21 dead, tank failure.", "high", 10, 8, 10, 7, 9, 7, 8),
    ("lake-nyos", "A Lake Exploded and Suffocated a Whole Valley", "1,700 people died in their sleep from an invisible cloud.", "forgotten-disasters", "FACT: 1986 Lake Nyos limnic eruption; CO2 release.", "high", 10, 9, 10, 7, 9, 6, 8),
    ("tunguska-event", "Something Flattened 800 Square Miles of Forest", "An explosion 1,000x Hiroshima — with no crater.", "forgotten-disasters", "FACT: 1908 Tunguska event; airburst THEORY (most accepted).", "high", 10, 9, 10, 8, 9, 8, 8),
    ("london-beer-flood", "A Tidal Wave of Beer Drowned People in London", "A burst vat sent 1 million litres into the streets.", "forgotten-disasters", "FACT: 1814 London Beer Flood; 8 dead.", "high", 10, 8, 10, 6, 8, 6, 8),
    ("tambora-1815", "A Volcano Caused a Year Without Summer", "1816 had snow in June and crops failed worldwide.", "forgotten-disasters", "FACT: 1815 Mt Tambora eruption; 1816 'Year Without a Summer'.", "high", 9, 8, 9, 8, 9, 7, 8),
    ("halifax-explosion", "The Biggest Man-Made Blast Before the Atom Bomb", "A ship collision leveled a city in 1917.", "forgotten-disasters", "FACT: 1917 Halifax Explosion; ~2,000 dead.", "high", 9, 7, 9, 8, 9, 7, 8),
    ("great-smog-1952", "A Fog So Toxic It Killed Thousands in Days", "London's air turned deadly and nobody could see.", "forgotten-disasters", "FACT: 1952 Great Smog of London; thousands of excess deaths.", "high", 8, 7, 8, 7, 9, 7, 8),
    ("tri-state-tornado", "The Deadliest Tornado Stayed on the Ground for 3 Hours", "One twister crossed three states and killed 695.", "forgotten-disasters", "FACT: 1925 Tri-State Tornado; deadliest in US history.", "high", 9, 7, 9, 7, 9, 7, 8),
    ("peshtigo-fire", "The Deadliest Fire in US History Was Forgotten", "It killed more than the Great Chicago Fire — the same night.", "forgotten-disasters", "FACT: 1871 Peshtigo Fire; overshadowed by Chicago.", "high", 9, 8, 9, 6, 9, 6, 8),
    ("banqiao-dam", "A Dam Failure That May Have Killed 170,000", "Cascading dam collapses erased entire towns.", "forgotten-disasters", "FACT/THEORY: 1975 Banqiao failure; death toll estimates vary widely.", "medium", 9, 8, 9, 6, 8, 6, 8),
    ("sultana-explosion", "America's Worst Maritime Disaster Was Buried in the News", "1,200 died — but it happened the week Lincoln was killed.", "forgotten-disasters", "FACT: 1865 Sultana explosion; overshadowed by Lincoln assassination.", "high", 9, 8, 9, 6, 9, 6, 8),
    ("laki-1783", "A Volcano in Iceland Helped Starve Europe", "An eruption poisoned skies and crops across a continent.", "forgotten-disasters", "FACT/THEORY: 1783 Laki eruption; downstream famine/death links partly modeled.", "medium", 8, 8, 8, 7, 8, 5, 8),
    ("cocoanut-grove-fire", "A Nightclub Fire That Changed Safety Laws Forever", "492 died in minutes behind locked exits.", "forgotten-disasters", "FACT: 1942 Cocoanut Grove fire; led to safety reforms.", "high", 8, 6, 8, 6, 9, 6, 7),
    ("aberfan-disaster", "A Mountain of Coal Waste Buried a School", "144 died, most of them children, in seconds.", "forgotten-disasters", "FACT: 1966 Aberfan disaster; colliery spoil tip collapse.", "high", 8, 6, 8, 6, 9, 6, 7),

    # ---------------- Strange Medical History ----------------
    ("radium-girls", "Factory Workers Painted With Glowing Poison", "They licked radioactive brushes — and their bones rotted.", "medical-history", "FACT: Radium Girls, 1910s-20s; landmark labor/health case.", "high", 10, 8, 10, 7, 9, 8, 8),
    ("phineas-gage", "A Man Survived an Iron Rod Through His Brain", "A 3-foot spike shot through his skull — and he walked away.", "medical-history", "FACT: Phineas Gage, 1848; personality-change claims partly THEORY.", "high", 10, 9, 10, 7, 9, 8, 8),
    ("leonid-rogozov", "A Doctor Removed His Own Appendix in Antarctica", "Stranded and dying, he operated on himself.", "medical-history", "FACT: Rogozov self-appendectomy, 1961.", "high", 10, 7, 10, 6, 9, 6, 8),
    ("semmelweis", "The Doctor Mocked for Saying 'Wash Your Hands'", "He cut deaths by 90% — and was driven to an asylum.", "medical-history", "FACT: Ignaz Semmelweis, handwashing, 1840s; rejected in his time.", "high", 9, 8, 9, 6, 9, 7, 8),
    ("eben-byers", "A Man Drank Radioactive 'Health Water' Until His Jaw Fell Off", "The miracle tonic was slowly killing him.", "medical-history", "FACT: Eben Byers, Radithor, died 1932.", "high", 10, 8, 10, 6, 9, 6, 8),
    ("trepanation", "People Drilled Holes in Skulls 7,000 Years Ago — and Survived", "Healed bone shows many patients lived.", "medical-history", "FACT: trepanation is one of the oldest surgeries; survival shown by bone healing.", "high", 9, 8, 9, 7, 9, 6, 8),
    ("walter-freeman-lobotomy", "A Doctor Performed Brain Surgery With an Ice Pick", "He did thousands, sometimes in minutes, through the eye.", "medical-history", "FACT: Walter Freeman's transorbital lobotomy.", "high", 9, 8, 9, 6, 9, 6, 8),
    ("patient-hm", "A Man Who Couldn't Make New Memories for 50 Years", "Surgery erased his ability to remember anything new.", "medical-history", "FACT: Henry Molaison (H.M.); foundational memory neuroscience.", "high", 8, 8, 8, 5, 9, 6, 8),
    ("clive-wearing", "A Man Whose Memory Lasts Only Seconds", "Every moment, he believes he just woke up.", "medical-history", "FACT: Clive Wearing, amnesia after encephalitis.", "high", 9, 8, 9, 5, 9, 6, 8),
    ("tobacco-enema", "Doctors Once Blew Smoke Up People's Backsides to Save Them", "It's where the phrase comes from — literally.", "medical-history", "FACT: tobacco smoke enemas used for resuscitation, 18th c.", "high", 9, 7, 9, 6, 8, 6, 8),
    ("corpse-medicine", "Europeans Once Ate Mummies as Medicine", "Ground-up human remains were sold as a cure.", "medical-history", "FACT: 'mummia'/corpse medicine well documented in early modern Europe.", "high", 9, 8, 9, 6, 8, 6, 8),
    ("washington-bloodletting", "Doctors May Have Bled a President to Death", "They drained ~40% of his blood trying to cure a sore throat.", "medical-history", "FACT/THEORY: Washington's 1799 treatment; bloodletting's role in death is debated.", "medium", 9, 8, 9, 5, 8, 7, 7),
    ("john-snow-cholera", "One Doctor Stopped an Epidemic by Removing a Pump Handle", "He mapped the deaths and traced them to a single well.", "medical-history", "FACT: John Snow, Broad Street pump, 1854; birth of epidemiology.", "high", 8, 7, 8, 7, 9, 7, 7),
    ("safety-coffins", "People Were So Afraid of Being Buried Alive They Built Escape Coffins", "Bells, air tubes, and 'I'm alive' flags for the dead.", "medical-history", "FACT: safety coffins patented in the 18th-19th c. amid premature-burial fears.", "high", 9, 8, 9, 7, 8, 6, 7),

    # ---------------- Lost Expeditions ----------------
    ("franklin-expedition", "129 Men Sailed Into the Arctic and Were Never Seen Alive Again", "Two ships, frozen in, slowly vanished.", "lost-expeditions", "FACT: Franklin's 1845 expedition lost; ships found 2014/2016; details still THEORY.", "high", 10, 10, 10, 8, 9, 8, 9),
    ("dyatlov-pass", "Nine Hikers Fled Their Tent Into the Snow and Died", "They cut their way out half-dressed in -25C — no one knows why.", "lost-expeditions", "FACT: 1959 Dyatlov Pass deaths real; cause THEORY (avalanche model recent, still debated).", "high", 10, 10, 10, 7, 8, 9, 9),
    ("andree-balloon", "Three Men Tried to Reach the North Pole by Balloon", "Their fate was a mystery for 33 years — until their camera was found.", "lost-expeditions", "FACT: S.A. Andree's 1897 balloon expedition; remains/film found 1930.", "high", 9, 9, 9, 8, 9, 6, 8),
    ("mallory-irvine", "Did Two Climbers Reach Everest 29 Years Before Hillary?", "One body was found in 1999 — the other, and the camera, are still missing.", "lost-expeditions", "FACT: Mallory & Irvine vanished 1924; summit question unresolved (THEORY).", "high", 9, 10, 9, 8, 8, 8, 8),
    ("donner-party", "A Wagon Train Trapped in the Snow Faced the Unthinkable", "Stranded for months, survivors did what they had to.", "lost-expeditions", "FACT: Donner Party, 1846-47; cannibalism attested by survivors.", "high", 9, 8, 9, 6, 9, 7, 8),
    ("the-karluk", "A Ship Crushed by Ice Left Its Crew on the Frozen Sea", "They walked across the ice as their ship sank.", "lost-expeditions", "FACT: Karluk disaster, 1913-16; survival story documented.", "high", 8, 8, 8, 7, 9, 5, 8),
    ("greely-expedition", "An Arctic Mission Ended in Starvation and Whispered Horrors", "Of 25 men, 6 came home — and questions followed.", "lost-expeditions", "FACT/THEORY: Greely expedition 1881-84; cannibalism allegations contested.", "medium", 8, 9, 8, 6, 7, 5, 8),
    ("la-perouse", "A French Expedition Vanished and Took Decades to Find", "Two ships sailed the Pacific and simply stopped reporting.", "lost-expeditions", "FACT: La Perouse expedition lost ~1788; wrecks later found at Vanikoro.", "high", 8, 8, 8, 7, 8, 5, 8),
    ("burke-and-wills", "They Crossed a Continent, Then Died Waiting at the Finish Line", "Rescue missed them by hours.", "lost-expeditions", "FACT: Burke and Wills, 1860-61 Australia.", "high", 8, 8, 8, 7, 9, 6, 8),
    ("henry-hudson-mutiny", "An Explorer Was Set Adrift by His Own Crew and Vanished", "His men put him in a small boat and sailed home.", "lost-expeditions", "FACT: Hudson cast adrift 1611; fate unknown.", "high", 8, 9, 8, 7, 8, 6, 8),
    ("shackleton-endurance", "A Ship Was Crushed by Ice and Everyone Still Survived", "Shackleton's open-boat journey is almost unbelievable.", "lost-expeditions", "FACT: Endurance 1914-17; all survived; wreck found 2022.", "high", 9, 7, 9, 9, 10, 8, 8),
    ("narvaez-expedition", "A 600-Man Expedition Ended With 4 Survivors Walking Across a Continent", "Eight years lost in the Americas.", "lost-expeditions", "FACT: Narvaez expedition 1527; Cabeza de Vaca's account survives.", "high", 8, 8, 8, 6, 8, 5, 8),
    ("darien-scheme", "A Disaster That Bankrupted an Entire Nation", "Scotland gambled its fortune on a colony and lost everything.", "lost-expeditions", "FACT: Darien scheme, 1690s; contributed to the 1707 Union.", "high", 8, 8, 8, 6, 9, 5, 8),
    ("amundsen-disappearance", "The Man Who Conquered the Poles Vanished on a Rescue", "He flew off to save a rival and was never found.", "lost-expeditions", "FACT: Amundsen disappeared 1928 during an Arctic rescue flight.", "high", 8, 8, 8, 6, 9, 7, 8),
]


def build() -> dict:
    counts: dict[str, int] = {}
    topics = []
    for (slug, title, hook, series_id, note, conf,
         h, m, sh, v, c, se, ser) in TOPICS:
        counts[series_id] = counts.get(series_id, 0) + 1
        total = 3 * h + 2 * m + 2 * sh + 2 * v + 2 * c + se + ser
        topics.append({
            "slug": slug,
            "title": title,
            "hook": hook,
            "category": series_id,
            "series_id": series_id,
            "series_name": SERIES[series_id],
            "episode_number": counts[series_id],
            "fact_theory_note": note,
            "source_confidence": conf,
            "scores": {
                "hook": h, "mystery": m, "shareability": sh, "visual": v,
                "credibility": c, "search": se, "series": ser, "total": total,
            },
            "shorts_eligible": v >= 7 and c >= 6 and total >= 85,
        })
    topics.sort(key=lambda t: -t["scores"]["total"])
    return {
        "_doc": "Pre-scored evergreen topic inventory. Built by build_topic_bank.py — edit TOPICS there and re-run, don't hand-edit this file. Weighted total = 3*hook+2*mystery+2*share+2*visual+2*cred+search+series (max 130). Greenlight >=85; cred<6 -> graveyard; visual<7 -> long-form only. Grow this toward 300-500 via the CONTENT_ENGINE sourcing funnel; every entry must be a REAL event (no padding).",
        "series": SERIES,
        "count": len(topics),
        "topics": topics,
    }


if __name__ == "__main__":
    out = Path(__file__).with_name("topic_bank.json")
    out.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {out} with {len(build()['topics'])} topics")
