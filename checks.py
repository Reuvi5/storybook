"""
Checks what the user types before anything is drawn or printed.

  - The name must be a real-sounding name (any language or culture). Insults, slurs, epithets,
    swear words, joke or meme names and "test" entries are refused.
  - Nothing inappropriate for a children's book in any About Me field (profanity, sexual, violent,
    hateful, drug content, bullying), and no personal contact details (phone, email, street address,
    links): they would be printed in a book.

Three layers, cheapest first:
  1. Rules in code: allowed characters, length, word count, digits, contact-detail patterns, a small
     word list. Instant and free, and works even without an API key.
  2. OpenAI's moderation endpoint on every field (free).
  3. A short model check of the name and the details, which catches what lists can't
     ("Stinky Loser" is clean text but not a name).

Returns {field: message} for every problem; empty means everything passed.
"""

import json
import logging
import os
import re
import unicodedata

import ai

log = logging.getLogger("storybook.checks")

FIELDS = {"name": "Name", "age": "Age", "favorite_color": "Favorite color", "favorite_food": "Favorite food",
          "favorite_animal": "Favorite animal", "about": "About me"}

# A deliberately small list of obvious words; the moderation and model checks do the real work.
BLOCKED = {
    "idiot", "stupid", "dumb", "moron", "loser", "ugly", "fat", "retard", "retarded", "loser", "jerk", "freak",
    "poop", "poopy", "butt", "fart", "shit", "fuck", "bitch", "bastard", "damn", "hell", "ass", "crap", "dick",
    "penis", "vagina", "sex", "sexy", "kill", "killer", "murder", "nazi", "hitler", "drugs", "weed", "cocaine",
    "test", "asdf", "qwerty", "admin", "null", "undefined", "nobody", "anonymous",
}

PHONE = re.compile(r"(\+?\d[\d\s().-]{6,}\d)")
EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[a-z]{2,}", re.I)
LINK = re.compile(r"(https?://|www\.|\.(com|net|org|io|co)\b)", re.I)
STREET = re.compile(r"\b\d{1,5}\s+\w+(\s\w+)*\s+(st|street|ave|avenue|rd|road|blvd|lane|ln|dr|drive|way|ct|court)\b", re.I)


def _letters_only(name: str) -> bool:
    """Letters from any alphabet, plus spaces, hyphens, apostrophes and periods."""
    for ch in name:
        if ch in " -'.’":
            continue
        if not unicodedata.category(ch).startswith("L") and not unicodedata.category(ch).startswith("M"):
            return False
    return True


def _words(text: str) -> set:
    return set(re.findall(r"[a-z]+", text.lower()))


def rule_checks(values: dict) -> dict:
    problems = {}
    name = values.get("name", "").strip()
    if not name:
        problems["name"] = "Please enter the name."
    elif not _letters_only(name) or not re.search(r"\w", name):
        problems["name"] = "A name can only use letters, spaces, hyphens and apostrophes."
    elif len(name.split()) > 4:
        problems["name"] = "That's too many words for a name. Use the first name, or first and last."
    elif re.search(r"(.)\1\1\1", name.lower()) or len(re.sub(r"[^\w]", "", name)) < 2:
        problems["name"] = "That doesn't look like a real name."
    elif _words(name) & BLOCKED:
        problems["name"] = "Please use the child's real name. Nicknames that are insults or jokes can't be printed."

    age = values.get("age", "").strip()
    if age:
        m = re.fullmatch(r"(\d{1,3})(\s*(years?|yrs?)(\s*old)?)?", age.lower())
        if not m or not 1 <= int(m.group(1)) <= 120:
            problems["age"] = "Age should be a number, like 7."

    for key in ("favorite_color", "favorite_food", "favorite_animal", "about"):
        text = values.get(key, "").strip()
        if not text:
            continue
        if EMAIL.search(text) or LINK.search(text):
            problems[key] = "Please don't include email addresses or links: this gets printed in a book."
        elif PHONE.search(text):
            problems[key] = "Please don't include phone numbers or other long numbers: this gets printed in a book."
        elif STREET.search(text):
            problems[key] = "Please don't include a street address: this gets printed in a book."
        elif _words(text) & (BLOCKED - {"test", "admin", "null", "undefined", "nobody", "anonymous"}):
            problems[key] = "Please keep this suitable for a children's book."
    return problems


