#!/usr/bin/env python3
"""완성된 SKILL.md 로부터 registry 엔트리를 생성하고, 필요하면 registry.json 에 병합·검증.

사용:
  # 미리보기(엔트리만 출력)
  python registry_entry.py <skill-dir> --version 0.1.0 [--group G]
  # registry.json 에 병합·검증·기록 (같은 name 이면 교체)
  python registry_entry.py <skill-dir> --version 0.1.0 --registry registry.json --write
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _schema import infer_domain, load_schema, parse_frontmatter, validate_entry, validate_registry

ORDER = ["name", "description", "domain", "group", "version", "path"]


def build_entry(skill_dir, version, group, schema):
    fm = parse_frontmatter(Path(skill_dir) / "SKILL.md")
    name = (fm.get("name") or "").strip()
    desc = (fm.get("description") or "").strip()
    if not name or not desc:
        sys.exit("[ERROR] SKILL.md frontmatter 에 name/description 가 모두 필요")
    dom = infer_domain(name, schema)
    if not dom:
        sys.exit(
            f"[ERROR] name '{name}' 이 승인 domain prefix 로 시작하지 않음. "
            f"domains: {schema['$defs']['skillEntry']['properties']['domain']['enum']}"
        )
    entry = {"name": name, "description": desc, "domain": dom, "version": version, "path": f"skills/{name}"}
    if group:
        entry["group"] = group
    return {k: entry[k] for k in ORDER if k in entry}


def main():
    ap = argparse.ArgumentParser(description="SKILL.md → registry 엔트리 생성/병합")
    ap.add_argument("skill_dir", help="대상 스킬 디렉터리(SKILL.md 포함)")
    ap.add_argument("--version", default="0.1.0", help="semver (기본 0.1.0)")
    ap.add_argument("--group", default=None, help="선택 group")
    ap.add_argument("--registry", default=None, help="registry.json 경로(주면 병합 대상)")
    ap.add_argument("--write", action="store_true", help="--registry 에 실제 기록")
    args = ap.parse_args()

    schema = load_schema()
    entry = build_entry(args.skill_dir, args.version, args.group, schema)

    ok, errs = validate_entry(entry, schema)
    if not ok:
        print("[INVALID ENTRY]")
        for e in errs:
            print("  -", e)
        sys.exit(1)

    if not args.registry:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return

    reg_path = Path(args.registry)
    reg = (
        json.loads(reg_path.read_text(encoding="utf-8"))
        if reg_path.exists()
        else {"schemaVersion": "1.0", "skills": []}
    )
    reg.setdefault("schemaVersion", "1.0")
    reg.setdefault("skills", [])
    reg["skills"] = [e for e in reg["skills"] if e.get("name") != entry["name"]]  # 같은 name 교체
    reg["skills"].append(entry)
    reg["skills"].sort(key=lambda e: e.get("name", ""))

    ok, errs = validate_registry(reg, schema)
    if not ok:
        print("[INVALID REGISTRY after merge]")
        for e in errs:
            print("  -", e)
        sys.exit(1)

    if args.write:
        reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] '{entry['name']}' → {reg_path} 병합·검증 완료 ({len(reg['skills'])} entries)")
    else:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        print(f"\n(미리보기. {reg_path} 에 기록하려면 --write 추가)")


if __name__ == "__main__":
    main()
