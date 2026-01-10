import json
import random
import re
from pathlib import Path

# ----------------------------
# Config
# ----------------------------

TAGS = [
    "TYPE", "STYLE", "LAYOUT", "ORIENTATION",
    "SEAT_HEIGHT_MM", "SEAT_DEPTH_MM", "SEAT_WIDTH_RANGE_MM",
    "SEAT_COUNT", "HAS_CHAISE", "ARMRESTS", "LEG_FAMILY", "TRANSFORMABLE"
]

RANDOM_SEED = 42

# ----------------------------
# Lexicons
# ----------------------------

TYPE_WORDS = ["диван", "софа"]

STYLE_WORDS = {
    "scandi": ["сканди", "скандинавский", "scandi"],
    "loft": ["лофт", "industrial", "индастриал"],
    "modern": ["модерн", "современный", "modern"],
    "minimal": ["минимализм", "минималистичный", "minimal"],
    "classic": ["классика", "классический", "classic"],
}

LAYOUT_WORDS = {
    "straight": ["прямой", "прямолинейный", "обычный"],
    "corner": ["угловой", "Г-образный", "l-образный"],
    "u_shape": ["п-образный", "u-образный"],
    "modular": ["модульный", "секции", "модули"],
}

ORIENTATION_WORDS = {
    "left": ["левый", "слева", "левосторонний"],
    "right": ["правый", "справа", "правосторонний"],
}

LEG_FAMILY_WORDS = {
    "tapered_cone": ["конусные ножки", "конусообразные ножки", "tapered_cone"],
    "tapered_prism": ["призматические ножки", "скошенная пирамида", "tapered_prism"],
    "cylindrical": ["цилиндрические ножки", "круглые ножки", "cylindrical"],
    "block": ["блочные ножки", "квадратные ножки", "block"],
    "hairpin": ["hairpin", "шпильки", "ножки-шпильки"],
    "sled": ["салазки", "sled", "полозья"],
    "frame": ["рамные ножки", "металлическая рама", "frame"],
}

ARMREST_WORDS = {
    "none": ["без подлокотников", "подлокотники не нужны", "no armrests"],
    "both": ["с подлокотниками", "два подлокотника", "с двух сторон"],
    "left": ["подлокотник слева", "левый подлокотник"],
    "right": ["подлокотник справа", "правый подлокотник"],
}

CHAISE_WORDS_TRUE = ["с оттоманкой", "с шезлонгом", "с канапе", "с удлинением"]
CHAISE_WORDS_FALSE = ["без оттоманки", "без шезлонга", "без удлинения"]

TRANSFORM_TRUE = ["раскладной", "трансформер", "с механизмом раскладывания"]
TRANSFORM_FALSE = ["не раскладной", "без механизма", "стационарный"]

# ----------------------------
# Helpers
# ----------------------------

def tokenize_ru(text: str):
    # токенизация как у тебя в примерах (слова/числа/знаки)
    # разделяем числа, точки, запятые
    tokens = re.findall(r"\d+|[A-Za-zА-Яа-яЁё]+|[^\w\s]", text, flags=re.UNICODE)
    return tokens

def tag_span(tokens, start_idx, end_idx, label):
    # end_idx exclusive
    tags = ["O"] * len(tokens)
    tags[start_idx] = f"B-{label}"
    for i in range(start_idx + 1, end_idx):
        tags[i] = f"I-{label}"
    return tags

def merge_tags(base_tags, span_tags):
    # span_tags has O except labeled region; overlay onto base_tags
    out = base_tags[:]
    for i, t in enumerate(span_tags):
        if t != "O":
            out[i] = t
    return out

def mm_or_cm_value(mm_value: int):
    # иногда пишем в мм, иногда в см
    if random.random() < 0.65:
        # см
        cm = round(mm_value / 10)
        return cm, "см"
    return mm_value, "мм"

def format_dim_phrase(kind: str, mm_value: int):
    # kind: высота сиденья / глубина сиденья
    val, unit = mm_or_cm_value(mm_value)
    # варианты формулировок
    templates = [
        f"{kind} {val} {unit}",
        f"{kind} — {val}{unit}",
        f"{kind}: {val} {unit}",
        f"{kind} примерно {val} {unit}",
    ]
    return random.choice(templates)

def format_width_range(min_mm: int, max_mm: int):
    min_val, unit1 = mm_or_cm_value(min_mm)
    # чтобы не было несостыковки единиц в одном диапазоне, делаем одинаковую единицу
    if unit1 == "см":
        max_val = round(max_mm / 10)
        unit = "см"
    else:
        max_val = max_mm
        unit = "мм"
    templates = [
        f"ширина посадки {min_val}–{max_val} {unit}",
        f"ширина сиденья от {min_val} до {max_val} {unit}",
        f"посадочное место {min_val}-{max_val} {unit} по ширине",
    ]
    return random.choice(templates)

