"""
The two stories, the character bible, and the 20-page template they share.

Nothing here is editable by users.

How a book is made (see generator.py):
  1. Ahead of time, once per story: each character in the bible gets a reference image, and
     each of the 20 scenes is drawn with a generic stand-in hero. These are the "scene plates".
  2. Per book: the uploaded photo -> the hero (in that story's outfit), then the hero is
     swapped into all 20 scene plates at the same time.

Every page has:
  text  - the words printed on the page (never drawn by the image model)
  zone  - where the scene keeps clear space for the text: "top", "middle" or "bottom"
          (the app checks every image and moves the text if that area turns out to be busy)
  cast  - which bible characters appear, besides the hero
  scene - what the picture shows
"""

STYLE = "Style: Modern 3D animated feature film. Rounded forms, large expressive eyes, soft rim light, warm storybook colors."

# Said on every image that copies a face, so "match the face exactly" is never read as "make it look real".
CARTOON_ONLY = (
    "ART STYLE (most important): a stylized 3D animated cartoon, exactly like the rest of the book. Large, "
    "simplified cartoon eyes with big irises and soft highlights; smooth, simplified skin with no pores or "
    "texture; softly rounded features; simple cartoon teeth. NOT photorealistic: never realistic eyes, "
    "realistic skin, realistic teeth or a real-photo look."
)

NO_TEXT = "Do not draw any text, letters, words, numbers, captions or speech bubbles anywhere in the image."

ZONE_RULES = {
    "top": "COMPOSITION: keep the top third of the image calm and empty (plain sky, plain wall or ceiling) with no faces, characters or important objects in it, so words can be printed there. Keep every character and the action in the lower two-thirds.",
    "bottom": "COMPOSITION: keep the bottom third of the image calm and empty (plain ground, floor, grass or path) with no faces, characters or important objects in it, so words can be printed there. Keep every character and the action in the upper two-thirds.",
    "middle": "COMPOSITION: keep a horizontal band across the middle of the image calm and empty (open sky or a soft bank of cloud) with no faces, characters or important objects in it, so words can be printed there.",
}

HERO_RULES = (
    "THE HERO: the hero's face is always clearly visible, front-lit and large enough to recognize "
    "(at least one-tenth of the image height). Never draw the hero tiny, far away, in silhouette, "
    "from behind, or with the face covered or in shadow."
)

# ---------------------------------------------------------------------------
# The two stories
# ---------------------------------------------------------------------------
STORIES = {}

