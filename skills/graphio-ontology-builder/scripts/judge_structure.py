#!/usr/bin/env python3
"""온톨로지 구조를 확정해도 되는지 판정한다.

검증 리포트는 무엇을 검사했는지 적는다. 이 스크립트는 그 결과에 등급을 매겨
「확정해도 되는가」 한 줄로 만든다. Error가 0건이면 확정할 수 있다.

    python3 judge_structure.py <온톨로지-정의.md> <온톨로지-검증-리포트.md> \\
        --converter <converter 스킬 폴더> --required-grade 필수 --manual-checked -o <구조-판정.md>

등급은 references/검사-규칙.md 에 규칙마다 정해져 있다. 검증 리포트 4.2절 지적 목록의 행, 5절 CQ별 판정,
6절 매핑 컬럼 대조, 2절 필수 CQ 기준에서 지적을 모아 규칙의 등급을 붙인다. 5·6절에는 규칙 번호를 적지
않는다. 판정값과 필수 여부로 이 스크립트가 CQS-01~04·MAP-01~04 를 정하고, 2절 필수 CQ 기준을 스킬이
정했으면 CQS-06 을 올린다.

스크립트 검사 결과는 적힌 대로 믿지 않는다. 수집 스크립트(collect_findings.py)를 수집 때와 같은 옵션으로
다시 수행해 4.2 표 아래 수집 조건 줄, 4.1 No.1·No.2 행, 4.2 스크립트 행(DOC·CNV·SPC)이 같은지 본다.
수집 뒤 정의 문서·스킬·converter 가 바뀌었거나 옵션이 다르면 원인을 알리고 멈춘다. 그래서 수집 때 준
옵션을 같이 준다.

    --converter <폴더>    converter 스킬 폴더. converter 스킬이 없었으면 대신 --spec-skipped
    --source <파일> ...   원천 구조 문서. 문서 정보 표에 적혀 있으면 반드시 준다
    --warn-mark <기호>    가이드가 정한 경고 기호가 ⚠ 가 아닐 때

스킬이 적은 위치(4.2 스킬 행, 5절 부분 응답·응답 불가 행)는 정의 문서에서 다시 찾는다. 줄 번호가
빠졌으면 채우고, 찾지 못하거나 줄 번호가 다르면 멈춘다. 6절의 매핑 컬럼은 정의 문서의 매핑과 맞대 본다.
5·6절에는 판정 표를 하나만 둔다. 표가 둘이거나 빈 줄로 갈린 조각이 있으면 멈춘다. 2절의 필수 CQ 응답·
필수 CQ 미응답·검사 수행 결과·지적 목록·매핑 컬럼 대조와 4.1 No.3·No.6 결과는 다시 세어 맞대 본다.

CQ 문서가 CQ에 등급을 매겼으면 어느 말을 필수로 볼지 --required-grade 로 알려 준다. 알려 주지 않으면
모든 CQ를 필수로 본다. 설계 리포트 11절(입력 문서 간 불일치)을 확인해 INP-01 행을 4.2절에 모두 적었으면
--manual-checked 를 준다. 주지 않으면 미수행 검사로 남는다.

입력을 읽지 못하거나 맞지 않으면 판정 문서를 쓰지 않고 멈춘다. 읽지 못한 채 판정하면 Error가 가려진
문서가 「확정 가능」 으로 나가기 때문이다. 종료 코드: 0 확정 가능, 1 확정 불가, 2 판정하지 않음.

문서의 꼴과 문체는 references/리포트-작성-규칙.md 를 따른다.
"""
import argparse
import datetime
import os
import re
import sys

import collect_findings as cf
import definition_index as di
import rule_catalog as rc

NONE = "해당 없음"

# 판정값. 리포트-작성-규칙.md 4장이 정한 닫힌 목록이라 여기서 늘리지 않는다.
CQ_VERDICTS = ("응답 가능", "부분 응답", "응답 불가")
MAP_VERDICTS = ("일치", "대체 매핑", "의미 불일치 미매핑", "원천 부재 미매핑", "원천 확인 필요 미매핑")
# 5절·6절 판정값으로 정하는 규칙. (필수 여부, 판정값) 과 판정값이 열쇠다.
CQ_RULE = {(True, "응답 불가"): "CQS-01", (True, "부분 응답"): "CQS-02",
           (False, "응답 불가"): "CQS-03", (False, "부분 응답"): "CQS-04"}
MAP_RULE = {"대체 매핑": "MAP-01", "의미 불일치 미매핑": "MAP-02",
            "원천 부재 미매핑": "MAP-03", "원천 확인 필요 미매핑": "MAP-04"}
# 스크립트 규칙을 가르는 기준은 rule_catalog 의 COLLECTED(수집 스크립트가 4.2절에 내는 규칙)와
# JUDGED(이 스크립트가 5·6절과 2절에서 정하는 규칙, 4.2절에 있으면 멈춤) 하나다. 접두어로 가르지 않는다.
assert set(CQ_RULE.values()) | {"CQS-06"} | set(MAP_RULE.values()) == set(rc.JUDGED)

# 4.1 No.3~6 의 검사 이름과 결과값. No.1·No.2 는 수집 스크립트가 낸 값과 맞대 본다.
CHECKS = {"3": "가이드 준수 검사", "4": "CQ-구조 정합성 검사", "5": "CQ 통과 조건 검사", "6": "매핑 의미 검사"}
RESULT_RE = re.compile(r"통과|지적 [1-9]\d*건|미수행")

# 필수 CQ 기준을 스킬이 정했다는 표시. 이 말이 있으면 CQS-06(CQ 등급 미확정)을 올린다.
SKILL_DECIDED = ("스킬 판단", "전체 CQ")
ALL_CQ = "전체 CQ(필수 등급 판별 불가)"

# 검증 리포트 문서 정보 표에서 판정 문서로 옮기는 행
CARRY_OVER = ("설계 리포트", "CQ 문서", "원천 구조 문서", "스타일 가이드", "서식 가이드")

# 지적이 적힌 검증 리포트의 자리. 출처 차례가 묶음 차례를 정한다.
SOURCE = {"4.2": (0, "검증 리포트 4.2절"), "5": (1, "검증 리포트 5절"), "6": (2, "검증 리포트 6절"),
          "2": (3, "검증 리포트 2절(검증 결과 요약) 필수 CQ 기준")}
WHERE_42 = "검증 리포트 4.2절(지적 목록)"
WHERE_3 = "검증 리포트 3절(산출 규모)"
WHERE_6 = "검증 리포트 6절(매핑 컬럼 대조 결과)"


class InputError(Exception):
    """판정할 수 없는 입력. 판정 문서를 쓰지 않고 멈춘다. fix 는 고칠 곳이다."""

    def __init__(self, message, fix):
        super().__init__(message)
        self.fix = fix


# ── 검증 리포트 읽기 ─────────────────────────────────────────────────────────

def norm(s):
    """표 칸의 값을 맞대 보기 좋게 다듬는다. 백틱과 공백은 뜻을 바꾸지 않는다."""
    return re.sub(r"\s+", "", (s or "").replace("`", "").replace("*", "")).lower()


# 표 칸을 막고 푸는 규칙은 수집 스크립트와 하나다. 수집 출력을 그대로 붙인 행이 대조에서 어긋나지 않게 한다.
esc, split_row, numbered = cf.esc, cf.split_row, cf.numbered


def headings(lines):
    """## 절과 ### 소절. [(제목, 시작 자리, 끝 자리)]. 끝은 같거나 높은 단계의 다음 제목 앞이다."""
    marks = [(len(m.group(1)), m.group(2).strip(), i) for i, ln in enumerate(lines)
             if (m := re.match(r"^(#{2,3})\s+(?!#)(.+?)\s*$", ln))]
    out = []
    for k, (level, title, i) in enumerate(marks):
        end = next((j for lv, _, j in marks[k + 1:] if lv <= level), len(lines))
        out.append((title, i + 1, end))
    return out


