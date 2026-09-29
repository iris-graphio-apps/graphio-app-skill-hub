#!/usr/bin/env python3
"""한국어 문서에서 기계적으로 잡히는 문제를 찾아낸다.

사람이 읽어야 판단되는 것(관용구 직역, 뜻이 통하는지)은 잡지 못한다.
여기서 나온 항목은 '확인할 곳'이지 '틀린 곳'이 아니다. 마지막에 사람이 판단한다.

사용법:
    python3 check_korean.py 파일.md [파일2.html ...]
    python3 check_korean.py 파일.md --pair 툴 도구 --pair 평가셋 "평가 세트"
"""

import argparse
import html
import re
import sys
from collections import Counter

# ── 1. 한글 문장 속에 남겨도 되는 로마자 ────────────────────────────────
# 약어와 널리 쓰이는 기술 표기. 고유명사는 아래 PROPER_NOUN에서 따로 다룬다.
KEEP_ROMAN = {
    "ai", "it", "api", "cli", "cpu", "gpu", "db", "sql", "url", "uri", "ui", "ux",
    "llm", "ml", "mcp", "rag", "sdk", "ide", "os", "http", "https", "json", "yaml",
    "csv", "pdf", "png", "svg", "html", "css", "roi", "sla", "slo", "kpi", "okr",
    "saas", "paas", "iaas", "ci", "cd", "pr", "qa", "vp", "cto", "ceo", "cfo",
    "id", "ip", "vpn", "ssh", "tls", "rest", "grpc", "eval", "pass", "npm", "git",
}

# ── 2. 한글 음차 ────────────────────────────────────────────────────────
# 원어 철자로 되돌려야 하는 것: 회사·제품·서비스 이름
PROPER_NOUN = {
    "슬랙": "Slack", "깃허브": "GitHub", "깃헙": "GitHub", "깃랩": "GitLab",
    "노션": "Notion", "지라": "Jira", "컨플루언스": "Confluence",
    "쿠버네티스": "Kubernetes", "도커": "Docker", "테라폼": "Terraform",
    "파이썬": "Python", "자바스크립트": "JavaScript", "타입스크립트": "TypeScript",
    "리액트": "React", "장고": "Django", "포스트그레": "PostgreSQL",
    "레디스": "Redis", "카프카": "Kafka", "에어플로우": "Airflow",
    "스노우플레이크": "Snowflake", "데이터브릭스": "Databricks",
    "앤트로픽": "Anthropic", "오픈에이아이": "OpenAI", "피그마": "Figma",
    "센트리": "Sentry", "데이터독": "Datadog", "그라파나": "Grafana",
}

# 한국어 뜻으로 풀어야 하는 것: 뜻이 그대로 사는 업무·기술 용어
KONGLISH = {
    "핸드오프": "이관", "컨펌": "승인", "어프루브": "승인", "어사인": "배정",
    "얼라인": "조율", "컨센서스": "합의", "디스커버리": "파악 단계",
    "프레이밍": "범위 확정", "스코프": "범위", "리커버리": "복구",
    "리드타임": "소요 기간", "팔로우업": "후속 조치", "리마인드": "다시 알림",
    "아카이빙": "보관", "액세스": "접근 권한", "셋업": "설치·설정",
    "워크스루": "훑어보기", "리딩": "읽기", "하네스": "harness",
    "시크릿": "비밀 값", "리스폰스 타임": "응답 시간", "이터레이션": "반복",
    "레버리지": "활용", "인사이트": "통찰", "니즈": "요구", "밸류": "가치",
    "이슈업": "문제 제기", "픽스": "수정", "머징": "병합", "롤백": "되돌리기",
    "트리아지": "원인 판정", "런북": "운영 매뉴얼", "유즈케이스": "후보 업무",
    "인벤토리": "목록", "베네핏": "이점", "리스크": "위험", "임팩트": "영향",
}

# ── 3. 번역투 군더더기 ──────────────────────────────────────────────────
TRANSLATIONESE = [
    (r"을 통하여|를 통하여|을 통해|를 통해", "조사로 (~로, ~에서)"),
    (r"에 대한|에 대하여|에 대해", "조사로 (~의, ~을)"),
    (r"에 있어서|에 있어", "~에서, ~할 때"),
    (r"되어지|하여지|지어지", "이중 피동 (~되다)"),
    (r"사료된다|사료됨", "~라고 본다"),
    (r"판단된다|판단됨|판단되었다", "누가 판단했는지 밝힌다"),
    (r"식별되었다|식별됨|파악되었다", "누가 찾았는지 밝힌다"),
    (r"수행되었|진행되었|이루어졌|이루어질", "누가 했는지 밝혀 능동으로"),
    (r"에 기인한|에 기인하", "~ 때문이다"),
    (r"목표로 하였|목표로 하고 있", "~하려 했다"),
    (r"할 수 있을 것으로 보인다|할 것으로 사료|될 것으로 예상된다", "짧게 단정한다"),
    (r"에 해당한다|에 해당하는", "~이다"),
    (r"라고 할 수 있다|라 할 수 있다", "군더더기. 빼고 단정한다"),
    (r"본 문서는|본 보고서는|본 파일럿은|본 프로젝트는", "이 문서는 / 이 사업은"),
    (r"[가-힣]{2,}성을 |[가-힣]{2,}성이 |[가-힣]{2,}성에 ", "~성(性): 빼도 뜻이 같으면 뺀다"),
    (r"[가-힣]{2,}적으로|[가-힣]{2,}적인 ", "~적(的): 빼도 뜻이 같으면 뺀다"),
]