STORIES["jack"] = {
    "id": "jack",
    "title": "Jack and the Beanstalk",
    "hero_name": "Jack",
    "hero_outfit": "a loose cream-colored linen shirt with rolled sleeves, a brown wool vest, dark brown knee-length trousers, and worn brown leather boots",
    "standin": "a friendly, slim young person with short brown hair (age left neutral so any real person can be swapped in)",
    # The character bible: everyone except the hero. Each gets one reference image.
    "bible": {
        "mother": "Jack's mother: a warm, hard-working farm mom with a kind face, chestnut-brown hair pinned up in a simple bun, wearing a plain long-sleeved faded blue work dress that reaches her ankles, a cream apron, and brown shoes.",
        "cow": "Milky-White: a gentle dairy cow, white all over with one large brown patch around her left eye and a small brown patch on her back, pink nose, short curved horns, and a brass bell on a leather collar.",
        "old_man": "The old man: small and stooped, with a long grey beard, bushy eyebrows, a twinkle in his eye, a patched green hooded cloak and a crooked walking stick.",
        "giant": "The giant: enormous, broad and shaggy, with a wild red beard, a big bald head, a bulbous nose, thick eyebrows, a brown leather tunic with a wide belt, and huge bare feet. Grumpy and loud, more funny than frightening.",
        "giants_wife": "The giant's wife: a very tall, round, kind-faced woman with grey hair in a bun, rosy cheeks, a mustard-yellow dress and a white apron.",
        "hen": "The magic hen: a plump little reddish-brown hen with a bright red comb and shining golden flecks in her feathers.",
        "harp": "The golden harp: a small golden harp whose top is carved into a woman's face with closed eyes, which opens her eyes and sings.",
    },
    # If OpenAI's safety filter blocks a character sheet, these plainer wordings of the SAME look are
    # tried next (the filter rejected every wording of the mother that mentioned "mother"/"mom").
    # Last resort: make the sheet FROM a scene that already passed (page number, who to copy).
    "sheet_from_scene": {
        "mother": (2, "the woman with chestnut-brown hair in a bun, the long faded blue dress and the cream apron"),
    },
    "sheet_alternatives": {
        "mother": [
            "A kind village woman with a gentle smile, chestnut-brown hair pinned up in a simple bun, wearing a plain long-sleeved faded blue dress that reaches her ankles, a cream apron, and brown shoes.",
            "A friendly storybook farm woman in a long blue dress and a cream apron, brown hair in a bun, brown shoes, smiling.",
        ],
    },
    "pages": [
        {"text": "Once upon a time, Jack and his mother lived in a tiny cottage. They were so poor that all they had left was their cow, Milky-White.",
         "zone": "bottom", "cast": ["mother", "cow"],
         "scene": "Outside a small, run-down thatched cottage on a sunny morning. Jack stands by the gate with his mother, both looking at Milky-White, who grazes in front of them. Jack and his mother face the viewer in three-quarter view."},
        {"text": "\"There is nothing for it,\" said his mother. \"Take Milky-White to market, and sell her for a good price.\"",
         "zone": "top", "cast": ["mother", "cow"],
         "scene": "Inside the bare cottage kitchen: an empty cupboard, a cold hearth, one wooden table. Jack's mother, sad and worried, hands Jack a rope tied to Milky-White, who stands at the open door. Jack looks up at her, determined."},
        {"text": "So Jack set off down the long road, leading Milky-White behind him.",
         "zone": "top", "cast": ["cow"],
         "scene": "A winding dirt road through green hills and wildflowers. Jack walks toward the viewer, cheerful, holding the rope; Milky-White follows just behind him."},
        {"text": "Before long he met a strange old man. \"Good morning, Jack,\" said the old man. \"Where are you off to?\"",
         "zone": "top", "cast": ["cow", "old_man"],
         "scene": "The same road beside an old stone wall. The old man steps out from behind a tree and tips his head at Jack. Jack, holding Milky-White's rope, turns toward him, curious. Jack in the foreground, larger than the old man."},
        {"text": "The old man opened his hand. \"Five magic beans,\" he whispered, \"for your cow. Plant them tonight, and by morning they will reach the sky.\"",
         "zone": "top", "cast": ["cow", "old_man"],
         "scene": "Close up of Jack and the old man on the road. The old man holds out his open palm toward Jack. In his palm are exactly five magic beans, no more and no fewer, spaced apart so each is visible: plump bean-shaped seeds (clearly beans, with a small seam, not candy or gems), each a different shimmering jewel color (emerald green, sapphire blue, ruby red, amethyst purple and gold), covered in tiny golden speckles and giving off a soft magical glow and a few sparkles. Jack leans in, amazed, the glow lighting his face. Milky-White's head is beside Jack."},
        {"text": "Jack could not resist. He traded Milky-White for the beans and ran all the way home.",
         "zone": "top", "cast": ["cow", "old_man"],
         "scene": "On the road: Jack runs toward the viewer, grinning, holding up his open hand with the five glowing, jewel-colored magic beans in it. Behind him, smaller, the old man leads Milky-White away down the road."},
        {"text": "\"Five beans? For our cow?\" sighed his mother. \"They're only ordinary beans, Jack.\" And she tossed them out of the window.",
         "zone": "bottom", "cast": ["mother"],
         "scene": "Inside the cottage kitchen at dusk. Jack's mother, tired and unimpressed but not angry, casually tosses the five beans over her shoulder out of the open window with a careless flick of her wrist, rolling her eyes with a small sigh, as if throwing away ordinary old beans. The five beans glow faintly in jewel colors as they fly out into the orange evening sky. Jack stands next to her, shocked, reaching toward the window. Warm candlelight inside."},
        {"text": "Jack was sent to bed without any supper. He looked out at the moon and wondered if he had been very foolish.",
         "zone": "top", "cast": [],
         "scene": "Jack's small attic bedroom at night. Jack sits on the edge of a simple wooden bed, chin in his hands, gloomy, lit by soft blue moonlight from a small window and a candle beside him."},
        {"text": "But in the morning, where the beans had landed, a giant beanstalk had grown, up, up, up, into the clouds.",
         "zone": "middle", "cast": [],
         "scene": "Morning outside the cottage. Jack stands in the garden in the lower part of the image, looking up in wonder with his face toward the viewer. Beside him a gigantic twisting green beanstalk with huge leaves rises straight up, past a band of soft white cloud across the middle of the image, and continues up to the top."},
        {"text": "Jack began to climb. He climbed and he climbed, higher than the birds, until he reached the sky.",
         "zone": "bottom", "cast": [],
         "scene": "Jack climbing the beanstalk high in the sky, seen from slightly above, his face turned up toward the viewer, smiling and determined. Huge leaves around him, small birds flying far below, and his tiny cottage and fields far, far below at the bottom of the image under a thin layer of mist."},
        {"text": "At the top was a road made of clouds, and at the end of the road stood an enormous castle.",
         "zone": "top", "cast": [],
         "scene": "Above the clouds: Jack steps off the top of the beanstalk onto a road of white clouds, in the foreground, seen in three-quarter view, gazing at an enormous grey stone castle in the distance."},
        {"text": "A giant woman opened the door. \"Hurry, little one,\" she whispered. \"My husband eats boys for breakfast! Hide!\"",
         "zone": "top", "cast": ["giants_wife"],
         "scene": "At the enormous castle door, which is many times taller than Jack. The giant's wife bends down kindly toward Jack, a finger to her lips. Jack looks up at her, startled. Both faces are visible."},
        {"text": "BOOM! BOOM! BOOM! In stomped the giant. \"Fee-fi-fo-fum!\" he roared. \"I smell a boy, I'm sure of one!\"",
         "zone": "top", "cast": ["giant", "giants_wife"],
         "scene": "The giant's huge kitchen. The giant stomps in through a doorway on the right, sniffing the air. In the foreground on the left, Jack is hidden INSIDE an enormous copper cooking pot on the floor: only his head, from the eyes up to his hair plus his hands gripping the rim, peeks over the edge. His eyes and upper face are clearly visible, wide with fear; the rest of him is out of sight inside the pot. The giant has not seen him. The giant's wife stands at the stove looking nervous."},
        {"text": "After dinner, the giant counted his gold and fell fast asleep. Jack grabbed a bag of gold and raced back down the beanstalk.",
         "zone": "top", "cast": ["giant"],
         "scene": "The giant snores in a huge wooden chair, slumped on the right, with gold coins spilled on the table. In the foreground Jack tiptoes away hugging a bag of gold coins, looking back at the viewer with a grin."},
        {"text": "Jack climbed up again. This time he found the giant's hen, which laid an egg of solid gold whenever the giant said, \"Lay!\"",
         "zone": "bottom", "cast": ["giant", "hen"],
         "scene": "The giant's kitchen table, enormous. The hen sits on the table beside a shining golden egg; the giant, seated behind, points at it, delighted. Jack is crouched behind an enormous loaf of bread on the table, completely hidden from the giant: only one side of his head peeks out around the loaf, toward the viewer, so his eyes and face are visible to the reader but not to the giant, who is looking at the hen."},
        {"text": "Then Jack saw a golden harp that sang all by itself. He picked it up, but the harp called out, \"Master! Master!\"",
         "zone": "top", "cast": ["harp", "giant"],
         "scene": "Jack holds the golden harp in both arms, facing the viewer with a surprised, alarmed expression; the harp's carved face is singing loudly. Behind him in the background, the giant is just waking up in his chair."},
        {"text": "The giant woke with a roar and thundered after Jack. Jack ran as fast as his legs could carry him.",
         "zone": "top", "cast": ["giant", "harp"],
         "scene": "On the cloud road: Jack sprints toward the viewer holding the harp, with an excited, frightened face. Far behind him, the giant chases, arms outstretched, smaller in the distance. The top of the beanstalk is in front of Jack."},
        {"text": "\"Mother! Mother! Bring the axe!\" shouted Jack, sliding down the beanstalk.",
         "zone": "top", "cast": ["mother", "harp"],
         "scene": "Lower part of the beanstalk near the ground. Jack slides down a thick stem toward the viewer, shouting, with the harp under one arm. Below, his mother runs out of the cottage holding a woodcutter's axe. Jack's face clearly visible."},
        {"text": "Jack chopped and chopped. Down came the beanstalk with a mighty CRASH, and the giant was never seen again.",
         "zone": "top", "cast": ["mother"],
         "scene": "In the garden: Jack has just swung the axe, the beanstalk is toppling sideways with leaves flying, and a big cloud of dust rises. His mother stands beside him, hands on her cheeks. Jack faces the viewer in three-quarter view, triumphant. No giant is shown."},
        {"text": "With the hen's golden eggs, Jack bought back Milky-White. And Jack, his mother, and Milky-White lived happily ever after.",
         "zone": "bottom", "cast": ["mother", "cow", "hen", "harp"],
         "scene": "A sunny garden in front of the now-repaired cottage, with flowers. Jack hugs Milky-White, smiling at the viewer. His mother laughs beside them, holding a basket of golden eggs, the hen at her feet, and the harp sits on a bench nearby."},
    ],
}

