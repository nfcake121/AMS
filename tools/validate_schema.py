# tools/validate_schema.py
import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]  # AMS/
sys.path.insert(0, str(ROOT))

from src.schema import SofaRequest, resolve_sofa  # noqa: E402


def main():
    path = ROOT / "data" / "examples" / "request_scandi.json"
    raw = json.loads(path.read_text(encoding="utf-8"))

    print("INPUT JSON:")
    print(json.dumps(raw, ensure_ascii=False, indent=2))

    try:
        req = SofaRequest.model_validate(raw)
        print("\nSofaRequest OK ✅")
        print(req.model_dump())

        resolved = resolve_sofa(req)
        print("\nSofaResolved OK ✅")
        print(json.dumps(resolved.model_dump(), ensure_ascii=False, indent=2))

    except ValidationError as e:
        print("\nVALIDATION ERROR ❌")
        print(e)


if __name__ == "__main__":
    main()