# ── 4. 숫자·단위·날짜 ───────────────────────────────────────────────────
PCT_FORMS = [(r"\d\s*%", "%"), (r"\d\s*퍼센트", "퍼센트"), (r"\d\s*프로\b", "프로")]
DATE_FORMS = [
    (r"\d{4}년\s*\d{1,2}월", "2026년 7월"),
    (r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}", "2026. 7. 1"),
    (r"\d{4}-\d{2}-\d{2}", "2026-07-01"),
    (r"\d{4}/\d{1,2}/\d{1,2}", "2026/7/1"),
]

MD_FENCE = re.compile(r"^\s*(```|~~~)")
TAG = re.compile(r"<[^>]+>")
ROMAN_NEAR_HANGUL = re.compile(
    r"(?:[가-힣][^\s]{0,3}\s*\b([A-Za-z][A-Za-z_.\-]{2,})\b"
    r"|\b([A-Za-z][A-Za-z_.\-]{2,})\b\s*[^\s]{0,3}[가-힣])"
)


def load_lines(path):
    """코드 블록과 태그를 걷어낸 (줄번호, 본문) 목록을 돌려준다."""
    raw = open(path, encoding="utf-8").read()
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    src = raw.splitlines()

    # 머리말(front matter)은 문장이 아니라 값 목록이므로 건너뛴다. 첫 줄이 --- 일 때만
    # 머리말로 본다 — 본문 가운데의 --- 는 그냥 가로줄이다.
    fm_end = 0
    if src and src[0].strip() == "---":
        for n in range(1, len(src)):
            if src[n].strip() == "---":
                fm_end = n + 1
                break

    out, in_fence = [], False
    for i, line in enumerate(src, 1):
        if i <= fm_end:
            continue
        if MD_FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        text = html.unescape(TAG.sub(" ", line))
        text = re.sub(r"`[^`]*`", " ", text)          # 인라인 코드 제외
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 링크 주소 제외
        out.append((i, text))
    return out


def sentences(lines):
    """줄바꿈으로 감긴 문장을 문단 단위로 이어 붙인 뒤 문장으로 나눈다."""
    buf, start = [], None
    for no, text in lines:
        t = text.strip()
        is_break = not t or t.startswith(("#", "|", ">")) or re.match(r"^[-*+]\s|^\d+[.)]\s", t)
        if is_break:
            if buf:
                yield from _split(start, " ".join(buf))
                buf, start = [], None
            continue
        if start is None:
            start = no
        buf.append(t)
    if buf:
        yield from _split(start, " ".join(buf))


def _split(no, para):
    for s in re.split(r"(?<=[.!?])\s+", para):
        s = s.strip()
        if s:
            yield no, s


def report(title, hits, limit=12):
    if not hits:
        return 0
    print(f"\n■ {title}  ({len(hits)}건)")
    for line in hits[:limit]:
        print(f"   {line}")
    if len(hits) > limit:
        print(f"   … 외 {len(hits) - limit}건")
    return len(hits)


