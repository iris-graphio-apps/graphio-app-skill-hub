#!/usr/bin/env python3
"""한국어 문서에서 기계적으로 잡히는 문제를 찾아낸다.

사람이 읽어야 판단되는 것(관용구 직역, 뜻이 통하는지)은 잡지 못한다.
여기서 나온 항목은 '확인할 곳'이지 '틀린 곳'이 아니다. 마지막에 사람이 판단한다.

일부러 틀리게 쓴 교육용 예시는 검사하지 않는다. 표 밖 같은 문단에서 한 줄 안의 '✗ … → ○', 줄 첫머리의 ✗ 부터
줄 첫머리의 ○ 까지, 그리고 머리에 '쓰지 말 것'이 들었거나 바로 윗줄이 <!-- style-teaching --> 인 표다.

사용법:
    python3 check_korean.py 파일.md [파일2.html ...]
    python3 check_korean.py 파일.md --pair 툴 도구 --pair 평가셋 "평가 세트"
    python3 check_korean.py --backup 고칠파일.md
    python3 check_korean.py --orig 원본.md 고친파일.md
    python3 check_korean.py --orig HEAD 고친파일.md
    python3 check_korean.py --selftest
"""

import argparse
import bisect
import contextlib
import difflib
import html
import io
import itertools
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, namedtuple
from dataclasses import dataclass
from decimal import Decimal

# ── 1. 한글 문장 속에 남겨도 되는 로마자 ────────────────────────────────
# 소문자로 적어도 그대로 두는 약어와 기술 표기.
KEEP_ROMAN = {
    "ai", "it", "api", "cli", "cpu", "gpu", "db", "sql", "url", "uri", "ui", "ux",
    "llm", "ml", "mcp", "rag", "sdk", "ide", "os", "http", "https", "json", "yaml",
    "csv", "pdf", "png", "svg", "html", "css", "roi", "sla", "slo", "kpi", "okr",
    "saas", "paas", "iaas", "ci", "cd", "pr", "qa", "vp", "cto", "ceo", "cfo",
    "id", "ip", "vpn", "ssh", "tls", "rest", "grpc", "eval", "pass", "npm", "git", "ppt", "toe",
}

# ── 2. 한글 음차 ────────────────────────────────────────────────────────
# 원어 철자로 되돌려야 하는 것: 회사·제품·서비스 이름. 정규식 → 원어 철자
PROPER_NOUN = {
    "슬랙": "Slack", "깃허브": "GitHub", "깃헙": "GitHub", "깃랩": "GitLab",
    "노션": "Notion", "(?<![가-힣])지라": "Jira", "컨플루언스": "Confluence",
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

# 음차를 피하려고 끼워 넣은 고유어 가운데 사전 뜻이 낮잡거나 여러 뜻으로 읽히는 말.
# 정규식 → 쓰려던 뜻에 맞는 말
MISFIT = {
    r"(?<![가-힣A-Za-z0-9%])(?<!(?:명|번|개|원|건|곳|회|일|달|주|년|배) )(?<!사람 )"
    r"꼴(?!찌|뚜기|등|불견|깍|딱|값|사나|사납|좋|통)": "뜻에 따라 패턴·형식·유형·형태",
    r"(?<![가-힣])(?:새|옛|기준|지금|이전|최신)\s판(?![을이]?\s?짜)"
    r"(?=(?:을|이|은|의|만|이다|입니다|보다|처럼|부터|까지[는도]?|(?:에|에서|으로|과)[는도]?)?(?:[^가-힣]|$))": "버전",
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
# 단위 글자 뒤에 조사·어미가 아닌 한글이 붙으면 '분석', '일반'처럼 다른 낱말의 첫 글자다.
NUM_SPACE_UNIT = re.compile(
    r"(?<!\d)(?<!\d[.,])\d+(?:[.,]\d+)*\s+(?:%|(?:퍼센트|분|초(?!과)|시간|일|주|개월|년|건|명|인|원)"
    r"(?=(?:(?:이었|였|입니|이에|이어|이고|이며|이나|이면|이라|이지|인데|이므|이다)[가-힣]*"
    r"|(?:에게|에서|으로|부터|까지|마다|이|가|을|를|은|는|의|에|도|만|간|씩|째|당|로|과|와|쯤|여|말|초|차|대)"
    r"[는도만]?)?(?![가-힣])))"
)

MD_FENCE = re.compile(r"^\s*(```|~~~)")
TAG = re.compile(r"<[^>]+>")
NOT_INSIDE_NAME_BEFORE = r"(?<![A-Za-z0-9_.\-/])"
NOT_INSIDE_NAME_AFTER = r"(?![A-Za-z0-9_\-/]|\.[A-Za-z0-9])"
JOINED_WORD = r"([A-Za-z]+(?:[-/][A-Za-z]+)*)"
ROMAN_WORD = NOT_INSIDE_NAME_BEFORE + JOINED_WORD + NOT_INSIDE_NAME_AFTER
ROMAN_NEAR_HANGUL = re.compile(rf"[가-힣][^\s]{{0,3}}\s*{ROMAN_WORD}|{ROMAN_WORD}\s*[^\s]{{0,3}}[가-힣]")

TEACHING_MARK = re.compile(r"<!--\s*style-teaching\s*-->")
BAD_EXAMPLE = re.compile(r"✗[^\n]*?→[ \t]*○|^[ \t]*(?:[-*+][ \t]+)?✗[^✗○]*?\n[ \t]*(?:[-*+][ \t]+)?○", re.M)


def is_teaching_table(header, prev_line):
    cells = [c.strip() for c in header.strip().strip("|").split("|")]
    return any("쓰지 말 것" in c for c in cells) or bool(TEACHING_MARK.search(prev_line))


def drop_bad_examples(para):
    masked = BAD_EXAMPLE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()),
                             "\n".join(t.replace("\n", " ") for _, t in para))
    return list(zip((no for no, _ in para), masked.split("\n")))


def load_lines(path):
    """코드 블록, 태그, 교육용 표, ✗ 예시를 걷어낸 (줄번호, 본문) 목록을 돌려준다."""
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

    out, para, in_fence, in_table, skip_table = [], [], False, False, False
    for i, line in enumerate(src, 1):
        if i <= fm_end:
            continue
        is_row, is_fence = line.lstrip().startswith("|"), bool(MD_FENCE.match(line))
        is_prose = not (is_row or is_fence or in_fence or not line.strip())
        if not is_prose:
            out += drop_bad_examples(para)
            para = []
        if is_fence:
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if is_row:
            if not in_table:
                in_table, skip_table = True, is_teaching_table(line, src[i - 2] if i > 1 else "")
            if skip_table:
                continue
        else:
            in_table = False
        text = html.unescape(TAG.sub(" ", line))
        text = re.sub(r"`[^`]*`", " ", text)          # 인라인 코드 제외
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 링크 주소 제외
        (para if is_prose else out).append((i, text))
    return out + drop_bad_examples(para)


def report(title, hits, limit=12):
    if not hits:
        return 0
    print(f"\n■ {title}  ({len(hits)}건)")
    for line in hits[:limit]:
        print(f"   {line}")
    if len(hits) > limit:
        print(f"   … 외 {len(hits) - limit}건")
    return len(hits)