STORIES["red"] = {
    "id": "red",
    "title": "Little Red Riding Hood",
    "hero_name": "Little Red Riding Hood",
    "hero_outfit": "a bright red hooded cape tied at the neck, with the hood down so the face and hair are fully visible, over a cream linen shirt, brown trousers, and brown leather boots",
    "standin": "a friendly young girl of about ten with shoulder-length brown hair",
    "bible": {
        "mother": "The mother: a cheerful woman in her thirties with dark curly hair tied back, a green dress and a white apron.",
        "grandmother": "Grandmother: a small, sweet old woman with white hair in a bun, round gold glasses, a lilac nightgown and a white frilly nightcap.",
        "wolf": "The wolf: a tall, skinny grey wolf with a long snout, yellow eyes, big pointed ears and a sly grin. Mischievous, more comic than scary. Walks on all fours.",
        "woodcutter": "The woodcutter: a big, gentle man with a short brown beard, a red-and-black checked shirt, brown trousers, and an axe over his shoulder.",
        "basket": "The basket: a woven wicker basket with a handle, covered by a red-and-white checked cloth, with a loaf of bread and a jar of honey peeking out. Just the basket on its own: no person, no hands, no character holding it.",
    },
    "pages": [
        {"text": "Once upon a time there was someone who always wore a bright red hooded cape, so everyone called them Little Red Riding Hood.",
         "zone": "bottom", "cast": [],
         "scene": "A pretty village street with timbered houses and flower boxes on a sunny morning. The hero stands in the middle of the street in the red cape, smiling and facing the viewer."},
        {"text": "One morning, Mother packed a basket. \"Grandmother is sick,\" she said. \"Take her this bread and honey. And stay on the path!\"",
         "zone": "top", "cast": ["mother", "basket"],
         "scene": "A cozy cottage kitchen. Mother hands the basket to the hero, wagging a finger in warning. The hero takes the basket, nodding. Both faces visible."},
        {"text": "Off went Little Red Riding Hood, along the path and into the deep green woods.",
         "zone": "top", "cast": ["basket"],
         "scene": "A dirt path leading into a sunlit forest of tall trees, ferns and flowers. The hero walks toward the viewer along the path, swinging the basket, happy."},
        {"text": "From behind a tree stepped a wolf. \"Good morning, little one,\" he said with a toothy smile.",
         "zone": "top", "cast": ["wolf", "basket"],
         "scene": "The forest path. The wolf leans out from behind a thick tree trunk on the right with a sly grin. The hero, on the left in the foreground with the basket, looks at the wolf, surprised but not scared."},
        {"text": "\"Where are you going?\" asked the wolf. \"To Grandmother's house, past the three big oak trees,\" said Little Red Riding Hood.",
         "zone": "top", "cast": ["wolf", "basket"],
         "scene": "The forest path. The wolf walks beside the hero, leaning in as if friendly, ears up, listening carefully. The hero points ahead down the path, chatting. The hero is in the foreground."},
        {"text": "\"What a lovely day,\" said the wolf. \"Why not pick some flowers for your grandmother?\"",
         "zone": "top", "cast": ["wolf", "basket"],
         "scene": "A sunny clearing full of colorful wildflowers just off the path. The wolf sweeps a paw toward the flowers. The hero looks at the flowers, delighted."},
        {"text": "So Little Red Riding Hood left the path to pick flowers, and the wolf slipped quietly away.",
         "zone": "top", "cast": ["wolf", "basket"],
         "scene": "In the flower clearing: the hero kneels in the foreground picking flowers, smiling, the basket beside them. In the background, small, the wolf sneaks off between the trees."},
        {"text": "The wolf ran straight to Grandmother's cottage, as fast as he could go.",
         "zone": "bottom", "cast": ["wolf"],
         "scene": "A cottage with a red door and roses at the edge of the forest. The wolf races toward it along a path, ears back, grinning. No other characters. The hero does not appear on this page."},
        {"text": "Knock, knock. \"Who is it?\" called Grandmother. \"It's me, Little Red Riding Hood,\" said the wolf, in his sweetest voice.",
         "zone": "bottom", "cast": ["wolf"],
         "scene": "Close up of the cottage's red front door. The wolf stands on his hind legs, knocking with one paw and holding the other paw to his mouth, putting on a sweet voice. The hero does not appear on this page."},
        {"text": "When Grandmother saw the wolf, she jumped out of bed and hid in the wardrobe.",
         "zone": "top", "cast": ["wolf", "grandmother"],
         "scene": "Inside Grandmother's bedroom. Grandmother, startled, slips into a tall wooden wardrobe and pulls the door almost closed, peeking out. The wolf stands in the bedroom doorway. The hero does not appear on this page."},
        {"text": "Then the wolf put on Grandmother's nightcap and glasses, climbed into her bed, and waited.",
         "zone": "top", "cast": ["wolf"],
         "scene": "Grandmother's bedroom. The wolf lies in the bed with the blanket pulled up, wearing Grandmother's frilly nightcap and round glasses, grinning. The hero does not appear on this page."},
        {"text": "Soon Little Red Riding Hood arrived with the basket and the flowers. The door was standing open.",
         "zone": "top", "cast": ["basket"],
         "scene": "Outside the cottage with the red door, which stands slightly open. The hero stands on the doorstep holding the basket and a bunch of flowers, looking at the open door, puzzled."},
        {"text": "\"Oh, Grandmother, what big ears you have!\" \"All the better to hear you with, my dear.\"",
         "zone": "top", "cast": ["wolf", "basket"],
         "scene": "Grandmother's bedroom. The wolf in nightcap and glasses lies in bed on the right, his big ears poking out of the cap. The hero stands by the bed on the left, looking at the ears, unsure. Both faces visible."},
        {"text": "\"Oh, Grandmother, what big eyes you have!\" \"All the better to see you with, my dear.\"",
         "zone": "top", "cast": ["wolf", "basket"],
         "scene": "Closer view of the same bedroom. The wolf in the bed peers over his glasses with big yellow eyes. The hero leans back a little, suspicious, in the foreground."},
        {"text": "\"Oh, Grandmother, what big teeth you have!\" \"All the better to EAT you with!\" cried the wolf, and he leaped out of bed.",
         "zone": "top", "cast": ["wolf"],
         "scene": "The bedroom. The wolf springs out of the bed with the nightcap flying off, mouth open in a comic snarl. The hero jumps backward in the foreground, frightened, the basket falling. Comic, not gory."},
        {"text": "\"Help! Help!\" shouted Little Red Riding Hood, running around and around the room.",
         "zone": "top", "cast": ["wolf"],
         "scene": "The bedroom in chaos: the hero runs toward the viewer, shouting, cape flying; the wolf chases behind, tripping over the blanket. A chair is knocked over."},
        {"text": "A woodcutter passing by heard the shouts. He burst through the door, and the wolf took one look at him and fled.",
         "zone": "top", "cast": ["woodcutter", "wolf"],
         "scene": "The bedroom door bursts open and the woodcutter stands in it, tall and brave. The wolf leaps out of an open window on the other side, tail between his legs. The hero stands in the foreground, relieved, facing the viewer."},
        {"text": "Out of the wardrobe stepped Grandmother, safe and sound. \"My brave dear,\" she said, and hugged Little Red Riding Hood tight.",
         "zone": "top", "cast": ["grandmother", "woodcutter"],
         "scene": "The bedroom. Grandmother steps out of the wardrobe and hugs the hero. The hero's face is toward the viewer, eyes closed with relief. The woodcutter smiles in the background."},
        {"text": "The wolf ran deep into the forest, and he was never seen in those woods again.",
         "zone": "bottom", "cast": ["wolf"],
         "scene": "The forest seen from the cottage window at sunset: the wolf, small in the distance, runs off over a hill into the trees, looking back nervously. The hero leans out of the window in the foreground, watching, smiling, face fully visible."},
        {"text": "Then they all sat down to bread, honey and tea. And Little Red Riding Hood never strayed from the path again.",
         "zone": "top", "cast": ["grandmother", "woodcutter", "mother", "basket"],
         "scene": "Grandmother's cozy table by the fire. Grandmother, Mother, the woodcutter and the hero share bread, honey and tea, laughing. The hero sits in the front, facing the viewer, smiling."},
    ],
}

