#!/usr/bin/env python3
"""앞 글 유지 확인. 설계 수정 차수에서 부분 수정한 N+1차 정의 문서가 연쇄 대상을 빠뜨리지 않았는지 N차 정의 문서와
블록 단위로 맞댄다. 설계 수정 차수의 ⑨ 걸음 2 앞(관문 3 자리)에서 부른다.

    python3 compare_definitions.py <N차 정의 문서> <N+1차 정의 문서> --design-report <N+1차 설계 리포트> --round <N+1> [--json]

블록은 개념(속성 표 포함), 관계(Link Type 표의 행), 매핑이다. 지적 갈래는 셋이다.

    ⓐ 기록 줄 없이 바뀐 블록   글자가 바뀌거나 생기거나 없어졌는데 이번 차수 기록에 이름이 없는 블록. 없어진 블록은
                               'N차 n줄'로 따로 적는다. 이번 차수 기록은 N+1차 정의 문서 「## 스킬 수정 기록」 절의
                               '- N+1차 ·' 줄, 설계 리포트 12절 이번 차수 행, 설계 리포트 2절 '※ 외부 수정 n:' 줄이다.
                               2절 외부 수정 줄이 가리키는 블록은 사람이 고친 것이라 기록이 있는 것으로 본다
    ⓑ 옛 이름이 남은 자리      이름 대응표의 옛 이름이 N+1차 서식 네 절(Object Type·Link Type·Meta Type·Object Mapping)의
                               본문·매핑 제목·경고문·[SQL] 줄에 남은 자리. 「## 스킬 수정 기록」 절은 찾지 않는다
    ⓒ 지운 요소를 가리키는 행  N차에서 지운 개념·속성을 가리키는 N+1차 관계 행(양끝 개념, 조인 속성)과 매핑(지운 개념의
                               매핑, 지운 속성의 매핑 속성 행)

이름이 들어 있는지는 표 줄이면 칸 전체가 그 이름인지, 산문이면 이름 앞뒤 글자가 한글·영숫자가 아니거나 뒤에 조사가
붙었는지로 본다. 기록에서는 괄호 안 글자(관계 양끝·컬럼 이름 등)를 먼저 빼고, 남은 글자에서 작은따옴표로 감싼
이름(매핑 '개념 ← 데이터 구조'는 양쪽 이름도)은 글자 그대로, 따옴표 밖 글자는 낱말로 찾는다. 기록 줄 꼴은
references/fix-procedure.md 6장, 2절 외부 수정 줄 꼴은 references/design-report-format.md 2절 외부 수정 소절에 있다.

이름 대응표는 설계 리포트 12절 이번 차수 행 가운데 앞 값과 뒤 값이 모두 이름으로 적힌 행이다(앞 값이 옛 이름, 뒤 값이
새 이름). 그 가운데 앞 값은 N차 정의 문서의 개념·속성·관계 이름이면서 N+1차에는 없고, 뒤 값은 N+1차에만 있는 행만
읽는다. 조인 속성이나 대표 표시 속성을 이미 있는 다른 속성으로 바꾼 행은 두 이름이 두 문서에 다 있어 이름 바꿈으로
읽지 않는다. 이번 차수 행은 문서 정보 표 「앞 차수 설계 리포트」 12절에 없는 No.의 행이고, 그 행이 「해당 없음」이면
12절 모든 행이다. 이름을 바꾼 블록은 N차 쪽 이름을 대응표대로 바꿔 짝짓고 맞댄다.

종료 코드: 0 지적 없음, 1 지적 있음(검사는 끝났고 결과가 다음 단계로 가지 못함, 오류 아님), 2 입력 쪽 멈춤(파일 없음·
UTF-8 아님·개념 없음), 3 처리하지 못한 예외, 4 출력 쓰기 실패(표준 출력). 출력 파일은 쓰지 않는다.
다시 고친 뒤 몇 번 돌렸는지는 부르는 쪽이 센다.

--json 이면 표준 출력에 JSON 하나를 낸다. 칸은 code·passed·findings·message_ko·model_hint·detail 이다. code 는
멈춤 목록(references/stop-catalog.md) 1장 표의 코드 이름이고 지적이 없으면 null 이다. message_ko 는 사람용 문장이라
옵션 이름을 넣지 않는다. 원문 예외와 종료 코드 숫자는 detail 에만 둔다.
"""
import argparse
import json
import os
import re
import sys

