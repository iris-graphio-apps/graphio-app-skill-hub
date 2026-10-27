#!/usr/bin/env python3
"""설계 리포트 4.2절 원천 대조표의 근거 위치를 원천 문서 글자와 맞대 본다.

    python3 source_match.py <설계-리포트.md> --source <원천 문서> [...]
    python3 source_match.py <설계-리포트.md> --source <원천 문서> [...] --definition <정의 문서> [--json]

4.2절 표의 행마다 아래 대조 셋을 한다. 표의 칸 이름은 No.·답 요소·요소 종류·사용 CQ·판정·근거 위치·
처리·결정 No. 여덟이다. 이 스크립트는 판정·근거 위치·처리·답 요소·요소 종류 칸만 읽는다. 4.2절에는 비고 칸이
없어 근거 위치 칸만 본다.

    ① 근거 위치 글자 대조   판정이 있음·형태 다름·경유인 행. 근거 위치에 '테이블.컬럼' 꼴(앞에 '원천 문서 n절'이
                           붙어도 됨)이 있으면 그 이름을 원천 글자에서 식별자 경계 단위로 찾는다. 'id'·'no' 같은
                           짧은 이름이 다른 낱말 안에서 걸려 늘 있음이 되지 않게 부분 문자열로 찾지 않는다.
                           그 꼴이 없고 근거 위치에 --source 로 받은 원천 파일 이름(확장자를 뺀 이름 포함)이
                           있으면 비정형 자료 목록에 적힌 문서 타입을 근거로 든 행이다. 근거 위치에서 파일 이름과
                           절 표기(n절·n.n절)를 지운 나머지를 「·」「,」로 나눈 조각을 문서 이름으로 보고 그 원천
                           글자에서 찾는다. 둘 다 아니면 가를 수 없는 행이라 결과를 '확인 필요'로 낸다
    ② 없음 판정의 같은 이름 컬럼   판정이 없음인 행. 답 요소와 같은 이름의 컬럼이 원천에 있으면 짚는다.
                           기존 데이터만으로 잇는 매핑 테이블 후보를 보인 행(처리 「빼고 보고(후보 미채택)」
                           또는 「매핑 테이블 MT-nn」)도 판정이 없음이라 이 대조만 하고 ①은 하지 않는다.
                           근거 위치에 적힌 것은 없다고 본 근거라 맞댈 원천 위치가 없다
    ③ 처리와 정의 문서 요소 유무   --definition 을 줄 때. 처리가 「만듦」이면 정의 문서에 요소가 있어야 하고,
                           「빼고 보고」·「빼고 보고(후보 미채택)」이면 없어야 한다. 그 밖 처리 값(조인·매핑 테이블·
                           연쇄 제외·규격 제약)은 이 대조를 하지 않는다

판정이 확인 필요인 행은 ①·②를 하지 않는다. 판정 칸 값이 닫힌 값(있음·형태 다름·경유·없음·확인 필요) 밖이면
가를 수 없는 행이라 결과를 '확인 필요'로 낸다. 결과 '확인 필요'도 종료 코드 1에 넣어 사람이 보게 한다.

판정 칸은 괄호 앞 낱말로 가른다. 사람이 판정을 바로잡은 「있음(판정 정정: 확인 필요 → 있음)」은 「있음」이다.
처리 칸은 괄호 앞 낱말로 가르지 않고 글자 전체로 읽는다. 「빼고 보고(후보 미채택)」을 「빼고 보고」와 가르기 위함이다.

정의 문서의 데이터 구조 이름이 원천에 있는지(DOC-08)는 대조하지 않는다. 그 규칙은 수집 스크립트
(collect_findings.py)와 판정 스크립트(judge_structure.py)가 맡는다.

원천 문서는 모두 읽은 뒤에 대조한다. 하나라도 UTF-8 텍스트로 읽지 못하면 대조하지 않고 멈춘다. 읽지 못한 파일이
빠진 채 대조하면 그 파일에만 있는 이름이 모두 '원천에 없음'으로 올라가기 때문이다.

표준 출력은 '4.2절 No.·대조 종류·결과·원천 위치' 표다. --json 이면 표준 출력에 JSON 하나를 낸다.

    code         모두 맞으면 null. SOURCE_MISMATCH(1)·SOURCE_INPUT(2)·SKILL_UNEXPECTED(3). 이름은 멈춤 목록 1장 표의 코드
    passed       모두 맞으면 true
    rows         결과 행 [{No., 대조 종류, 결과, 원천 위치, 답 요소}]. 4.2절 행 차례, 같은 행 안에서는 대조 차례
    message_ko   사람용 한 줄
    model_hint   다음에 할 일
    detail       읽은 파일과 건수. 멈추면 까닭

종료 코드(멈춤 목록과 같은 뜻): 0 모두 맞음, 1 어긋난 행 있음('확인 필요' 포함, 오류 아님),
2 입력 쪽 멈춤(설계 리포트·원천 문서·정의 문서를 UTF-8로 읽지 못함, 4.2절 표나 칸 이름이 없음),
3 처리하지 못한 예외(스킬 쪽 실패), 4 출력 쓰기 실패(표준 출력).
"""
import argparse
import json
import os
import re
import sys