def check(path, pairs):
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
            parts = re.split("[-/]", word)
            formula_or_placeholder = any(len(set(p)) < 2 for p in parts)
            if len(word) < 3 or not word.islower() or set(parts) <= KEEP_ROMAN or formula_or_placeholder:
                continue
            seen[word] += 1
            if seen[word] <= 2:
                hits.append(f"{no:>4}줄  {word}")
    total += report("한글 문장 속에 남은 영어 — 뜻으로 풀거나 고유명사인지 확인", hits)

    # ② 한글 음차
    hits = [f"{no:>4}줄  {m.group(0)} → {v}" for k, v in PROPER_NOUN.items()
            for no, t in lines if (m := re.search(k, t))][:40]
    total += report("고유명사 음차 — 원어 철자로", hits)

    hits = [f"{no:>4}줄  {k} → {v}" for k, v in KONGLISH.items()
            for no, t in lines if k in t][:40]
    total += report("음차한 업무·기술 용어 — 한국어 뜻으로 (분야에서 굳어진 말이면 유지)", hits)

    hits = [f"{no:>4}줄  {m.group(0)} → {v}" for k, v in MISFIT.items()
            for no, t in lines for m in re.finditer(k, SPAN.sub(" ", t))][:40]
    total += report("뜻이 맞지 않는 고유어 — 사전 뜻을 확인하고 쓰려던 뜻에 맞는 한자어·외래어로", hits)

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

    # ⑤ 번역투 군더더기
    hits, seen = [], Counter()
    for no, text in lines:
        for pat, fix in TRANSLATIONESE:
            m = re.search(pat, text)
            if m:
                seen[fix] += 1
                if seen[fix] <= 3:
                    hits.append(f"{no:>4}줄  {m.group(0).strip()}  → {fix}")
    total += report("번역투 군더더기", hits, limit=18)

    # ⑥ 숫자·단위·날짜
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
        for m in NUM_SPACE_UNIT.finditer(text):
            hits.append(f"{no:>4}줄  '{m.group(0)}' → 숫자와 단위를 붙인다")
        for m in re.finditer(r"약\s*[\d.,]+\s*[가-힣%]*\s*(정도|가량|쯤)", text):
            hits.append(f"{no:>4}줄  '{m.group(0)}' → '약'과 '정도' 중 하나만")
    total += report("숫자·단위·날짜 표기", hits, limit=15)

    # ⑦ 제목 안 같은 말 반복
    hits = []
    for no, text in lines:
        t = text.strip()
        if not t.startswith("#"):
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


DEFAULT_PAIRS = [
    ("툴", "도구"), ("평가셋", "평가 세트"), ("핸드오프|handoff", "이관"),
    ("유저", "사용자"), ("에러", "오류"), ("리퀘스트", "요청"),
]

Zone = namedtuple("Zone", "no kind text")
Line = namedtuple("Line", "no text")
Number = namedtuple("Number", "key text approx")

SPAN = re.compile(
    r"(?P<코드>`[^`]+`|<code\b[^>]*>.*?</code\s*>)"
    r"|(?P<주소>https?://[^\s)>\]」』\"'”’]+|(?<=\]\()[^)\s]+"
    r"|(?<![A-Za-z0-9_.@/-])(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?(?:/[^\s)>\]」』\"'”’]*)?)"
    r"|(?P<따옴표>\"[^\"]+\"|“[^”]+”|「[^」]+」|『[^』]+』"
    r"|(?<![A-Za-z0-9])'(?!\d\d(?!\d))[^']+'(?![A-Za-z])"
    r"|(?<![A-Za-z0-9])‘(?!\d\d(?!\d))[^’]+’(?![A-Za-z]))",
    re.S | re.I)
HTML_BLOCK = re.compile(r"<(table|blockquote|pre)\b[^>]*>.*?</\1\s*>", re.S | re.I)
HTML_KIND = {"table": "표", "blockquote": "인용", "pre": "코드"}
TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s")
BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d{1,9}[.)]\s|#|```|~~~|\||<)")


def block_kinds(lines):
    """마크다운(CommonMark·GFM)이 그 줄을 코드·표·인용 가운데 무엇으로 그리는지 따른다. 본문 줄은 None."""
    kinds, joined = [None] * len(lines), "\n".join(lines)
    starts = list(itertools.accumulate((len(x) + 1 for x in lines), initial=0))
    for m in HTML_BLOCK.finditer(joined):
        first, last = (bisect.bisect_right(starts, pos) - 1 for pos in (m.start(), m.end() - 1))
        kinds[first:last + 1] = [HTML_KIND[m.group(1).lower()]] * (last - first + 1)
    in_fence = in_quote = in_table = in_list = False
    for i, line in enumerate(lines):
        nxt, indent = lines[i + 1] if i + 1 < len(lines) else "", len(line.expandtabs(4)) - len(line.lstrip())
        if kinds[i]:
            in_quote = in_table = False
        elif MD_FENCE.match(line) or in_fence:
            in_fence ^= bool(MD_FENCE.match(line))
            kinds[i] = "코드"
        elif not line.strip():
            in_quote = in_table = False
        elif line.lstrip().startswith(">") or in_quote and not BLOCK_START.match(line):
            kinds[i], in_quote = "인용", True
        elif line.lstrip().startswith("|") or "|" in line and (in_table or "|" in nxt and TABLE_DELIM.match(nxt)):
            kinds[i], in_table = "표", True
        elif indent >= 4 and not in_list and (i == 0 or not lines[i - 1].strip() or kinds[i - 1] == "코드"):
            kinds[i] = "코드"
        elif LIST_ITEM.match(line):
            in_list = True
        elif indent == 0:
            in_list = False
    return kinds


def fidelity_view(text):
    lines = text.splitlines()
    fixed, prose, para = [], [], []

    def flush():
        joined = "\n".join(lines[i] for i in para)
        starts = list(itertools.accumulate((len(lines[i]) + 1 for i in para), initial=0))
        masked = list(joined)
        for m in SPAN.finditer(joined):
            no = para[bisect.bisect_right(starts, m.start()) - 1] + 1
            fixed.append(Zone(no, m.lastgroup, re.sub(r"\s*\n\s*", " ", m.group())))
            masked[m.start():m.end()] = [c if c == "\n" else " " for c in m.group()]
        prose.extend(Line(i + 1, t) for i, t in zip(para, "".join(masked).split("\n")))
        para.clear()

    for i, kind in enumerate(block_kinds(lines)):
        if kind or not lines[i].strip():
            flush()
            if kind:
                fixed.append(Zone(i + 1, kind, lines[i].rstrip()))
            else:
                prose.append(Line(i + 1, ""))
        else:
            para.append(i)
    flush()
    return fixed, prose


SCALE = {"십": 10, "백": 100, "천": 1000, "만": 10 ** 4, "억": 10 ** 8, "조": 10 ** 12}
UNIT_SAME = {"퍼센트": "%", "프로": "%", "퍼센트포인트": "%p", "pp": "%p", "주일": "주", "달": "개월", "해": "년", "살": "세"}
UNITS = ("퍼센트포인트|%p|pp|퍼센트|프로|%|원|달러|엔|유로|위안|분기|반기|시간|주일|개월|세기|초|분|시|일|주|달|년|월|세|살"
         "|배|km|cm|mm|kg|GB|MB|KB|TB|ms")