import definition_index as di
import design_report_index as dri  # 12절·이름 대응표·2절 외부 수정 줄 읽기

EXIT_PASS, EXIT_FOUND, EXIT_INPUT, EXIT_SKILL, EXIT_ENV = 0, 1, 2, 3, 4  # 4는 표준 출력 쓰기 실패만, 10은 내지 않음
# 멈춤 JSON code. 멈춤 목록 1장 표의 코드 이름이다
STOP_CODE = {EXIT_FOUND: "CARRY_OVER_FINDINGS", EXIT_INPUT: "CARRY_OVER_INPUT", EXIT_SKILL: "SKILL_UNEXPECTED",
             EXIT_ENV: "OUTPUT_WRITE_FAILED"}
INPUT_MESSAGE = "맞댈 정의 문서·설계 리포트를 읽지 못함"     # 입력 쪽 멈춤의 사람용 한 줄. 어느 문서인지는 detail 에 둔다
HINT = {EXIT_PASS: "다음 단계로 간다",
        EXIT_FOUND: "지적한 자리를 N+1차 정의 문서에서 고친 뒤 한 번만 다시 확인함. 다시 지적이 나오면 더 고치지 않고 "
                    "지적을 사람에게 보이고 멈춤",
        EXIT_INPUT: "두 정의 문서와 설계 리포트의 경로·인코딩을 확인한 뒤 다시 수행함",
        EXIT_SKILL: "스크립트를 고치지 말고 사용자에게 알림"}
KINDS = {"ⓐ": "기록 줄 없이 바뀐 블록", "ⓑ": "옛 이름이 남은 자리", "ⓒ": "지운 요소를 가리키는 행"}

WORD = re.compile(r"[0-9A-Za-z가-힣ㄱ-ㅎㅏ-ㅣ]")    # 이름 앞뒤에 붙으면 낱말이 이어진 것으로 보는 글자
# 이름 뒤에 붙어도 이름으로 읽는 조사. 긴 것부터 맞춰 본다
JOSA = tuple(sorted(("이", "가", "은", "는", "을", "를", "의", "에", "에서", "에게", "께", "께서", "한테", "와", "과",
                     "로", "으로", "도", "만", "까지", "부터", "보다", "처럼", "마다", "만큼", "조차", "마저", "이나", "나",
                     "이며", "며", "이고", "이다", "이랑", "랑", "에는", "에도", "으로는", "로는", "와는", "과는",
                     "만을", "만이"), key=len, reverse=True))
SKILL_LOG = "스킬수정기록"                            # 「## 스킬 수정 기록」 제목에서 공백을 뺀 꼴
EXTERNAL_LINE = re.compile(r"^※ 외부 수정 \d+\s*:")   # 설계 리포트 2절 외부 수정 줄. 번호 없는 경고 줄은 빼고 읽음
LOG_CELLS = ("대상", "고른 값", "앞 값", "뒤 값", "연쇄 대상")   # 12절 이번 차수 행에서 요소 이름을 읽는 칸
TRAILING = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})?\s*$")       # 블록 끝의 빈 줄·가름 줄. 맞댈 때 뺀다