def find_section(heads, *choices):
    """제목에 낱말이 든 절을 찾는다. 절 번호가 바뀌어도 찾아낸다. choices 는 앞의 묶음부터 맞춰 본다."""
    for words in choices:
        for title, start, end in heads:
            if all(w in title for w in words):
                return start, end
    return None


def tables(lines, span):
    """절 안의 본문 표를 모두 [(머리글, 행들)] 로 읽는다. 인용문(>) 안의 표는 건너뛴다."""
    out, head, rows = [], None, []
    for ln in lines[span[0]:span[1]] + [""]:
        s = ln.strip()
        if s.startswith("|"):
            cells = split_row(s)
            if all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
                continue
            if head is None:
                head = [norm(c) for c in cells]
            elif any(cells):
                rows.append(cells)
        elif head is not None:
            out.append((head, rows))
            head, rows = None, []
    return out


def column(head, *names):
    """표 머리글에서 열 자리를 찾는다. 같은 이름을 먼저, 없으면 이름이 든 열을 찾는다."""
    if not head:
        return None
    for want in names:
        if norm(want) in head:
            return head.index(norm(want))
    for want in names:
        w = norm(want)
        for i, h in enumerate(head):
            if w and w in h:
                return i
    return None


def cell(row, idx):
    return row[idx].strip() if idx is not None and idx < len(row) else ""


def pick_table(lines, span, *want):
    """want 열이 있는 첫 표. 표가 없으면 (None, None), 표는 있는데 열이 없으면 (머리글, None)."""
    found = tables(lines, span)
    for head, rows in found:
        if column(head, *want) is not None:
            return head, rows
    return (found[0][0] if found else None), None


def only_table(lines, span, where):
    """판정 표를 두는 절(5·6절)의 표. [(머리글, 행들)] 로 많아야 하나를 돌려준다.

    표가 둘 이상이거나 빈 줄로 갈린 표 조각이 있으면 멈춘다. 첫 표만 읽으면 뒤 표나 조각에 적힌
    Error가 빠진 채 「확정 가능」 이 나오기 때문이다. 조각에는 머리글 아래 구분 줄이 없다.
    """
    starts = [i for i in range(span[0], span[1]) if lines[i].strip().startswith("|")
              and (i == span[0] or not lines[i - 1].strip().startswith("|"))]
    if len(starts) > 1:
        raise InputError("%s에 표가 %d개임(빈 줄로 갈린 표 조각 포함). 판정 표는 하나만 두고 행을 한 표에 이어 적음"
                         % (where, len(starts)), where)
    if starts:
        i = starts[0] + 1
        if i >= span[1] or not all(re.fullmatch(r":?-+:?", c) for c in split_row(lines[i])) \
                or not lines[i].strip().startswith("|"):
            raise InputError("%s 표 머리글 아래 구분 줄이 없음(검증 리포트 %d줄)" % (where, starts[0] + 1), where)
    return tables(lines, span)


def row_number(row, ni, where):
    """5·6절 행의 No.. 양의 정수가 아니면 멈춘다. 판정 문서 참고 자료가 이 번호로 행을 가리킨다."""
    text = cell(row, ni)
    if not re.fullmatch(r"[1-9]\d*", text):
        raise InputError("%s No. 칸이 양의 정수가 아님: '%s'" % (where, text), where)
    return int(text)


def info_table(lines):
    """제목 아래 첫 절 앞의 문서 정보 표를 {항목: 내용} 으로 읽는다."""
    out = {}
    for ln in lines:
        if re.match(r"^##\s", ln):
            break
        if ln.strip().startswith("|"):
            cells = split_row(ln)
            if len(cells) >= 2 and not re.fullmatch(r":?-+:?", cells[0] or "-"):
                out[cells[0]] = cells[1]
    return out


def need(head, where, *names):
    """표에 반드시 있어야 하는 열 자리들. 없으면 멈춘다."""
    idx = [column(head, n) for n in names]
    missing = [n for n, i in zip(names, idx) if i is None]
    if missing:
        raise InputError("%s 표에 %s 열이 없음" % (where, ", ".join("'%s'" % m for m in missing)), where)
    return idx


# ── 위치 확인 ────────────────────────────────────────────────────────────────

# 요소가 있어야 하는 머리말과 그 요소를 찾는 법
FINDERS = {
    "개념": lambda idx, v: idx.find_concepts(v["name"]),
    "개념 › 속성": lambda idx, v: idx.find_properties(v["concept"], v["name"]),
    "관계": lambda idx, v: idx.find_relations(v["name"], v["source"], v["target"]),
    "데이터 구조": lambda idx, v: idx.find_structures(v["name"]),
    "데이터 구조 › 컬럼": lambda idx, v: idx.find_columns(v["structure"], v["name"]),
    "매핑": lambda idx, v: idx.find_mappings(v["concept"], v["structure"]),
    "매핑 › 속성": lambda idx, v: idx.find_mapping_rows(v["concept"], v["structure"], v["name"]),
}


def check_part(idx, head, values, where, part):
    """위치 한 조각을 정의 문서에서 확인하고 줄 번호를 채운 꼴을 돌려준다."""
    fix = "%s 위치 칸" % where
    if head in FINDERS:
        lines = sorted({e.line for e in FINDERS[head](idx, values)})
        if not lines:
            raise InputError("%s 위치의 요소를 정의 문서에서 찾지 못함: %s" % (where, part), fix)
        if values["line"] is None:
            if len(lines) > 1:
                raise InputError("%s 위치의 요소가 정의 문서 %s줄에 여럿이라 줄 번호를 적어야 함: %s"
                                 % (where, "·".join(map(str, lines)), part), fix)
            values = dict(values, line=lines[0])
        elif values["line"] not in lines:
            raise InputError("%s 위치의 줄 번호가 정의 문서와 다름: %s(정의 문서 %s줄)"
                             % (where, part, "·".join(map(str, lines))), fix)
        return di.location(head, **values)
    # '(없음)' 꼴은 상위 요소가 있는지와 그 요소가 없는지를 본다
    if head == "개념(없음)":
        present = idx.find_concepts(values["name"])
    elif head == "개념 › 속성(없음)":
        if not idx.find_concepts(values["concept"]):
            raise InputError("%s 위치의 개념을 정의 문서에서 찾지 못함: %s" % (where, part), fix)
        present = idx.find_properties(values["concept"], values["name"])
    elif head == "관계(없음)":
        for name in (values["source"], values["target"]):
            if not idx.find_concepts(name):
                raise InputError("%s 위치의 개념을 정의 문서에서 찾지 못함: %s" % (where, part), fix)
        present = idx.find_relations(source=values["source"], target=values["target"])
        if values.get("join"):
            present = [r for r in present if values["join"] in (r.source_prop, r.target_prop)]
    elif head == "데이터 구조(없음)":
        present = idx.find_structures(values["name"])
    elif head == "매핑(없음)":
        present = idx.find_mappings(values["concept"], values["structure"])
    elif head == "정의 문서":
        if not 1 <= values["line"] <= len(idx.lines):
            raise InputError("%s 위치의 줄이 정의 문서에 없음: %s(전체 %d줄)" % (where, part, len(idx.lines)), fix)
        present = []
    else:                               # CQ·입력 문서는 정의 문서 밖이라 꼴만 본다
        present = []
    if present:
        raise InputError("%s 위치는 없다고 적었으나 정의 문서 %s줄에 있음: %s"
                         % (where, "·".join(str(e.line) for e in present), part), fix)
    return di.location(head, **values)