def pick_style():
    key = random.choice(list(STYLE_WORDS.keys()))
    return key, random.choice(STYLE_WORDS[key])

def pick_layout():
    key = random.choice(list(LAYOUT_WORDS.keys()))
    return key, random.choice(LAYOUT_WORDS[key])

def pick_orientation():
    key = random.choice(list(ORIENTATION_WORDS.keys()))
    return key, random.choice(ORIENTATION_WORDS[key])

def pick_legs():
    key = random.choice(list(LEG_FAMILY_WORDS.keys()))
    return key, random.choice(LEG_FAMILY_WORDS[key])

def pick_armrests():
    key = random.choice(list(ARMREST_WORDS.keys()))
    return key, random.choice(ARMREST_WORDS[key])

def maybe(include_prob=0.7):
    return random.random() < include_prob

# ----------------------------
# Sample generator
# ----------------------------

def generate_one():
    # Core choices
    type_word = random.choice(TYPE_WORDS)

    style_key, style_word = pick_style()
    layout_key, layout_word = pick_layout()

    # Orientation only for corner/u_shape sometimes mentioned
    orientation_key = None
    orientation_word = None
    if layout_key in ("corner", "u_shape") and maybe(0.85):
        orientation_key, orientation_word = pick_orientation()

    # Dimensions
    seat_height = random.randint(380, 500)   # mm typical
    seat_depth = random.randint(520, 700)    # mm typical

    w_min = random.randint(450, 650)
    w_max = random.randint(max(w_min + 50, 520), min(w_min + 300, 900))

    # Seat count
    seat_count = random.choice([2, 3, 4, 5])

    # Options
    has_chaise = random.random() < 0.35
    leg_key, leg_word = pick_legs()
    arm_key, arm_word = pick_armrests()
    transformable = random.random() < 0.25

    # Text templates (shuffled clauses)
    clauses = []

    # intro
    intro_templates = [
        f"Мне нужен {type_word}",
        f"Хочу {type_word}",
        f"Подберите {type_word}",
        f"Нужен {type_word} для гостиной",
    ]
    clauses.append(random.choice(intro_templates))

    # style + layout
    style_layout_templates = [
        f"в стиле {style_word}",
        f"{style_word} стиль",
        f"стиль {style_word}",
    ]
    clauses.append(random.choice(style_layout_templates))

    layout_templates = [
        f"{layout_word}",
        f"компоновка {layout_word}",
        f"формат {layout_word}",
    ]
    clauses.append(random.choice(layout_templates))

    # orientation clause
    if orientation_word:
        orientation_templates = [
            f"угол {orientation_word}",
            f"ориентация {orientation_word}",
            f"{orientation_word} угол",
        ]
        clauses.append(random.choice(orientation_templates))

    # seat count
    if maybe(0.75):
        seat_templates = [
            f"на {seat_count} места",
            f"{seat_count}-местный",
            f"количество мест {seat_count}",
        ]
        clauses.append(random.choice(seat_templates))

    # dimensions
    if maybe(0.8):
        clauses.append(format_dim_phrase("высота сиденья", seat_height))
    if maybe(0.8):
        clauses.append(format_dim_phrase("глубина сиденья", seat_depth))
    if maybe(0.7):
        clauses.append(format_width_range(w_min, w_max))

    # legs
    if maybe(0.75):
        legs_templates = [
            f"ножки {leg_word}",
            f"с ножками: {leg_word}",
            f"тип ножек {leg_word}",
        ]
        clauses.append(random.choice(legs_templates))

    # armrests
    if maybe(0.75):
        clauses.append(arm_word)

    # chaise
    if maybe(0.65):
        clauses.append(random.choice(CHAISE_WORDS_TRUE if has_chaise else CHAISE_WORDS_FALSE))

    # transformable
    if maybe(0.6):
        clauses.append(random.choice(TRANSFORM_TRUE if transformable else TRANSFORM_FALSE))

    # Shuffle clauses and join
    random.shuffle(clauses)
    text = ", ".join(clauses) + "."

    tokens = tokenize_ru(text)
    tags = ["O"] * len(tokens)

    # Labeling helper to find token spans of inserted phrases
    def label_phrase(phrase: str, label: str):
        nonlocal tags
        phrase_tokens = tokenize_ru(phrase)
        # find first occurrence
        for i in range(len(tokens) - len(phrase_tokens) + 1):
            if tokens[i:i+len(phrase_tokens)] == phrase_tokens:
                span = tag_span(tokens, i, i+len(phrase_tokens), label)
                tags = merge_tags(tags, span)
                return True
        return False

    # TYPE
    label_phrase(type_word, "TYPE")

    # STYLE (label only the style word/phrase)
    label_phrase(style_word, "STYLE")

    # LAYOUT
    # label the main layout_word if present
    label_phrase(layout_word, "LAYOUT")

    # ORIENTATION
    if orientation_word:
        label_phrase(orientation_word, "ORIENTATION")

    # SEAT_COUNT: label the number token only (simpler and consistent)
    # locate seat_count as token
    for i, tok in enumerate(tokens):
        if tok == str(seat_count):
            tags[i] = "B-SEAT_COUNT"
            break

    # SEAT_HEIGHT_MM / SEAT_DEPTH_MM: label the numeric+unit region where possible
    # we label [число][единица] (e.g. "44", "см")
    def label_number_unit(mm_kind_label: str):
        nonlocal tags
        # look for pattern: number then unit token
        for i in range(len(tokens) - 1):
            if tokens[i].isdigit() and tokens[i+1] in ("см", "мм"):
                # Heuristic: check previous token context in window
                window = " ".join(tokens[max(0, i-4):i])
                if mm_kind_label == "SEAT_HEIGHT_MM" and ("высота" in window and "сиденья" in window):
                    tags[i] = f"B-{mm_kind_label}"
                    tags[i+1] = f"I-{mm_kind_label}"
                    return
                if mm_kind_label == "SEAT_DEPTH_MM" and ("глубина" in window and "сиденья" in window):
                    tags[i] = f"B-{mm_kind_label}"
                    tags[i+1] = f"I-{mm_kind_label}"
                    return

    label_number_unit("SEAT_HEIGHT_MM")
    label_number_unit("SEAT_DEPTH_MM")

    # SEAT_WIDTH_RANGE_MM: label the min–max + unit
    # patterns: number, "–"/"-", number, unit  OR  "от", number, "до", number, unit
    def label_width_range():
        nonlocal tags
        # pattern 1: N – N unit
        for i in range(len(tokens) - 3):
            if tokens[i].isdigit() and tokens[i+1] in ("–", "-") and tokens[i+2].isdigit() and tokens[i+3] in ("см", "мм"):
                tags[i] = "B-SEAT_WIDTH_RANGE_MM"
                tags[i+1] = "I-SEAT_WIDTH_RANGE_MM"
                tags[i+2] = "I-SEAT_WIDTH_RANGE_MM"
                tags[i+3] = "I-SEAT_WIDTH_RANGE_MM"
                return
        # pattern 2: от N до N unit
        for i in range(len(tokens) - 4):
            if tokens[i].lower() == "от" and tokens[i+1].isdigit() and tokens[i+2].lower() == "до" and tokens[i+3].isdigit() and tokens[i+4] in ("см", "мм"):
                tags[i] = "B-SEAT_WIDTH_RANGE_MM"
                for j in range(i+1, i+5):
                    tags[j] = "I-SEAT_WIDTH_RANGE_MM"
                return

    label_width_range()

    # HAS_CHAISE: label whole phrase (simple)
    chaise_phrase = random.choice(CHAISE_WORDS_TRUE if has_chaise else CHAISE_WORDS_FALSE)
    # but note: we used random choice when building clauses; we must find which one ended up in text
    for ph in CHAISE_WORDS_TRUE + CHAISE_WORDS_FALSE:
        if ph in text:
            label_phrase(ph, "HAS_CHAISE")
            break

    # ARMRESTS: label phrase
    for ph in sum(ARMREST_WORDS.values(), []):
        if ph in text:
            label_phrase(ph, "ARMRESTS")
            break

    # LEG_FAMILY: label phrase
    for ph in sum(LEG_FAMILY_WORDS.values(), []):
        if ph in text:
            label_phrase(ph, "LEG_FAMILY")
            break

    # TRANSFORMABLE: label phrase
    for ph in TRANSFORM_TRUE + TRANSFORM_FALSE:
        if ph in text:
            label_phrase(ph, "TRANSFORMABLE")
            break

    return {"tokens": tokens, "tags": tags}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20000, help="number of samples")
    parser.add_argument("--out", type=str, default="data/sofa_ner_train.jsonl")
    args = parser.parse_args()

    random.seed(RANDOM_SEED)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for _ in range(args.n):
            sample = generate_one()
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"✅ Wrote {args.n} samples to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