class InputStop(Exception):
    """입력 쪽 멈춤(종료 코드 2). message 는 어느 문서를 왜 읽지 못했는지 적은 까닭이고 경로는 detail 에만 둔다.
    멈춤 JSON 의 message_ko 는 INPUT_MESSAGE 한 줄이고 이 까닭은 detail 에 담는다."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message, self.detail = message, detail


# ── 이름 맞대기 ───────────────────────────────────────────────────────────────

def bounded(text, start, end):
    """text[start:end] 의 앞뒤가 낱말 경계인가. 뒤에 조사가 붙고 그 뒤가 경계여도 된다."""
    if start > 0 and WORD.match(text[start - 1]):
        return False
    rest = text[end:]
    if not rest or not WORD.match(rest[0]):
        return True
    return any(rest.startswith(j) and (len(rest) == len(j) or not WORD.match(rest[len(j)])) for j in JOSA)


def in_prose(name, text):
    """산문 text 에 name 이 낱말로 들어 있는가."""
    i = text.find(name) if name else -1
    while i >= 0:
        if bounded(text, i, i + len(name)):
            return True
        i = text.find(name, i + 1)
    return False


def is_table(line):
    return line.strip().startswith("|")


def cells(line):
    return [c.strip().strip("`").strip() for c in di.split_row(line)]


def word_in(name, line):
    """표 줄이면 칸 전체가 name 인 칸이 있는가, 산문이면 name 이 낱말로 들어 있는가."""
    if not name:
        return False
    return name in cells(line) if is_table(line) else in_prose(name, line)


def replace_word(text, old, new):
    """산문 text 에서 낱말로 든 old 만 new 로 바꾼다."""
    out, i, j = [], 0, text.find(old)
    while j >= 0:
        if bounded(text, j, j + len(old)):
            out.append(text[i:j] + new)
            i = j + len(old)
            j = text.find(old, i)
        else:
            j = text.find(old, j + 1)
    out.append(text[i:])
    return "".join(out)


def outside_parens(text):
    """괄호 밖 글자. 괄호 안 글자는 빈칸 하나로 바꾼다. 괄호 밖 작은따옴표 안의 괄호는 이름 글자로 두고, 괄호가
    겹치면 가장 바깥 괄호까지 뺀다."""
    out, depth, quoted = [], 0, False
    for ch in text:
        if depth == 0 and ch == "'":
            quoted = not quoted
        elif not quoted and ch in "(（":
            depth += 1
            continue
        elif depth and ch in ")）":
            depth -= 1
            if not depth:
                out.append(" ")
            continue
        if not depth:
            out.append(ch)
    return "".join(out)


def mentions(text, name):
    """기록 글자 text 가 요소 이름 name 을 가리키는가. 괄호 안 관계 양끝·컬럼 이름은 그 요소의 기록으로 보지 않으므로
    괄호 안 글자를 먼저 뺀다. 남은 글자에서 작은따옴표 안 이름은 글자 그대로(화살표로 이은 매핑 이름은 양쪽도),
    따옴표 밖 글자는 낱말로 찾는다."""
    if not name:
        return False
    text = outside_parens(text)
    for quoted in re.findall(r"'([^']*)'", text):
        if name in {quoted.strip()} | {x.strip() for x in re.split(r"\s*(?:←|→)\s*", quoted)}:
            return True
    return in_prose(name, re.sub(r"'[^']*'", " ", text))


# ── 블록 ─────────────────────────────────────────────────────────────────────

def blocks(idx):
    """맞댈 블록 {열쇠: 요소}. 개념 ('개념', 이름), 관계 ('관계', 이름, 출발, 도착), 매핑 ('매핑', 개념, 데이터 구조)."""
    out = {("개념", c.name): c for c in idx.concepts}
    out.update({("관계", r.name, r.source, r.target): r for r in idx.relations})
    out.update({("매핑", m.concept or m.name, m.structure): m for m in idx.mappings})
    return out


def renamed(name, renames):
    """이름 대응표대로 바꾼 이름. 이름 전체가 옛 이름일 때만 바꾼다."""
    for old, new in renames:
        if name == old:
            name = new
    return name


def renamed_key(key, renames):
    return (key[0],) + tuple(renamed(x, renames) if isinstance(x, str) else x for x in key[1:])


def canon(line, renames=()):
    """맞댈 꼴의 줄. 표 줄은 칸 묶음(칸 전체가 옛 이름인 칸은 새 이름으로), 산문은 끝 공백을 뗀 글자(낱말로 든 옛 이름은
    새 이름으로)."""
    if is_table(line):
        row = cells(line)
        for old, new in renames:
            row = [new if c == old else c for c in row]
        return ("표",) + tuple(row)
    text = line.rstrip()
    for old, new in renames:
        text = replace_word(text, old, new)
    return ("글", text)


def body(idx, el, renames=()):
    """블록 글자. 블록 끝의 빈 줄·가름 줄은 빼고 맞댄다(다음 절을 더해도 앞 블록이 바뀐 것으로 보지 않음)."""
    lines = idx.lines[el.line - 1:el.end]
    while lines and TRAILING.match(lines[-1]):
        lines = lines[:-1]
    return [canon(ln, renames) for ln in lines]


def key_text(key):
    """블록 이름 글자. 위치 꼴(references/report-conventions.md 7장)에서 줄 번호를 뺀 꼴이다."""
    if key[0] == "개념":
        return "개념 '%s'" % key[1]
    if key[0] == "관계":
        return "관계 '%s'(%s → %s)" % key[1:]
    return "매핑 '%s ← %s'" % (key[1], key[2]) if key[2] else "매핑 '%s'" % key[1]  # 제목이 '개념 ← 데이터 구조' 꼴이 아니면 제목 그대로


def format_lines(idx):
    """서식 네 절 안의 줄 번호(1부터). 「## 스킬 수정 기록」 절처럼 네 절이 아닌 절은 들지 않는다."""
    return [n for _, _, start, end in idx.sections for n in range(start, end + 1)]


