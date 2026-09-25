"""Shared test data for question tests: a note, a pool of distinct grounded questions, and a reply builder."""

import json


def _section(title: str, body: str, repeats: int = 3) -> str:
    """One heading, then the body repeated so the section is comfortably over the minimum size."""
    return title + "\n\n" + " ".join([body.strip()] * repeats) + "\n\n"


NOTE_TEXT = (
    _section(
        "1. Magnetic Materials",
        "A magnet attracts iron, nickel and cobalt. Wood, glass, rubber and copper are not attracted by a magnet. "
        "Steel needles and iron nails are magnetic. Copper wire is not magnetic even though it is a metal.",
    )
    + _section(
        "2. Poles and Directions",
        "Every magnet has two poles, the north pole and the south pole. The attraction is strongest at the poles. "
        "Like poles repel each other and unlike poles attract each other. A freely hanging bar magnet comes to rest "
        "pointing in the north-south direction. A compass has a magnetic needle that shows directions.",
    )
    + _section(
        "3. Making and Keeping Magnets",
        "A steel needle can be made into a magnet by stroking it with a bar magnet in one direction using the single touch method. "
        "An electromagnet is made by winding a wire around an iron nail and connecting a battery. More turns of wire make it stronger. "
        "Heating a magnet strongly can weaken it. Bar magnets are stored in pairs with a keeper so they keep their strength. "
        "The space around a magnet where its force acts is called the magnetic field. Lodestones hung by a thread pointed north.",
    )
    + _section(
        "4. Quick Recap",
        "Key terms: magnet, pole, compass, keeper, electromagnet, magnetic field, lodestone. Repeat of the main facts for revision.",
        repeats=4,
    )
)


def _q(qtype, text, answer, options=None, topic="Magnets", difficulty="easy", bloom="Remember", explanation="From the note."):
    return {
        "type": qtype, "question": text, "options": options, "answer": answer, "explanation": explanation,
        "difficulty": difficulty, "bloom": bloom, "topic": topic,
    }


# Fifteen questions that are clearly different from each other and grounded in NOTE_TEXT.
POOL = [
    _q("mcq", "Which of these materials is attracted by a magnet?", "Iron", ["Wood", "Iron", "Glass", "Rubber"], "Materials"),
    _q("mcq", "Which instrument uses a magnetic needle to show directions?", "Compass", ["Compass", "Balance", "Telescope", "Barometer"], "Poles"),
    _q("true_false", "Every magnet has exactly two poles.", "True", None, "Poles"),
    _q("true_false", "Copper is strongly attracted by a magnet.", "False", None, "Materials"),
    _q("fill_blank", "Two like poles of magnets _____ each other.", "repel", None, "Poles"),
    _q("fill_blank", "A freely hanging bar magnet points in the north-south _____ .", "direction", None, "Poles"),
    _q("short", "Why are bar magnets stored with a keeper?", "The keeper helps the magnets keep their strength.", None, "Keeping"),
    _q("short", "Name two magnetic materials mentioned in the note.", "Iron and nickel are magnetic materials.", None, "Materials"),
    _q("long", "Explain how an electromagnet is made and how its strength can be increased.", "Wind a wire around an iron nail and connect a battery, and use more turns of wire to make it stronger.", None, "Making"),
    _q("long", "Describe how a steel needle can be turned into a magnet.", "Stroke the steel needle with a bar magnet in one direction using the single touch method many times.", None, "Making"),
    _q("mcq", "Where is the attraction of a bar magnet strongest?", "Poles", ["Middle", "Poles", "Corners", "Sides"], "Poles"),
    _q("mcq", "What happens when unlike poles of two magnets come close?", "They attract", ["They attract", "They repel", "They melt", "Nothing happens"], "Poles"),
    _q("true_false", "Heating a magnet strongly can weaken it.", "True", None, "Keeping"),
    _q("fill_blank", "The space around a magnet where its force acts is the magnetic _____ .", "field", None, "Field"),
    _q("short", "What did lodestones do when they were hung by a thread?", "Lodestones pointed north when hung by a thread.", None, "History"),
]


def reply(items: list[dict], insufficient: bool = False) -> str:
    return json.dumps({"questions": items, "insufficient": insufficient})


def pool(start: int, stop: int) -> list[dict]:
    return [dict(q) for q in POOL[start:stop]]