import definition_index as di
import design_report_index as dri

# 4.2절 표의 칸 이름. 읽을 때는 공백을 지운 꼴(답요소·근거위치)을 열쇠로 쓴다
COLUMNS = ("No.", "답 요소", "요소 종류", "사용 CQ", "판정", "근거 위치", "처리", "결정 No.")
KEYS = tuple(c.replace(" ", "") for c in COLUMNS)
HEADING = re.compile(r"^(#{1,6})\s*4\.2(?![\d.])")

BASIS = re.compile(r"(?:원천 문서 \d+(?:\.\d+)*절 )?([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)")  # 테이블.컬럼
SECTION = re.compile(r"\d+(?:\.\d+)*절")
VERDICTS = ("있음", "형태 다름", "경유", "없음", "확인 필요")
CHECK_BASIS = ("있음", "형태 다름", "경유")
MAKE = "만듦"
KEEP_OUT = ("빼고 보고", "빼고 보고(후보 미채택)")  # 처리 칸은 글자 전체로 읽음
UNSURE = "확인 필요"

CODES = {1: "SOURCE_MISMATCH", 2: "SOURCE_INPUT", 3: "SKILL_UNEXPECTED", 4: "OUTPUT_WRITE_FAILED"}


class InputError(Exception):
    """입력 쪽 멈춤(종료 코드 2)."""

    def __init__(self, message, **detail):
        super().__init__(message)
        self.detail = detail


# ── 칸 읽기 ──────────────────────────────────────────────────────────────────
def verdict(cell):
    """판정 칸 값. 괄호 앞 낱말로 가른다."""
    # 판정 칸 읽기 규칙은 설계 리포트 읽기 모듈(design_report_index.py)의 verdict() 한 곳에 두고 불러 쓴다
    return dri.verdict(cell)


def element_name(cell):
    """답 요소 칸(값 이름과 짧은 뜻)에서 이름만. 괄호·대시·쌍점 앞 글자다."""
    return re.split(r"[(（]|\s+[—–-]\s+|:\s", cell, 1)[0].strip()


def clean(cell):
    """칸 글자에서 서식 표지를 걷는다. 코드 표시 따옴표와 줄바꿈 표지다."""
    return re.sub(r"<br\s*/?>", " ", cell.replace("`", "")).strip()