def place(idx, text, where, cq=False):
    """스킬이 적은 위치를 정의 문서에서 확인한다. 빠진 줄 번호를 채운 위치를 돌려준다.

    '; ' 로 이은 위치는 조각마다 본다. cq 면 첫 조각이 'CQ 번호' 여야 한다.
    """
    out = []
    for k, part in enumerate(di.split_locations(text)):
        try:
            head, values = di.parse_location(part)
        except di.LocationError as e:
            if "공백뿐" in str(e):
                raise InputError("%s 위치의 이름이 공백뿐임: %s" % (where, part), "%s 위치 칸" % where)
            raise InputError("%s 위치가 위치 머리말 목록 밖임: %s" % (where, part), "%s 위치 칸" % where)
        if cq and k == 0 and head != "CQ":
            raise InputError("%s 위치가 'CQ 번호'로 시작하지 않음: %s" % (where, text), "%s 위치 칸" % where)
        try:
            out.append(check_part(idx, head, values, where, part))
        except ValueError as e:     # di.location() 이 꼴을 받지 않음. 예상 밖 예외로 끝나지 않게 멈춤으로 바꾼다
            raise InputError("%s 위치를 다시 적지 못함: %s (%s)" % (where, part, e), "%s 위치 칸" % where)
    return "; ".join(out)


# ── 지적 모으기 ──────────────────────────────────────────────────────────────

def finding(rule, code, where, problem, route, fix, owner, refs, source, no):
    return {"규칙": rule, "외부 코드": code, "위치": where, "문제 설명": problem, "발생 경로": route,
            "조치 방안": fix, "조치 주체": owner, "참고 자료": refs, "출처": source, "No.": no}


def load_rules():
    try:
        return rc.load()
    except rc.RuleError as e:
        raise InputError("규칙 목록 문서를 읽지 못했거나 확인에 걸림: %s" % e, cf.MISMATCH_HINT)


def recollect(args, lines, heads):
    """수집 스크립트를 다시 수행해 수집 조건, 4.1 No.1·No.2, 4.2 스크립트 행을 맞대 본다.

    맞으면 (다시 수행한 결과, 4.1 행들, 4.2 행들) 을 돌려준다.
    """
    span = find_section(heads, ("검사 항목별 결과",))
    if span is None:
        raise InputError("검증 리포트 4.1절(검사 항목별 결과)을 찾지 못함", "검증 리포트 4.1절")
    head, rows = pick_table(lines, span, "검사 항목")
    if rows is None:
        raise InputError("검증 리포트 4.1절에 검사 항목 표가 없음", "검증 리포트 4.1절")
    ni, ri, ti = need(head, "검증 리포트 4.1절", "No.", "결과", "지적 내용")
    results = {cell(r, ni): {"결과": cell(r, ri), "지적 내용": cell(r, ti)} for r in rows}
    # 수집 스크립트가 낸 주석만 맞대 본다. 스킬이 쓰는 ※ No.1·※ No.2 Warning 확인 주석은 보지 않는다
    filled = [ln.strip() for ln in lines[span[0]:span[1]] if ln.strip().startswith("※ No.2 자동 채움:")]
    missing = [n for n in ("1", "2", "3", "4", "5", "6") if n not in results]
    if missing:
        raise InputError("검증 리포트 4.1절 표에 No.%s 행이 없음" % "·".join(missing), "검증 리포트 4.1절")
    bad = ["No.%s '%s'" % (n, results[n]["결과"]) for n in CHECKS if not RESULT_RE.fullmatch(results[n]["결과"])]
    if bad:
        raise InputError("검증 리포트 4.1절 결과값이 정해진 값(통과·지적 n건·미수행)이 아님: %s" % ", ".join(bad),
                         "검증 리포트 4.1절")

    span = find_section(heads, ("지적 목록",))
    if span is None:
        raise InputError("검증 리포트 4.2절(지적 목록)을 찾지 못함", "검증 리포트 4.2절")
    found = tables(lines, span)
    body = [ln.strip() for ln in lines[span[0]:span[1]]]
    if len(found) > 1:
        raise InputError("검증 리포트 4.2절에 표가 %d개임. 표는 하나만 둠" % len(found), "검증 리포트 4.2절")
    listed = []
    if found:
        head, table = found[0]
        if head != [norm(c) for c in cf.COLUMNS]:
            raise InputError("검증 리포트 4.2절 표 머리글이 정해진 칸과 다름. 머리글: %s" % " | ".join(cf.COLUMNS),
                             "검증 리포트 4.2절")
        for row in table:
            if len(row) != len(cf.COLUMNS) or not re.fullmatch(r"[1-9]\d*", row[0]):
                raise InputError("검증 리포트 4.2절 행의 칸 수나 No.가 머리글과 맞지 않음: No.%s" % row[0],
                                 "검증 리포트 4.2절")
            listed.append(dict(zip(cf.COLUMNS, row)))
    elif NONE not in body:
        raise InputError("검증 리포트 4.2절에 지적 목록 표도 '해당 없음'도 없음", "검증 리포트 4.2절")
    notes = [ln for ln in body if ln.startswith("※")]
    if not notes or not notes[0].startswith("※ 수집 조건:"):
        raise InputError("검증 리포트 4.2절 표 아래 첫 주석에 수집 조건 줄이 없음",
                         "수집 스크립트 출력을 4.2절에 다시 붙임")
    written = cf.parse_condition(notes[0])
    if written is None:
        raise InputError("검증 리포트 4.2절 수집 조건 줄의 꼴이 수집 스크립트가 낸 꼴과 다름",
                         "수집 스크립트 출력을 4.2절에 다시 붙임")

    # 다시 수집하기 전에 수집 조건부터 맞대 본다. 수집 뒤 정의 문서가 바뀌어 다시 수집이 실패해도
    # 원인(정의 문서가 바뀜)으로 알리기 위해서다.
    try:
        now = cf.condition(args.definition, converter=args.converter, spec_skipped=args.spec_skipped,
                           warn_mark=args.warn_mark, sources=args.source)
    except cf.CollectError as e:
        raise InputError("수집 조건을 다시 만들지 못함: %s" % e, "정의 문서 또는 옵션")
    causes = []
    if written["정의 문서"] != now["정의 문서"]:
        causes.append("수집 뒤 정의 문서가 바뀜(정의 문서 해시 %s → %s). 수집 스크립트를 다시 수행해 4.1·4.2절을 "
                      "바꿔 붙임. 고친 내용에 맞춰 5·6절과 스킬 행도 다시 봄" % (written["정의 문서"], now["정의 문서"]))
    if written["경고 기호"] != now["경고 기호"]:
        causes.append("경고 기호가 수집 때와 다름(수집 %s, 판정 %s). --warn-mark 를 수집 때와 같게 줌"
                      % (written["경고 기호"], now["경고 기호"]))
    if written["규격 검사"] != now["규격 검사"]:
        causes.append("규격 검사 수행 여부가 수집 때와 다름(수집 %s, 판정 %s). --converter·--spec-skipped 를 "
                      "수집 때와 같게 줌" % (written["규격 검사"], now["규격 검사"]))
    elif written["converter"] != now["converter"]:
        causes.append("converter 판본이 수집 때와 다름(converter 해시 %s → %s). 수집 때의 converter 스킬로 "
                      "판정하거나 다시 수집함" % (written["converter"], now["converter"]))
    src = [sorted(s["해시"] or cf.NOT_TEXT for s in c["원천 구조 문서"]) for c in (written, now)]
    if src[0] != src[1]:
        causes.append("원천 구조 문서가 수집 때와 다름(수집 %d건, 판정 %d건, 또는 내용이 바뀜). --source 를 수집 때와 "
                      "같은 파일로 주거나 다시 수집함" % (len(src[0]), len(src[1])))
    if written["빌더"] != now["빌더"]:
        causes.append("수집 뒤 스킬이 바뀜(빌더 판본 해시 %s → %s). 수집 스크립트를 다시 수행해 4.1·4.2절을 바꿔 붙임"
                      % (written["빌더"], now["빌더"]))
    if causes:
        raise InputError("수집 조건이 판정할 때의 조건과 다름. %s" % " / ".join(causes),
                         "다시 수집하거나 옵션을 수집 때와 맞춤")
    try:
        res = cf.collect(args.definition, converter=args.converter, spec_skipped=args.spec_skipped,
                         warn_mark=args.warn_mark, sources=args.source)
    except cf.MismatchError as e:
        raise InputError("수집 스크립트를 다시 수행하지 못함: %s" % e, cf.MISMATCH_HINT)
    except cf.CollectError as e:
        raise InputError("수집 스크립트를 다시 수행하지 못함: %s" % e, "정의 문서 또는 옵션")

    for exp in res["검사 결과"]:
        got = results[str(exp["No."])]
        for key in ("결과", "지적 내용"):
            if got[key] != exp[key]:
                raise InputError("검증 리포트 4.1 No.%d의 %s 칸이 다시 수행한 결과와 다름(적힌 값 '%s', 다시 수행 '%s')"
                                 % (exp["No."], key, got[key], exp[key]),
                                 "수집 스크립트 출력을 4.1절에 다시 붙임")
    keys = cf.COLUMNS[1:]
    mine = [tuple(r[k] for k in keys) for r in listed if r["규칙"] in rc.COLLECTED]
    theirs = [tuple(str(r[k]) for k in keys) for r in res["지적 목록"]]
    if sorted(mine) != sorted(theirs):
        extra = [r for r in mine if r not in theirs]
        lack = [r for r in theirs if r not in mine]
        sample = (extra or lack)[0]
        raise InputError("검증 리포트 4.2절 스크립트 행이 다시 수행한 결과와 다름(남는 행 %d건, 빠진 행 %d건. "
                         "첫 차이: %s %s). 손으로 적거나 고친 스크립트 행도 여기에 걸림"
                         % (len(extra), len(lack), sample[0], sample[2]), "수집 스크립트 출력을 4.2절에 다시 붙임")
    # 4.1 No.1·No.2 지적 내용과 판정 문서 참고 자료가 '4.2절 No.n' 으로 행을 가리키므로 차례와 번호도 본다.
    for k, r in enumerate(listed, 1):
        if int(r["No."]) != k:
            raise InputError("검증 리포트 4.2절 No.가 1부터 이어지지 않음(%d번째 행이 No.%s)" % (k, r["No."]),
                             "검증 리포트 4.2절")
    # 스크립트 행은 표 앞에 수집 차례대로 두고, No.는 1부터 이어 매김
    head_rows = [tuple(r[k] for k in keys) for r in listed[:len(theirs)]]
    if head_rows != theirs:
        raise InputError("검증 리포트 4.2절 스크립트 행이 표 앞에 수집 스크립트 출력 차례대로 있지 않음. "
                         "스킬 행은 스크립트 행 뒤에 둠", "수집 스크립트 출력을 4.2절에 다시 붙이고 스킬 행을 뒤에 이어 적음")
    if filled != res["자동 채움 주석"]:
        raise InputError("검증 리포트 4.1절 표 아래 '※ No.2 자동 채움:' 주석이 다시 수행한 결과와 다름"
                         "(적힌 주석 %d줄, 다시 수행 %d줄)" % (len(filled), len(res["자동 채움 주석"])),
                         "수집 스크립트 출력을 4.1절에 다시 붙임")
    return res, results, listed


