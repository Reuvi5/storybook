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
    "title_with_name": "{name} and the Beanstalk",
    "hero_name": "Jack",
    "default_pronoun": "they",
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
        {"text": "Once upon a time, {name} lived with Mother in a tiny cottage. They were so poor that all they had left was their cow, Milky-White.",
         "zone": "bottom", "cast": ["mother", "cow"],
         "scene": "Outside a small, run-down thatched cottage on a sunny morning. Jack, a slim child of about nine, stands by the gate with his mother; he is much shorter than her, the top of his head only reaching her shoulder, both looking at Milky-White, who grazes in front of them. Jack and his mother face the viewer in three-quarter view."},
        {"text": "\"We have no money left,\" said Mother sadly. \"Take Milky-White to market, and sell her for a good price.\"",
         "zone": "top", "cast": ["mother", "cow"],
         "scene": "Inside the bare cottage kitchen: an empty cupboard, a cold hearth, one wooden table. Jack's mother, sad and worried, hands Jack a rope tied to Milky-White, who stands at the open door. Jack looks up at her, determined."},
        {"text": "So {name} set off down the long road, leading Milky-White along.",
         "zone": "top", "cast": ["cow"],
         "scene": "A winding dirt road through green hills and wildflowers. Jack walks toward the viewer, cheerful, holding the rope; Milky-White follows just behind him."},
        {"text": "Before long, {name} met a strange old man. \"Good morning, {name},\" said the old man. \"Where are you off to?\"",
         "zone": "top", "cast": ["cow", "old_man"],
         "scene": "The same road beside an old stone wall. The old man steps out from behind a tree and tips his head at Jack. Jack, holding Milky-White's rope, turns toward him, curious. Jack in the foreground, larger than the old man."},
        {"text": "The old man opened his hand. \"Five magic beans,\" he whispered, \"for your cow. Plant them tonight, and by morning they will reach the sky.\"",
         "zone": "top", "cast": ["cow", "old_man"],
         "scene": "Close up of Jack and the old man on the road. The old man holds out his open palm toward Jack. In his palm are exactly five magic beans, no more and no fewer, spaced apart so each is visible: plump bean-shaped seeds (clearly beans, with a small seam, not candy or gems), each a different shimmering jewel color (emerald green, sapphire blue, ruby red, amethyst purple and gold), covered in tiny golden speckles and giving off a soft magical glow and a few sparkles. Jack leans in, amazed, the glow lighting his face. Milky-White's head is beside Jack."},
        {"text": "{name} could not resist, traded Milky-White for the beans, and ran all the way home.",
         "zone": "top", "cast": ["cow", "old_man"],
         "scene": "On the road: Jack runs toward the viewer, grinning, holding up his open hand with the five glowing, jewel-colored magic beans in it. Behind him, smaller, the old man leads Milky-White away down the road."},
        {"text": "\"Five beans? For our cow?\" sighed Mother. \"They're only ordinary beans, {name}.\" And she tossed them out of the window.",
         "zone": "bottom", "cast": ["mother"],
         "scene": "Inside the cottage kitchen at dusk. Jack's mother, tired and unimpressed but not angry, casually tosses the five beans over her shoulder out of the open window with a careless flick of her wrist, rolling her eyes with a small sigh, as if throwing away ordinary old beans. The five beans glow faintly in jewel colors as they fly out into the orange evening sky. Jack, a slim child much shorter than his mother (his head reaches her shoulder), stands next to her, shocked, reaching toward the window. Warm candlelight inside."},
        {"text": "{name} was sent to bed without any supper. Looking out at the moon, {name} wondered: had that been a very foolish trade?",
         "zone": "top", "cast": [],
         "scene": "Jack's small attic bedroom at night. Jack sits on the edge of a simple wooden bed, chin in his hands, gloomy, lit by soft blue moonlight from a small window and a candle beside him."},
        {"text": "But in the morning, where the beans had landed, a giant beanstalk had grown, up, up, up, into the clouds.",
         "zone": "middle", "cast": [],
         "scene": "Morning outside the cottage. Jack stands in the garden in the lower part of the image, his head tilted back, looking UP at the beanstalk in wonder, seen in three-quarter view so his face is still visible. Beside him a gigantic twisting green beanstalk with huge leaves rises straight up, past a band of soft white cloud across the middle of the image, and continues up to the top."},
        {"text": "{name} began to climb, up and up, higher than the birds, all the way to the sky.",
         "zone": "bottom", "cast": [],
         "scene": "Jack climbing the beanstalk high in the sky, seen from slightly above, his face turned up toward the viewer, smiling and determined. Huge leaves around him, small birds flying far below, and his tiny cottage and fields far, far below at the bottom of the image under a thin layer of mist."},
        {"text": "At the top was a road made of clouds, and at the end of the road stood an enormous castle.",
         "zone": "top", "cast": [],
         "scene": "Above the clouds: Jack steps off the top of the beanstalk onto a road of white clouds, in the foreground, seen from the side, his face in profile turned toward the castle (a side view of his face is visible), gazing at an enormous grey stone castle in the distance."},
        {"text": "A giant woman opened the door. \"Hurry, little one,\" she whispered. \"My husband eats children for breakfast! Quick, hide in this big pot!\"",
         "zone": "top", "cast": ["giants_wife"],
         "scene": "At the enormous castle door, which is many times taller than Jack. The giant's wife bends down kindly toward Jack, a finger to her lips. Jack looks up at her, startled. Both faces are visible."},
        {"text": "BOOM! BOOM! BOOM! In stomped the giant. \"Fee-fi-fo-fum!\" he roared. \"I smell a {child}, I'm sure of one!\"",
         "zone": "top", "cast": ["giant", "giants_wife"],
         "scene": "The giant's huge kitchen. The giant stomps in through a doorway on the right, sniffing the air. In the foreground on the left, Jack is hidden INSIDE an enormous copper cooking pot on the floor: only his head, from the eyes up to his hair plus his hands gripping the rim, peeks over the edge. His eyes and upper face are clearly visible, wide with fear; the rest of him is out of sight inside the pot. The giant has not seen him. The giant's wife stands at the stove looking nervous."},
        {"text": "The giant sniffed all around, but he never found {name}. After dinner, he counted his gold and fell fast asleep. {name} crept out, took a bag of gold, and hurried home.",
         "zone": "top", "cast": ["giant"],
         "scene": "The giant snores in a huge wooden chair, slumped on the right, with gold coins spilled on the table. In the foreground Jack tiptoes away hugging a bag of gold coins, looking back at the viewer with a grin."},
        {"text": "For a while, {name} and Mother had all they needed. But one day the bag of gold was empty, so {name} climbed the beanstalk once more.",
         "zone": "top", "cast": ["mother"],
         "scene": "Inside the cottage kitchen in the evening. Jack and his mother sit at the wooden table looking at an empty, flat money bag turned inside out, with not a single coin left; the mother holds it up, shrugging sadly. Jack faces the viewer, worried. Through the open window behind them, the giant beanstalk rises into the sky. Warm candlelight. No giant in this picture."},
        {"text": "Up in the castle, the giant had a hen that laid a golden egg whenever he said, \"Lay!\" and a harp that sang all by itself. When he fell asleep, {name} took them both.",
         "zone": "top", "cast": ["giant", "hen", "harp"],
         "scene": "The giant's enormous kitchen. On the huge wooden table in the foreground sits the hen on a straw nest, having just laid a shining golden egg, with a little pile of golden eggs beside the nest. Jack stands on the table in the foreground, tiptoeing, with the hen tucked under one arm and the golden harp held in the other arm, looking at the viewer with a sly, excited face. FAR away in the background, small, the giant is slumped fast asleep in his chair by the fireplace, eyes closed, snoring. The giant is far from Jack and cannot see him."},
        {"text": "But as {name} ran, the harp sang out, \"Master! Master!\" The giant woke with a roar and thundered after {name}.",
         "zone": "top", "cast": ["giant", "harp", "hen"],
         "scene": "On the cloud road: Jack sprints toward the viewer with the harp in one arm and the hen tucked under the other, with an excited, frightened face. Far behind him, the giant chases, arms outstretched, smaller in the distance. The top of the beanstalk is in front of Jack."},
        {"text": "\"Mother! Mother! Bring the axe!\" shouted {name}, sliding down the beanstalk with the hen and the harp.",
         "zone": "top", "cast": ["mother", "harp", "hen"],
         "scene": "Lower part of the beanstalk near the ground. Jack slides down a thick stem toward the viewer, shouting, with the harp under one arm and the hen riding on his shoulder, flapping. Below, his mother runs out of the cottage holding a woodcutter's axe. Jack's face clearly visible."},
        {"text": "{name} chopped and chopped. Down came the beanstalk with a mighty CRASH, and the giant was never seen again.",
         "zone": "top", "cast": ["mother"],
         "scene": "In the garden: Jack has just swung the axe, the beanstalk is toppling sideways with leaves flying, and a big cloud of dust rises. His mother stands beside him, hands on her cheeks. Jack faces the viewer in three-quarter view, triumphant. No giant is shown."},
        {"text": "With the hen's golden eggs, {name} bought back Milky-White. And {name}, Mother, and Milky-White lived happily ever after.",
         "zone": "bottom", "cast": ["mother", "cow", "hen", "harp"],
         "scene": "A sunny garden in front of the now-repaired cottage, with flowers. Jack, a slim child much shorter than his mother (his head reaches her shoulder), hugs Milky-White, smiling at the viewer. His mother laughs beside them, holding a basket of golden eggs, the hen at her feet, and the harp sits on a bench nearby."},
    ],
}