def moderation_checks(values: dict, meter=None) -> dict:
    keys = [k for k in FIELDS if values.get(k, "").strip()]
    if not keys:
        return {}
    resp = ai.client().moderations.create(model="omni-moderation-latest", input=[values[k] for k in keys])
    problems = {}
    for key, result in zip(keys, resp.results):
        if result.flagged:
            cats = [c for c, v in result.categories.model_dump().items() if v]
            log.info("moderation_flagged field=%s categories=%s", key, ",".join(cats))
            problems[key] = ("Please use the child's real name." if key == "name"
                             else "Please keep this suitable for a children's book.")
    return problems


MODEL_CHECK = """You check what a parent typed into a personalized children's picture book before it is printed.
The book is printed and mailed, so anything here will appear in a real book a child reads.

Name: {name!r}
Other details: {details}

Reply with JSON only:
{{
  "name_ok": true/false,   // a plausible real given name or common nickname, from any language or culture,
                           // optionally with a family name. FALSE for insults, slurs, epithets, swear words,
                           // body or toilet words, mocking or joke names ("Stinky", "Big Loser", "Mr Poopy Pants"),
                           // meme or troll names, keyboard mashing, "test" or placeholder text, or obviously not a person.
                           // Unusual or rare real names are fine.
  "name_reason": "short reason if false, else empty",
  "fields": {{"<field>": {{"ok": true/false, "reason": "short reason if false"}}}}
                           // for each detail: FALSE if it is inappropriate for a children's book (profanity, sexual,
                           // violent, hateful, drugs or alcohol, bullying or mocking the child) or gives contact
                           // details (phone, email, home address). Silly but harmless answers ("pizza", "dragons") are fine.
}}"""


def model_checks(values: dict, meter=None) -> dict:
    details = {k: values[k] for k in FIELDS if k != "name" and values.get(k, "").strip()}
    content = MODEL_CHECK.format(name=values.get("name", ""), details=json.dumps(details, ensure_ascii=False))
    kwargs = dict(model=ai.VISION_MODEL, messages=[{"role": "user", "content": content}],
                  response_format={"type": "json_object"})
    try:
        resp = ai.client().chat.completions.create(reasoning_effort="minimal", **kwargs)
    except Exception as e:  # noqa: BLE001
        if "reasoning" not in str(e).lower():
            raise
        resp = ai.client().chat.completions.create(**kwargs)
    if meter:
        u = resp.usage
        meter.add("analysis", (u.prompt_tokens * ai.PRICE["vision_in"] + u.completion_tokens * ai.PRICE["vision_out"]) / 1e6)
    r = json.loads(resp.choices[0].message.content)
    problems = {}
    if not r.get("name_ok", True):
        log.info("name_rejected reason=%s", r.get("name_reason", "")[:120])
        problems["name"] = "Please enter the child's real name. Insults, jokes and nicknames that make fun of someone can't be printed."
    for key, verdict in (r.get("fields") or {}).items():
        if key in FIELDS and isinstance(verdict, dict) and verdict.get("ok") is False:
            problems[key] = "Please keep this suitable for a children's book, and leave out contact details."
    return problems


def check_details(values: dict, meter=None) -> dict:
    """{field: problem}. Empty means OK to draw and print."""
    problems = rule_checks(values)
    if problems or ai.FAKE or not os.environ.get("OPENAI_API_KEY"):
        return problems
    try:
        problems.update(moderation_checks(values, meter))
        if not problems:
            problems.update(model_checks(values, meter))
    except Exception:  # noqa: BLE001 - if the checker is down, don't print unchecked text
        log.exception("details_check_failed")
        return {"name": "We couldn't check the details right now. Please try again in a minute."}
    return problems