PAGE_COUNT = 20
for _story in STORIES.values():
    assert len(_story["pages"]) == PAGE_COUNT, _story["id"]
    for _i, _p in enumerate(_story["pages"], 1):
        _p["number"] = _i
        assert _p["zone"] in ZONE_RULES
        for _c in _p["cast"]:
            assert _c in _story["bible"], (_story["id"], _i, _c)


def get_story(story_id: str) -> dict:
    return STORIES[story_id]


def hero_appears(page: dict) -> bool:
    return "does not appear on this page" not in page["scene"]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
OBJECTS = {"basket"}  # bible entries that are things, not characters


def sheet_from_scene_prompt(s: dict, key: str) -> str:
    who = s["sheet_from_scene"][key][1]
    return (
        f"{STYLE}\n\nImage 1 is a finished illustration from the picture book \"{s['title']}\". Make a character "
        f"design sheet of {who} from image 1: exactly the same face, hair, clothes and colors. One single full-body "
        f"view, standing, facing the viewer, friendly expression, even soft lighting, plain light grey background. "
        f"Only this one character, nobody else from the scene. {NO_TEXT}"
    )


def bible_prompts(s: dict, key: str) -> list:
    """The character sheet prompt, then any fallback wordings (used only if the first is blocked)."""
    return [bible_prompt(s, key)] + [bible_prompt(s, key, alt) for alt in s.get("sheet_alternatives", {}).get(key, [])]