COUNTERS = "가지|군데|단계|차례|사람|건|곳|개|명|인|번|회|차|대|장|권|부|편|쪽|줄|항|팀|해|분"
# 단위 뒤에 조사·어미가 아닌 한글이 붙으면 단위가 아니라 다른 낱말의 첫 글자다('세 개발자'의 '개').
UNIT_END = (r"(?=[^가-힣]|$|(?<=[^가-힣])|이었|였|입니|이에|이어|이고|이며|이나|이면|이라|이지|인데|이므|이다|에서|에게|으로|부터|까지"
            r"|마다|정도|가량|남짓|내외|안팎|이상|이하|미만|초과|짜리|동안|전후|[이가을를은는의에도만과와로씩째차당간쯤여뿐밖나대말초께경후전다라야요지])")
APPROX_AFTER = r"\s?(?:정도|쯤|가량|남짓|내외|안팎)"
NUMERIC_DATE = re.compile(r"(?<![\d.])((?:19|20)\d\d)\s*([.\-/])\s*(\d{1,2})"
                  r"(?:\s*\2\s*(\d{1,2})(?!\d)|(?=\.?(?:[^\d.가-힣]|$)|\.[가-힣]))")
NUMBER = re.compile(r"(?P<sign>(?<![A-Za-z0-9.])[-−–])?(?P<num>\d+(?:\.\d+){2,}|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
                    rf"(?P<approx>여(?=\s?(?:[십백천만억조]|{UNITS}|{COUNTERS})|[^가-힣]|$))?"
                    rf"(?:\s?(?P<scale>[십백천]?[만억조]|[백천](?=\s?(?:{UNITS}|{COUNTERS})|[^가-힣]|$)))?"
                    rf"(?:\s?(?P<unit>{UNITS}|{COUNTERS}){UNIT_END})?(?P<after>(?:(?<=\d)\s?[가-힣%]{{1,3}})?{APPROX_AFTER})?")
KOR_NUMBER = re.compile(r"(?<![가-힣])(?P<tens>열|스물|스무|서른|마흔|쉰)?(?P<ones>한|두|세|네|다섯|여섯|일곱|여덟|아홉)?"
                        r"(?<=[가-힣]) ?(?P<unit>가지|군데|차례|사람|시간|개|명|곳|건|번|배|달|해|살|권|장|주|팀|분)"
                        rf"{UNIT_END}(?P<after>{APPROX_AFTER})?")
KOR_VALUE = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9,
             "열": 10, "스물": 20, "스무": 20, "서른": 30, "마흔": 40, "쉰": 50}
APPROX_BEFORE = re.compile(r"(?<![가-힣])(?:약|대략) ?$")
RANGE = re.compile(r"\s*[~∼〜–-]\s*")


def unit_key(unit):
    """세는 말(건·곳·명)은 바로잡느라 바꿔 쓰는 일이 많아 단위가 없는 것과 같게 본다."""
    unit = UNIT_SAME.get(unit or "", unit or "")
    return "" if re.fullmatch(COUNTERS, unit) else unit


@dataclass
class Found:
    start: int
    end: int
    sign: str
    value: object
    scale: int
    unit: str
    shown: str
    approx: bool


def value_key(value, scale, unit):
    """단위·배수가 없는 소수는 판 번호일 수 있어 표기 그대로('3.10'과 '3.1'은 다르다), 양은 값으로 견준다."""
    if isinstance(value, str):
        return value
    return f"{value:f}" if scale == 1 and not unit else f"{(value * scale).normalize():f}"


def numbers_in(text):
    found, taken = [], set()

    def add(m, sign, value, scale, approx):
        before = APPROX_BEFORE.search(text[:m.start()])
        found.append(Found(m.start(), m.end(), sign, value, scale, m.group("unit"),
                           text[(before or m).start():m.end()].strip(), bool(approx or before or m.group("after"))))

    for m in NUMERIC_DATE.finditer(text):
        found += [Found(m.start(), m.end(), "", Decimal(v), 1, u, v + u, False)
                  for v, u in zip(m.group(1, 3, 4), "년월일") if v]
        taken.update(range(m.start(), m.end()))
    for m in NUMBER.finditer(text):
        if m.start() not in taken:
            num, scale = m.group("num"), m.group("scale") or ""
            add(m, "-" if m.group("sign") else "", num if num.count(".") > 1 else Decimal(num.replace(",", "")),
                SCALE[scale[-1]] * SCALE.get(scale[:-1], 1) if scale else 1, m.group("approx"))
    for m in KOR_NUMBER.finditer(text):
        add(m, "", Decimal(KOR_VALUE.get(m.group("tens"), 0) + KOR_VALUE.get(m.group("ones"), 0)), 1, False)
    found.sort(key=lambda f: f.start)
    for a, b in zip(found, found[1:]):  # '4~6월'의 4는 뒤 숫자의 배수와 단위를 함께 쓴다
        if not a.unit and a.scale == 1 and RANGE.fullmatch(text[a.end:b.start]):
            a.scale, a.unit = b.scale, b.unit
    return [Number((f.sign, value_key(f.value, f.scale, f.unit), unit_key(f.unit)), f.shown, f.approx) for f in found]


# 한 정규식으로 묶어 앞에 둔 것이 먼저 잡히므로 순서가 뜻을 정한다('불가능'은 '불가'보다 앞에 둔다).
RIEUL_FINAL = "[" + "".join(chr(0xAC00 + 28 * i + 8) for i in range(19 * 21)) + "]"
NOUN_MYEON = "화|측|전|이|표|국|장|방|정|반|단|내|외|지|평|도|수|체|대|서|당|직|양|앞|뒷|일|라|냉|다"
MARKERS = [
    (("판단",), r"것으로 ?판단|판단(?:된다|됩니다|됨|되었|됐|되며|되어)|사료(?:된다|됩니다|됨|되었|됐|되며)"
              r"|(?:로|고) (?:본다|봅니다|봄|보았|봤)"),
    (("전언",), r"것으로 ?알려|알려(?:져|졌|진)"),
    (("출처",), r"따르면|밝혔|밝힌"),
    (("추측",), r"것으로 ?(?:보[이인임여였]|추정|예상|전망|관측)|(?:처럼|듯이) ?보[이인임여였]|지도 모[르른를]|지도 몰라|것 ?같|듯"
              r"|(?<!을 )(?<!를 )보(?:인다|입니다|이며|이고|임|였|여(?! ?주))|추정|예상"),
    (("가능", "부정"), r"수(?:도)? 없|불가능"),
    (("가능",), r"수(?:도)? 있|가능"),
    (("미래",), rf"(?<={RIEUL_FINAL}) 것(?:이다|입니다|임|이며|이고|이라|이었|이므)"),
    (("예정",), r"예정"),
    (("검토 중",), r"검토 ?중"),
    (("부정",), r"(?<!까)지 ?(?:마(?:세요|십시오|시오|라|요)?|말(?:고|아|라|자|기| ?것)?)(?![가-힣])|불(?:가|필요|확실)|미(?:확인|확정|정)|않|없|아[니닌닐님닙]"
              r"|못(?= |[하한할함합해했])|(?<![가-힣])안(?= |[되돼된될됨됩])"),
    (("한정 조건",), r"경우에만|경우에 ?한(?:해|하여)|에 ?한(?:해|하여)|때(?:에)?만"),
    (("조건",), r"경우(?:에는?|엔)?(?=[\s,]|$)|(?:(?<=[가-힣0-9A-Za-z%])[가-힣]|(?<![가-힣0-9A-Za-z%])"
              rf"(?!(?:{NOUN_MYEON})면)[가-힣])면(?=[\s,]|$)"),
    (("이상",), r"이상(?=[이을의은도에으만과와]|[^가-힣]|$)"),
    (("이하",), r"이하(?=[이을의은도에로만]|[^가-힣]|$)"),
    (("미만",), r"미만"),
    (("초과",), r"초과"),
    (("최대",), r"최대(?!화)"),
    (("최소",), r"최소(?!화)"),
    (("거의",), r"거의"),
    (("대부분",), r"대부분"),
]
MARKER = re.compile("|".join(f"(?P<m{i}>{p})" for i, (_, p) in enumerate(MARKERS)))
MARKER_CATEGORY = {**dict.fromkeys(("추측", "가능", "미래", "예정", "검토 중"), "확정 수준 표지"), "부정": "부정 표지",
                   **dict.fromkeys(("조건", "한정 조건"), "조건 표지"), **dict.fromkeys(("판단", "전언", "출처"), "출처·전언 표지"),
                   **dict.fromkeys(("이상", "이하", "미만", "초과", "최대", "최소", "거의", "대부분"), "한정어")}