def split_row(line):
    """표 한 줄을 칸으로 나눈다. 칸 안의 '\\|' 는 세로줄 글자로 둔다."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", body)]


def is_separator(cells):
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c.replace(" ", "")) for c in cells)


def tables(lines, start=0, end=None):
    """start~end 줄 안의 표 [(머리글 줄 번호, 머리글 칸, [(줄 번호, 칸)])]. 줄 번호는 1부터."""
    end = len(lines) if end is None else end
    out, i = [], start
    while i < end:
        if lines[i].lstrip().startswith("|") and i + 1 < end and is_separator(split_row(lines[i + 1])):
            head, rows, j = split_row(lines[i]), [], i + 2
            while j < end and lines[j].lstrip().startswith("|"):
                rows.append((j + 1, split_row(lines[j])))
                j += 1
            out.append((i + 1, head, rows))
            i = j
        else:
            i += 1
    return out


def read_report(text):
    """설계 리포트에서 4.2절 표를 읽는다. [(No., {칸 열쇠: 글자})]. 표나 칸 이름이 없으면 InputError."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if HEADING.match(line)), None)
    if start is None:
        raise InputError("설계 리포트에 4.2절 제목이 없음")
    level = len(HEADING.match(lines[start]).group(1))
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^#{1,%d}\s" % level, lines[i])), len(lines))
    found = tables(lines, start + 1, end)
    if not found:
        raise InputError("설계 리포트 4.2절에 원천 대조표가 없음", 줄=start + 1)
    header_line, head, rows = found[0]
    keys = [c.replace(" ", "") for c in head]
    missing = [c for c, k in zip(COLUMNS, KEYS) if k not in keys]
    if missing:
        raise InputError("설계 리포트 4.2절 원천 대조표에 칸 이름이 없음: %s" % "·".join(missing),
                         줄=header_line, 빠진_칸=missing)
    out = []
    for line, cells in rows:
        row = {k: clean(cells[i]) if i < len(cells) else "" for i, k in enumerate(keys)}
        out.append((row["No."] or "%d줄" % line, row))
    return out


# ── 원천 맞대기 ──────────────────────────────────────────────────────────────
def in_source(name, text):
    """식별자 경계 단위 맞대기. 앞뒤에 영문자·숫자·밑줄이 붙은 자리는 치지 않는다."""
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(name), text) is not None


def doc_list(basis, sources):
    """근거 위치에 파일 이름이 적힌 --source 원천(비정형 자료 목록). (파일 이름, 글자) 또는 None."""
    for path, text in sources:
        name = os.path.basename(path)
        if name in basis or os.path.splitext(name)[0] in basis:
            return name, text
    return None


def doc_names(basis, name):
    """근거 위치에서 파일 이름·절 표기를 지운 나머지 조각. 조각마다 문서 이름 하나다."""
    rest = SECTION.sub("", basis.replace(name, "").replace(os.path.splitext(name)[0], ""))
    return [x.strip() for x in re.split(r"[·,]", rest) if x.strip()]


def drop_file_names(basis, sources):
    """근거 위치에서 --source 파일 이름을 지운다. 'list.md' 같은 파일 이름이 테이블.컬럼 꼴로 뽑히지 않게 한다."""
    for path, _ in sources:
        basis = basis.replace(os.path.basename(path), " ")
    return basis


def source_columns(sources):
    """원천 문서 표에서 컬럼 이름 칸의 값 {casefold 이름: 원문}. 칸 이름에 '컬럼'이 들었거나 column 인 칸이다."""
    out = {}
    for _, text in sources:
        for _, head, rows in tables(text.splitlines()):
            idx = [i for i, c in enumerate(head) if "컬럼" in c or c.strip().lower() in ("column", "column name")]
            for _, cells in rows:
                for i in idx:
                    if i < len(cells):
                        value = clean(cells[i])
                        if value:
                            out.setdefault(value.casefold(), value)
                            out.setdefault(value.replace(" ", "").casefold(), value)
    return out


def same_name_column(name, columns):
    """답 요소와 같은 이름의 원천 컬럼. 대소문자와 띄어쓰기는 가리지 않는다. 없으면 None."""
    if not name:
        return None
    return columns.get(name.casefold()) or columns.get(name.replace(" ", "").casefold())