def model_findings(listed, idx, rules):
    """4.2절 행. 스크립트 행은 이미 맞대 보았고, 스킬 행은 스킬이 적는 규칙(rules.skill_rules())이고
    칸이 다 차 있어야 하며 위치를 정의 문서에서 확인한다."""
    out, skill = [], rules.skill_rules()
    for r in listed:
        rule, no = r["규칙"], int(r["No."])
        where = "검증 리포트 4.2절 No.%d" % no
        if rule not in rules:
            raise InputError("%s 규칙 번호가 규칙 목록에 없음: %s" % (where, rule), "검증 리포트 4.2절")
        if rules.get(rule)["상태"] != "사용":
            raise InputError("%s 규칙이 '사용하지 않음' 규칙임: %s" % (where, rule), "검증 리포트 4.2절")
        if rule in rc.JUDGED:
            raise InputError("%s 규칙은 5·6절이나 2절에서 판정 스크립트가 정함: %s. 4.2절에서 지움" % (where, rule),
                             "검증 리포트 4.2절")
        if rule in rc.COLLECTED:
            location = r["위치"]
        elif rule not in skill:
            raise InputError("%s 규칙은 스킬이 4.2절에 적는 규칙이 아님: %s. 적을 수 있는 규칙: %s"
                             % (where, rule, "·".join(skill)), "검증 리포트 4.2절")
        else:
            empty = [k for k in cf.COLUMNS if not r[k].strip()]
            if empty:
                raise InputError("%s 스킬 행에 빈 칸이 있음: %s" % (where, ", ".join(empty)), "검증 리포트 4.2절")
            location = place(idx, r["위치"], where)
        out.append(finding(rule, r["외부 코드"], location, r["문제 설명"], r["발생 경로"], r["조치 방안"],
                           r["조치 주체"], r["참고 자료"], "4.2", no))
    return out


def required_basis(lines, heads, grades, present):
    """필수 CQ 기준을 정하고 검증 리포트 2절과 맞대 본다. 어긋나면 멈춘다."""
    if grades:
        missing = [g for g in grades if norm(g) not in present]
        if missing:
            raise InputError("검증 리포트 5절 등급 칸에 없는 --required-grade 값: %s. 5절 등급 칸의 값: %s"
                             % ("·".join(missing), "·".join(sorted(v for v in present if v)) or "없음"),
                             "옵션 또는 검증 리포트 5절 등급 칸")
    span = find_section(heads, ("검증 결과 요약",))
    written = ""
    if span:
        for _, rows in tables(lines, span):
            for row in rows:
                if norm(cell(row, 0)) == norm("필수 CQ 기준"):
                    written = cell(row, 1)
    expected = "CQ 문서 등급 %s" % ", ".join("'%s'" % g for g in grades) if grades else ALL_CQ
    if not written:
        return expected
    quoted = {norm(q) for q in re.findall(r"'([^']+)'", written)}
    if {norm(g) for g in grades} != quoted:
        raise InputError("검증 리포트 2절 '필수 CQ 기준'(%s)과 --required-grade(%s)가 다름. 이 옵션이면 받는 꼴: %s"
                         "(스킬이 정한 기준이면 뒤에 '(스킬 판단)')"
                         % (written, ", ".join(grades) or "지정 없음", expected), "옵션 또는 검증 리포트 2절")
    return written