def markers_in(lines):
    count, words = Counter(), {}
    for line in lines:
        for m in MARKER.finditer(line.text):
            for meaning in MARKERS[int(m.lastgroup[1:])][0]:
                count[meaning] += 1
                words.setdefault(meaning, []).append(m.group().strip())
    return count, words


def changed_blocks(a, b):
    sm = difflib.SequenceMatcher(None, [x.text for x in a], [x.text for x in b], autojunk=False)
    return [(a[i1:i2], b[j1:j2]) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]


def where(olds, news):
    lines = news or olds
    span = f"{lines[0].no}" if len(lines) == 1 else f"{lines[0].no}~{lines[-1].no}"
    return f"{span:>4}줄  " if news else f"원문 {span}줄  "


def unmatched(xs, ys):
    pool, out = Counter(y.key for y in ys), []
    for x in xs:
        if pool[x.key]:
            pool[x.key] -= 1
        else:
            out.append(x)
    return out


def compare(orig_name, orig_text, path):
    print("=" * 66)
    print(f"점검 대상: {path}")
    print(f"원문: {orig_name}")
    print("=" * 66)
    (fixed_a, prose_a), (fixed_b, prose_b) = fidelity_view(orig_text), fidelity_view(read_text(path))
    total = 0

    hits = [(f"{n.no:>4}줄  " if n else f"원문 {o.no}줄  ") + f"{(n or o).kind}  "
            + " → ".join(f"'{x.text}'" if x else "(없음)" for x in (o, n))
            for olds, news in changed_blocks(fixed_a, fixed_b)
            for o, n in itertools.zip_longest(olds, news)]
    total += report("글자가 바뀐 고정 구역(코드·표·인용·따옴표·주소)", hits)

    values, order, approx = [], [], []
    marks = {}
    for olds, news in changed_blocks(prose_a, prose_b):
        at = where(olds, news)
        a = [n for line in olds for n in numbers_in(line.text)]
        b = [n for line in news for n in numbers_in(line.text)]
        gone, came = unmatched(a, b), unmatched(b, a)
        if gone or came:
            values.append(at + f"{', '.join(n.text for n in gone) or '(없음)'} → {', '.join(n.text for n in came) or '(없음)'}")
        elif [n.key for n in a] != [n.key for n in b]:
            order.append(at + f"{', '.join(n.text for n in a)} → {', '.join(n.text for n in b)}")
        else:
            approx += [at + f"'{x.text}' → '{y.text}'" for x, y in zip(a, b) if x.approx != y.approx]
        (ca, wa), (cb, wb) = markers_in(olds), markers_in(news)
        for meaning in sorted(ca.keys() | cb.keys(), key=list(MARKER_CATEGORY).index):
            if ca[meaning] != cb[meaning]:
                shown = "·".join(dict.fromkeys(wa.get(meaning, []) + wb.get(meaning, [])))
                marks.setdefault(MARKER_CATEGORY[meaning], {}).setdefault(at, []).append(
                    f"{shown} {ca[meaning]}→{cb[meaning]}")
    total += report("원문과 다른 숫자", values)
    total += report("자리가 바뀐 숫자", order)
    total += report("어림 표지가 달라진 숫자", approx)
    for category in dict.fromkeys(MARKER_CATEGORY.values()):
        total += report(f"{category}가 달라진 곳", [at + ", ".join(d) for at, d in marks.get(category, {}).items()])

    print()
    print("-" * 66)
    print(f"원문과 달라진 곳 {total}군데. "
          + ("새로 덧붙인 주장처럼 기계가 잡지 못하는 것은 사람이 읽어 확인하세요." if total == 0
             else "원문의 사실·인용·확정 수준을 바꿨는지 하나씩 확인하세요."))
    return total


class SourceError(Exception):
    pass


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def git_head(path):
    folder, name = os.path.split(os.path.abspath(path))
    try:
        r = subprocess.run(["git", "-C", folder, "cat-file", "blob", f"HEAD:./{name}"], capture_output=True)
    except OSError as e:
        return None, f"git 을 실행하지 못함: {e.strerror}"
    if r.returncode:
        return None, (r.stderr.decode(errors="replace").strip().splitlines() or [f"git exit {r.returncode}"])[-1]
    return r.stdout, None


def backup(path, stamp=None):
    with open(path, "rb") as f:
        data = f.read()
    if git_head(path)[0] == data:
        print(f"백업 건너뜀: {path} (git HEAD 와 같음)")
        return
    target = f"{path}.bak.{stamp or time.strftime('%Y%m%d%H%M%S')}"
    try:
        with open(target, "xb") as f:
            f.write(data)
    except FileExistsError:
        with open(target, "rb") as f:
            if f.read() != data:
                raise SourceError(f"이름이 같고 내용이 다른 백업이 이미 있음: {target}. 1초 뒤에 다시 돌리세요.")
    print(f"백업: {target}")


def read_orig(orig, path):
    if orig != "HEAD":
        return orig, read_text(orig)
    data, why = git_head(path)
    if data is None:
        raise SourceError(f"원본을 git HEAD 에서 꺼내지 못함: {path} ({why}). 1단계에서 만든 백업을 원본으로 주세요.")
    return f"git HEAD 의 {path}", data.decode("utf-8")