def check(path, pairs, max_len):
    print("=" * 66)
    print(f"점검 대상: {path}")
    print("=" * 66)
    lines = load_lines(path)
    body = " ".join(t for _, t in lines)
    total = 0

    # ① 한글 문장 속에 남은 로마자
    hits, seen = [], Counter()
    for no, text in lines:
        for m in ROMAN_NEAR_HANGUL.finditer(text):
            word = m.group(1) or m.group(2)
            if word.lower() in KEEP_ROMAN or word in PROPER_NOUN.values():
                continue
            seen[word] += 1
            if seen[word] <= 2:
                hits.append(f"{no:>4}줄  {word}")
    total += report("한글 문장 속에 남은 영어 — 뜻으로 풀거나 고유명사인지 확인", hits)

    # ② 한글 음차
    hits = [f"{no:>4}줄  {k} → {v}" for k, v in PROPER_NOUN.items()
            for no, t in lines if k in t][:40]
    total += report("고유명사 음차 — 원어 철자로", hits)

    hits = [f"{no:>4}줄  {k} → {v}" for k, v in KONGLISH.items()
            for no, t in lines if k in t][:40]
    total += report("음차한 업무·기술 용어 — 한국어 뜻으로 (분야에서 굳어진 말이면 유지)", hits)

    # ③ 용어 혼용
    hits = []
    for a, b in pairs:
        na, nb = len(re.findall(a, body)), len(re.findall(b, body))
        if na and nb:
            keep = a if na >= nb else b
            hits.append(f"{a} {na}회  ↔  {b} {nb}회   → 많은 쪽 '{keep}'으로 통일")
    total += report("한 개념을 두 단어로 부름", hits)

    # ④ 문체 혼용
    hap = len(re.findall(r"(습니다|합니다|입니다|됩니다)[.!?]", body))
    han = len(re.findall(r"(한다|된다|이다|았다|었다|없다|있다|왔다)[.!?]", body))
    gae = len(re.findall(r"(함|음|됨|임)[.!?]|(함|음|됨|임)\s*$", body))
    forms = [("합니다체", hap), ("한다체", han), ("개조식", gae)]
    used = [(n, c) for n, c in forms if c]
    hits = []
    if len(used) >= 2 and sum(c for _, c in used) >= 4:
        top = max(used, key=lambda x: x[1])
        odd = [f"{n} {c}회" for n, c in used if n != top[0]]
        hits.append(f"{top[0]} {top[1]}회 사이에 " + ", ".join(odd)
                    + f"가 섞임   → '{top[0]}'으로 통일")
    total += report("문체 혼용", hits)

    # ⑤ 긴 문장
    hits = [f"{no:>4}줄부터  {len(s)}자  {s[:38]}…"
            for no, s in sentences(lines) if len(s) > max_len]
    total += report(f"{max_len}자를 넘는 문장 — 서술어를 기준으로 자른다", hits)

    # ⑥ 번역투 군더더기
    hits, seen = [], Counter()
    for no, text in lines:
        for pat, fix in TRANSLATIONESE:
            m = re.search(pat, text)
            if m:
                seen[fix] += 1
                if seen[fix] <= 3:
                    hits.append(f"{no:>4}줄  {m.group(0).strip()}  → {fix}")
    total += report("번역투 군더더기", hits, limit=18)

    # ⑦ 숫자·단위·날짜
    hits = []
    used_pct = [(name, len(re.findall(p, body))) for p, name in PCT_FORMS]
    used_pct = [(n, c) for n, c in used_pct if c]
    if len(used_pct) > 1:
        hits.append("백분율 표기 혼용: " + ", ".join(f"{n} {c}회" for n, c in used_pct)
                    + "   → '%' 하나로")
    used_date = [(name, len(re.findall(p, body))) for p, name in DATE_FORMS]
    used_date = [(n, c) for n, c in used_date if c]
    if len(used_date) > 1:
        hits.append("날짜 표기 혼용: " + ", ".join(f"{n} {c}회" for n, c in used_date)
                    + "   → 한 가지로")
    for no, text in lines:
        for m in re.finditer(r"\d+\s+(%|퍼센트|분|초|시간|일|주|개월|년|건|명|인|원)", text):
            hits.append(f"{no:>4}줄  '{m.group(0)}' → 숫자와 단위를 붙인다")
        for m in re.finditer(r"약\s*[\d.,]+\s*[가-힣%]*\s*(정도|가량|쯤)", text):
            hits.append(f"{no:>4}줄  '{m.group(0)}' → '약'과 '정도' 중 하나만")
    total += report("숫자·단위·날짜 표기", hits, limit=15)

    # ⑧ 제목 안 같은 말 반복
    hits = []
    for no, text in lines:
        t = text.strip()
        if not (t.startswith("#") or re.match(r"^\s*\d+[.)]\s", t)):
            continue
        words = re.findall(r"[가-힣]{2,}", re.sub(r"^#+\s*", "", t))
        dup = [w for w, c in Counter(words).items() if c > 1]
        if dup:
            hits.append(f"{no:>4}줄  '{t[:40]}' 안에서 {', '.join(dup)} 반복")
    total += report("제목 안에서 같은 말 반복", hits)

    print()
    print("-" * 66)
    print("깨끗합니다. 남은 것은 사람이 읽어야 판단되는 부분입니다."
          if total == 0 else f"확인할 곳 {total}군데. 규칙에 비춰 하나씩 판단하세요.")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--pair", nargs=2, action="append", metavar=("A", "B"),
                    help="같은 뜻으로 섞어 쓴 낱말 쌍. 문서마다 바꿔 넣는다")
    ap.add_argument("--max-len", type=int, default=100, help="긴 문장 기준 글자 수")
    args = ap.parse_args()

    pairs = [tuple(p) for p in (args.pair or [])] or [
        ("툴", "도구"), ("평가셋", "평가 세트"), ("핸드오프|handoff", "이관"),
        ("유저", "사용자"), ("에러", "오류"), ("리퀘스트", "요청"),
    ]
    total = sum(check(f, pairs, args.max_len) for f in args.files)
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