def definition_element(idx, name, kind):
    """정의 문서에서 답 요소 이름의 요소. 요소 종류로 찾을 곳을 정한다. 없으면 None."""
    found = idx.find_concepts(name) + idx.find_structures(name)
    if kind != "대상":   # 값·잇는 값, 또는 종류 칸이 비거나 닫힌 값 밖이면 속성·관계까지 찾는다
        found += [p for c in idx.concepts for p in c.children if p.name == name]
        found += idx.find_relations(name=name)
    return found[0] if found else None


def match_rows(rows, sources, idx):
    """대조 ①~③. 결과 행 [(No., 대조 종류, 결과, 원천 위치, 답 요소)]. 맞으면 행이 없다."""
    text = "\n".join(t for _, t in sources)
    columns = source_columns(sources)
    out = []
    for no, r in rows:
        v, basis, name = verdict(r["판정"]), r.get("근거위치", ""), element_name(r.get("답요소", ""))
        if v not in VERDICTS:  # 가를 수 없는 행
            out.append((no, "판정", UNSURE, r["판정"] or "(빈 칸)", name))
        elif v in CHECK_BASIS:  # 대조 ①
            names, doc = BASIS.findall(drop_file_names(basis, sources)), doc_list(basis, sources)
            if names:  # 정형: 테이블.컬럼
                out += [(no, "근거 위치", "원천에 없음", n, name) for n in names
                        if not (in_source(n, text) or in_source(n.split(".")[-1], text))]
            elif doc:  # 비정형 자료 목록에 적힌 문서 타입: 목록 문서의 문서 이름과 대조
                pieces = doc_names(basis, doc[0])
                if not pieces:
                    out.append((no, "근거 위치", UNSURE, basis, name))
                out += [(no, "근거 위치", "원천에 없음", "%s: %s" % (doc[0], d), name)
                        for d in pieces if d not in doc[1]]
            else:  # 가를 수 없는 행
                out.append((no, "근거 위치", UNSURE, basis or "(빈 칸)", name))
        elif v == "없음":  # 대조 ②. 매핑 테이블 후보 행(빼고 보고(후보 미채택)·매핑 테이블 MT-nn)도 이것만 함
            column = same_name_column(name, columns)
            if column:
                out.append((no, "없음 판정", "같은 이름 컬럼이 원천에 있음", column, name))
        handling = r.get("처리", "")
        if idx is not None and (handling == MAKE or handling in KEEP_OUT):  # 대조 ③
            el = definition_element(idx, name, r.get("요소종류", ""))
            if (el is not None) != (handling == MAKE):
                out.append((no, "처리", "정의 문서 요소 유무와 다름",
                            el.location() if el is not None else "정의 문서에 없음", name))
    return out


# ── 실행 ─────────────────────────────────────────────────────────────────────
def read(path, what):
    try:
        return di.read_text(path)
    except di.ReadError as e:
        raise InputError("%s를 읽지 못함: %s (%s)" % (what, e.path, e.problem), 문서=what, 경로=e.path, 문제=e.problem)


def run(report, sources, definition=None):
    """대조를 마친 결과 dict. 입력 쪽 멈춤은 InputError."""
    rows = read_report(read(report, "설계 리포트"))
    texts = [(p, read(p, "원천 문서")) for p in sources]  # 모두 읽은 뒤에 대조한다
    idx = di.DefinitionIndex(read(definition, "정의 문서").splitlines()) if definition else None
    found = match_rows(rows, texts, idx)
    unsure = sum(1 for f in found if f[2] == UNSURE)
    detail = {"설계 리포트": report, "원천 문서": list(sources), "정의 문서": definition,
              "대조 ③": "수행" if definition else "미수행(정의 문서 미제공)",
              "4.2절 행": len(rows), "결과 행": len(found), "확인 필요": unsure}
    if found:
        message = "설계 리포트 4.2절 근거 위치가 원천 문서 글자와 맞지 않음(%d건, 확인 필요 %d건)" % (len(found), unsure)
        hint = ("결과 행의 4.2절 No.마다 근거 위치·판정·처리를 원천 문서와 다시 맞대 고친다. "
                "'확인 필요' 행은 판정이나 근거 위치를 가를 수 없는 행이라 사람에게 보인다")
    else:
        message = "설계 리포트 4.2절 %d행이 원천 문서 글자와 모두 맞음" % len(rows)
        hint = "다음 걸음으로 간다"
    return {"code": None if not found else CODES[1], "passed": not found,
            "rows": [dict(zip(("No.", "대조 종류", "결과", "원천 위치", "답 요소"), f)) for f in found],
            "message_ko": message, "model_hint": hint, "detail": detail}


