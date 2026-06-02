#!/usr/bin/env python3
"""registry.json 을 회사 스키마(references/registry.schema.json)에 대조 검증.

사용:
  python validate_registry.py [registry.json]   # 기본: ./registry.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _schema import jsonschema_validate, load_schema, validate_registry


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("registry.json")
    if not path.exists():
        sys.exit(f"[ERROR] 파일 없음: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    schema = load_schema()

    ok_js, errs_js, used = jsonschema_validate(obj, schema)
    if used:
        print("jsonschema:", "VALID ✓" if ok_js else "INVALID ✗")
        for e in errs_js:
            print("  -", e)
    else:
        print("(jsonschema 미설치 → 수동 미러 검증으로 대체)")

    ok, errs = validate_registry(obj, schema)
    n = len(obj.get("skills", []))
    print("manual:", f"VALID ✓ ({n} entries)" if ok else "INVALID ✗")
    for e in errs:
        print("  -", e)

    sys.exit(0 if ok and ok_js is not False else 1)


if __name__ == "__main__":
    main()
