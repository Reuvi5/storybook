"""
Everything about the story itself: the prompts and the pages.

The prompts here are fixed. Users can't see or edit them.

To add a page later (page 4: the beanstalk at dawn), add one more entry to PAGES.
Nothing else in the app needs to change.
"""

# ---------------------------------------------------------------------------
# Step 1: the real photo -> Jack's character design (used as the cover too).
# ---------------------------------------------------------------------------
CHARACTER_PROMPT = """Style: Modern 3D animated feature — rounded forms, large expressive eyes, soft rim light.

Create the official character design for an animated film, based on the child in the attached photo. This character is Jack, from "Jack and the Beanstalk".

FACE AND BODY: Jack must be instantly recognizable as this exact child: identical face shape, eye shape and color, eyebrows, nose, mouth, ears, skin tone, freckles or marks, hair color, hair length, hairstyle and hair part. Keep his age and body proportions as in the photo. Stylize him into the art style, but never change who he is.

OUTFIT: a loose cream-colored linen shirt with rolled sleeves, a brown wool vest, dark brown knee-length trousers, and worn brown leather boots. Do not use the clothes from the photo.

POSE AND LAYOUT: one single view of Jack from the knees up, standing and facing the viewer, arms relaxed, with a gentle, neutral, friendly expression. His face is large and fills the upper part of the image, so every facial detail is clear. Even, soft front lighting. Plain light grey background.

Only Jack: no other characters, no props, no scenery. Do not draw any text, letters, labels or captions."""

# ---------------------------------------------------------------------------
# Step 2: sent with EVERY page, word for word, together with Jack's character image.
# ---------------------------------------------------------------------------
SHARED_PROMPT = """Style: Modern 3D animated feature — rounded forms, large expressive eyes, soft rim light.

REFERENCE IMAGE: The attached image is the official character design of Jack. Jack on this page must be this exact character, as if the same 3D character model were placed into the scene: identical face shape, eyes, eyebrows, nose, mouth, skin tone, hair color, hairstyle, body proportions and outfit. Do not redesign, reinterpret, age up, or "improve" his face. Only change his pose, expression and camera angle to fit the scene. Do not copy the grey background or the standing pose from the reference.

JACK'S MOTHER (never changes): a kind, slender woman in her thirties with chestnut-brown hair tied back in a low bun, wearing a long faded blue dress with a cream apron.

MILKY-WHITE (never changes): a gentle brown-and-white dairy cow with a white face and a brown patch over one eye.

Jack's face must always be clearly visible, well lit, and large enough to recognize. Never show him tiny, far away, in silhouette, or with his face hidden.

Do not draw any text, letters, words, captions or speech bubbles anywhere in the image."""

# ---------------------------------------------------------------------------
# The pages, in book order.
#   text       - the story text, drawn onto the page in the PDF (never by the image model)
#   text_area  - where the text goes: "top" or "bottom" (the area each scene keeps quiet)
#   theme      - "light" (dark text on a light panel) or "dark" (light text on a dark panel)
# ---------------------------------------------------------------------------
PAGES = [
    {
        "number": 1,
        "title": "The empty cupboard",
        "text": "Jack and his mother had nothing left to sell but Milky-White.",
        "text_area": "bottom",
        "theme": "light",
        "scene": """Scene: Jack and his mother stand in a bare cottage kitchen with an empty cupboard. His mother looks worried because they have no food left and must sell the cow; Jack's expression is calm and neutral. Through the open door behind them, Milky-White is happily eating grass outside. Show a large part of the cottage interior with cozy cottage items (a wooden table, a cold hearth, hanging pots), but keep the focus on Jack, his mother, and the cow. Jack faces the viewer with his full face front-lit, looking at his mother. Jack fills a large part of the frame.

Composition: keep the lower third of the image quiet and uncluttered (plain wooden floor) so text can be placed there later.""",
    },
    {
        "number": 2,
        "title": "The trade",
        "text": "Five magic beans, said the old man. For one cow.",
        "text_area": "top",
        "theme": "light",
        "scene": """Scene: On a winding dirt road to the market, lined with grass and a few wildflowers, Jack meets a strange old man with a long grey beard, a patched green cloak, and a twinkle in his eye. The old man holds out his open palm toward Jack, showing exactly five beans, no more and no fewer, each a different bright color (blue, green purple, red, yellow) and spaced apart so each is visible. Jack holds a rope tied to Milky-White, who stands calmly beside him. Jack is in three-quarter view, turned only slightly so both eyes and his whole face are clearly visible, smiles as he is tempted. Jack is in the foreground and large in the frame.

Composition: the top third of the image is open, calm sky with only soft, simple clouds and no trees, birds or objects, so text can be placed there later. Keep Jack, the old man, the cow and the beans in the lower two-thirds.""",
    },
    {
        "number": 3,
        "title": "Out the window",
        "text": "Beans! she cried. And out the window they went.",
        "text_area": "bottom",
        "theme": "dark",
        "scene": """Scene: The same small thatched cottage, seen from outside at dusk. The sky is deep orange and purple, and warm candlelight glows in the windows. Jack's mother leans out of an open window and casually tosses a handful of mainly brown beans but the colorful beans clearly noticeable BRIGHT blue, green purple, red, yellow beans mixed in away with an easy, offhand flick of her wrist, as if they don't matter. Her expression is calm and unbothered, with a small resigned sigh, not angry. The beans scatter lightly through the air and fall into the garden below. Jack stands in the open cottage doorway in the background, farther from the viewer as the focus is on the mother, his face large, clearly visible and lit warmly by the light from inside, watching the beans fall with a quiet, surprised expression. Use a darker evening palette than a daytime scene, but keep Jack's face bright and recognizable. There should be no cow in the scene.

Composition: the lower third of the image is dark, plain grass in shadow, quiet and uncluttered, so light-colored text can be placed there later.""",
    },
    # Page 4 (the beanstalk at dawn) goes here when it's ready.
]

PAGE_BY_NUMBER = {p["number"]: p for p in PAGES}

BOOK_TITLE = "Jack and the Beanstalk"


def page_prompt(page: dict) -> str:
    """The full prompt for one page: the shared block, then that page's scene."""
    return f"{SHARED_PROMPT}\n\n{page['scene']}"
