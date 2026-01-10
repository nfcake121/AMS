import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.ner_infer import predict
from src.schema import SofaRequest, resolve_sofa

MODEL_DIR = "models/sofa_ner_rubert"


def parse_length_to_mm(s: str) -> int:
    t = s.lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    if not m:
        raise ValueError(f"Cannot parse length: {s}")
    value = float(m.group(1))

    if "мм" in t:
        mm = value
    elif "см" in t:
        mm = value * 10
    elif "м" in t:
        mm = value * 1000
    else:
        mm = value  # по умолчанию считаем мм

    return int(round(mm))


def parse_int(s: str) -> int:
    m = re.search(r"\d+", s)
    if not m:
        raise ValueError(f"Cannot parse int: {s}")
    return int(m.group(0))


def normalize_entities(entities: dict) -> dict:
    data: dict = {}

    # простые строковые
    for key in ["type", "style", "layout", "orientation", "leg_family", "armrests"]:
        K = key.upper()
        if K in entities and entities[K]:
            data[key] = entities[K][0].strip()

    # числовые
    if "SEAT_HEIGHT_MM" in entities and entities["SEAT_HEIGHT_MM"]:
        data["seat_height_mm"] = parse_length_to_mm(entities["SEAT_HEIGHT_MM"][0])

    if "SEAT_DEPTH_MM" in entities and entities["SEAT_DEPTH_MM"]:
        data["seat_depth_mm"] = parse_length_to_mm(entities["SEAT_DEPTH_MM"][0])

    if "SEAT_COUNT" in entities and entities["SEAT_COUNT"]:
        data["seat_count"] = parse_int(entities["SEAT_COUNT"][0])

    if "SEAT_WIDTH_RANGE_MM" in entities and entities["SEAT_WIDTH_RANGE_MM"]:
        joined = " ".join(entities["SEAT_WIDTH_RANGE_MM"])
        nums = [int(x) for x in re.findall(r"\d+", joined)]
        if len(nums) >= 2:
            data["seat_width_range_mm"] = (nums[0], nums[1])

    if "TRANSFORMABLE" in entities and entities["TRANSFORMABLE"]:
        t = " ".join(entities["TRANSFORMABLE"]).lower()
        data["transformable"] = not ("без" in t or "нет" in t)

    return data


def main():
    text = (
        "Мне нужен скандинавский угловой диван, "
        "высота сиденья 44 см, глубина 60 см, "
        "на 3 места, без механизма, ножки конусные."
    )

    print("\n=== USER TEXT ===")
    print(text)

    out = predict(text, MODEL_DIR, max_len=128)

    print("\n=== TOKENS ===")
    print(out.tokens)

    print("\n=== TAGS ===")
    print(out.tags)

    print("\n=== NER ENTITIES ===")
    for k, v in out.entities.items():
        print(f"{k}: {v}")

    params = normalize_entities(out.entities)
    print("\n=== NORMALIZED PARAMS ===")
    print(params)

    # 1) validate + aliases (Request)
    req = SofaRequest(**params)

    # 2) deterministic resolve (IR for Builder)
    resolved = resolve_sofa(req)

    print("\n=== SOFA RESOLVED (IR) ===")
    # красиво JSON-ом
    print(resolved.model_dump_json(indent=2, ensure_ascii=False))

    # если нужен dict:
    # print(resolved.model_dump())


if __name__ == "__main__":
    main()