# ── 기록과 이름 대응표 ────────────────────────────────────────────────────────

def skill_log(idx, round_no):
    """N+1차 정의 문서 「## 스킬 수정 기록」 절에서 이번 차수 표시('- N차 ·')가 붙은 줄."""
    mark = re.compile(r"^\s*[-*]\s*%d차\s*·" % round_no)
    out, inside = [], False
    for ln in idx.lines:
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", ln)
        if m:
            inside = re.sub(r"\s", "", m.group(1)) == SKILL_LOG
        elif inside and mark.match(ln):
            out.append(ln.strip())
    return out


def read_report(path, what):
    """설계 리포트를 읽는다. 읽지 못하면 입력 쪽 멈춤. what 은 문서 이름이다."""
    try:
        return dri.read_report(path)
    except dri.ReportError as e:  # 읽기 오류 문장에는 경로가 이미 있음(경로 한 번)
        raise InputStop("%s(%s)" % (what, e.problem), detail=str(e))


def this_round_rows(rep):
    """설계 리포트 12절에서 이번 차수에 더한 행. 앞 차수 설계 리포트 12절에 없는 No.의 행이다."""
    rows = rep.rows("12")
    prev = rep.info_path("앞 차수 설계 리포트")
    if not prev:
        return rows
    old = {no for no, _ in read_report(rep.resolve(prev), "앞 차수 설계 리포트").rows("12")}
    return [(no, row) for no, row in rows if no not in old]


def name_value(cell):
    """12절 앞 값·뒤 값 칸의 이름. 작은따옴표로 감싼 이름이 있으면 그것이다. 이름 꼴이 아니면 None
    (빈 값·'해당 없음', 화살표·등호·괄호가 든 값, 한글·영문자가 없는 값)."""
    text = dri.clean(cell)
    if dri.is_none(text):
        return None
    quoted = re.findall(r"'([^']+)'", text)
    text = (quoted[-1] if quoted else text).strip()
    if not text or re.search(r"[→←↔=|,;()（）]", text) or not re.search(r"[가-힣A-Za-z]", text):
        return None
    return text


def names(idx):
    """정의 문서의 개념·속성·관계 이름 집합. 매핑 제목·데이터 구조 이름은 넣지 않는다."""
    out = {c.name for c in idx.concepts} | {p.name for c in idx.concepts for p in c.children}
    return (out | {r.name for r in idx.relations}) - {"", None}


def rename_pairs(rows, before, after):
    """이름 대응표 [(옛 이름, 새 이름)]. 12절 이번 차수 행 가운데 앞 값·뒤 값이 모두 이름이고, 앞 값은 N차 정의
    문서(before)의 개념·속성·관계 이름이면서 N+1차(after)에는 없고, 뒤 값은 N+1차에만 있는 행이다. 조인 속성·대표
    표시 속성을 이미 있는 다른 속성으로 바꾼 행처럼 두 이름이 두 문서에 다 있으면 이름 바꿈으로 읽지 않는다."""
    old_names, new_names = names(before), names(after)
    out = []
    for _, row in rows:
        old, new = name_value(dri.pick(row, "앞 값")), name_value(dri.pick(row, "뒤 값"))
        if (old in old_names - new_names and new in new_names - old_names) and (old, new) not in out:
            out.append((old, new))
    return out


# ── 지적 ─────────────────────────────────────────────────────────────────────

def finding(kind, block, new_line=None, old_line=None):
    return {"갈래": kind, "뜻": KINDS[kind], "블록": block, "N+1차 줄": new_line, "N차 줄": old_line}


def changed(old, el_old, new, el_new, renames):
    """블록 글자가 바뀌었는가. 이름 대응표대로 옛 이름만 새 이름으로 바꾼 차이는 바뀐 것으로 보지 않는다."""
    now = body(new, el_new)
    return body(old, el_old) != now and body(old, el_old, renames) != now


