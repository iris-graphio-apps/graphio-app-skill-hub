#!/usr/bin/env python3
"""회사 skill-hub 규약에 맞는 새 스킬 뼈대를 skills/<name>/ 에 생성.

name 규약(lowercase-hyphen, ≤64, domain prefix)을 자동 검증하고, compliant 한
SKILL.md frontmatter + 본문 스켈레톤을 만든다. (registry 등록은 description 을 채운 뒤
registry_entry.py 로 한다.)

사용:
  python scaffold_skill.py mobigen-foo                      # 현재 디렉터리를 hub 루트로
  python scaffold_skill.py graphio-bar --hub-root /path/to/company-skills
  python scaffold_skill.py mobigen-foo --desc "..." --force
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _schema import domains, infer_domain, load_schema

SCRIPTS = Path(__file__).resolve().parent

TEMPLATE = """---
name: __NAME__
description: __DESC__
---

# __NAME__

(한 줄 요약: 이 스킬이 무엇을 가능하게 하는가)

## 언제 쓰나 / 언제 안 쓰나

- **쓴다**: ... (구체적 사용자 표현/맥락)
- **안 쓴다(대신 다른 스킬)**: ...

## 사용법

1. ...

## 참고

- ...
"""


def main():
    ap = argparse.ArgumentParser(description="회사 skill-hub 규약 스캐폴더")
    ap.add_argument("name", help="스킬 이름 (domain prefix + lowercase-hyphen, 예: mobigen-foo / graphio-bar)")
    ap.add_argument("--hub-root", default=".", help="skills/ 와 registry.json 이 있는 hub 루트 (기본: 현재 디렉터리)")
    ap.add_argument("--desc", default=None, help="초기 description (미지정 시 플레이스홀더)")
    ap.add_argument("--force", action="store_true", help="기존 SKILL.md 덮어쓰기")
    args = ap.parse_args()

    schema = load_schema()
    name = args.name
    name_pat = schema["$defs"]["skillEntry"]["properties"]["name"]["pattern"]
    if not re.match(name_pat, name) or len(name) > 64:
        sys.exit(f"[ERROR] name 규약 위반(lowercase-hyphen, ≤64): {name!r}")
    dom = infer_domain(name, schema)
    if not dom:
        sys.exit(f"[ERROR] name 은 승인 domain 으로 시작해야 함. domains: {domains(schema)}  (예: mobigen-{name})")

    hub = Path(args.hub_root).resolve()
    skill_dir = hub / "skills" / name
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists() and not args.force:
        sys.exit(f"[ERROR] 이미 존재: {skill_md} (--force 로 덮어쓰기)")

    desc = args.desc or (
        f"TODO(30자 이상): {name} 가 언제 무엇을 하는지와 언제 안 쓰는지를 적는다. "
        f"약간 pushy 하게, 꺾쇠 기호 없이. domain={dom}."
    )
    body = TEMPLATE.replace("__NAME__", name).replace("__DESC__", desc)
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(body, encoding="utf-8")

    rel = skill_md.relative_to(hub)
    print(f"[OK] 생성: {rel}  (domain={dom})")
    print("\n다음 단계:")
    print(f"  1) {rel} 의 description(30–1024자, when-to+when-not, 약간 pushy, 꺾쇠 금지)과 본문을 채운다")
    print(f"  2) python {SCRIPTS / 'lint_description.py'} {skill_dir}")
    print(f"  3) python {SCRIPTS / 'registry_entry.py'} {skill_dir} --version 0.1.0 "
          f"--registry {hub / 'registry.json'} --write")
    print(f"  4) python {SCRIPTS / 'validate_registry.py'} {hub / 'registry.json'}")


if __name__ == "__main__":
    main()