def cq_findings(args, lines, heads, idx, rules):
    """5절 CQ별 판정에서 CQS-01~04 지적을 만든다. (지적, {전체, 집계, 기준}). 기준은 필수 CQ 기준이다."""
    span = find_section(heads, ("CQ별", "판정"))
    if span is None:
        raise InputError("검증 리포트 5절(CQ별 판정)을 찾지 못함", "검증 리포트 5절")
    found = only_table(lines, span, "검증 리포트 5절")
    if not found:
        raise InputError("검증 리포트 5절(CQ별 판정)에 표가 없음", "검증 리포트 5절")
    head, rows = found[0]
    if column(head, "판정") is None:
        raise InputError("검증 리포트 5절 표에 '판정' 열이 없음", "검증 리포트 5절")
    if not rows:
        raise InputError("검증 리포트 5절 표에 행이 없음", "검증 리포트 5절")
    ni, qi, vi, mi, wi, bi, fi = need(head, "검증 리포트 5절", "No.", "CQ", "판정", "누락 항목", "위치", "근거", "조치 방안")
    gi = column(head, "등급")
    if args.required_grade and gi is None:
        raise InputError("--required-grade 를 받았으나 검증 리포트 5절 표에 '등급' 열이 없음", "옵션 또는 검증 리포트 5절")
    bad = ["%s: '%s'" % (cell(r, qi) or "(CQ 이름 없음)", cell(r, vi)) for r in rows if cell(r, vi) not in CQ_VERDICTS]
    if bad:
        raise InputError("검증 리포트 5절 판정값이 정해진 값(%s)이 아님: %s" % ("·".join(CQ_VERDICTS), ", ".join(bad)),
                         "검증 리포트 5절. 말은 리포트-작성-규칙.md 4장")
    present = {norm(cell(r, gi)) for r in rows} if gi is not None else set()
    basis = required_basis(lines, heads, args.required_grade, present)

    required = {norm(g) for g in args.required_grade}
    out, tally = [], {}
    for r in rows:
        name, verdict = cell(r, qi) or "(CQ 이름 없음)", cell(r, vi)
        is_req = (not required) or (norm(cell(r, gi)) in required)
        key = ("필수" if is_req else "그 밖", verdict)
        tally[key] = tally.get(key, 0) + 1
        where = "검증 리포트 5절 No.%d" % row_number(r, ni, "검증 리포트 5절")
        location, fix = cell(r, wi), cell(r, fi)
        if verdict == "응답 가능":
            if norm(location) != norm(NONE) or norm(fix) != norm(NONE):
                raise InputError("%s 판정이 응답 가능인데 위치나 조치 방안에 '해당 없음' 밖의 값이 있음" % where,
                                 "검증 리포트 5절")
            continue
        if norm(location) in ("", norm(NONE)) or norm(fix) in ("", norm(NONE)):
            raise InputError("%s 판정이 %s인데 위치나 조치 방안이 비어 있음" % (where, verdict), "검증 리포트 5절")
        rule = CQ_RULE[(is_req, verdict)]
        gap = cell(r, mi)
        located = place(idx, location, where, cq=True)
        # 위치가 이미 'CQ 번호' 로 시작하므로 CQ 칸 앞의 같은 번호는 되풀이하지 않는다.
        # CQ 문장은 작은따옴표로 가려 판정값과 이어 읽히지 않게 한다
        cq_no = di.parse_location(di.split_locations(located)[0])[1]["number"]
        text = re.sub(r"^%s(?![\w-])[\s.:：)\]-]*" % re.escape(cq_no), "", name).strip() or name
        problem = "'%s' %s%s. %s" % (text, verdict,
                                     "(누락 항목: %s)" % gap if norm(gap) not in ("", norm(NONE)) else "",
                                     "필수 CQ라 확정을 막음" if is_req else "필수 CQ가 아니므로 확정을 막지 않음")
        base = rules.get(rule)
        out.append(finding(rule, NONE, located, problem, cell(r, bi), fix,
                           base["기본 조치 주체"], base["기본 참고 자료"], "5", row_number(r, ni, where)))
    return out, {"전체": len(rows), "집계": tally, "기준": basis}


def target_of(text):
    """6절 대상 속성 '개념 · 속성' 을 (개념, 속성) 으로. 개념 이름에는 가운뎃점이 없다."""
    concept, sep, prop = text.replace("`", "").partition("·")
    return (concept.strip(), prop.strip()) if sep and concept.strip() and prop.strip() else None


def comma_hint(text):
    """6절 대상 속성·매핑 컬럼을 쉼표가 아닌 말('/', ' · ' 여럿)로 이어 적었으면 붙이는 안내. 아니면 ''."""
    plain = text.replace("`", "")
    if "/" in plain or plain.count("·") > 1 or re.search(r"[\w`]\s+·\s+[\w`]+\.\w", text):
        return (". 한 행에 둘 이상을 적을 때는 대상 속성 '개념 · 속성'과 매핑 컬럼 '데이터 구조.컬럼'을 "
                "같은 차례로 쉼표로 나눠 적음('/'나 가운뎃점으로 잇지 않음)")
    return ""


def column_of(text):
    """6절 매핑 컬럼 '데이터 구조.컬럼' 을 (데이터 구조, 컬럼) 으로. 데이터 구조 이름에 마침표가 들 수 있어
    마지막 마침표에서 나눈다(스키마.테이블.컬럼). 꼴이 다르면 None."""
    structure, sep, col = text.replace("`", "").strip().rpartition(".")
    return (structure.strip(), col.strip()) if sep and structure.strip() and col.strip() else None


def mapped_rows(idx, concept, prop, structure, col):
    """그 개념·데이터 구조의 매핑에서 속성을 그 컬럼에 이은 행."""
    return [r for m in idx.find_mappings(concept, structure) for r in m.children if r.name == prop and r.column == col]


def map_findings(lines, heads, idx, rules):
    """6절 매핑 컬럼 대조에서 MAP-01 지적과 MAP-02~04 건수를 만든다. 표가 없으면 (None, None, 미수행 사유)."""
    span = find_section(heads, ("매핑", "대조"))
    if span is None:
        raise InputError("검증 리포트 6절(매핑 컬럼 대조 결과)을 찾지 못함", "검증 리포트 6절")
    found = only_table(lines, span, "검증 리포트 6절")
    head, rows = found[0] if found else (None, None)
    if head is not None and column(head, "판정") is None:
        raise InputError("검증 리포트 6절 표에 '판정' 열이 없음", "검증 리포트 6절")
    if not rows:
        why = next((re.sub(r"^[-*]\s*", "", ln.strip()) for ln in lines[span[0]:span[1]] if "미수행" in ln), "")
        return None, None, why or "검증 리포트 6절 표에 행 없음"
    ni, ki, pi, ci, vi, bi, fi = need(head, "검증 리포트 6절", "No.", "값", "대상 속성", "매핑 컬럼", "판정",
                                      "판정 근거", "조치 방안")
    bad = ["%s: '%s'" % (cell(r, ki) or "(값 이름 없음)", cell(r, vi)) for r in rows if cell(r, vi) not in MAP_VERDICTS]
    if bad:
        raise InputError("검증 리포트 6절 판정값이 정해진 값(%s)이 아님: %s" % ("·".join(MAP_VERDICTS), ", ".join(bad)),
                         "검증 리포트 6절. 말은 리포트-작성-규칙.md 4장")
    out, counts = [], {"판정별": {}}     # 판정별은 2절 '매핑 컬럼 대조' 칸을 다시 셀 때 쓴다
    for r in rows:
        verdict = cell(r, vi)
        counts["판정별"][verdict] = counts["판정별"].get(verdict, 0) + 1
        where = "검증 리포트 6절 No.%d" % row_number(r, ni, "검증 리포트 6절")
        targets = [t for t in re.split(r",\s*", cell(r, pi)) if t.strip()]
        parsed = [target_of(t) for t in targets]
        if not parsed or None in parsed:
            raise InputError("%s 대상 속성이 '개념 · 속성' 꼴이 아님: %s%s" % (where, cell(r, pi), comma_hint(cell(r, pi))),
                             "검증 리포트 6절")
        for concept, prop in parsed:
            if not idx.find_properties(concept, prop):
                raise InputError("%s 대상 속성을 정의 문서에서 찾지 못함: %s · %s%s"
                                 % (where, concept, prop, comma_hint(cell(r, pi))), "검증 리포트 6절 또는 정의 문서")
        if verdict in ("일치", "대체 매핑"):
            columns = [c for c in re.split(r",\s*", cell(r, ci)) if c.strip()]
            if len(columns) != len(parsed):
                raise InputError("%s 대상 속성과 매핑 컬럼의 수가 다름(대상 속성 %d건, 매핑 컬럼 %d건)"
                                 % (where, len(parsed), len(columns)), "검증 리포트 6절")
            if verdict == "대체 매핑" and len(parsed) > 1:
                raise InputError("%s 대체 매핑 행에 조인 쌍 두 쪽을 함께 적음. 쪽마다 한 행으로 나눔" % where,
                                 "검증 리포트 6절")
            found = []
            for (concept, prop), col in zip(parsed, columns):
                split = column_of(col)
                if split is None:
                    raise InputError("%s 매핑 컬럼이 '데이터 구조.컬럼' 꼴이 아님: %s%s" % (where, col, comma_hint(cell(r, ci))),
                                     "검증 리포트 6절")
                hit = mapped_rows(idx, concept, prop, *split)
                if not hit:
                    actual = ["%s.%s" % (m.structure, x.column) for m in idx.find_mappings(concept=concept)
                              for x in m.children if x.name == prop]
                    raise InputError("%s 매핑 컬럼이 정의 문서의 매핑과 다름: %s · %s → %s(정의 문서: %s)%s"
                                     % (where, concept, prop, col.replace("`", ""), ", ".join(actual) or "매핑 없음",
                                        comma_hint(cell(r, ci))),
                                     "검증 리포트 6절 또는 정의 문서")
                found.append(hit[0])
            if verdict == "대체 매핑":
                if norm(cell(r, fi)) in ("", norm(NONE)):
                    raise InputError("%s 판정이 대체 매핑인데 조치 방안이 비어 있음" % where, "검증 리포트 6절")
                base = rules.get("MAP-01")
                route = " → ".join((cell(r, ki), cell(r, pi), cell(r, ci), cell(r, bi)))
                out.append(finding("MAP-01", NONE, found[0].location(), "뜻이 다른 컬럼이 매핑되어 질의 결과가 틀림",
                                   route, cell(r, fi), base["기본 조치 주체"], base["기본 참고 자료"],
                                   "6", row_number(r, ni, where)))
        else:
            for concept, prop in parsed:
                if [x for m in idx.find_mappings(concept=concept) for x in m.children if x.name == prop]:
                    raise InputError("%s 판정이 %s인데 정의 문서에 매핑이 있음: %s · %s" % (where, verdict, concept, prop),
                                     "검증 리포트 6절 또는 정의 문서")
            counts[MAP_RULE[verdict]] = counts.get(MAP_RULE[verdict], 0) + 1
    return out, counts, None


