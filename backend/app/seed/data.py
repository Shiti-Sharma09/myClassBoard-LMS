"""Static seed content: chapters, topics, demo students and tests. All synthetic."""

DEMO_PASSWORD = "demo1234"
SUBJECT = "Science"
GRADE = 6

# CBSE Class 6 Science. NCERT "Curiosity" (2024) chapter list; topics are our own breakdown.
CHAPTERS: list[tuple[int, str, list[str]]] = [
    (1, "The Wonderful World of Science", ["What is Science", "The Scientific Method", "Curiosity and Observation"]),
    (2, "Diversity in the Living World", ["Habitats and Adaptations", "Classifying Plants", "Classifying Animals"]),
    (3, "Mindful Eating: A Path to a Healthy Body", ["Nutrients and their Functions", "Balanced Diet", "Deficiency Diseases"]),
    (4, "Exploring Magnets", ["Magnetic and Non-magnetic Materials", "Poles of a Magnet", "Uses of Magnets"]),
    (5, "Measurement of Length and Motion", ["Standard Units", "Measuring Length", "Types of Motion"]),
    (6, "Materials Around Us", ["Properties of Materials", "Grouping Materials", "Transparency and Solubility"]),
    (7, "Temperature and its Measurement", ["Hot and Cold", "Thermometers", "Heat Transfer"]),
    (8, "A Journey through States of Water", ["States of Water", "The Water Cycle", "Evaporation and Condensation"]),
    (9, "Methods of Separation in Everyday Life", ["Handpicking and Sieving", "Filtration and Decantation", "Evaporation and Winnowing"]),
    (10, "Living Creatures: Exploring their Characteristics", ["Characteristics of Living Things", "Food and Movement", "Growth and Reproduction"]),
    (11, "Nature's Treasures", ["Natural Resources", "Renewable and Non-renewable Resources", "Conservation"]),
    (12, "Beyond Earth", ["The Solar System", "Stars and Constellations", "The Moon and its Phases"]),
]

# Six unit tests over these chapters (3 topics each, 10 marks per topic). Dates are fixed so the demo is repeatable.
TESTS: list[tuple[str, str, int]] = [
    ("Unit Test 1", "2026-07-20", 2),
    ("Unit Test 2", "2026-08-03", 3),
    ("Unit Test 3", "2026-08-17", 4),
    ("Unit Test 4", "2026-08-31", 5),
    ("Unit Test 5", "2026-09-07", 6),
    ("Unit Test 6", "2026-09-21", 8),
]
MARKS_PER_TOPIC = 10

# (first name, last name, persona, chapter number where a "gap" persona struggles)
STUDENTS: list[tuple[str, str, str, int | None]] = [
    ("Aarav", "Sharma", "strong", None),
    ("Rohan", "Verma", "weak", None),
    ("Diya", "Nair", "average", None),
    ("Saanvi", "Gupta", "improving", None),
    ("Kavya", "Menon", "declining", None),
    ("Tara", "Bose", "gap", 4),
    ("Ananya", "Iyer", "strong", None),
    ("Meera", "Patel", "weak", None),
    ("Kabir", "Singh", "average", None),
    ("Reyansh", "Joshi", "improving", None),
    ("Advait", "Kulkarni", "declining", None),
    ("Yash", "Malhotra", "gap", 8),
    ("Vihaan", "Mehta", "strong", None),
    ("Arjun", "Reddy", "weak", None),
    ("Ishita", "Rao", "average", None),
]

CLASSES = [("6-A", 6, "A"), ("6-B", 6, "B")]

TEACHER = ("Priya Deshmukh", "teacher@demo.school")
ADMIN = ("Admin", "admin@demo.school")

DEFAULT_SETTINGS = {"weak_topic_threshold": "60"}

# Students and parents shown as one-click logins on the login page (all accounts share DEMO_PASSWORD).
DEMO_LOGIN_STUDENTS = ["Aarav", "Diya", "Rohan"]