def findings(old, new, records, renames):
    """세 갈래 지적. records 는 이번 차수 기록 글자, renames 는 이름 대응표다."""
    def logged(*names):
        return any(mentions(text, n) for text in records for n in names if n)

    b = blocks(new)
    pairs, gone = [], []     # N차 블록마다 짝 N+1차 열쇠(대응표대로 바꾼 이름, 없으면 그 이름 그대로). 짝이 없으면 없어짐
    for k, el in blocks(old).items():
        k2 = renamed_key(k, renames)
        target = k2 if k2 in b else k if k in b else None
        if target:
            pairs.append((k, el, target))
        else:
            gone.append((k, el))
    out = [finding("ⓐ", key_text(t), new_line=b[t].line) for k, el, t in pairs
           if changed(old, el, new, b[t], renames) and not logged(t[1], k[1])]
    matched = {t for _, _, t in pairs}
    out += [finding("ⓐ", key_text(k), new_line=b[k].line) for k in set(b) - matched if not logged(k[1])]
    out += [finding("ⓐ", key_text(k), old_line=el.line) for k, el in gone if not logged(k[1], renamed(k[1], renames))]
    lines = format_lines(new)
    for old_name, _ in renames:
        out += [finding("ⓑ", "옛 이름 '%s'" % old_name, new_line=n) for n in lines
                if word_in(old_name, new.lines[n - 1])]
    gone_c = {name for k, _ in gone if k[0] == "개념" for name in (k[1], renamed(k[1], renames))}
    have_p = {(c.name, p.name) for c in new.concepts for p in c.children if p.name}
    gone_p = set()
    for c in old.concepts:
        for p in c.children:
            both = {(c.name, p.name), (renamed(c.name, renames), renamed(p.name, renames))}
            if p.name and not both & have_p:
                gone_p |= both
    for r in new.relations:
        if {r.source, r.target} & gone_c or (r.source, r.source_prop) in gone_p or (r.target, r.target_prop) in gone_p:
            out.append(finding("ⓒ", key_text(("관계", r.name, r.source, r.target)), new_line=r.line))
    for m in new.mappings:
        if m.concept and m.concept in gone_c:
            out.append(finding("ⓒ", key_text(("매핑", m.concept, m.structure)), new_line=m.line))
            continue
        out += [finding("ⓒ", "%s › 속성 '%s'" % (key_text(("매핑", m.concept, m.structure)), row.name), new_line=row.line)
                for row in m.children if m.concept and (m.concept, row.name) in gone_p]
    order = {kind: n for n, kind in enumerate(KINDS)}
    return sorted(out, key=lambda f: (order[f["갈래"]], f["N+1차 줄"] is None, f["N+1차 줄"] or f["N차 줄"] or 0))


# ── 실행 ─────────────────────────────────────────────────────────────────────

def read_definition(path, what):
    """정의 문서를 읽어 색인을 만든다. 읽지 못하거나 개념이 없으면 입력 쪽 멈춤."""
    try:
        lines = di.read_text(path).splitlines()
    except di.ReadError as e:  # 읽기 오류 문장에는 경로가 이미 있음(경로 한 번)
        raise InputStop("%s(%s)" % (what, e.problem), detail=str(e))
    idx = di.DefinitionIndex(lines)
    if not idx.concepts:
        raise InputStop("%s(개념 없음)" % what, detail=path)
    return idx


def parse_args():
    ap = argparse.ArgumentParser(
        description="앞 글 유지 확인. 부분 수정한 N+1차 정의 문서를 N차와 블록 단위로 맞대 기록 줄 없이 바뀐 블록, "
                    "옛 이름이 남은 자리, 지운 요소를 가리키는 행을 짚는다.")
    ap.add_argument("before", metavar="N차정의문서", help="N차 정의 문서")
    ap.add_argument("after", metavar="N+1차정의문서", help="부분 수정한 N+1차 정의 문서")
    ap.add_argument("--design-report", required=True, metavar="파일",
                    help="N+1차 설계 리포트. 12절 이번 차수 행·이름 대응표·2절 외부 수정 줄을 읽는다")
    ap.add_argument("--round", required=True, type=int, metavar="N+1",
                    help="이번 차수. 정의 문서 스킬 수정 기록에서 이 차수 표시가 붙은 줄을 기록으로 읽는다")
    ap.add_argument("--json", action="store_true", help="표준 출력에 JSON 하나를 낸다")
    return ap.parse_args()


