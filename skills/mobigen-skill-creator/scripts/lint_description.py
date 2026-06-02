#!/usr/bin/env python3
"""SKILL.md description 의 hub 규약 적합성 + 트리거 품질을 정적 점검.

하드 규칙(스키마): 길이 30–1024, 꺾쇠(< >) 금지 → 실패 시 exit 1.
소프트 신호(품질): when-to / when-not / pushy / 구체 트리거 토큰 → ⚠ 경고.
정밀 트리거 최적화는 공식 skill-creator 의 run_loop.py(설치되어 있을 때)에 위임.

사용:
  python lint_description.py <skill-dir | SKILL.md | description.txt>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _schema import load_schema, parse_frontmatter

WHEN_TO = ["때", "쓴다", "쓸 때", "사용", "use this", "use when", "when ", "나오면", "언급"]
WHEN_NOT = ["단,", "대신", "아니라", "안 쓴", "안쓴", "말고", "제외", "instead", "rather than", "except", "not ", "n't"]
PUSHY = ["반드시", "항상", "꼭", "로드", "make sure", "use this skill", "whenever", "나오면", "같은 표현", "even if"]


def get_description(arg: str) -> str:
    p = Path(arg)
    if p.is_dir():
        return (parse_frontmatter(p / "SKILL.md").get("description") or "").strip()
    if p.suffix.lower() == ".md":
        return (parse_frontmatter(p).get("description") or "").strip()
    return p.read_text(encoding="utf-8").strip()


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "."
    desc = get_description(arg)
    dp = load_schema()["$defs"]["skillEntry"]["properties"]["description"]
    low = desc.lower()

    length_ok = dp["minLength"] <= len(desc) <= dp["maxLength"]
    angle_ok = "<" not in desc and ">" not in desc

    print(f"description ({len(desc)}자):\n  {desc}\n")
    print("하드 규칙(스키마):")
    print(f"  {'✓' if length_ok else '✗'} 길이 {len(desc)} (허용 {dp['minLength']}–{dp['maxLength']})")
    print(f"  {'✓' if angle_ok else '✗'} 꺾쇠(< >) 미포함")

    soft = [
        (any(k in desc for k in WHEN_TO), "‘언제 쓰는지’ 신호"),
        (any(k.lower() in low for k in WHEN_NOT), "‘언제 안 쓰는지’ 신호(단,/대신/instead 등)"),
        (any(k.lower() in low for k in PUSHY), "약간 pushy(반드시/로드/whenever 등)"),
        ("'" in desc or "`" in desc or '"' in desc, "구체 트리거 토큰(따옴표/백틱 표현)"),
    ]
    print("\n트리거 품질(소프트):")
    for ok, msg in soft:
        print(f"  {'✓' if ok else '⚠'} {msg}")

    if not all(ok for ok, _ in soft):
        print("\n개선 제안: ⚠ 항목을 보완하면 과소트리거가 줄어든다. "
              "정밀 최적화는 공식 skill-creator 의 run_loop.py 사용(설치 시).")

    sys.exit(0 if (length_ok and angle_ok) else 1)


if __name__ == "__main__":
    main()