def bible_prompt(s: dict, key: str, description: str = None) -> str:
    """Reference image for one bible character (made once, ahead of time)."""
    description = description or s["bible"][key]
    if key in OBJECTS:
        return (
            f"{STYLE}\n\nProp design sheet for the animated film \"{s['title']}\". {description}\n\n"
            f"The object alone, centered, three-quarter view, even soft lighting, plain light grey background. "
            f"No people, no hands, no animals. {NO_TEXT}"
        )
    return (
        f"{STYLE}\n\nCharacter design sheet for the animated film \"{s['title']}\". "
        f"{description}\n\nOne single full-body view, standing, facing the viewer, even soft lighting, "
        f"plain light grey background. Only this one character. {NO_TEXT}"
    )


def standin_prompt(s: dict) -> str:
    return (
        f"{STYLE}\n\nCharacter design sheet for the hero of \"{s['title']}\": {s['standin']}, wearing "
        f"{s['hero_outfit']}. Knees-up view, standing, facing the viewer, friendly expression, plain light "
        f"grey background. Only this one character. {NO_TEXT}"
    )


def plate_prompt(s: dict, page: dict) -> str:
    """A scene drawn ahead of time with the stand-in hero. Reference images: stand-in, then the cast."""
    refs = ["Image 1 is the hero (the stand-in)."] if hero_appears(page) else []
    for i, key in enumerate(page["cast"], start=len(refs) + 1):
        refs.append(f"Image {i} is {s['bible'][key].split(':')[0]}.")
    looks = "\n".join(f"- {s['bible'][k]}" for k in page["cast"])
    return (
        f"{STYLE}\n\nAn illustration for page {page['number']} of the picture book \"{s['title']}\".\n\n"
        f"REFERENCE IMAGES: {' '.join(refs)} Every character must match their reference image exactly: "
        f"same face, colors, markings and clothes. Do not copy the grey backgrounds.\n"
        + (f"\nCHARACTERS ON THIS PAGE:\n{looks}\n" if looks else "")
        + f"\nSCENE: {page['scene']}\n\n"
        + (HERO_RULES + "\n\n" if hero_appears(page) else "")
        + f"{ZONE_RULES[page['zone']]}\n\n{NO_TEXT}"
    )


