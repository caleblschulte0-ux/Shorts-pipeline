"""WHAT THE VOICE IS HANDED — every word spelled the way a person says it.

Operator, 2026-10-08: *"whatever you feeding to the TTS needs to be in word
format everything and anything it could mis read or will read in a way that
sound unnatural"*. The explainer spelled out plain digits, dollars and
percents, and handed everything else to the engine as written: "km²",
"242 mph", "900°F", "1990s", "21st", "5x", "9/11", "S&P", "US" (read "us"),
"ONE MILLION" (read letter by letter), "29147", "8,776‑sq‑mi". This module is
the one place that turns written narration into SPOKEN narration.

  `shorthand(text)` — the trending renderer's normaliser, moved here
      verbatim ($3B, 350M, 25%, $650-900B). Trending times its captions and
      its shot cues from a transcript of the audio, which comes back in
      digits, so trending keeps reading digits to the engine.
  `say(text)` — everything: shorthand, then units, symbols, ranges,
      decades, ordinals, fractions, acronyms and finally every number as
      words. Captions keep the digits; only the audio is spelled.

`tests/test_the_voice_reads_words.py` runs every line in the queue through
`say` and fails on anything a voice could misread.
"""
from __future__ import annotations

import re


def shorthand(text: str) -> str:
    """Rewrite numeric shorthand so Kokoro/edge-tts pronounce it the way
    a human would read it aloud.

    Kokoro reads "$3B" as "dollar three bee" and "25%" as "twenty five
    percent sign". Fix by expanding the symbols before the engine sees
    them. Phrase-matching (find_phrase_start) runs the same normaliser
    so triggers stay aligned with the spoken transcript.

      $3B / $1.5B / $650-900B  -> N billion dollars (preserves "to" in ranges)
      $559M / $30.9M           -> N million dollars
      $1T / $1.05T             -> N trillion dollars
      $15,000 / $559           -> N dollars
      350M (no $)              -> 350 million
      25% / 130 percent        -> N percent (already-spelled passthrough)
    """
    s = text
    # Dollar ranges with B/M/T suffix: "$650-900B" -> "650 to 900 billion dollars"
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*[Bb]\b",
               r"\1 to \2 billion dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*[Mm]\b",
               r"\1 to \2 million dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*[Tt]\b",
               r"\1 to \2 trillion dollars", s)
    # Single-value dollar amounts with B/M/K/T suffix.
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Bb]\b", r"\1 billion dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Mm]\b", r"\1 million dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Tt]\b", r"\1 trillion dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Kk]\b", r"\1 thousand dollars", s)
    # Dollar with WRITTEN-OUT unit: "$10.9 billion" -> "10.9 billion dollars".
    # Must run BEFORE bare "$NUM" so the unit stays inside the substitution.
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s+(billion|million|trillion|thousand|hundred)\b",
               r"\1 \2 dollars", s, flags=re.I)
    # Plain "$NUM" -> "NUM dollars" (after the suffixed forms have run).
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)", r"\1 dollars", s)
    # Percent symbol.
    s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", s)
    # Bare abbreviations after a number (no $). Lookahead avoids breaking
    # acronyms like "AMD" or words starting with B/M/K/T.
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*B\b(?![A-Za-z])", r"\1 billion", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*M\b(?![A-Za-z])", r"\1 million", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*T\b(?![A-Za-z])", r"\1 trillion", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*K\b(?![A-Za-z])", r"\1 thousand", s)
    return s


# ---------------------------------------------------------------------------
# Numbers as words
# ---------------------------------------------------------------------------
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
        "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
        "eighty", "ninety"]
_SCALES = ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"),
           (1000, "thousand"))