# 2절에서 다시 세어 맞대 보는 항목. 필수 CQ 기준은 required_basis() 가, 구조 판정은 대조하지 않는다
RECOUNTED = ("필수 CQ 응답", "필수 CQ 미응답", "검사 수행 결과", "지적 목록", "매핑 컬럼 대조")


def summary_table(lines, heads):
    """검증 리포트 2절 표를 {항목: 결과} 로 읽는다."""
    span = find_section(heads, ("검증 결과 요약",))
    if span is None:
        raise InputError("검증 리포트 2절(검증 결과 요약)을 찾지 못함", "검증 리포트 2절")
    return {cell(row, 0): cell(row, 1) for _, rows in tables(lines, span) for row in rows}


def recount(lines, heads, results, res, listed, counted, map_counts):
    """스크립트가 셀 수 있는 손 집계를 다시 세어 맞대 본다. 다르면 멈춘다.

    2절의 필수 CQ 응답·필수 CQ 미응답(5절), 검사 수행 결과(4.1), 지적 목록(4.2), 매핑 컬럼 대조(6절)와
    4.1 No.3(4.2 GDE 행 수)·No.6(6절에서 일치가 아닌 행 수)이다. No.4·No.5는 스킬이 가르는 수라 보지 않는다.
    """
    tally = counted["집계"]
    req = {v: tally.get(("필수", v), 0) for v in CQ_VERDICTS}
    no = res["건수"]
    passed = failed = skipped = 0
    for n in ("1", "2", "3", "4", "5", "6"):
        if n == "1":
            ok = no["정의 문서 검사"]["Error"] == 0
            state = "통과" if ok else "지적"
        elif n == "2":
            spec = no["서식 변환 검사"]
            state = ("미수행" if spec["결과"] == "미수행"
                     else "통과" if spec["결과"] == "성공" and spec["규격 Error"] == 0 else "지적")
        else:
            value = results[n]["결과"]
            state = "통과" if value == "통과" else "미수행" if value == "미수행" else "지적"
        passed, failed, skipped = (passed + (state == "통과"), failed + (state == "지적"),
                                   skipped + (state == "미수행"))
    script = sum(1 for r in listed if r["규칙"] in rc.COLLECTED)
    verdicts = (map_counts or {}).get("판정별")
    if verdicts is None:
        mapping = "미수행"
    else:
        unmapped = sum(verdicts.get(v, 0) for v in MAP_VERDICTS[2:])
        mapping = "%d건 중 일치 %d건, 미매핑 %d건, 대체 매핑 %d건" % (
            sum(verdicts.values()), verdicts.get("일치", 0), unmapped, verdicts.get("대체 매핑", 0))
    expected = {
        "필수 CQ 응답": "%d건 중 %d건 응답 가능(전체 CQ %d건)" % (sum(req.values()), req["응답 가능"], counted["전체"]),
        "필수 CQ 미응답": (NONE if not req["부분 응답"] and not req["응답 불가"]
                        else "부분 응답 %d건, 응답 불가 %d건" % (req["부분 응답"], req["응답 불가"])),
        "검사 수행 결과": "6건 중 통과 %d건, Error·지적 %d건, 미수행 %d건" % (passed, failed, skipped),
        "지적 목록": (NONE if not listed
                  else "%d건 중 스크립트 %d건, 스킬 %d건" % (len(listed), script, len(listed) - script)),
        "매핑 컬럼 대조": mapping,
    }
    gde = sum(1 for r in listed if r["규칙"] in ("GDE-01", "GDE-02"))
    non_match = None if verdicts is None else sum(v for k, v in verdicts.items() if k != "일치")
    for n, count, basis, idle in (("3", gde, "4.2절 GDE-01·02 행 수", ("통과", "미수행")),
                                  ("6", non_match, "6절에서 판정이 일치가 아닌 행 수. 6절에 표가 없으면 미수행",
                                   ("통과",))):
        value = results[n]["결과"]
        if count is None:
            want = ("미수행",)
        elif count == 0:
            want = idle
        else:
            want = ("지적 %d건" % count,)
        if value not in want:
            raise InputError("검증 리포트 4.1 No.%s 결과가 다시 센 값과 다름(적힌 값 '%s', 다시 센 값 '%s'). %s"
                             % (n, value, "' 또는 '".join(want), basis), "검증 리포트 4.1절")
    written = summary_table(lines, heads)
    for key in RECOUNTED:
        if key not in written:
            raise InputError("검증 리포트 2절에 '%s' 행이 없음" % key, "검증 리포트 2절")
        if norm(written[key]) != norm(expected[key]):
            raise InputError("검증 리포트 2절 '%s' 칸이 다시 센 값과 다름(적힌 값 '%s', 다시 센 값 '%s')"
                             % (key, written[key], expected[key]), "검증 리포트 2절")


def basis_finding(basis, rules):
    """2절 필수 CQ 기준을 스킬이 정했으면 CQS-06."""
    if not any(w in basis for w in SKILL_DECIDED):
        return []
    base = rules.get("CQS-06")
    return [finding("CQS-06", NONE, "입력 문서 'CQ 문서' 등급 표기",
                    "필수 등급 표기가 없어 필수 CQ 기준을 스킬이 정함. 필수 CQ 범위가 바뀌면 판정이 달라질 수 있음",
                    "CQ 문서 등급 → 필수 등급 표기 없음 → 스킬이 정한 기준: %s" % basis,
                    "필수 등급 확인 후 판정 재수행", base["기본 조치 주체"], base["기본 참고 자료"], "2", 0)]