def git_selftest():
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    fails = []
    with tempfile.TemporaryDirectory() as d:
        def git(cwd, *args):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                           cwd=os.path.join(d, cwd), env=env, check=True, capture_output=True)

        def write(name, text):
            path = os.path.join(d, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            return path

        def cli(*args):
            r = subprocess.run([sys.executable, os.path.abspath(__file__), *args],
                               cwd=d, env=env, capture_output=True, text=True)
            return r.returncode, r.stdout + r.stderr

        def baks(path):
            folder, name = os.path.split(path)
            return [os.path.join(folder, n) for n in os.listdir(folder) if n.startswith(name + ".bak.")]

        os.makedirs(os.path.join(d, "repo"))
        git("repo", "init", "-q")
        for name in ("kept.md", "edited.md", "alias.md"):
            write(f"repo/{name}", "| 신규 모델 | 보류 |\n")
        git("repo", "add", ".")
        git("repo", "commit", "-qm", "c")
        os.makedirs(os.path.join(d, "repo/inner"))
        git("repo/inner", "init", "-q")
        write("repo/inner/kept.md", "안쪽 저장소에 커밋한 글\n")
        git("repo/inner", "add", "kept.md")
        git("repo/inner", "commit", "-qm", "c")
        write("repo/edited.md", "| 신규 모델 | 승인 |\n")
        write("repo/alias.md", "| 신규 모델 | 승인 |\n")
        git("repo", "config", "status.showUntrackedFiles", "no")
        alias = os.path.join(d, "repo/ALIAS.md")
        cases = [
            ("커밋한 그대로인 파일", "repo/kept.md", False),
            ("안쪽 저장소에 커밋한 그대로인 파일", "repo/inner/kept.md", False),
            ("커밋한 뒤 고친 파일", "repo/edited.md", True),
            ("showUntrackedFiles=no 저장소의 커밋하지 않은 파일", write("repo/new.md", "새 글\n"), True),
            ("안쪽 저장소의 커밋하지 않은 파일", write("repo/inner/new.md", "새 글\n"), True),
            ("저장소 밖의 파일", write("outside/doc.md", "밖의 글\n"), True),
        ]
        if os.path.exists(alias):
            cases.append(("고친 파일을 대소문자가 다른 경로로 부름", alias, True))
        for desc, name, expect_copy in cases:
            path = os.path.join(d, name)
            code, out = cli("--backup", path)
            made = baks(path)
            if expect_copy:
                with open(path, "rb") as a:
                    same = len(made) == 1 and open(made[0], "rb").read() == a.read()
                ok = code == 0 and same and re.search(r"^백업: .+\.bak\.\d{14}$", out, re.M)
            else:
                ok = code == 0 and not made and "백업 건너뜀" in out
            if not ok:
                fails.append(f"--backup {desc}: exit {code}, 백업 {len(made)}개, 출력 {out.strip()!r}")

        def keeps_older_backup():
            target = os.path.join(d, "repo/edited.md.bak.20000101000000")
            with open(target, "w", encoding="utf-8") as f:
                f.write("먼저 있던 백업\n")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    backup(os.path.join(d, "repo/edited.md"), stamp="20000101000000")
                return "--backup 같은 시각의 다른 백업을 덮어쓰려 해도 멈추지 않음"
            except SourceError:
                return None if read_text(target) == "먼저 있던 백업\n" else "--backup 같은 시각의 다른 백업을 덮어씀"

        def orig_head_reads_commit():
            before = sorted(os.walk(d))
            code, out = cli("--orig", "HEAD", os.path.join(d, "repo/edited.md"))
            if code != 1 or "■ 글자가 바뀐 고정 구역" not in out or sorted(os.walk(d)) != before:
                return f"--orig HEAD 커밋한 뒤 고친 파일: exit {code}, 출력 {out.strip()[-80:]!r}"

        def orig_head_refuses_untracked():
            code, out = cli("--orig", "HEAD", os.path.join(d, "repo/new.md"))
            if code != 2 or "git HEAD" not in out:
                return f"--orig HEAD 커밋하지 않은 파일: exit {code}, 출력 {out.strip()!r}"

        extra = (keeps_older_backup, orig_head_reads_commit, orig_head_refuses_untracked)
        fails += [f for f in (test() for test in extra) if f]
    return len(cases) + len(extra), fails


# ── 자체 시험 ───────────────────────────────────────────────────────────
# SKILL.md 1번·5번 표의 행: (보고 제목 앞부분, 쓰지 말 것 칸, 한국어·고침 칸)
SELFTEST_CASES = [
    ("음차한 업무", "컨펌 / 어프루브", "승인"),
    ("음차한 업무", "어사인", "배정"),
    ("음차한 업무", "얼라인", "조율"),
    ("음차한 업무", "핸드오프", "이관"),
    ("음차한 업무", "디스커버리", "파악 단계"),
    ("음차한 업무", "프레이밍", "범위 확정"),
    ("음차한 업무", "스코프", "범위"),
    ("음차한 업무", "트리아지", "원인 판정"),
    ("음차한 업무", "런북", "운영 매뉴얼"),
    ("음차한 업무", "유즈케이스", "후보 업무"),
    ("음차한 업무", "인벤토리", "목록"),
    ("음차한 업무", "셋업 / 아카이빙", "설치·설정 / 보관"),
    ("번역투", "~을 통해 / ~를 통하여", "조사로 — ~로, ~에서"),
    ("번역투", "~에 대한 / ~에 대하여", "조사로 — ~의, ~을"),
    ("번역투", "~에 있어서", "~에서, ~할 때"),
    ("번역투", "~되어지다", "이중 피동 — ~되다"),
    ("번역투", "~에 기인한 것으로", "~ 때문이다"),
    ("번역투", "~하는 것을 목표로 하였다", "~하려 했다"),
    ("번역투", "~라고 할 수 있다", "빼고 단정한다"),
    ("번역투", "~에 해당한다", "~이다"),
    ("번역투", "본 문서는 / 본 파일럿은", "이 문서는 / 이 사업은"),
]

# 같은 표에서 정규식 없이 사람이 판단하는 행. 자체 시험에서 뺀다.
HUMAN_JUDGMENT = [
    "씬 슬라이스 / 얇은 동작 버전", "사람 보정 기준",
    "~을 가지고 있다", "~에 의해 (피동)", "~에서의 / ~으로의",
    "~할 수 있다 남발", "그 / 그녀 / 그것 (대명사 직역)", "~들 (복수 남발)",
]

CHECK_MUST_HIT = [
    ("한글 문장 속에 남은 영어", "이번 분기 retention 지표가 떨어졌다."),
    ("고유명사 음차", "지라 티켓을 새로 만들었다."),
    ("제목 안에서 같은 말 반복", "## 도구 2 · 도구 설계"),
    ("숫자·단위·날짜", "응답에 1.1 분이 걸렸고 85 %가 만족했다."),
    ("음차한 업무", "| 나쁜 예 | 좋은 예 |\n|---|---|\n| 컨펌 받음 | 승인 받음 |"),
    ("음차한 업무", "## 지원 현황\n\n- A: ○\n- B: ✗\n- C: 스코프 밖이라 컨펌을 받는다."),
    ("음차한 업무", "표에서 ✗ 는 미지원을 뜻한다.\n이번 배포는 팀장 컨펌을 받은 뒤 슬랙에 알린다."),
    ("음차한 업무", "| 항목 | 지원 여부 |\n|---|---|\n| 가 기능 | ✗ |\n| 나 기능 | 컨펌 필요 |\n| 다 기능 | 슬랙 연동 |"),
    ("한글 문장 속에 남은 영어", "OECD는 이를 green stimulus packages로 표현했다."),
    ("숫자·단위·날짜", "취업률은 일자리취업,13.4 % 였다."),
    *(("한글 문장 속에 남은 영어", t) for t in (
        "이번 분기의 no-go 조건을 정리했다.", "속도와 비용의 trade-off를 따져 보았다.",
        "먼저 end-to-end 시험을 돌린다.", "관리자에게 read/write 권한을 준다.", "학습 자료는 train/test 로 나눈다.")),
    *(("숫자·단위·날짜", t) for t in (
        "참석자는 5 명이었다.", "접수된 문의는 총 12 건입니다.", "직원 5 명에게 물었다.", "처리에는 3 일이나 걸렸다.",
        "점검은 3 일마다 한다.", "대기는 30 분이면 끝난다.", "회의는 10 분쯤 늦게 시작했다.", "담당자 2 명과 면담했다.",
        "(단위: 억 원, ’19 년말 기준)")),
    ("음차한 업무", "| 형태 | 예 | 설명 |\n|---|---|---|\n| 요약 | 주간 보고 | 핸드오프 전에 컨펌을 받는다 |"),
    ("음차한 업무", "- 로그인: ○\n- 결제: ✗ (핸드오프 컨펌 대기)\n- 알림: ○"),
    ("음차한 업무", "✗ 표시는 아직 붙이지 못한 기능이다. 슬랙 연동은 핸드오프 컨펌을 받았다. ○ 표시는 끝난 기능이다."),
]

CHECK_MUST_PASS = [
    "No-code 도구와 OECD.STAT 자료, snake_case 이름을 함께 본다.",
    "OECD 회원국의 GDP 성장률은 Bloomberg 자료로 확인했다.",
    "비가 올지라도 회의는 예정대로 연다.",
    "타겟 그룹에 소구되는 메시지라면 먼저 보여 준다.",
    "파일에 없는 것은 한국어 어문 규범 전문(korean.go.kr/kornorms)에서 찾는다.",
    "3. **그 밖에 한국어로 뜻이 서는 말인가** → 한국어로 푼다.",
    "2026-11-11 분석 결과를 정리했다.",
    "| 표현 | 쓰지 말 것 |\n|---|---|\n| 승인 | 컨펌 |",
    "<!-- style-teaching -->\n| 나쁜 예 | 좋은 예 |\n|---|---|\n| 컨펌 받음 | 승인 받음 |",
    "기준은 10 초과로 정했다. 10 초과 시 경고한다.",
    "주소는 https://localhost:8080/admin 이고 설정 파일은 config.yaml 이다.",
    "투자 비율(a/b)과 증감(b-a)을 1페이지 ppt로 정리했다. (단위: 백만toe)",
    "vvvvvv가)v○○○○○",
]

MISFIT_MUST_HIT = [
    "구조 꼴을 정한다.", "임시 꼴로 둔다.", "카드 꼴로 보인다.", "이 꼴로 적는다.", "URL 꼴 낱말을 찾는다.",
    "「꼴」을 피하라 했는데 카드 꼴로 썼다.",
    "새 판으로 바꿨다.", "지금 판은 느리다.", "옛 판의 기록을 본다.", "기준 판과 견준다.", "이전 판에서는 없었다.",
    "이것이 새 판이다.", "지금 판입니다.", "새 판보다 빠른 것은 없다.", "새 판부터 적용한다.",
    "이전 판까지는 문제가 없었다.", "옛 판처럼 느리지는 않다.",
    "'24년 설계 꼴을 유지하고 '25년에도 그대로 쓴다.", "‘24년 설계 꼴을 유지하고 ’25년에 새 판으로 바꾼다.",
    "it's 꼴이 이상하다고 don't 라고 적었다.",
]

MISFIT_MUST_PASS = [
    "글꼴을 바꾼다.", "꼴등을 했다.", "꼴불견이다.", "침을 꼴깍 삼켰다.", "꼴값을 한다.", "볼꼴 사납다.",
    "세모꼴, 네모꼴, 마름모꼴, 사다리꼴을 그린다.", "한 달에 한 번꼴로 연다.", "한 사람에 만 원꼴이다.",
    "밤을 꼴딱 새웠다.", "그 모습이 꼴사나웠다.", "하는 짓이 꼴사납다.", "꼴좋게 됐다.", "저 꼴통이 또 왔다.",
    "자료가 하루에 2GB꼴로 쌓인다.", "매출이 해마다 10%꼴로 늘었다.", "열 명 가운데 한 명 꼴로 답했다.",
    "판단했다.", "판매가 늘었다.", "제2판을 냈다.", "개정판과 초판을 견준다.", "두 판을 이겼다.",
    "이 판에 끼어들다.", "판이 커졌다.", "업계가 새 판을 짜고 있다.", "새 판이 짜였다.", "새 판단을 내렸다.",
    "반도체 새 판도, 누가 쥐나.",
    "「꼴」은 낮잡는 말이다.", '"새 판"은 버전으로 고친다.', "“지금 판”을 쓰지 않는다.",
    "'꼴'을 피한다.", "‘옛 판’이라 적지 않는다.",
]

FIDELITY_ORIG = """# 파일럿 결과

정확도는 87퍼센트, 재현율은 61.0%였고 표본은 1200건이다. 1.1 분 걸렸고 2026. 7. 1에 시작한다.
신규 모델 도입은 아직 검토 중이다. 응답 속도는 개선된 것으로 보인다.
외부 업체는 도입하지 않는다. 효과는 확정되지 않았다. 약 500건 정도를 다시 봤다.
계약 3건은 슬랙으로 알린다. 이 양식이 정답은 아니지만 쓸 만하다.
`--limit` 값과 자료 주소 https://example.com/pilot 는 그대로 둔다.

| 항목 | 상태 |
|---|---|
| 신규 모델 | 보류 |

> 고객은 답이 느리다고 말했다.

```bash
python3 run.py --limit 100
```"""

FIDELITY_MUST_PASS = [
    ("87퍼센트, 재현율은 61.0%였고 표본은 1200건이다. 1.1 분 걸렸고 2026. 7. 1에",
     "87%, 재현율은 61%였고 표본은 1,200건이다. 1.1분 걸렸고 2026-07-01에"),
    ("2026. 7. 1에", "2026.07.01에"),
    ("약 500건 정도를", "약 500건을"),
    ("슬랙으로", "Slack으로"),
    ("응답 속도는", "응답 속도가"),
    ("효과는 확정되지 않았다", "효과를 확정하지 못했다"),
    ("정답은 아니지만", "정답은 아닙니다. 그래도"),
    ("계약 3건은", "3건의 계약은"),
]

FIDELITY_MUST_HIT = [
    ("글자가 바뀐 고정 구역", "| 신규 모델 | 보류 |", "| 신규 모델 | 승인 |"),
    ("글자가 바뀐 고정 구역", "답이 느리다", "답이 매우 느리다"),
    ("글자가 바뀐 고정 구역", "run.py", "main.py"),
    ("글자가 바뀐 고정 구역", "`--limit`", "`--max`"),
    ("글자가 바뀐 고정 구역", "example.com/pilot", "example.com/trial"),
    *(("글자가 바뀐 고정 구역", "개선된", f"{q[0]}업계 최고{q[1]} 수준으로 개선된")
      for q in ('""', "“”", "''", "‘’", "「」")),
    ("원문과 다른 숫자", "개선된", "30% 개선된"),
    ("원문과 다른 숫자", "표본은 1200건이다. ", ""),
    ("어림 표지가 달라진 숫자", "약 500건 정도를", "500건을"),
    ("확정 수준 표지", "아직 검토 중이다", "확정했다"),
    ("확정 수준 표지", "개선된 것으로 보인다", "개선되었다"),
    ("확정 수준 표지", "도입하지 않는다", "도입하지 않을 것이다"),
    ("부정 표지", "도입하지 않는다", "도입한다"),
]

FIDELITY_DOC_HIT = [
    ("확정 수준 표지", "응답 속도는 개선된 듯하다.\n비용 절감 효과에 대한 확인이 가능하다.",
     "응답 속도는 개선되었다.\n비용 절감 효과를 확인할 수 있다."),
    ("확정 수준 표지", "응답 속도는 개선된 듯하다.\n\n오류율은 줄었다.", "응답 속도는 개선되었다.\n\n오류율은 줄어든 듯하다."),
    ("원문과 다른 숫자", "2026. 7. 1에 시작한다.", "2027. 7. 1에 시작한다."),
    ("원문과 다른 숫자", "영업이익은 전년보다 -3.2% 줄었다.", "영업이익은 전년보다 3.2% 줄었다."),
    ("원문과 다른 숫자", "응답이 3.2초에서 0.8초로 줄었다.", "응답이 3.2분에서 0.8초로 줄었다."),
    ("원문과 다른 숫자", "1분기 12억을 썼다.", "1분기 12조를 썼다."),
    ("원문과 다른 숫자", "표본은 1200건이다.", "표본은 1200만 건이다."),
    ("원문과 다른 숫자", "부서 3건 가운데 두 곳에서 줄었다.", "부서 네 곳 가운데 두 곳에서 줄었다."),
    ("원문과 다른 숫자", "처리량은 두 배로 늘었다.", "처리량은 세 배로 늘었다."),
    ("원문과 다른 숫자", "런타임은 Python 3.10을 쓴다.", "런타임은 Python 3.1을 쓴다."),
    ("원문과 다른 숫자", "약 500건을 봤다. 결과는 1200건이다.", "약 500건을 봤다. 결과는 500건이다."),
    ("자리가 바뀐 숫자", "A안 찬성은 30%, B안 찬성은 70%다.", "A안 찬성은 70%, B안 찬성은 30%다."),
    ("어림 표지가 달라진 숫자", "500여건을 다시 봤다.", "500건을 다시 봤다."),
    ("부정 표지", "운영 환경에서는 이 옵션을 켜지 마세요.", "운영 환경에서는 이 옵션을 켜세요."),
    ("부정 표지", "외부 공개는 불가하다.", "외부 공개는 가능하다."),
    ("부정 표지", "효과는 아직 미확인 상태다.", "효과는 확인된 상태다."),
    ("부정 표지", "- 신규 모델은 도입하지 말 것", "- 신규 모델은 도입할 것"),
    ("조건 표지", "예산이 승인되면 6월에 도입한다.", "6월에 도입한다."),
    ("조건 표지", "장애가 났을 때만 수동으로 되돌린다.", "장애가 나면 수동으로 되돌린다."),
    ("출처·전언 표지", "업계 조사에 따르면 이용률은 61%다.", "이용률은 61%다."),
    ("출처·전언 표지", "이 방식은 문의에 통한다고 알려져 있다.", "이 방식은 문의에 통한다."),
    ("출처·전언 표지", "효과가 있다고 판단된다.", "효과가 있다."),
    ("확정 수준 표지", "원인은 캐시 설정일지도 모른다.", "원인은 캐시 설정이다."),
    ("확정 수준 표지", "- 응답 속도는 나아진 것처럼 보였음", "- 응답 속도는 나아졌음"),
    ("한정어", "설문에는 1,000명 이상이 참여했다.", "설문에는 1,000명이 참여했다."),
    ("한정어", "처리 시간을 최대 30% 줄인다.", "처리 시간을 30% 줄인다."),
    ("한정어", "정확도는 거의 90%에 이른다.", "정확도는 90%에 이른다."),
    ("한정어", "대부분의 문의에 통한다.", "모든 문의에 통한다."),
    ("글자가 바뀐 고정 구역", '고객은 "응답이 느리고 화면이\n자주 멈춘다"고 말했다.',
     '고객은 "응답이 느리고 화면이\n가끔 멈춘다"고 말했다.'),
    ("글자가 바뀐 고정 구역", "담당자는 「야간 문의는\n다음 분기에 다룬다」고 답했다.",
     "담당자는 「야간 문의는\n이번 분기에 다룬다」고 답했다."),
    ("글자가 바뀐 고정 구역", "> 고객은 답이 느리고\n화면이 자주 멈춘다고 말했다.", "> 고객은 답이 느리고\n화면이 가끔 멈춘다고 말했다."),
    ("글자가 바뀐 고정 구역", "명령은 아래와 같다.\n\n    make deploy --mode safe\n\n끝.",
     "명령은 아래와 같다.\n\n    make deploy --mode fast\n\n끝."),
    ("글자가 바뀐 고정 구역", "항목 | 상태\n---|---\n신규 모델 | 보류", "항목 | 상태\n---|---\n신규 모델 | 승인"),
    ("글자가 바뀐 고정 구역", "<table>\n<tr><td>신규 모델</td><td>보류</td></tr>\n</table>",
     "<table>\n<tr><td>신규 모델</td><td>승인</td></tr>\n</table>"),
    ("글자가 바뀐 고정 구역", "<blockquote>고객은 답이 느리다고 말했다.</blockquote>",
     "<blockquote>고객은 답이 매우 느리다고 말했다.</blockquote>"),
    ("글자가 바뀐 고정 구역", "<pre>python3 run.py --mode dry</pre>", "<pre>python3 run.py --mode live</pre>"),
    ("글자가 바뀐 고정 구역", "자료는 docs.example.com/pilot 에 있다.", "자료는 docs.example.com/trial 에 있다."),
    ("글자가 바뀐 고정 구역", "자세한 내용은 [보고서](./reports/pilot.md)에 있다.", "자세한 내용은 [보고서](./reports/trial.md)에 있다."),
]

FIDELITY_DOC_PASS = [
    ("야간 배치는 자동화가 가능하다.\n\n추가 인력은 불필요하다.\n\n재시도는 불가능하다.",
     "야간 배치는 자동화할 수 있다.\n\n추가 인력은 필요 없다.\n\n재시도할 수 없다."),
    ("부서 3건 가운데 두 곳에서 줄었다.", "부서 세 곳 가운데 두 곳에서 줄었다."),
    ("일정은 2026. 7. 1에 시작해 4월부터 6월까지 돈다.", "일정은 2026-07-01에 시작해 4~6월에 돈다."),
    ("## 도구 2 · 도구 설계", "## 02 · 도구 설계"),
    ("신청은 15일까지 마감하고 예산은 이달까지 마련한다.", "신청은 15일에 마감하고 예산은 이달에 마련한다."),
    ("지연은 캐시 누락에 기인한 것으로 보고됐다.", "지연은 캐시 누락 때문이라고 보고됐다."),
    ("이 사업의 목표는 응답 시간의 단축이다.", "이 사업의 목표는 응답 시간을 줄이는 것이다."),
    ("다음 분기에는 범위를 넓힐 것임.", "다음 분기에는 범위를 넓힐 것이다."),
    ("효과가 있다고 판단된다.", "효과가 있다고 본다."),
    ("- 항목 하나\n\n    이어지는 설명은 슬랙으로 알린다.", "- 항목 하나\n\n    이어지는 설명은 Slack으로 알린다."),
    ("It's a test. 결과는 슬랙으로\nalready 알린다. Don't 걱정.", "It's a test. 결과는 Slack으로\nalready 알린다. Don't 걱정."),
    ("'24년 계획을 '25년에 슬랙으로 알렸다.", "'24년 계획을 '25년에 Slack으로 알렸다."),
]


def edited(pairs):
    text = FIDELITY_ORIG
    for a, b in pairs:
        text = text.replace(a, b, 1)
    return text


def selftest():
    rows = "\n".join(f"| {bad} | {good} |" for _, bad, good in SELFTEST_CASES)
    must_hit = [(title, text) for title, bad, good in SELFTEST_CASES
                for text in (*bad.split(" / "), f"- ✗ {good} → ○ {bad}", f"✗ 예시\n\n{bad}",
                             f"✗ 는 미지원이다.\n{bad}", f"- A: ○\n- B: ✗\n- C: {bad}",
                             f"| 항목 | 지원 |\n|---|---|\n| 가 | ✗ |\n| 나 | {bad} |\n| 다 | ○ |")]
    must_hit.append(("번역투", f"| 이전 | 이후 |\n|---|---|\n{rows}"))
    must_hit += [("뜻이 맞지 않는 고유어", text) for text in MISFIT_MUST_HIT]
    must_hit += CHECK_MUST_HIT
    must_pass = [text for _, bad, good in SELFTEST_CASES
                 for text in (good, f"- ✗ {bad} → ○ {good}", f"- ✗ {bad}\n- ○ {good}")]
    must_pass += [f"<!-- style-teaching -->\n| 군더더기 | 고침 |\n|---|---|\n{rows}",
                  f"| 고침 | 군더더기 (쓰지 말 것) |\n|---|---|\n{rows}"]
    must_pass += MISFIT_MUST_PASS
    must_pass += CHECK_MUST_PASS
    orig_hit = [(title, [(a, b)]) for title, a, b in FIDELITY_MUST_HIT]
    orig_pass = [[p] for p in FIDELITY_MUST_PASS] + [FIDELITY_MUST_PASS]

    phrases = [a for a, _ in FIDELITY_MUST_PASS] + [a for _, a, _ in FIDELITY_MUST_HIT]
    fails = [f"FIDELITY_ORIG 에 없는 구절: {a!r}" for a in phrases if a not in FIDELITY_ORIG]
    with tempfile.TemporaryDirectory() as d:
        path, orig = os.path.join(d, "case.md"), os.path.join(d, "orig.md")
        with open(orig, "w", encoding="utf-8") as f:
            f.write(FIDELITY_ORIG + "\n")

        def run(text, against=None):
            with open(path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                total = compare(against, read_text(against), path) if against else check(path, DEFAULT_PAIRS)
            return total, out.getvalue()

        fails += [f"걸려야 하는데 안 걸림: {t!r}" for title, t in must_hit if f"■ {title}" not in run(t)[1]]
        fails += [f"걸리면 안 되는데 걸림: {t!r}" for t in must_pass if run(t)[0]]
        for title, p in orig_hit:
            total, out = run(edited(p), orig)
            if not total or f"■ {title}" not in out:
                fails.append(f"원문 대조에서 안 걸림: {p}")
        fails += [f"원문 대조에서 걸림: {p}" for p in orig_pass if run(edited(p), orig)[0]]
        pair_orig = os.path.join(d, "pair-orig.md")
        for title, a, b in [*FIDELITY_DOC_HIT, *((None, a, b) for a, b in FIDELITY_DOC_PASS)]:
            with open(pair_orig, "w", encoding="utf-8") as f:
                f.write(a + "\n")
            total, out = run(b, pair_orig)
            if bool(title) != bool(total) or title and f"■ {title}" not in out:
                fails.append(f"원문 대조 {a!r} → {b!r}: {total}군데")

        clean, dirty, changed = (os.path.join(d, n) for n in ("clean.md", "dirty.md", "changed.md"))
        for name, text in ((clean, "이번 배포는 팀장 승인을 받았다."), (dirty, "이번 배포는 팀장 컨펌을 받았다."),
                           (changed, edited([("| 신규 모델 | 보류 |", "| 신규 모델 | 승인 |")]))):
            with open(name, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        cli_cases = [
            ((clean,), 0, r"깨끗합니다\. 남은 것은 사람이 읽어야 판단되는 부분입니다\."),
            ((dirty,), 1, r"확인할 곳 1군데\. 규칙에 비춰 하나씩 판단하세요\."),
            ((clean, dirty), 1, r"확인할 곳 1군데\. 규칙에 비춰 하나씩 판단하세요\."),
            (("--orig", orig, orig), 0,
             r"원문과 달라진 곳 0군데\. 새로 덧붙인 주장처럼 기계가 잡지 못하는 것은 사람이 읽어 확인하세요\."),
            (("--orig", orig, changed), 1, r"원문과 달라진 곳 1군데\. 원문의 사실·인용·확정 수준을 바꿨는지 하나씩 확인하세요\."),
        ]
        for args, code, last in cli_cases:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), *args], capture_output=True, text=True)
            got = (r.stdout.strip().splitlines() or [""])[-1]
            if r.returncode != code or not re.fullmatch(last, got):
                fails.append(f"명령 {[os.path.basename(a) for a in args]}: exit {r.returncode}, 마지막 줄 {got!r}")

    total = (len(must_hit) + len(must_pass) + len(orig_hit) + len(orig_pass)
             + len(FIDELITY_DOC_HIT) + len(FIDELITY_DOC_PASS) + len(cli_cases))
    git_result = git_selftest()
    if git_result is None:
        print("git 이 없어 --backup·--orig HEAD 시험을 건너뜁니다")
    else:
        total += git_result[0]
        fails += git_result[1]
    for f in fails:
        print("실패  " + f)
    print(f"자체 시험 {total}건 중 실패 {len(fails)}건")
    print(f"사람 판단으로 뺀 행 {len(HUMAN_JUDGMENT)}개: " + ", ".join(HUMAN_JUDGMENT))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--pair", nargs=2, action="append", metavar=("A", "B"),
                    help="같은 뜻으로 섞어 쓴 낱말 쌍. 문서마다 바꿔 넣는다")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--backup", action="store_true",
                      help="고치기 전에 <파일>.bak.<시각> 으로 복사한다. git HEAD 에 커밋한 그대로면 건너뛴다")
    mode.add_argument("--orig", metavar="원본",
                      help="고친 파일을 이 원본과 견줘 사실·인용·확정 수준이 달라진 곳만 보고한다. "
                           "HEAD 를 주면 git HEAD 에 커밋한 내용을 원본으로 쓴다")
    mode.add_argument("--selftest", action="store_true",
                      help="SKILL.md 표에서 옮긴 사례로 검사기를 시험한다")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.files:
        ap.error("검사할 파일을 하나 이상 주세요")
    if args.backup or args.orig:
        try:
            if args.backup:
                for f in args.files:
                    backup(f)
                sys.exit(0)
            total = sum(compare(*read_orig(args.orig, f), f) for f in args.files)
        except (SourceError, OSError, UnicodeDecodeError) as e:
            print(f"오류: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        pairs = [tuple(p) for p in (args.pair or [])] or DEFAULT_PAIRS
        total = sum(check(f, pairs) for f in args.files)
    sys.exit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