STORIES["red"] = {
    "id": "red",
    "title": "Little Red Riding Hood",
    "hero_name": "Little Red Riding Hood",
    "default_pronoun": "they",
    "hero_outfit": ("a bright red hooded cape tied at the neck, with the hood down so the face and hair are fully visible. "
                    "Under the cape: if the child is a girl, a simple knee-length storybook dress (a cream blouse with "
                    "puffed sleeves under a laced dark-red pinafore skirt), white stockings and brown leather Mary Jane "
                    "shoes; NOT trousers or pants. If the child is a boy, a cream linen shirt, brown trousers and brown "
                    "leather boots"),
    "standin": "a friendly young girl of about ten with shoulder-length brown hair",
    "bible": {
        "mother": "The mother: a cheerful woman in her thirties with dark curly hair tied back, a green dress and a white apron.",
        "grandmother": "Grandmother: a small, sweet old woman with white hair in a bun, round gold glasses, a lilac nightgown and a white frilly nightcap.",
        "wolf": "The wolf: a tall, skinny grey wolf with a long snout, yellow eyes, big pointed ears and a sly grin. Mischievous, more comic than scary. Walks on all fours.",
        "woodcutter": "The woodcutter: a big, gentle man with a short brown beard, a red-and-black checked shirt, brown trousers, and an axe over his shoulder.",
        "basket": "The basket: a woven wicker basket with a handle, covered by a red-and-white checked cloth, with a loaf of bread and a jar of honey peeking out. Just the basket on its own: no person, no hands, no character holding it.",
    },
    "pages": [
        {"text": "Once upon a time there was a child who always wore a bright red hooded cape, so everyone called {him} Little Red Riding Hood.",
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
        {"text": "The wolf pushed the door open. When Grandmother saw him, she jumped out of bed and hid in the wardrobe.",
         "zone": "top", "cast": ["wolf", "grandmother"],
         "scene": "Inside Grandmother's bedroom. Grandmother, startled, slips into a tall wooden wardrobe and pulls the door almost closed, peeking out. The wolf stands in the bedroom doorway. The hero does not appear on this page."},
        {"text": "Then the wolf put on Grandmother's nightcap and glasses, climbed into her bed, and waited.",
         "zone": "top", "cast": ["wolf"],
         "scene": "Grandmother's bedroom. The wolf lies in the bed with the blanket pulled up, wearing Grandmother's frilly nightcap and round glasses, grinning. The hero does not appear on this page."},
        {"text": "Soon Little Red Riding Hood arrived with the basket and the flowers, and found the door standing wide open.",
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
         "scene": "The bedroom door bursts open and the woodcutter stands in it, tall and brave. On the other side of the room, the wolf is escaping OUT through the open window: we see him from behind, his back and bushy tail toward the room, his front half already outside, leaping away toward the forest with his tail between his legs. The hero stands in the foreground, relieved, facing the viewer."},
        {"text": "Out of the wardrobe stepped Grandmother, safe and sound. \"My brave dear,\" she said, and hugged Little Red Riding Hood tight.",
         "zone": "top", "cast": ["grandmother", "woodcutter"],
         "scene": "The bedroom. Grandmother steps out of the wardrobe and hugs the hero. The hero's face is toward the viewer, eyes closed with relief. The woodcutter smiles in the background."},
        {"text": "The wolf ran deep into the forest, and he was never seen in those woods again.",
         "zone": "bottom", "cast": ["wolf"],
         "scene": "The forest seen from the cottage window at sunset: the wolf, small in the distance, runs off over a hill into the trees, looking back nervously. The hero leans out of the window in the foreground, watching, smiling, face fully visible."},
        {"text": "Soon Mother came by too, and everyone sat down to bread, honey and tea. And Little Red Riding Hood never strayed from the path again.",
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


# The hero's expression on each page (page 1 first). The face itself never changes, only the expression,
# the way an animator would draw the same character happy, worried or surprised.
EXPRESSIONS = {
    "jack": [
        "a soft, slightly wistful smile",
        "worried: eyebrows raised in the middle, a small frown",
        "hopeful and determined, with a small smile",
        "curious: eyebrows raised, mouth slightly open",
        "amazed: eyes wide, mouth open in wonder",
        "thrilled: a big open-mouthed grin",
        "sad and embarrassed: eyebrows tilted up, a small frown",
        "thoughtful and a little sad: eyes looking up, a small frown",
        "astonished: eyes wide, mouth open",
        "determined, with a confident small smile",
        "awed: eyes wide, mouth slightly open in wonder",
        "startled and nervous: eyebrows up, mouth slightly open",
        "frightened: eyes wide, lips pressed together, holding their breath",
        "excited and a little nervous: a tense grin",
        "worried: eyebrows raised in the middle, a small frown",
        "sneaky and excited: a sly little smile",
        "scared but determined: eyes wide, mouth open, running",
        "urgent: shouting, mouth wide open, eyebrows up",
        "determined: eyebrows lowered, jaw set",
        "joyful: a big happy smile",
    ],
    "red": [
        "a warm, friendly smile",
        "attentive, listening carefully, a small soft smile",
        "cheerful: a happy smile",
        "surprised: eyebrows up, mouth in a small round 'oh'",
        "polite and trusting: a friendly smile",
        "delighted: a happy smile, eyes bright",
        "happy and carefree: a gentle smile",
        "calm, a small smile",
        "calm, a small smile",
        "calm, a small smile",
        "calm, a small smile",
        "curious and a little unsure: eyebrows slightly raised, no smile",
        "puzzled: one eyebrow raised, mouth slightly open",
        "uneasy: eyes wide, a small worried frown",
        "frightened: eyes wide, mouth open in a gasp",
        "scared: eyes wide, eyebrows up, mouth open, shouting",
        "relieved: a small shaky smile",
        "relieved: eyes closed, a gentle smile",
        "calm and content: a soft smile",
        "joyful: laughing, eyes crinkled",
    ],
}


# What a page MUST show about the hero, where the story depends on it. Told to the drawing and checked after.
MUST = {
    "red": {
        17: "The wolf is leaping OUT of the window, away from the room: his back and tail face the room and his head is "
            "outside, toward the forest. He is NOT coming in.",
    },
    "jack": {
        7: "Jack is SLIM, exactly the build of image 2 (not chubby, no round belly or full cheeks), and clearly "
           "shorter than his mother.",
        9: "Jack is looking UP at the beanstalk, head tilted back, NOT looking at the viewer.",
        11: "Jack is looking toward the castle in the distance, NOT at the viewer (a side view of his face is fine).",
        13: "Jack is HIDDEN inside the big copper pot: only his eyes, the top of his head and his fingers on the rim "
            "show above its edge. His body is NOT visible and he is NOT standing up. The giant is not looking at him.",
        14: "The giant is fast asleep with his eyes closed while Jack tiptoes away.",
        15: "This is at home in the cottage with Jack's mother. There is NO giant anywhere in the picture.",
        16: "Jack has the hen under one arm AND the golden harp in the other arm, and a golden egg the hen has laid is "
            "clearly visible. The giant is far away in the background, fast asleep with his eyes closed, NOT near Jack.",
        17: "Jack is carrying both the hen and the golden harp.",
        18: "Jack has both the hen and the golden harp with him as he slides down.",
    },
}


def must(s: dict, page: dict):
    return MUST.get(s["id"], {}).get(page.get("number", 0))


# The picture shown for each story on the home page and the New book page (a story page number).
SHOWCASE = {"jack": 10, "red": 5}
# Three more pages shown as samples on the home page.
SAMPLES = {"jack": (5, 13, 17), "red": (4, 15, 18)}


# The child is the hero: Jack's story is told with the child's own name ("Simcha climbed the beanstalk"),
# and both stories use the child's pronouns. Little Red Riding Hood keeps her title and nickname.
PRONOUNS = {
    "he": {"he": "he", "He": "He", "his": "his", "His": "His", "him": "him", "child": "boy"},
    "she": {"he": "she", "He": "She", "his": "her", "His": "Her", "him": "her", "child": "girl"},
    "they": {"he": "they", "He": "They", "his": "their", "His": "Their", "him": "them", "child": "child"},
}


def page_text(s: dict, page: dict, name: str = None, pronoun: str = None) -> str:
    """A page's words for this child. Without a name (the pre-drawn scenes) the story's own hero is used."""
    words = PRONOUNS.get(pronoun or s.get("default_pronoun", "they"), PRONOUNS["they"])
    text = page["text"].replace("{name}", name or s["hero_name"])
    for token, word in words.items():
        text = text.replace("{" + token + "}", word)
    return text


def book_title(s: dict, name: str = None) -> str:
    """Jack's book is named after the child ("Simcha and the Beanstalk"); Red Riding Hood keeps her title."""
    if s.get("title_with_name") and name:
        return s["title_with_name"].replace("{name}", name)
    return s["title"]


def book_subtitle(s: dict, name: str = None) -> str:
    """The line under the title on the cover: "FEATURING MEIRA" (none for Jack: the name is in the title)."""
    if s.get("title_with_name") or not name:
        return ""
    return f"FEATURING {name.upper()}"


def expression(s: dict, page: dict) -> str:
    faces = EXPRESSIONS.get(s["id"], [])
    n = page.get("number", 0)
    return faces[n - 1] if 0 < n <= len(faces) else "a natural expression that fits this moment in the story"


def swap_prompt(s: dict, page: dict, head_hidden: bool = False) -> str:
    """Per book: put the user's hero into a pre-drawn scene. Image 1 = scene, image 2 = hero, image 3 = face."""
    hidden = (
        "The hero's head in image 1 has been blurred out on purpose. Draw the hero's whole head, face and hair "
        "there from images 2 and 3, at the same size, angle and position as the blurred head. Nothing may stay "
        "blurry, and nothing of the old face may remain.\n\n" if head_hidden else "")
    return (
        f"{STYLE}\n\n"
        "Image 1 is a finished picture-book illustration. Image 2 is the hero's official character design. "
        "Image 3 is a close-up of the hero's face from that design.\n\n"
        + hidden +
        "Replace the hero in image 1 with the character from image 2: same hair, skin tone, any head covering, "
        "body proportions and outfit as image 2, in exactly the same position, pose, size and lighting as "
        "the hero in image 1. The clothes must be image 2's clothes: if the hero in image 1 is dressed differently "
        "(for example trousers instead of a dress), redraw their clothes to match image 2.\n\n"
        "ARMS AND HANDS: keep the hero's body pose from image 1 exactly, including where each arm and hand is. The "
        "hero has exactly TWO arms and TWO hands. Never add an arm or a hand, and do not copy the arm pose of image 2 "
        "(image 2 only shows what the hero looks like, not how they stand).\n\n"
        "THE FACE MUST BE IMAGE 3'S FACE, as if it were the same 3D character model: same face shape, eye shape "
        "and color, eyebrow shape, nose, mouth shape, ears, cheeks, freckles, hairline, hair color and curls, and the "
        "same apparent age. Do not redesign, simplify, age up or age down the face. It must stay clearly visible, "
        "front-lit and recognizable. Copy the face's SHAPES and FEATURES, drawn in the same cartoon style as image 2.\n\n"
        "BODY: exactly image 2's build, weight and proportions. Never make the hero chubbier, rounder, heavier, "
        "thinner, taller, shorter, older or younger than image 2, in the face or the body.\n\n"
        "SIZE: the hero is a CHILD. Keep the hero exactly as tall as in image 1. Next to an adult (a parent, a "
        "grandmother, an old man), the hero is clearly shorter: the top of the hero's head is at about the adult's "
        "shoulder, never level with their face.\n\n"
        "GAZE: keep the hero looking in the same direction as in image 1 (at another character, at something in the "
        "scene, or at the viewer); don't turn the head toward the viewer unless the hero faces the viewer in image 1.\n\n"
        f"EXPRESSION ON THIS PAGE: {expression(s, page)}, to fit this moment in the story. Image 3 shows what the face "
        "looks like, not which expression to use. Show the expression only with the mouth, eyebrows and eyelids, "
        "the way an animator draws the same character happy, worried or surprised: the character must still be "
        "instantly recognizable as image 3, and the face must not get rounder, wider or fuller. Keep it natural and "
        "gentle, never exaggerated or distorted.\n\n"
        + (f"THIS PAGE MUST SHOW: {must(s, page)} If the hero is hiding in image 1, keep them hidden exactly as in "
           "image 1 and never draw the rest of their body.\n\n" if must(s, page) else "") +
        f"{CARTOON_ONLY}\n\n"
        "Change NOTHING else: keep every other character, the background, the colors, the composition and any empty areas "
        f"exactly as they are in image 1. {NO_TEXT}"
    )