def hero_prompt(s: dict) -> str:
    """The uploaded photo -> this story's hero (also used on the cover)."""
    return (
        f"{STYLE}\n\nCreate the official character design for the hero of \"{s['title']}\", based on the person in the attached photo.\n\n"
        "FACE: the character must be instantly recognizable as this exact person: identical face shape, eye shape and color, "
        "eyebrows, nose, mouth, ears, skin tone, freckles or marks, hair color, hair length, hairstyle and hair part. "
        "Keep any head covering they wear, such as a kippah. Stylize into the art style, but never change who they are. "
        "Keep their real age: do not make them look younger or older.\n\n"
        f"OUTFIT: {s['hero_outfit']}. Do not use the clothes from the photo.\n\n"
        f"{CARTOON_ONLY} Turn the real person into a cartoon character; do not keep the photo's realism.\n\n"
        "POSE: one view from the knees up, standing, facing the viewer, arms relaxed, friendly expression. The face is large "
        f"and fills the upper part of the image. Even, soft front lighting. Plain light grey background. Only this one character. {NO_TEXT}"
    )


def swap_prompt(s: dict, page: dict) -> str:
    """Per book: put the user's hero into a pre-drawn scene. Image 1 = scene, image 2 = hero."""
    return (
        f"{STYLE}\n\n"
        "Image 1 is a finished picture-book illustration. Image 2 is the hero's official character design. "
        "Image 3 is a close-up of the hero's face from that design.\n\n"
        "Replace the hero in image 1 with the character from image 2: same hair, skin tone, any head covering, "
        "body proportions and outfit as image 2, in exactly the same position, pose, size, expression and lighting as "
        "the hero in image 1.\n\n"
        "THE FACE MUST MATCH IMAGE 3 EXACTLY, as if it were the same 3D character model: same face shape, eye shape "
        "and color, eyebrows, nose, mouth, ears, cheeks, freckles, hairline, hair color and curls, and the same apparent "
        "age. Do not redesign, simplify, age up or age down the face. It must stay clearly visible, front-lit and "
        "recognizable. Copy the face's SHAPES and FEATURES, drawn in the same cartoon style as image 2.\n\n"
        f"{CARTOON_ONLY}\n\n"
        "Change NOTHING else: keep every other character, the background, the colors, the composition and any empty areas "
        f"exactly as they are in image 1. {NO_TEXT}"
    )