def main(args):
    old = read_definition(args.before, "N차 정의 문서")
    new = read_definition(args.after, "N+1차 정의 문서")
    rep = read_report(args.design_report, "설계 리포트")
    rows = this_round_rows(rep)
    renames = rename_pairs(rows, old, new)
    records = skill_log(new, args.round)
    records += [" ".join(dri.pick(row, c) for c in LOG_CELLS) for _, row in rows]
    records += [ln for ln in rep.note_lines("※ 외부 수정") if EXTERNAL_LINE.match(ln)]
    found = findings(old, new, records, renames)
    detail = {"N차 정의 문서": args.before, "N+1차 정의 문서": args.after, "설계 리포트": args.design_report,
              "차수": args.round, "이름 대응표": [list(p) for p in renames], "기록": len(records)}
    return emit(args, found, detail)


def message(found):
    if not found:
        return "앞 글 유지 확인 통과(지적 없음)"
    n = {kind: sum(1 for f in found if f["갈래"] == kind) for kind in KINDS}
    return ("앞 글 유지 확인에서 지적 %d건(기록 줄 없이 바뀐 블록 %d건, 옛 이름이 남은 자리 %d건, 지운 요소를 가리키는 행 "
            "%d건)이 나와 다음 단계로 가지 않음" % (len(found), n["ⓐ"], n["ⓑ"], n["ⓒ"]))


def table(found):
    """사람용 지적 표 줄."""
    out = ["", "| 블록 | 지적 갈래 | N+1차 줄 |", "|---|---|---|"]
    for f in found:
        where = f["N+1차 줄"] if f["N+1차 줄"] is not None else "N차 %d줄" % f["N차 줄"]
        out.append("| %s | %s %s | %s |" % (f["블록"].replace("|", "\\|"), f["갈래"], f["뜻"], where))
    return out


def write_out(body=None, lines=()):
    """표준 출력에 JSON 하나(body) 또는 사람용 줄을 쓴다. 읽는 쪽이 먼저 닫힌 파이프 같은 쓰기 실패면 표준 오류 한 줄을
    내고 False. 표준 출력을 os.devnull 로 돌려 해석기가 끝날 때 버퍼를 다시 비우다 실패하지 않게 한다."""
    try:
        if body is not None:
            json.dump(body, sys.stdout, ensure_ascii=False)
            print()
        else:
            print("\n".join(lines))
        sys.stdout.flush()
    except OSError as err:  # 읽는 쪽이 먼저 닫힌 파이프 → 종료 코드 4
        print("앞 글 유지 확인 결과를 내지 못함: %s" % (err.strerror or err), file=sys.stderr)
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return False
    return True


def emit(args, found, detail):
    code = EXIT_FOUND if found else EXIT_PASS
    detail["종료 코드"] = code
    if args.json:
        ok = write_out({"code": STOP_CODE.get(code), "passed": not found, "findings": found,
                        "message_ko": message(found), "model_hint": HINT[code], "detail": detail})
    else:
        ok = write_out(lines=[message(found)] + (table(found) if found else []))
    return code if ok else EXIT_ENV


def fail_out(args, code, why, detail):
    """멈춤 출력. 입력 쪽 멈춤은 사람용 한 줄을 INPUT_MESSAGE 로 두고, 어느 문서를 왜 읽지 못했는지(why)와 원문은
    detail 에 담는다."""
    text, info = (INPUT_MESSAGE, {"까닭": why, "원문": detail}) if code == EXIT_INPUT else (why, {"까닭": detail})
    if getattr(args, "json", False):
        body = {"code": STOP_CODE[code], "passed": False, "findings": [], "message_ko": text,
                "model_hint": HINT[code], "detail": dict({"종료 코드": code}, **info)}
        if not write_out(body):
            return EXIT_ENV
    else:
        print("%s: %s" % (text, why) if code == EXIT_INPUT else text, file=sys.stderr)
    return code


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(main(args))
    except InputStop as e:  # 입력 쪽 멈춤. 경로는 detail 에만
        sys.exit(fail_out(args, EXIT_INPUT, e.message, e.detail))
    except Exception as e:  # 처리하지 못한 예외
        sys.exit(fail_out(args, EXIT_SKILL, "앞 글 유지 확인이 끝나지 못함", repr(e)))