def stopped(code, message, hint, detail):
    return {"code": CODES[code], "passed": False, "rows": [], "message_ko": message,
            "model_hint": hint, "detail": detail}


def emit(args, res):
    """결과를 낸다(--json 이면 표준 출력에 JSON 하나, 아니면 사람용 줄). 읽는 쪽이 먼저 닫힌 파이프 같은 쓰기 실패면
    표준 오류 한 줄을 내고 False. 표준 출력을 os.devnull 로 돌려 해석기가 끝날 때 버퍼를 다시 비우다 실패하지 않게 한다."""
    try:
        if args.json:
            json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
            print()
        elif res["code"] in (CODES[2], CODES[3]):
            print("대조하지 않음: %s" % res["message_ko"], file=sys.stderr)
            print(res["model_hint"], file=sys.stderr)
        else:
            print(res["message_ko"])
            if res["rows"]:
                print()
                print("| 4.2절 No. | 대조 종류 | 결과 | 원천 위치 |")
                print("|---|---|---|---|")
                for r in res["rows"]:
                    print("| %s |" % " | ".join(str(r[k]).replace("|", "\\|")
                                                for k in ("No.", "대조 종류", "결과", "원천 위치")))
        sys.stdout.flush()
    except OSError as err:      # 읽는 쪽이 먼저 닫힌 파이프 → 종료 코드 4
        print("원천 대조 결과를 내지 못함: %s" % (err.strerror or err), file=sys.stderr)
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return False
    return True


def main():
    ap = argparse.ArgumentParser(
        description="설계 리포트 4.2절 원천 대조표의 근거 위치·판정·처리를 원천 문서 글자와 맞대 본다. "
                    "DOC-08(정의 문서의 데이터 구조 이름 대조)은 맡지 않는다.")
    ap.add_argument("report", help="설계 리포트. 4.2절 원천 대조표를 읽는다")
    ap.add_argument("--source", nargs="+", required=True, metavar="파일",
                    help="원천 문서(정형 원천 문서, 비정형 자료 목록). 하나라도 읽지 못하면 대조하지 않는다")
    ap.add_argument("--definition", metavar="파일",
                    help="정의 문서. 주면 처리와 정의 문서 요소 유무를 맞댄다(대조 ③)")
    ap.add_argument("--json", action="store_true", help="표준 출력에 JSON 하나로 낸다")
    args = ap.parse_args()
    try:
        res = run(args.report, args.source, args.definition)
        code = 0 if res["passed"] else 1
    except InputError as e:
        res = stopped(2, str(e), "빠진 입력을 채우거나 UTF-8로 바꾼 뒤 다시 수행한다. 대조 결과 행은 내지 않았다",
                      e.detail)
        code = 2
    except Exception as e:      # 처리하지 못한 예외가 종료 코드 1(어긋난 행 있음)로 읽히지 않게 3 으로 끝낸다
        res = stopped(3, "원천 대조 스크립트가 예상하지 못한 오류로 멈춤(%s: %s)" % (type(e).__name__, e),
                      "입력이나 옵션으로 풀리지 않는다. 스크립트를 고치지 말고 사용자에게 알린다",
                      {"예외": type(e).__name__})
        code = 3
    if not emit(args, res):
        return 4
    return code


if __name__ == "__main__":
    sys.exit(main())