def judge(args, lines, rules):
    """지적을 모아 등급별로 가른다."""
    if args.converter and args.spec_skipped:
        raise InputError("--converter 와 --spec-skipped 를 함께 줌. 둘 가운데 하나만 줌", "옵션")
    if not args.converter and not args.spec_skipped:
        raise InputError("--converter 와 --spec-skipped 가운데 하나를 주지 않음", "옵션")
    heads = headings(lines)
    info = info_table(lines)
    listed_source = info.get("원천 구조 문서", "")
    if norm(listed_source) not in ("", norm(NONE)) and not args.source:
        raise InputError("검증 리포트 문서 정보 표의 원천 구조 문서 행에 문서가 적혀 있으나 --source 가 없음", "옵션")
    try:
        idx = di.load(args.definition)
    except di.ReadError as e:
        raise InputError("정의 문서를 읽지 못함: %s (%s)" % (e.path, e.problem), "정의 문서")

    res, results, listed = recollect(args, lines, heads)
    found = model_findings(listed, idx, rules)
    cq, counted = cq_findings(args, lines, heads, idx, rules)
    mapped, map_counts, map_skip = map_findings(lines, heads, idx, rules)
    if (results["6"]["결과"] == "미수행") != (mapped is None):
        raise InputError("검증 리포트 4.1 No.6 결과(%s)와 6절 표 유무가 맞지 않음" % results["6"]["결과"],
                         "검증 리포트 4.1절·6절")
    found += cq + (mapped or []) + basis_finding(counted["기준"], rules)
    recount(lines, heads, results, res, listed, counted, map_counts)

    unchecked = []
    if args.spec_skipped:
        unchecked.append(("서식 변환 검사", "converter 스킬 없음"))
    elif res["건수"]["서식 변환 검사"]["결과"] == "실패":
        unchecked.append(("서식 변환 검사", "변환 실패로 규격 검사 미수행"))
    if mapped is None:
        unchecked.append(("매핑 의미 검사", map_skip))
    for n in ("3", "4", "5"):
        if results[n]["결과"] == "미수행":
            unchecked.append((CHECKS[n], results[n]["지적 내용"] or "검증 리포트 4.1절 지적 내용 없음"))
    if not args.manual_checked:
        unchecked.append(("입력 문서 간 불일치 확인", "설계 리포트 11절 확인 결과 미반영"))
    if res["원천 구조 문서 대조"] != "수행":
        unchecked.append(("원천 구조 문서 대조(DOC-08)",
                          "원천 구조 문서 미제공" if not args.source else "텍스트로 읽을 수 없는 형식"))

    grade = {f["규칙"]: rules.get(f["규칙"])["등급"] for f in found}
    critical = [f for f in found if grade[f["규칙"]] == "Error"]
    major = [f for f in found if grade[f["규칙"]] == "Warning"]

    leave = []      # 조치 대상 외 항목. Info 규칙의 건수
    for rule in rules.rules:
        base = rules.get(rule)
        if base["등급"] != "Info":
            continue
        if rule == "DOC-10":
            n, where = res.get("통계", {}).get("확인 필요 표기", 0), WHERE_3
        elif rule in MAP_RULE.values():
            n, where = (map_counts or {}).get(rule, 0), WHERE_6
        else:
            n, where = sum(1 for r in listed if r["규칙"] == rule), WHERE_42
        if n:
            refs = where if base["기본 참고 자료"] == NONE else "%s, %s" % (where, base["기본 참고 자료"])
            leave.append((rule, base["이름"], "%d건" % n, refs))
    return critical, major, leave, unchecked, counted, info


# ── 판정 문서 ────────────────────────────────────────────────────────────────

def sentences(text):
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def arrange(items, rules):
    """묶음 목록. 규칙 번호 차례 → 묶음 차례(묶음 첫 행이 출처 표에 나오는 차례) → 출처 No. 차례.

    규칙·외부 코드·문제 설명·조치 방안·조치 주체가 같은 지적을 한 묶음으로 둔다.
    """
    groups = {}
    for f in sorted(items, key=lambda f: (rules.order(f["규칙"]), SOURCE[f["출처"]][0], f["No."])):
        key = (f["규칙"], f["외부 코드"], f["문제 설명"], f["조치 방안"], f["조치 주체"])
        groups.setdefault(key, []).append(f)
    return list(groups.values())


def record(group):
    """묶음이 적힌 검증 리포트 자리."""
    source = group[0]["출처"]
    if source == "2":
        return SOURCE["2"][1]
    return numbered(SOURCE[source][1] + " ", [f["No."] for f in group])


def graded(label, items, rules):
    """3.1·3.2 소절. 요약표 뒤에 묶음마다 상세표를 둔다."""
    if not items:
        return [NONE]
    groups = arrange(items, rules)
    out = ["- 지적 한 건마다 요약표에 한 행을 둠",
           "- 규칙·외부 코드·문제 설명·조치 방안·조치 주체가 같은 지적은 상세표 하나로 묶음", "",
           "| No. | 규칙 | 위치 | 문제 설명 |", "|---|---|---|---|"]
    n = 0
    spans = []
    for g in groups:
        spans.append((n + 1, n + len(g)))
        for f in g:
            n += 1
            out.append("| %d | %s | %s | %s |" % (n, f["규칙"], esc(f["위치"]), esc(f["문제 설명"])))
    for g, (a, b) in zip(groups, spans):
        f, base = g[0], rules.get(g[0]["규칙"])
        nos = "No.%d" % a if a == b else "No.%d~%d" % (a, b)
        paths = [x["발생 경로"] for x in g]
        notes = []
        if len(set(paths)) == 1 and sentences(paths[0]) <= 2:
            route = paths[0]
        elif len(set(paths)) == 1:
            route = "표 아래 ※ 주석에 적음"
            notes.append("※ %s 발생 경로: %s" % (nos, paths[0]))
        else:
            route = "건별로 표 아래 ※ 주석에 적음"
            notes += ["※ No.%d 발생 경로: %s" % (k, p) for k, p in enumerate(paths, a)]
        refs = []
        for x in g:
            if x["참고 자료"] not in refs and norm(x["참고 자료"]) not in ("", norm(NONE)):
                refs.append(x["참고 자료"])
        refs.append(record(g))
        rows = (("지적 번호", "%s-%d" % (label, a) if a == b else "%s-%d~%d" % (label, a, b)),
                ("규칙", "%s %s" % (f["규칙"], base["이름"])),
                ("외부 코드", f["외부 코드"] or NONE),
                ("위치", f["위치"] if a == b else "요약표 %s" % nos),
                ("문제 설명", f["문제 설명"]), ("발생 경로", route), ("조치 방안", f["조치 방안"]),
                ("조치 주체", f["조치 주체"]), ("참고 자료", ", ".join(refs)), ("탐지 방식", base["탐지 방식"]))
        out += ["", "| 항목 | 내용 |", "|---|---|"] + ["| %s | %s |" % (k, esc(v)) for k, v in rows]
        if notes:
            out += [""] + [esc(x) for x in notes]
    return out


def table(head, rows):
    """번호를 붙인 표. 줄이 없으면 '해당 없음' 한 줄."""
    if not rows:
        return [NONE]
    out = ["| No. | %s |" % " | ".join(head), "|%s|" % "|".join(["---"] * (len(head) + 1))]
    out += ["| %d | %s |" % (i, " | ".join(esc(c) for c in r)) for i, r in enumerate(rows, 1)]
    return out


def follow_ups(critical, major, unchecked):
    out = []
    if critical:
        out.append("3.1 Error 조치 후 판정 재수행 필요")
    if unchecked:
        out.append("5절 미수행 검사 수행 후 판정 재수행 필요")
    if not critical and not unchecked:
        out.append("구조 확정 가능. 검증 리포트 7절(후속 조치) 사항 이행 필요")
    if major:
        out.append("3.2 Warning은 확정과 별개로 조치 필요. 처리 시점은 인수 측이 결정함")
    if any(f["규칙"] in ("CQS-03", "CQS-04") for f in major):
        out.append("3.2의 CQ 가운데 필수 CQ로 격상되는 CQ가 있으면 판정 재수행 필요")
    out.append("CQ 등급이 바뀌어 필수 CQ가 달라지면 판정 재수행 필요")
    return out