def card(n: int) -> str:
    """A whole number as words: 29147 -> "twenty nine thousand one hundred
    forty seven"."""
    if n < 0:
        return "minus " + card(-n)
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        r = n % 100
        return ONES[n // 100] + " hundred" + (" " + card(r) if r else "")
    for size, name in _SCALES:
        if n >= size:
            r = n % size
            return card(n // size) + " " + name + (" " + card(r) if r else "")
    return str(n)                                   # unreachable


def year(n: int) -> str:
    """1816 -> "eighteen sixteen", 2005 -> "two thousand five", 1900 ->
    "nineteen hundred"."""
    if 2000 <= n <= 2009:
        return "two thousand" + (" " + ONES[n % 10] if n % 10 else "")
    hi, lo = n // 100, n % 100
    if lo == 0:
        return card(hi) + " hundred"
    if lo < 10:
        return card(hi) + " oh " + ONES[lo]
    return card(hi) + " " + card(lo)


def number(s: str) -> str:
    """A written number (commas, a decimal point) as cardinal words — never
    a year. '1,920' -> 'one thousand nine hundred twenty', '0.74' -> 'zero
    point seven four'."""
    s = s.replace(",", "")
    if "." in s:
        whole, frac = s.split(".", 1)
        return (card(int(whole or 0)) + " point "
                + " ".join(ONES[int(d)] for d in frac if d.isdigit()))
    return card(int(s))


_ORD_IRREG = {"one": "first", "two": "second", "three": "third",
              "five": "fifth", "eight": "eighth", "nine": "ninth",
              "twelve": "twelfth"}


def ordinal(n: int) -> str:
    """21 -> "twenty first"."""
    words = card(n).split()
    last = words[-1]
    if last in _ORD_IRREG:
        last = _ORD_IRREG[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return " ".join(words[:-1] + [last])


def _plural(words: str) -> str:
    """'nineteen ninety' -> 'nineteen nineties', 'two thousand' -> 'two
    thousands', 'twenty ten' -> 'twenty tens'."""
    if words.endswith("y"):
        return words[:-1] + "ies"
    return words + "s"


# ---------------------------------------------------------------------------
# Units, symbols, acronyms
# ---------------------------------------------------------------------------
#: A unit written after a number, as it is said. Longest first, so "km²"
#: is not read as "km" then "²". Only ever AFTER a number: "mi" alone is a
#: word fragment, "5 mi" is five miles.
_UNITS = [
    (r"km²|km2|sq[.\s\-‑]*km|square km", "square kilometers"),
    (r"mi²|sq[.\s\-‑]*mi|square mi", "square miles"),
    (r"m²|sq[.\s\-‑]*m", "square meters"),
    (r"sq[.\s\-‑]*ft|ft²", "square feet"),
    (r"km/h|kph|km per hour", "kilometers per hour"),
    (r"mph", "miles per hour"),
    (r"m/s", "meters per second"),
    (r"kWh", "kilowatt hours"), (r"MWh", "megawatt hours"),
    (r"GWh", "gigawatt hours"), (r"TWh", "terawatt hours"),
    (r"GHz", "gigahertz"), (r"MHz", "megahertz"),
    (r"kW", "kilowatts"), (r"MW", "megawatts"), (r"GW", "gigawatts"),
    (r"TW", "terawatts"),
    (r"km", "kilometers"), (r"cm", "centimeters"), (r"mm", "millimeters"),
    (r"kg", "kilograms"), (r"mg", "milligrams"), (r"µg|mcg", "micrograms"),
    (r"lbs?", "pounds"), (r"oz", "ounces"), (r"ft", "feet"), (r"mi", "miles"),
    (r"mL|ml", "milliliters"), (r"ppm", "parts per million"),
    (r"ppb", "parts per billion"), (r"Gt", "gigatonnes"),
    (r"Mt", "megatonnes"), (r"hrs?", "hours"), (r"mins?", "minutes"),
    (r"yrs?", "years"), (r"PSI|psi", "P S I"), (r"TEU", "T E U"),
    (r"°C|º C|° C", "degrees Celsius"), (r"°F|º F|° F", "degrees Fahrenheit"),
    (r"°", "degrees"),
]
_NUM = r"\d[\d,]*(?:\.\d+)?"
_UNIT_RX = [(re.compile(rf"({_NUM}|\b(?:million|billion|thousand|trillion))"
                        rf"[\s\-‑]*(?:{pat})(?![A-Za-z0-9²])"), said)
            for pat, said in _UNITS]

#: Names and formulas that no rule reads right.
_NAMED = [(r"\bCO2e\b", "C O two equivalent"), (r"\b[Cc][Oo]2\b", "C O two"),
          (r"\b[Cc][Hh]4\b", "C H four"), (r"\bN2O\b", "N two O"),
          (r"\bH2O\b", "H two O"), (r"\bPM2\.5\b", "P M two point five"),
          (r"\b3I/ATLAS\b", "three I Atlas"), (r"\bF1\b", "F one")]

#: What, said after a 4-digit number, makes it a count and not a year.
_COUNTED = (r"(thousand|million|billion|trillion|percent|times|people|"
            r"dollars|euros|pounds|yen|tons|tonnes|units|"
            + "|".join(sorted({w.split()[-1] for _, w in _UNITS})) + r")\b")

_FRACTIONS = {"1/2": "one half", "1/3": "one third", "2/3": "two thirds",
              "1/4": "one quarter", "3/4": "three quarters",
              "1/5": "one fifth", "1/10": "one tenth", "24/7": "twenty four seven",
              "9/11": "nine eleven"}

#: Acronyms a person says as a WORD. Everything else short and in capitals
#: is said letter by letter ("US" is "U S", never "us").
_SAID_AS_WORD = {"NASA", "NOAA", "COVID", "SIDS", "NATO", "AIDS", "RAND",
                 "UNESCO", "UNICEF", "OPEC", "FEMA", "NAFTA", "ASEAN", "SARS",
                 "MERS", "FIFA", "LEGO", "OSHA", "MRSA", "SWAT", "SCUBA",
                 "LASER", "RADAR", "ZIP", "GIF", "ISIS", "WIFI", "SONAR"}
#: Short capitalised words that are EMPHASIS, not acronyms: "ONE MILLION",
#: "YOUR heart". Said as the word.
_EMPHASIS = {"ONE", "TWO", "SIX", "TEN", "ALL", "YOU", "YOUR", "FULL", "NOT",
             "NO", "NOW", "THIS", "THAT", "BIG", "HUGE", "ONLY", "JUST",
             "REAL", "TRUE", "DEAD", "GONE", "MOST", "BEST", "AND", "OR",
             "THE", "IS", "ARE", "WAS", "IT", "IN", "ON", "OF", "TO", "WHY",
             "HOW", "WHAT", "EVEN", "HALF", "ZERO", "MORE", "LESS", "EVER",
             "LAST", "NEW", "OLD", "BUT", "DID", "CAN", "WILL", "STOP",
             "EACH", "SAME", "VERY", "FAST", "OVER", "UP", "DOWN", "OUT",
             "OFF", "BACK", "YES", "WOW", "OMG", "WAY", "DAY", "DAYS", "YEAR",
             "LIFE", "TIME", "FREE", "SO", "TOO", "ALSO", "MUCH", "MANY",
             "WE", "OUR", "THEY", "HE", "SHE", "HIS", "HER", "ITS", "BE",
             "AT", "AS", "BY", "FOR", "IF", "AN", "A", "I"}


def _acronym(m: re.Match) -> str:
    tok, tail = m.group(1), m.group(2) or ""
    if tok in _SAID_AS_WORD:
        return tok.capitalize() + tail
    if tok in _EMPHASIS or (len(tok) >= 5 and re.search(r"[AEIOUY]", tok)):
        return tok.lower() + tail
    letters = " ".join(tok)
    return letters + ("'s" if tail == "s" else tail)


def say(text: str) -> str:
    """The narration as the voice should hear it: no digit, no symbol, no
    abbreviation left for an engine to guess at."""
    s = str(text or "")
    # one hyphen, one minus, one times sign
    s = s.replace("‑", "-").replace("‐", "-").replace("−", "-")
    s = s.replace(" ", " ").replace(" ", " ")
    s = re.sub(r"(\d[\d,.]*\s*%?)\+", r"more than \1", s)
    for rx, said in _NAMED:
        s = re.sub(rx, said, s)
    s = re.sub(r"(?<=[A-Z])/(?=[A-Z])", " ", s)          # AM/FM
    s = shorthand(s)
    s = re.sub(r"€\s?(" + _NUM + r")", r"\1 euros", s)
    s = re.sub(r"£\s?(" + _NUM + r")", r"\1 pounds", s)
    s = re.sub(r"¥\s?(" + _NUM + r")", r"\1 yen", s)
    s = re.sub(r"\b(" + _NUM + r")\s?(?:x|×)(?![A-Za-z0-9])", r"\1 times", s)
    s = re.sub(r"(?:x|×)\s?(" + _NUM + r")\b", r"times \1", s) \
        if re.search(r"(?<![A-Za-z])[x×]\s?\d", s) else s
    s = re.sub(r"~\s?(?=\d)", "about ", s)
    s = re.sub(r"#\s?(\d)", r"number \1", s)
    for frac, said in _FRACTIONS.items():
        s = re.sub(rf"(?<![\d/]){re.escape(frac)}(?![\d/])", said, s)
    s = re.sub(r"(?<![\d/])(\d+)/(\d+)(?![\d/])", r"\1 out of \2", s)
    for rx, said in _UNIT_RX:
        s = rx.sub(lambda m, said=said: m.group(1) + " " + said, s)
    s = re.sub(r"(?<=[A-Za-z])/(?=[A-Za-z])", " per ", s) \
        if re.search(r"\b(?:dollars|kilograms|people)/", s) else s
    s = s.replace("&", " and ").replace("@", " at ")
    s = re.sub(r"\bvs\.?(?=\s)", "versus", s)
    s = re.sub(r"\be\.g\.", "for example", s)
    s = re.sub(r"\bi\.e\.", "that is", s)
    s = re.sub(r"\bapprox\.", "about", s)
    s = re.sub(r"\betc\.", "and so on", s)
    # a range between two numbers: "2010-2020", "10–20" (a word after the
    # hyphen, "11-year", stays a compound)
    s = re.sub(rf"({_NUM})\s?[-–—]\s?(?={_NUM}(?![\d,]*[-‑]?[A-Za-z]))",
               r"\1 to ", s)
    # decades: 1990s, '90s, 2000s
    s = re.sub(r"\b(1[5-9]\d0|20[0-9]0)['’]?s\b",
               lambda m: _plural(year(int(m.group(1)))), s)
    s = re.sub(r"['’](\d)0s\b", lambda m: _plural(TENS[int(m.group(1))]), s)
    # ordinals: 1st, 22nd, 3rd, 19th
    s = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b",
               lambda m: ordinal(int(m.group(1))), s)
    # negatives: a minus at a word start
    s = re.sub(r"(?<![\w\d])-(?=\d)", "minus ", s)
    # acronyms and shouting (letters only; a single capital is a word)
    s = re.sub(r"\b([A-Z]{2,})(s?)\b", _acronym, s)
    # letters run into digits: "CO2" -> "C O 2", "G5" -> "G 5"
    s = re.sub(r"\b([A-Z]+)(\d+)\b",
               lambda m: " ".join(m.group(1)) + " " + m.group(2), s)

    # numbers last: a bare 1900-2099 is a year, unless what follows says it
    # is a count ("2000 billion galaxies", "1900 dollars", "2050 kilometers")
    def _n(m):
        raw = m.group(0)
        after = s[m.end():m.end() + 24].lstrip().lower()
        if (re.fullmatch(r"1[1-9]\d\d|20\d\d", raw)
                and not re.match(_COUNTED, after)):
            return year(int(raw))
        return number(raw)
    s = re.sub(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?<=\d)", _n, s)
    s = s.replace("%", " percent").replace("$", " dollars")
    return re.sub(r"[ \t]+", " ", s).strip()