def report(args, rules, critical, major, leave, unchecked, counted, info):
    name = args.name or os.path.basename(args.definition).split("-온톨로지")[0]
    verdict = "확정 불가" if critical else "확정 가능"
    tally = counted["집계"]
    req_total = sum(v for (kind, _), v in tally.items() if kind == "필수")
    req_yes = tally.get(("필수", "응답 가능"), 0)

    p = ["# %s 온톨로지 구조 판정" % name, "",
         "| 항목 | 내용 |", "|---|---|",
         "| 판정일 | %s |" % datetime.date.today().isoformat(),
         "| 대상 문서 | `%s` |" % esc(cf.shown_path(args.definition)),
         "| 검증 리포트 | `%s` |" % esc(cf.shown_path(args.report))]
    for key in CARRY_OVER:
        value = info.get(key, "")
        if not value:
            print("경고: 검증 리포트 문서 정보 표에 '%s' 행이 없다" % key, file=sys.stderr)
            value = "확인 필요(검증 리포트 문서 정보 표에 없음)"
        p.append("| %s | %s |" % (key, esc(value)))

    applied = {f["규칙"] for f in critical + major} | {r[0] for r in leave}
    p += ["", "## 1. 개요", "",
          "### 1.1 목적", "",
          "- 검증 리포트의 검사 결과에 등급을 부여하여 온톨로지 구조의 확정 가능 여부를 판정함",
          "- 조치가 필요한 항목과 조치 대상 외 항목을 구분함", "",
          "### 1.2 판정 기준", "",
          "- Error 0건이면 확정 가능, 1건 이상이면 확정 불가로 판정함",
          "- Warning은 확정을 막지 않음. 처리 시점은 인수 측이 결정함",
          "- 등급은 규칙마다 정해져 있음(1.3 참조)", "",
          "| 등급 | 정의 | 판정 영향 |", "|---|---|---|",
          "| Error | 필수 CQ에 응답하지 못하거나 틀린 답을 내는 항목, 또는 Graphio 반입을"
          " 막는 항목 | 1건 이상이면 확정 불가 |",
          "| Warning | 구조와 필수 CQ 응답에는 문제가 없으나 인수 측이 인지해야 하는 항목"
          " | 영향 없음 |",
          "| Info | 규칙에 따라 비워 두었거나 대상 환경에서 이어서 할 항목 | 영향 없음 |", "",
          "- Info 항목은 3절에 올리지 않고 4절에 건수만 기재함",
          "- 검증 리포트 7절(후속 조치)의 사항은 판정에 영향 없음",
          "- 5절에 미수행 검사가 있으면 판정은 수행한 검사 범위 내에서만 유효함", "",
          "### 1.3 적용 규칙", ""]
    if applied:
        p += ["- 이 판정 문서의 3·4절에 나온 규칙임", "- 설명은 규칙이 무엇을 찾고 왜 그 등급인지를 적음",
              "- '스킬'은 이 설계를 수행한 도구를 가리킴. 탐지 방식의 '스킬 검사'는 스킬이 문서를 읽고 판단한 검사임", "",
              "| 규칙 | 이름 | 등급 | 탐지 방식 | 설명 |", "|---|---|---|---|---|"]
        for rule in rules.rules:
            if rule in applied:
                r = rules.get(rule)
                p.append("| %s |" % " | ".join(esc(r[k]) for k in ("규칙", "이름", "등급", "탐지 방식", "설명")))
    else:
        p.append(NONE)

    p += ["", "## 2. 판정 결과", "",
          "| 항목 | 결과 |", "|---|---|",
          "| 판정 | **%s** |" % verdict,
          "| Error | %d건 |" % len(critical),
          "| Warning | %d건 |" % len(major),
          "| 미수행 검사 | %s |" % ("%d건" % len(unchecked) if unchecked else NONE),
          "| 필수 CQ 응답 | %d건 중 %d건 응답 가능(전체 CQ %d건) |" % (req_total, req_yes, counted["전체"]),
          "| 필수 CQ 기준 | %s |" % esc(counted["기준"])]
    if unchecked:
        p += ["", "- 미수행 검사 %d건이 있어 판정은 수행한 검사 범위 내에서만 유효함(5절 참조)" % len(unchecked)]

    p += ["", "## 3. 지적 사항", "", "### 3.1 Error", ""]
    p += graded("Error", critical, rules)
    p += ["", "### 3.2 Warning", ""]
    p += graded("Warning", major, rules)

    p += ["", "## 4. 조치 대상 외 항목", ""]
    if leave:
        p += ["- 규칙에 따라 비워 두었거나 다음 단계로 넘긴 항목임",
              "- 건수를 줄이기 위해 값을 임의로 채우지 않음",
              "- 조치 일정과 방법은 검증 리포트 7절(후속 조치)에 있음", ""]
    p += table(["규칙", "항목", "건수", "참조 위치"], [list(r) for r in leave])

    p += ["", "## 5. 미수행 검사", ""]
    if unchecked:
        p += ["- 미수행 검사 항목은 판정에 반영되지 않았으므로 해당 범위의 지적 사항이 있을 수 있음", ""]
    p += table(["검사 항목", "미수행 사유"], [list(u) for u in unchecked])

    p += ["", "## 6. 후속 조치", ""]
    p += ["- %s" % s for s in follow_ups(critical, major, unchecked)]
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser(
        description="온톨로지 구조를 확정해도 되는지 판정한다. Error가 0건이면 확정한다.")
    ap.add_argument("definition", help="온톨로지 정의 문서")
    ap.add_argument("report", help="온톨로지 검증 리포트")
    ap.add_argument("--required-grade", action="append", default=[], metavar="말",
                    help="등급 칸에서 필수로 볼 말. 여러 번 줄 수 있다. 주지 않으면 모든 CQ를 필수로 본다")
    ap.add_argument("--converter", metavar="폴더",
                    help="converter 스킬 폴더. 수집 스크립트를 다시 수행해 검증 리포트와 맞대 본다")
    ap.add_argument("--spec-skipped", action="store_true",
                    help="converter 스킬이 없어 서식 변환 검사를 수행하지 못했다. --converter 와 함께 주지 않는다")
    ap.add_argument("--source", nargs="+", default=[], metavar="파일",
                    help="원천 구조 문서. 수집 때 준 것과 같은 파일을 준다")
    ap.add_argument("--manual-checked", action="store_true",
                    help="설계 리포트 11절을 확인해 입력 문서 간 불일치(INP-01) 행을 4.2절에 모두 적었다")
    ap.add_argument("--warn-mark", default=None, metavar="기호",
                    help="가이드가 정한 경고 기호. 수집 때 준 것과 같게 준다")
    ap.add_argument("--name", default=None, help="문서 제목에 쓸 이름")
    ap.add_argument("-o", "--out", default=None, metavar="파일",
                    help="판정 문서를 쓸 곳. 주지 않으면 화면에 낸다")
    args = ap.parse_args()

    try:
        if args.out and not os.path.isdir(os.path.dirname(os.path.abspath(args.out))):
            raise InputError("판정 문서를 쓸 폴더가 없음: %s" % os.path.dirname(os.path.abspath(args.out)), "-o 경로")
        rules = load_rules()
        if not os.path.isfile(args.definition):
            raise InputError("정의 문서가 없음: %s" % args.definition, "정의 문서 경로")
        try:
            with open(args.report, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError) as e:
            raise InputError("검증 리포트를 읽지 못함: %s (%s)" % (args.report, e), "검증 리포트 경로")
        critical, major, leave, unchecked, counted, info = judge(args, lines, rules)
        text = report(args, rules, critical, major, leave, unchecked, counted, info)
        if args.out:
            try:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
            except OSError as e:
                raise InputError("판정 문서를 쓰지 못함: %s (%s)" % (args.out, e.strerror or e), "-o 경로")
    except Exception as e:      # 예상 밖 예외도 종료 코드 2 로 끝낸다. 1 은 '확정 불가' 라 헷갈리기 때문이다
        if isinstance(e, InputError):
            print("판정하지 않음: %s" % e, file=sys.stderr)
            print("고칠 곳: %s" % e.fix, file=sys.stderr)
            if e.fix == cf.MISMATCH_HINT:
                print("판정 문서는 쓰지 않았다.", file=sys.stderr)
            else:
                print("검증 리포트나 옵션을 고친 뒤 다시 수행한다. 판정 문서는 쓰지 않았다.", file=sys.stderr)
        else:
            print("판정하지 않음: 판정 스크립트가 예상하지 못한 오류로 멈춤(%s: %s)" % (type(e).__name__, e),
                  file=sys.stderr)
            print("고칠 곳: 스크립트를 고치지 말고 사용자에게 알림. 판정 문서는 쓰지 않았다.", file=sys.stderr)
        if args.out and os.path.exists(args.out):
            print("경고: -o 파일이 이미 있음: %s. 이전 실행의 판정 문서이며 이번 판정 결과가 아니다" % args.out,
                  file=sys.stderr)
        return 2

    if args.out:
        print("판정: %s   Error %d건 · Warning %d건 · 미수행 검사 %d건"
              % ("확정 불가" if critical else "확정 가능", len(critical), len(major), len(unchecked)))
        print("썼다: %s" % args.out)
    else:
        print(text)
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
