#!/usr/bin/env python3
"""설계 리포트가 다음 단계로 가도 되는지 가리는 관문 검사.
규칙 번호(DOC·CQS 등)를 내지 않는다. 산출물 품질 지적이 아니라 다음 단계로 가도 되는지 가리는 관문이기 때문이다.

    python3 check_design_report.py <설계 리포트> --stage 설계 [--stop-file <멈춤 질문 파일>] [--json]
    python3 check_design_report.py <설계 리포트> --stage 검증뒤 --definition <정의 문서> [--json]

정의 문서만 보는 검사는 check_design_doc.py 가 맡는다. 이 스크립트는 그 검사를 넓히지 않는다.
종료 코드: 0 통과, 1 빠짐·어긋남·요청서 옮김 누락(다음 단계로 가지 않음), 2 입력 쪽 멈춤(설계를 바꾸는 외부 수정 포함),
3 처리하지 못한 예외, 4 출력 쓰기 실패(파일·표준 출력).

관문은 --stage 로 고른다.

    설계     관문 1(⑥ 출력 앞). 문서 정보 표, 리포트 판 「설계 단계」, 2절 설계안 확인 「확인 대기」, 12절 정한 쪽,
             2절 건수와 뒤 절 줄 수, 입력 해시, CQ 번호 참조, 정의 문서가 아직 없음, 자료 등급과 개인정보 꼴,
             같은 차수 회차 사본이 남은 채 ⑥에서 기다리던 판을 덮어쓰지 않았는지.
             CQ 문서를 직접 읽어 4절 CQ 행 '해시/등급' 칸의 자리표시를 채워 쓴다. 설계 리포트에서 이 칸만 고쳐 쓰고
             그 밖의 결과는 표준 출력으로만 낸다
    확인     관문 2(⑦ 진입 앞). 설계안 확인 결과, 2절 사유와 12절 답이 온 길, 2절 회차·건수와 회차 사본·12절 행,
             입력 해시
    검증뒤   관문 4(판정 앞). 리포트 판 「검증 뒤」, 남은 「정의 문서 작성 뒤 기재」·「확인 대기」, 2절 건수와 정의 문서
             규모 표, 정의 문서와의 이름 맞대기(설계 리포트 먼저 차례), 입력 해시, CQ 문서에서 다시 셈한 '해시/등급'.
             설계 차이마다 수정 요청서 사람 요청 행 초안을 design_diff[] 의 '요청서 초안' 칸에 붙인다

맞대기 옵션
    --fix-request <N차 요청서> <N+1차 요청서>
             단계와 상관없이 N차 수정 요청서 「사람 요청과 CQ 변경」 절에서 옮겨야 할 행(출처와 상관없이 상태가
             「적용」·「적용 안 됨(…)」이 아닌 행)이 N+1차 요청서에 모두 있는지 No.로 맞댄다. 빠지면 종료 코드 1
    --external
             검증뒤 에서 검증만 모드의 외부 수정 자리임을 알린다. 설계 차이가 있으면 차례 위반 대신 설계를 바꾸는 외부
             수정으로 보고 검사하지 않고 멈춘다(종료 코드 2)
    --findings <구조 판정>
             검증뒤 끝에서 구조 판정의 Error·Warning 지적마다 수정 성격(정비·설계 변경·입력 변경, 답 전이면
             결정 필요)을 갈라 nature[] 에 낸다. 종료 코드에 영향이 없다

보조 출력: --diff 는 같은 차수의 앞 사본과 지금 판의 차이를 한 줄로 낸다. 관문 판정에 영향이 없다.
--render-stage6 은 검사하지 않고 멈춤 질문 파일로 ⑥ 출력을 다시 그린다.

--json 이면 표준 출력에 JSON 하나를 낸다. 칸은 code·stage·passed·missing·mismatches·design_diff·cq_changes·nature·
message_ko·model_hint·detail 이다. code 는 멈춤 목록(references/stop-catalog.md) 1장 표의 코드 이름이고 통과하면 null
이다. message_ko 는 사람용 문장이라 해시·옵션 이름을 넣지 않는다. 원문 예외와 종료 코드 숫자는 detail 에만 둔다.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

import check_design_doc as cdd
import definition_index as di
import judge_structure as js
import design_report_index as dri  # 읽기·비교·맞대기는 모두 이 모듈

STAGES = ("설계", "확인", "검증뒤")
GATES = {"설계": "관문 1(⑥ 출력 앞)", "확인": "관문 2(⑦ 진입 앞)", "검증뒤": "관문 4(판정 앞)"}
NEXT = {"설계": "⑥ 출력을 내지 않음", "확인": "⑦로 가지 않음", "검증뒤": "판정하지 않음"}

EXIT_PASS, EXIT_BLOCKED, EXIT_INPUT, EXIT_SKILL, EXIT_ENV = 0, 1, 2, 3, 4  # 4는 출력 쓰기 실패(파일·표준 출력)만, 10은 내지 않음
# 멈춤 JSON code. 멈춤 목록 1장 표의 코드 이름이다. 같은 종료 코드라도 어느 자리인지 이 이름으로 가른다
GATE_FAILED, GATE_CQ_HASH, DESIGN_FIRST_ORDER = "GATE_FAILED", "GATE_CQ_HASH", "DESIGN_FIRST_ORDER"
CARRY_MISSING, EXTERNAL_DESIGN_CHANGE = "CARRY_MISSING", "EXTERNAL_DESIGN_CHANGE"   # 요청서 옮김 누락 1, 외부 설계 변경 2
STOP_CODE = {EXIT_INPUT: "GATE_INPUT", EXIT_SKILL: "SKILL_UNEXPECTED", EXIT_ENV: "OUTPUT_WRITE_FAILED"}
HINT = {EXIT_INPUT: "입력 문서나 경로를 확인함. 입력이 바뀌었으면 입력 목록을 고쳐 ①부터 다시 함. 설계 리포트를 고쳐 "
                    "입력에 맞추지 않음",
        EXIT_SKILL: "스크립트를 고치지 말고 사용자에게 알림",
        EXIT_ENV: "출력 폴더의 쓰기 권한과 남은 공간을 확인한 뒤 같은 관문을 다시 수행함"}

PENDING = dri.PENDING
PENDING_SECTIONS = ("7.2", "10")       # 이 표기를 절 전체에 허용. 5.1절은 대표 표시 칸만
CQ_COL, FILL = dri.CQ_COL, dri.FILL
WAITING = "확인 대기"
STOP_HASH = "멈춤 질문 파일 설계 리포트 해시"
# 해시를 맞댄 자리의 사람용 문장. 사람용 출력에는 해시 값을 싣지 않는다
HASH_TEXT = {STOP_HASH: "설계 리포트가 멈춤 질문 파일을 쓴 뒤 바뀜"}


class InputStop(Exception):
    """입력 쪽 멈춤(종료 코드 2). message 는 사람용 문장이고 해시·경로는 detail 에만 둔다.
    hint 를 주면 멈춤 JSON 의 model_hint 를 그 글자로 낸다."""

    def __init__(self, message, detail="", hint=None):
        super().__init__(message)
        self.message, self.detail, self.hint = message, detail, hint


class OutputFail(Exception):
    """출력 파일 쓰기 실패(종료 코드 4). 관문 1이 설계 리포트 4절 CQ 행 칸을 쓰다 실패할 때만 난다."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message, self.detail = message, detail


INPUT_ERRORS = (InputStop, di.ReadError, js.PreviousError, json.JSONDecodeError)


class Result:
    """관문 한 번의 결과. missing 은 빠진 칸, mismatches 는 어긋난 자리, blocks 는 차례 위반 같은 멈춤이다.
    external 은 검증만 모드 외부 수정 자리에서 설계 차이가 나와 검사하지 않고 멈춘 것(종료 코드 2), carry_lost 는
    N+1차 수정 요청서에 옮기지 않은 N차 요청서 행의 No. 목록이다."""

    def __init__(self, stage):
        self.stage = stage
        self.missing, self.mismatches, self.design_diff, self.cq_changes, self.nature = [], [], [], [], []
        self.blocks, self.detail = [], {}
        self.external, self.carry_lost = False, []

    def expect(self, label, actual, expected):
        if actual is None:
            self.missing.append(label)
        elif dri.clean(actual) != expected:
            self.mismatch(label, actual, expected)

    def expect_count(self, name, written, actual):
        if written is None:
            self.missing.append("2절 「%s」 건수" % name)
        elif written != actual:
            self.mismatch("2절 「%s」 건수" % name, written, actual)

    def mismatch(self, where, written, expected):
        self.mismatches.append({"자리": where, "적힌 값": written, "맞아야 할 값": expected})

    def block(self, message, hint):
        self.blocks.append({"까닭": message, "할 일": hint})

    def blocked(self):
        return bool(self.missing or self.mismatches or self.blocks)

    def hash_changed(self):
        """CQ 문서가 4절 CQ 행 칸과 달라졌는가. 자리표시만 남은 것은 관문을 거치지 않은 리포트라 넣지 않는다."""
        return any(c["갈래"] != "자리표시 남음" for c in self.cq_changes)

    def code(self):
        if not self.blocked():
            return None
        if self.external:
            return EXTERNAL_DESIGN_CHANGE
        if self.hash_changed():
            return GATE_CQ_HASH
        if self.blocks:
            return DESIGN_FIRST_ORDER
        return CARRY_MISSING if self.carry_lost else GATE_FAILED

    def exit_code(self):
        """설계를 바꾸는 외부 수정은 입력 쪽 멈춤 2, 그 밖의 막힘은 1, 통과는 0."""
        if self.external:
            return EXIT_INPUT
        return EXIT_BLOCKED if self.blocked() else EXIT_PASS

    def message_ko(self):
        gate = GATES[self.stage]
        code = self.code()
        if code is None:
            return "%s 통과" % gate
        if code == EXTERNAL_DESIGN_CHANGE:
            return ("%s에서 사람이 고친 정의 문서에 설계를 바꾸는 차이가 있어 검사하지 않고 멈춤(설계 차이 %d건)"
                    % (gate, len(self.design_diff)))
        if code == CARRY_MISSING:
            return ("N차 수정 요청서의 행 %d건(No. %s)이 N+1차 수정 요청서에 옮겨지지 않아 다음 단계로 가지 않음"
                    % (len(self.carry_lost), ", ".join(map(str, self.carry_lost))))
        if code == GATE_CQ_HASH:
            return ("%s에서 CQ 문서가 설계 리포트 4절의 CQ 확인 값과 달라 다음 단계로 가지 않음(CQ %d건)"
                    % (gate, sum(1 for c in self.cq_changes if c["갈래"] != "자리표시 남음")))
        if code == DESIGN_FIRST_ORDER:
            return "%s에서 %s" % (gate, self.blocks[0]["까닭"])
        return "%s에서 빠진 칸 %d건·어긋난 자리 %d건이 나와 다음 단계로 가지 않음" % (
            gate, len(self.missing), len(self.mismatches))

    def model_hint(self):
        code = self.code()
        if code is None:
            return "다음 단계로 간다"
        if code == EXTERNAL_DESIGN_CHANGE:
            return EXTERNAL_HINT
        if code == CARRY_MISSING:
            return ("빠진 No.의 행을 N차 수정 요청서 「사람 요청과 CQ 변경」 절에서 N+1차 수정 요청서의 같은 절로 옮겨 적은 뒤 "
                    "다시 검사함")
        if code == GATE_CQ_HASH:
            return "CQ 문서를 바꿨으면 --fix 로 설계 수정 차수에서 반영"
        if code == DESIGN_FIRST_ORDER:
            return self.blocks[0]["할 일"]
        return ("missing·mismatches 의 자리를 설계 리포트에서 고친 뒤 같은 --stage 로 다시 수행함. 통과하기 전에는 %s"
                % NEXT[self.stage])

    def print_human(self):
        if "설계 차이" in self.detail:
            print(self.detail["설계 차이"])
        print(self.message_ko())
        for m in self.missing:
            print("- 빠짐: %s" % m)
        for m in self.mismatches:
            where = str(m.get("자리", ""))
            if where.startswith("4절 CQ "):
                continue        # CQ 확인 값 어긋남은 아래 CQ 변경 줄로 낸다
            if "까닭" in m:
                lost = "(No. %s)" % ", ".join(map(str, m["No."])) if m.get("No.") else ""
                print("- 어긋남: %s: %s%s" % (m.get("자리") or m.get("대상 키"), m["까닭"], lost))
            elif "해시" in where:     # 해시 값은 사람용 줄에 싣지 않는다
                print("- 어긋남: %s" % HASH_TEXT.get(where, "%s 다름" % where))
            else:
                print("- 어긋남: %s: %s → %s" % (m["자리"], m["적힌 값"], m["맞아야 할 값"]))
        for d in self.design_diff:
            print("- 설계 차이: %s %s %s" % (d["종류"], d["대상 키"], d["갈래"]))
        for c in self.cq_changes:
            print("- CQ 변경: %s %s" % (c["cq"], c["갈래"]))
        for b in self.blocks:
            print("- 멈춤: %s. %s" % (b["까닭"], b["할 일"]))
        for n in self.nature:
            where = "(맞댄 곳: %s)" % n["맞댄 곳"] if n.get("맞댄 곳") else ""
            print("- 성격: %s %s %s%s" % (n["지적"], n["규칙"], n["성격"], where))


def read_report(path, what):
    """설계 리포트(또는 그 사본)를 읽는다. 읽지 못하면 입력 쪽 멈춤. what 은 '…을/를' 까지 적은 이름이다."""
    try:
        return dri.read_report(path)
    except dri.ReportError as e:
        raise InputStop("%s 읽지 못함(%s)" % (what, e.problem), detail=str(e))


def report_stage(rep):
    """문서 정보 표 「리포트 판」 값. 행이 없으면 입력 쪽 멈춤."""
    if "리포트 판" not in rep.info:
        raise InputStop("설계 리포트 문서 정보 표에 리포트 판 행이 없음", detail=rep.path)
    return rep.info["리포트 판"]


# ── 관문 1: --stage 설계 ──────────────────────────────────────────────────────

DECIDED_BY = ("사람 수정", "사람", "기본값(사람 확인 없음)")


def decided_head(row):  # 정한 쪽 칸에서 ' · ' 앞 글자
    return dri.clean(row.get("정한쪽", "")).split(" · ")[0].strip()


def no_human(row):
    return decided_head(row) == "기본값(사람 확인 없음)"


# 2절 행 이름과 뒤 절. 절 항목은 절 번호 또는 (절, 행 거르기 함수)
COUNT_SECTIONS = (("개념", ("5.1",)), ("관계", ("6",)), ("원천 대조", ("4.2",)),
                  ("매핑 테이블 제안", ("7.1",)), ("문서 타입", ("7.2",)), ("확인 필요 사항", ("8",)),
                  ("제외 항목", ("9.1", "9.2")), ("입력 문서 간 불일치", ("11",)),
                  ("사람 확인 없음", (("12", no_human),)))


def check_design_stage(rep, res):
    for key, value in rep.info.items():
        if not value.strip():
            res.missing.append("문서 정보 표 「%s」 행" % key)
    res.expect("리포트 판", report_stage(rep), "설계 단계")
    res.expect("2절 설계안 확인", rep.summary_value("설계안 확인"), WAITING)
    for no, row in this_round_rows(rep):
        if dri.clean(row.get("고른값", "")) == WAITING and not row.get("정한쪽", "").strip():
            continue
        if decided_head(row) not in DECIDED_BY:
            res.mismatch("12절 No.%s 정한 쪽" % no, row.get("정한쪽"), " / ".join(DECIDED_BY))
    rep.pending_outside(PENDING, PENDING_SECTIONS, allow=("5.1", "대표표시"), res=res)
    for name, secs in COUNT_SECTIONS:  # 2절 행 이름과 절
        if not any(rep.is_pending(s if isinstance(s, str) else s[0]) for s in secs):
            res.expect_count(name, rep.summary_count(name), sum(rep.count_rows(s) if isinstance(s, str)
                                                                else sum(1 for _, r in rep.rows(s[0]) if s[1](r))
                                                                for s in secs))


PATTERN_BASIS_TITLE = ("구조", "꼴", "근거")  # 제목 낱말
REQUIRE_PATTERN_BASIS = False


def check_pattern_basis(rep, res, stage):
    """구조 꼴 선택 근거 절. 번호가 아니라 제목 낱말로 찾고, 표만 있고 설명 문장이 없으면 빠짐으로 센다."""
    if not REQUIRE_PATTERN_BASIS:
        return
    span = js.find_section(rep.heads, PATTERN_BASIS_TITLE)
    if span is None:
        res.missing.append("구조 꼴 선택 근거 절")
        return
    table_mark = chr(124)  # 표 줄의 첫 글자
    prose = [ln for ln in rep.lines[span[0]:span[1]]
             if ln.strip() and not ln.lstrip().startswith(("#", table_mark))]
    if not prose:
        res.missing.append("구조 꼴 선택 근거 절의 설명 문장(표만 있음)")


def sha12(path):
    return dri.sha12_file(path)


INPUT_ROWS = ("CQ 문서", "참고 문서", "스타일 가이드", "서식 가이드")


def check_input_hashes(rep, res=None, skip=()):
    """문서 정보 표 입력 행의 '(경로) (해시 앞 12자)' 를 지금 파일과 맞댄다. 다르면 입력 쪽 멈춤.
    해시가 적히지 않은 입력 행은 res 의 빠짐으로 센다. skip 에 든 행은 해시가 달라도 멈추지 않는다."""
    for label, path, written in rep.input_hashes(INPUT_ROWS):
        if written is None:
            if res is not None:
                res.missing.append("문서 정보 표 「%s」 행의 입력 해시" % label)
            continue
        full = rep.resolve(path)
        if not os.path.exists(full):
            raise InputStop("입력 파일 없음", detail=path)
        if sha12(full) != written and label not in skip:
            raise InputStop("입력 문서가 설계 리포트를 쓴 뒤 바뀜", detail="%s (%s → %s)" % (label, written, sha12(full)))


def check_cq_refs(rep, res):
    known = rep.cq_keys("4.1")
    for sec in ("5.1", "6", "7.1", "7.2"):
        for no, cq in rep.cited_cqs(sec, "근거cq"):
            if cq not in known:
                res.mismatch("%s절 No.%s 근거 CQ" % (sec, no), cq, "4.1절에 있는 CQ 번호")


def this_round_rows(rep):
    """12절에서 이번 차수에 더한 행만 고른다. 앞 차수 행으로 관문 1·2를 통과시키지 않는다."""
    rows = rep.rows("12")
    prev_path = rep.info_path("앞 차수 설계 리포트")
    if not prev_path:
        return rows
    prev = read_report(rep.resolve(prev_path), "앞 차수 설계 리포트를")  # 읽지 못하면 InputStop, 종료 코드 2
    old = {no for no, _ in prev.rows("12")}
    return [(no, row) for no, row in rows if no not in old]


def check_definition_absent(rep, res):
    own = rep.info_path("정의 문서")
    if not own:
        res.missing.append("문서 정보 표 「정의 문서」 행의 경로")
        return
    prev_path = rep.info_path("앞 차수 설계 리포트")
    if prev_path and own == read_report(rep.resolve(prev_path), "앞 차수 설계 리포트를").info_path("정의 문서"):
        res.mismatches.append({"자리": "문서 정보 표 「정의 문서」 행", "까닭": "정의 문서 행을 이번 차수 경로로 갱신하지 않음"})
        return
    path = rep.resolve(own)
    if os.path.exists(path):
        res.mismatches.append({"자리": "문서 정보 표 「정의 문서」 행", "경로": path,
                               "까닭": "정의 문서가 설계안 확인보다 먼저 생김"})


def copy_round(path):  # 회차 사본 이름 -r<n> 의 n
    m = re.search(r"-r(\d+)\.md$", dri.nfc(os.path.basename(path)))
    return int(m.group(1)) if m else 0


def answer_rows(rep):
    """12절에서 ⑥ 답을 적은 행의 No. 집합. 멈춤이 「설계안 확인」·「⑥(N차)」 이거나 대상이 입력 문서인 행이다."""
    return {str(no) for no, row in rep.rows("12")
            if dri.clean(row.get("멈춤", "")) == "설계안 확인" or SIX_ROUND.match(dri.clean(row.get("멈춤", "")))
            or dri.clean(dri.pick(row, "대상")).startswith("입력 문서")}


def check_round_copies(rep):
    """관문 1. 같은 차수 회차 사본이 남았는데 설계 리포트가 새 판임을 보이지 못하면 앞 실행이 ⑥에서 기다리던
    「확인 대기」 판을 덮어쓴 것으로 보고 입력 쪽 멈춤. 관문 1에서는 2절 설계안 확인이 「확인 대기」라 회차 수가
    적히지 않으므로 둘 가운데 하나면 통과한다. 설계 리포트가 회차 사본 가운데 하나와 같은 판(이어 가기·되돌림)이거나,
    마지막 회차 사본에 없던 ⑥ 답 행이 12절에 있음(답을 받아 고친 판)."""
    copies = [read_report(p, "회차 사본을") for p in sorted(rep.round_copies(), key=copy_round)]
    if not copies:
        return
    last = copies[-1]
    if any(c.text == rep.text for c in copies) or answer_rows(rep) - answer_rows(last):
        return
    raise InputStop("「확인 대기」 판을 덮어씀. 앞 판은 회차 사본 r%d에 있음" % copy_round(last.path),
                    detail=last.path, hint="12절에 이번 ⑥ 답 행이 있는지 먼저 확인하고, 없으면 덮어쓴 리포트를 회차 사본으로 "
                                           "되돌리고 사람에게 알림")


STOP_KEYS = ("stop", "seq", "design_report", "upper", "text_md")


def load_stop(path):
    """멈춤 질문 파일(JSON)을 읽는다. 읽지 못하거나 JSON 객체가 아니면 입력 쪽 멈춤."""
    try:
        data = json.loads(di.read_text(path))
    except di.ReadError as e:  # 읽기 오류 문장에는 경로가 이미 있음(경로 한 번)
        raise InputStop("멈춤 질문 파일을 읽지 못함", detail=str(e))
    except ValueError as e:
        raise InputStop("멈춤 질문 파일을 읽지 못함", detail="%s: %s" % (path, e))
    if not isinstance(data, dict):
        raise InputStop("멈춤 질문 파일을 읽지 못함", detail="%s: JSON 객체가 아님" % path)
    return data


def check_stop_file(rep, res, path):
    data = load_stop(path)
    res.missing += ["멈춤 질문 파일 「%s」 칸" % k for k in STOP_KEYS
                    if k not in data or (k != "upper" and not data.get(k))]  # upper 는 빈 목록 허용
    report = data.get("design_report") if isinstance(data.get("design_report"), dict) else {}
    res.expect(STOP_HASH, report.get("sha12"), sha12(rep.path))
    # upper[].key 집합 맞대기: 확인 대상 자리를 설계 리포트 서식과 설계안 확인 문서가 정한 뒤 더함


# ── 관문 2: --stage 확인 ──────────────────────────────────────────────────────

REASONS = ("사람 확인", "사전 지시")
REASON_TAILS = {"사람 확인": ("채팅", "버튼", "답 파일", "일괄"), "사전 지시": ("사전 지시",)}
DIRECTIVE_SOURCES = ("호출 글", "멈춤 답", "run_directives")
CONFIRMED = re.compile(r"^\d{4}-\d{2}-\d{2}, 확인\(\d+회\. .+\)$")       # 사람 확인
UNCONFIRMED = re.compile(r"^미확인 진행\(사전 지시: (.+)\)$")              # 사전 지시
SIX_ROUND = re.compile(r"^⑥\(\d+차\)$")      # '사람 수정' 행의 멈춤 칸(서식 12절 칸 표 「멈춤」 행 예외)


def confirm_reason(value):  # 2절 '설계안 확인' 값 → (사유, 출처). 닫힌 꼴이 아니면 (None, None)
    value = value.strip()
    if CONFIRMED.match(value):
        return "사람 확인", None
    m = UNCONFIRMED.match(value)
    return ("사전 지시", m.group(1).strip()) if m else (None, None)


def decided_tail(row):  # 12절 정한 쪽 칸에서 ' · ' 뒤 글자(답이 온 길)
    parts = dri.clean(row.get("정한쪽", "")).split(" · ", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def check_reason_tail(rep, res):
    value = dri.clean(rep.summary_value("설계안 확인") or "")
    if not value or value.startswith(WAITING):
        return  # check_confirm_stage 가 빠짐으로 셈
    reason, source = confirm_reason(value)
    if reason is None:
        return res.mismatch("2절 설계안 확인", value, "YYYY-MM-DD, 확인(n회. …) / 미확인 진행(사전 지시: 출처)")
    if reason == "사전 지시" and source not in DIRECTIVE_SOURCES:
        res.mismatch("2절 사전 지시 출처", source, " / ".join(DIRECTIVE_SOURCES))
    for no, row in this_round_rows(rep):
        stop = dri.clean(row.get("멈춤", ""))
        if stop != "설계안 확인" and not SIX_ROUND.match(stop):  # ②-2 답(원천 확인) 행은 맞대지 않음
            continue
        tail = decided_tail(row)
        if tail not in REASON_TAILS[reason]:
            res.mismatch("12절 No.%s 정한 쪽 답이 온 길" % no, tail, " / ".join(REASON_TAILS[reason]))


def check_summary_vs_log(rep, res):
    rows = [row for _, row in rep.rows("12")]
    counts = {"설계안 확인": len(rep.round_copies()),  # 회차 사본 -r<n> 수
              "입력 문서 추가": sum(1 for row in rows if dri.clean(row.get("대상", "")).startswith("입력 문서"))}
    if rep.summary_has("사람 수정"):  # 2절에 그 칸을 둔 경우만
        counts["사람 수정"] = sum(1 for row in rows if decided_head(row).startswith("사람 수정"))
    for name, n in counts.items():
        written = rep.summary_number(name)  # 2절 값에서 첫 숫자(회·건)를 읽음. 칸이 없으면 None
        if written is not None and written != n:
            res.mismatch("2절 %s" % name, written, "12절 %d행" % n)


PII_PATTERNS = {"전화번호": r"(?<!\d)01[016789]-?\d{3,4}-?\d{4}(?!\d)",
                "주민등록번호": r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)",
                "이메일": r"[\w.+-]+@[\w-]+\.[\w.]+"}


def check_personal_data(rep, res):
    """자료 등급이 「구조 정보만」이면(칸이 없으면 이 값) 설계 리포트에서 개인정보 꼴을 찾는다.
    걸린 자리는 줄 번호와 꼴 이름만 내고 값은 싣지 않는다."""
    if dri.clean(rep.info.get("자료 등급", "구조 정보만")) != "구조 정보만":
        return
    for n, line in enumerate(rep.lines, 1):
        for name, pat in PII_PATTERNS.items():
            if re.search(pat, line):
                res.mismatches.append({"자리": "설계 리포트 %d줄" % n, "까닭": "구조 정보만 등급에 %s 꼴" % name})


def check_confirm_stage(rep, res, args):
    value = dri.clean(rep.summary_value("설계안 확인") or "")
    if not value or value.startswith(WAITING):
        res.missing.append("2절 설계안 확인 결과(아직 확인 대기)")
    raised = load_stop(args.stop_file).get("upper", []) if args.stop_file else []
    if raised and not any(dri.clean(row.get("멈춤", "")) == "설계안 확인" for _, row in this_round_rows(rep)):
        res.missing.append("12절 설계안 확인 행")
    try:
        check_input_hashes(rep, res)
    except InputStop as e:
        raise InputStop("입력이 ⑥ 뒤에 바뀜", detail=e.detail)
    check_definition_absent(rep, res); check_reason_tail(rep, res); check_summary_vs_log(rep, res)


# ── 관문 4: --stage 검증뒤 ────────────────────────────────────────────────────

def check_after_verify(rep, res, args):
    res.expect("리포트 판", report_stage(rep), "검증 뒤")
    for mark in (PENDING, WAITING):
        res.mismatches += [{"자리": "설계 리포트 %d줄" % n, "까닭": "검증 뒤 판에 「%s」 남음" % mark}
                           for n in rep.find_lines(mark)]
    for key in ("정의 문서", "검증 리포트"):
        own = rep.info_path(key)
        if not own or not os.path.exists(rep.resolve(own)):
            res.missing.append("문서 정보 표 「%s」 행의 파일" % key)
    lines = di.read_text(args.definition).splitlines()  # ReadError 는 종료 코드 2
    st = cdd.collect_stats(lines, cdd.read_blocks(lines))
    for name in ("개념", "관계"):
        res.expect_count(name, rep.summary_count(name), st[name])
    check_cq_hashes(rep, res)
    # CQ 문서가 바뀐 것을 번호별로 가렸으면 그 행의 파일 해시 차이로 따로 멈추지 않는다
    check_input_hashes(rep, res, skip=("CQ 문서",) if res.hash_changed() else ())
    idx = di.DefinitionIndex(lines)
    stamp = (rep.round_no(), sha12(rep.path))     # 요청서 초안 '기준' 칸: 설계 리포트의 차수와 해시 앞 12자
    res.design_diff = [dict(d, **{"요청서 초안": request_draft(d, *stamp)}) for d in dri.design_diff(rep, idx)]
    check_order(res, args)
    if args.findings:
        res.nature = classify_natures(rep, idx, args.findings)
    if args.last_confirmed:
        check_after_confirm(rep, read_report(args.last_confirmed, "마지막 확인 회차 사본을"), res)


def request_draft(d, round_no, report_sha12):
    """설계 차이 한 건의 수정 요청서 「사람 요청과 CQ 변경」 절 사람 요청 행 초안 칸. 파일은 쓰지 않고 값으로만 낸다.
    요청서에 옮겨 쓰는 일은 수정·검증 절차 지시문 몫이다."""
    return {"출처": "사람 요청", "기준": "%d차 %s" % (round_no, report_sha12), "대상 키": d["대상 키"],
            "바꿀 내용": "%s %s" % (d["종류"], d["갈래"]) + (" (%s)" % d["꼴"] if d.get("꼴") else ""),
            "성격": "설계 변경", "상태": "해석 필요", "근거": ""}


EXTERNAL_STOP = "설계를 바꾸는 외부 수정이 있어 검사하지 않고 멈춤"
EXTERNAL_TODO = "바뀐 설계를 수정 요청서의 사람 요청 행으로 옮기고 설계 수정 차수에서 반영함"     # 사람용 줄
EXTERNAL_HINT = "design_diff[].요청서 초안을 -N차 요청서 사람 요청 행으로 쓰고 사용자에게 --fix 를 안내함"


def check_order(res, args):
    """1차 생성과 설계 수정 차수에서 설계 리포트와 정의 문서의 설계 차이가 한 건이라도 있으면 차례 위반으로 멈춘다.
    검증만 모드의 외부 수정 자리(--external)에서는 같은 차이를 설계를 바꾸는 외부 수정으로 알리고 검사하지 않고
    멈춘다(종료 코드 2). 어긋남을 정의 문서 쪽으로 맞추라는 안내는 내지 않는다."""
    if not res.design_diff:
        return
    if args.external:
        res.external = True
        res.block(EXTERNAL_STOP, hint=EXTERNAL_TODO)
    else:
        res.block("설계 리포트 먼저 차례 위반(⑦·⑨ 설계 변경이 설계 리포트에 먼저 들어가지 않음)",
                  hint="설계 리포트를 먼저 고치고 정의 문서에 옮긴 뒤 다시 검사함")


def round_of_copy(path):
    """회차 사본의 차수. 이름 <이름>-온톨로지-설계-리포트-N차-r<n>.md 의 N차, 그 꼴이 아니면 사본의 「차수」 행."""
    n = dri.round_of_name(path)
    return n if n is not None else read_report(path, "사본을").round_no()


def same_round(rep, snap_path):  # 마지막 확인 회차 사본과 앞 회차 사본은 같은 차수 사본만 받음
    if rep.round_no() != round_of_copy(snap_path):
        raise InputStop("다른 차수의 회차 사본", detail=snap_path)


def check_after_confirm(rep, snap, res):
    same_round(rep, snap.path)
    noted = (rep.summary_value("설계안 확인 후 변경") or "") + "\n".join(rep.note_lines("※ 변경"))
    for key in sorted(dri.names(snap).symmetric_difference(dri.names(rep))):
        text = dri.key_text(key)  # 개념 이름, 개념 › 속성, 관계(출발 → 도착)
        if text not in noted:
            res.mismatches.append({"대상 키": text, "까닭": "설계안 확인 뒤 바뀌었는데 2절 기록이 없음"})


# ── CQ 번호별 문장 해시: 관문 1 채움, 관문 4 다시 셈 ──────────────────────────

def previous_numbers(rep):
    """관문 1. 번호 없는 CQ 문서의 번호 잇기에 쓸 앞 차수 번호 {문장 해시 앞 12자: 번호}. 문서 정보 표
    「앞 차수 설계 리포트」 4절 '해시/등급' 칸을 뒤집는다. 그 행이 「해당 없음」이면(1차) None."""
    prev_path = rep.info_path("앞 차수 설계 리포트")
    if not prev_path:
        return None
    prev = read_report(rep.resolve(prev_path), "앞 차수 설계 리포트를")  # 읽지 못하면 InputStop, 종료 코드 2
    return dri.cq_previous(prev.cells("4", CQ_COL))


def fill_cq_hashes(rep, path):  # 관문 1(--stage 설계, ⑥ 출력 앞)
    cq_paths = rep.input_paths("CQ 문서")
    if not cq_paths:
        return False
    previous = previous_numbers(rep)
    now = dri.cq_hashes(cq_paths, previous)  # {CQ 번호: "해시 앞 12자/등급"}
    text = rep.with_cells("4", CQ_COL, now, only=FILL, dups=dri.cq_duplicates(cq_paths, previous))  # 자리표시 칸만 바꿈
    if text != rep.text:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:  # 출력 파일 쓰기 실패 → 종료 코드 4
            raise OutputFail("설계 리포트에 CQ 확인 값을 쓰지 못함", detail=str(e))
    return True


def check_cq_filled(rep, res, filled):
    """관문 1이 채우지 못한 4절 CQ 행. '해시/등급' 칸이 없거나, CQ 문서를 읽었는데 그 번호가 없어 자리표시가
    남은 행이다. CQ 문서 파일이 없으면(filled 가 거짓) 칸이 있는지만 본다."""
    if not dri.has_cq_hash(rep):
        res.missing.append("4.1절 '%s' 칸" % CQ_COL)
        return
    if not filled:
        res.detail["CQ 확인 값"] = "CQ 문서 파일이 없어 채우지 않음"
        return
    dups = dri.cq_duplicates(rep.input_paths("CQ 문서"), previous_numbers(rep))
    for no, value in sorted(rep.cells("4", CQ_COL, dups).items()):
        if value == FILL:
            res.missing.append("4절 CQ %s %s(CQ 문서에서 그 번호를 찾지 못함)" % (no, CQ_COL))


def check_cq_hashes(rep, res):  # 관문 4(--stage 검증뒤, 판정 앞)
    cq_paths = rep.input_paths("CQ 문서")
    if not cq_paths:
        res.detail["CQ 확인 값"] = "CQ 문서 파일이 없어 맞대지 않음"
        return
    previous = dri.cq_previous(rep.cells("4", CQ_COL))  # 번호 없는 CQ 문서는 관문 1이 이은 4절 번호를 그대로 씀
    dups = dri.cq_duplicates(cq_paths, previous)
    now, kept = dri.cq_hashes(cq_paths, previous), rep.cells("4", CQ_COL, dups)
    for no in sorted(set(now) | set(kept)):
        kind = dri.cq_change(kept.get(no), now.get(no))  # 더함·뺌·문장 바뀜·등급 바뀜, 자리표시 남음
        if kind:
            res.cq_changes.append({"cq": no, "갈래": kind})
            res.mismatch("4절 CQ %s 해시/등급" % (no,), kept.get(no), now.get(no))


# ── 수정 요청서 옮김 누락: --fix-request ─────────────────────────────────────

REQUEST_SECTION = ("사람 요청", "CQ 변경")       # 수정 요청서 「사람 요청과 CQ 변경」 절 제목 낱말


def read_request(path):
    """수정 요청서 「사람 요청과 CQ 변경」 절 표의 행 [{no, 출처, 상태}]. 판정 지적 표(3·4·5절)는 세지 않는다.
    읽지 못하면 입력 쪽 멈춤. 그 절이 없거나 표 대신 「해당 없음」만 있으면 빈 목록이다."""
    try:
        lines = di.read_text(path).splitlines()
    except di.ReadError as e:  # 읽기 오류 문장에는 경로가 이미 있음(경로 한 번)
        raise InputStop("수정 요청서를 읽지 못함(%s)" % e.problem, detail=str(e))
    span = js.find_section(js.headings(lines), REQUEST_SECTION)
    found = js.tables(lines, span) if span else []
    if not found:
        return []
    head, rows = found[0]
    ni, si, ti = (js.column(head, name) for name in ("No.", "출처", "상태"))
    if None in (ni, si, ti):
        raise InputStop("수정 요청서 「사람 요청과 CQ 변경」 절 표에 No.·출처·상태 칸이 없음", detail=path)
    return [{"no": dri.clean(js.cell(r, ni)), "출처": dri.clean(js.cell(r, si)), "상태": dri.clean(js.cell(r, ti))}
            for r in rows if dri.clean(js.cell(r, ni))]


def must_carry(row):
    """N+1차 요청서로 옮겨야 하는 행. 출처와 상관없이 상태가 아직 「적용」·「적용 안 됨(…)」이 아닌 행이다."""
    state = row.get("상태", "")
    return not state.startswith(("적용 안 됨", "적용"))


def number_key(no):  # No. 차례. 정수가 아닌 No.는 뒤에 글자 차례로
    return (0, int(no), "") if no.isdigit() else (1, 0, no)


def check_request_carryover(prev_path, next_path, res):
    """N차 요청서에서 옮겨야 할 행의 No.가 N+1차 요청서에 모두 있는가. No.는 이어 매기고 지우지 않으므로 집합
    포함으로 센다. 빠지면 res 의 어긋남(종료 코드 1, code CARRY_MISSING). 빠진 No.는 요청서 칸 글자 그대로 낸다."""
    prev, nxt = read_request(prev_path), read_request(next_path)
    lost = sorted({r["no"] for r in prev if must_carry(r)} - {r["no"] for r in nxt}, key=number_key)
    if lost:
        res.carry_lost = lost
        res.mismatches.append({"자리": "수정 요청서 N+1차", "까닭": "옮기지 않은 행", "No.": lost})


# ── 성격 가르기: --findings ───────────────────────────────────────────────────
# 구조 판정의 Error·Warning 지적마다 수정 성격을 가른다. 고정 성격은 규칙 번호로, 하위 경우마다 성격이 다른 규칙은
# 판정 지적의 외부 코드나 문제 설명 글자로 가른 뒤 설계 리포트 절·칸과 맞댄다. 맞댄 결과는 고칠 값이 설계 리포트에
# 이미 있으면 정비, 요소를 더하거나 지우거나 설계 칸 값을 바꿔야 하면 설계 변경이다. 설계 리포트가 가리키지 않는
# 요소를 지우는 수정은 정비다. 가르지 못하면 설계 변경으로 둔다.

FIX, DESIGN, INPUT, DECIDE = "정비", "설계 변경", "입력 변경", "결정 필요"  # DECIDE 는 답 전 상태라 요청서 성격 칸에 적지 않음
FIXED = {"DOC-01": FIX, "DOC-02": FIX, "DOC-03": FIX, "DOC-04": FIX, "DOC-05": FIX, "DOC-06": FIX, "DOC-07": FIX,
         "DOC-11": FIX, "CNV-01": FIX, "SPC-01": FIX, "SPC-02": FIX, "GDE-01": FIX, "GDE-02": FIX,
         "CQS-01": DECIDE, "CQS-02": DECIDE, "CQS-03": DESIGN, "CQS-04": DESIGN, "CQS-05": DESIGN,
         "CQS-06": INPUT, "CQS-07": DECIDE, "INP-01": INPUT}  # fix-procedure.md 3장 규칙 표 성격 칸의 고정 값
# 외부 코드 → 성격 또는 CASE_BY_CASE 열쇠. 외부 코드 칸은 가운뎃점(DOC-04)·쉼표(GDE)로 이어지므로 나눠 찾음
BY_CODE = {"GOS61011": DESIGN, "GOS61106": DESIGN, "GOS61203": DESIGN, "GOS61330": DECIDE,
           "C-01": DESIGN, "C-02": DESIGN, "C-03": DESIGN, "C-04": DESIGN,
           "GOS61005": "속성 수", "GOS61010": "속성 수", "GOS61008": "식별 속성", "GOS61016": "근거 위치",
           "GOS61108": "조인 속성", "GOS61110": "조인 속성", "GOS61109": "조인 속성", "GOS61111": "조인 속성",
           "GOS61002": "개념", "GOS61021": "매핑 개념", "GOS61107": "끝 개념", "GOS61102": "관계",
           "C-14": "끝 개념", "C-15": "연결 키"}
# 외부 코드가 '해당 없음'인 지적(CNV-01 전부, SPC-01·02 코드 없는 지적)은 문제 설명 글자의 앞부분으로 찾음.
# 글자는 collect_findings.py 변환표의 문제 설명이다. CNV-01 서식 값 9종은 정비, 나머지 6종은 건마다 가름
BY_PROBLEM = {"참·거짓 칸의 값": FIX, "화면 색이 #RRGGBB 꼴이 아니어서": FIX, "속성 표에 '속성' 또는": FIX,
              "데이터 타입이 7종에 없어": FIX, "관계 방향을 3종": FIX, "데이터 구조 종류가 3종": FIX,
              "컬럼 이름 칸이 비어": FIX, "매핑 제목이": FIX,
              "개념 이름이 규격 형식을 어겨": "개념", "속성 표가 없어": "속성 수", "속성 이름 칸이 비어": "빈 속성",
              "관계 행에 빈 칸이 있어": "관계 행", "속성 매핑 표가 없어": "근거 위치", "속성 매핑 행의": "근거 위치",
              "데이터 구조 이름이 없음": "데이터 구조", "매핑할 데이터 구조 이름이 없음": "데이터 구조",
              "매핑한 데이터 구조가 Meta Type 절에 없음": "데이터 구조",
              "양쪽 조인 속성의 데이터 타입이 다름": DECIDE, "도착 쪽 조인 속성이 식별 속성이 아님": DECIDE}
BY_RULE = {"DOC-08": "구조 이름", "DOC-15": "구조 표지", "DOC-12": "원천", "DOC-13": "근거 위치",
           "DOC-14": "연결 근거", "MAP-01": "매핑 근거"}
GDE02 = {"5.1": DESIGN, "5.4": DESIGN, "5.6": DESIGN, "10": DESIGN,  # 기본 서식 가이드 절 번호
         "4.1": "개념", "4.5": "식별 속성", "6.1": "데이터 구조", "7.2": "근거 위치"}
NAME_RE = re.compile(r"^[a-zA-Z가-힣][a-zA-Z0-9가-힣_]{0,49}$")      # 규격의 개념 이름 형식
BLANK_CELLS = {"관계 이름": "관계", "source": "출발", "target": "도착",
               "source 속성": "조인 속성", "target 속성": "조인 속성"}       # 관계 행 빈 칸 → 6절 칸. 방향 칸은 6절에 없음
EXTERNAL_LINE = re.compile(r"^※ 외부 수정 \d+\s*:")


def located(f):
    """판정 지적의 첫 위치를 (머리말, 값) 으로. 풀지 못하면 ValueError(di.LocationError)."""
    return di.parse_location(di.split_locations(f["위치"])[0])


def element(f):
    return located(f)[1]


def row_of(rep, no, col, name):
    return next((r for _, r in rep.rows(no) if dri.clean(dri.pick(r, col)) == name), None)


def label(name):
    """데이터 구조 이름의 테이블 꼴. 마지막 토막을 소문자로(4.2절 근거 위치 읽기와 같은 꼴)."""
    return (name or "").split(".")[-1].strip().lower()


def source_tables(cell):
    """5.1절 원천 칸에 적힌 테이블·문서 이름의 테이블 꼴 집합. 괄호 안 글자(4.2절 No.)는 읽지 않는다."""
    text = re.sub(r"[(（][^)）]*[)）]", " ", dri.clean(cell))
    return {label(t) for t in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", text)}


def relation_of(idx, f):
    """관계 지적의 (이름, 출발, 도착). 위치가 '정의 문서 n줄' 이면 그 줄의 관계 행에서 읽는다."""
    head, v = located(f)
    if head == "관계":
        return v["name"], v["source"], v["target"]
    el = idx.element_at(v["line"]) if v.get("line") else None
    if el is None or el.kind != "관계":
        raise ValueError("관계를 가리키는 위치가 아님")
    return el.name, el.source, el.target


def relation_row(rep, name, source=None, target=None):
    """6절 관계 행 하나. 이름·출발·도착이 모두 같은 행, 없으면 이름과 한쪽 끝이 같은 행, 그래도 없으면 이름이 같은
    행을 찾는다(끝 개념 이름이 틀린 지적). 이름이 비었으면 양끝으로 찾는다. 하나로 정해지지 않으면 None."""
    rows = [r for _, r in rep.rows("6")]
    tries = [[(k, v) for k, v in (("관계", name), ("출발", source), ("도착", target)) if v]]
    if name:
        tries += [[("관계", name), ("출발", source)], [("관계", name), ("도착", target)], [("관계", name)]]
    for pairs in tries:
        if not pairs or not all(v for _, v in pairs):
            continue
        found = [r for r in rows if all(dri.clean(r.get(k, "")) == v for k, v in pairs)]
        if found:
            return found[0] if len(found) == 1 else None
    return None


def joined_by(rep, concept, prop):
    """concept 의 prop 이 6절 관계의 조인 속성이고 그 행 연결 근거에 연결 키 컬럼이 있는가."""
    return any(prop in dri.split_join(dri.pick(r, "조인 속성"))
               and concept in (dri.clean(r.get("출발", "")), dri.clean(r.get("도착", "")))
               and dri.TABLE_COLUMN.search(dri.clean(dri.pick(r, "연결 근거"))) for _, r in rep.rows("6"))


def marked_structure(rep, idx, f):  # DOC-08·15: 채택한 매핑 테이블·문서 타입인데 표지만 빠짐
    name = element(f).get("name")
    adopted = {n for n, taken in rep.adopted_mts("7.1") if taken}
    return FIX if name in adopted or name in rep.col("7.2", "이름") else DECIDE


def concept_source(rep, idx, f):  # DOC-12: 5.1절 원천 칸에 원천 테이블·문서 종류가 있으면 매핑을 더하는 정비
    row = row_of(rep, "5.1", "개념", element(f).get("name"))
    return FIX if row and not dri.is_none(dri.pick(row, "원천")) else None


def column_basis(rep, idx, f):
    """DOC-13·GOS61016, 매핑 표 없음·매핑 행 빈 칸: 4.2절 근거 위치(조인 속성이면 6절 연결 근거)에 그 데이터 구조의
    컬럼이 있으면 설계대로 매핑을 적는 정비."""
    head, v = located(f)
    concept, structure, prop, column = v.get("concept"), v.get("structure"), None, None
    if head == "개념 › 속성":
        prop, structure = v["name"], None
    elif head == "매핑 › 속성":
        prop = v["name"]
    elif head == "정의 문서":
        el = idx.element_at(v["line"])
        if el is None or el.kind not in ("매핑", "매핑 속성"):
            return None
        block = el if el.kind == "매핑" else el.parent
        concept, structure = block.concept, block.structure
        if el.kind == "매핑 속성":
            prop, column = el.name or None, el.column or None
    elif head != "매핑":
        return None
    basis = rep.source_basis("4.2")          # {답 요소 이름: {(테이블, 컬럼)}}
    if structure:
        tables = {label(structure)}
    else:
        tables = {label(m.structure) for m in idx.mappings if m.concept == concept and m.structure}
        row = row_of(rep, "5.1", "개념", concept)
        tables |= source_tables(dri.pick(row, "원천")) if row else set()
    if prop:
        if any(not tables or t in tables for t, _ in basis.get(prop, ())):
            return FIX
        return FIX if joined_by(rep, concept, prop) else None
    if column:      # 속성 칸이 빈 매핑 행. 그 컬럼을 근거 위치로 가진 설계 속성이 있어야 함
        names = {p for c, p in rep.props() if c == concept}
        hit = any((t, label(column)) in pairs for n, pairs in basis.items() if n in names for t in tables)
        return FIX if hit else None
    return FIX if any(t in tables for pairs in basis.values() for t, _ in pairs) else None


def link_basis(rep, idx, f):
    """DOC-14: 6절 연결 근거(연결 키·MT)나 4.2절 요소 종류 '잇는 값' 행 근거 위치에 컬럼이 있으면 조인 속성 매핑을
    더하는 정비."""
    name, source, target = relation_of(idx, f)
    row = relation_row(rep, name, source, target)
    if row is not None:
        ground = dri.clean(dri.pick(row, "연결 근거"))
        if dri.TABLE_COLUMN.search(ground) or re.search(r"MT-?\d+", ground):
            return FIX
    for _, r in rep.rows("4.2"):
        if (dri.clean(dri.pick(r, "요소 종류")) == "잇는 값" and dri.element_name(dri.pick(r, "답 요소")) == name
                and dri.verdict(dri.pick(r, "판정")) in dri.BASIS_VERDICTS
                and dri.TABLE_COLUMN.search(dri.clean(dri.pick(r, "근거 위치")))):
            return FIX
    return None


def external_lines(rep):  # 설계 리포트 2절 '※ 외부 수정 n:' 줄
    return [ln for ln in rep.note_lines("※ 외부 수정") if EXTERNAL_LINE.match(ln)]


def map01_basis(rep, idx, f):
    """MAP-01: 4.2절 근거 위치대로 고치면 정비, 근거 위치가 다른 데이터 구조거나 2절 ※ 외부 수정 줄이 가리키는
    사람이 이은 매핑이면 결정 필요, 근거 위치가 없으면 설계 변경."""
    head, v = located(f)
    if head != "매핑 › 속성":
        return None
    mark = "매핑 '%s ← %s' › 속성 '%s'" % (v["concept"], v["structure"], v["name"])
    if any(mark in ln for ln in external_lines(rep)):
        return DECIDE
    pairs = rep.source_basis("4.2").get(v["name"])
    if not pairs:
        return None
    return FIX if any(t == label(v["structure"]) for t, _ in pairs) else DECIDE


def props_basis(rep, idx, f):
    """GOS61005·61010, 속성 표 없음: 그 개념(겹친 속성이면 그 속성)이 설계 속성 목록에 있으면 설계대로 적는 정비.
    5.1절 속성 수가 0이면 설계 변경."""
    head, v = located(f)
    design = rep.props()
    if head == "개념 › 속성":
        return FIX if (v["concept"], v["name"]) in design else None
    if head != "개념":
        return None
    row = row_of(rep, "5.1", "개념", v["name"])
    count = rep.int_cell(row, "속성 수") if row is not None else None
    return FIX if any(c == v["name"] for c, _ in design) and (count is None or count >= 1) else None


def blank_prop_basis(rep, idx, f):  # 속성 이름 빈칸: 정의 문서에 없는 그 개념의 설계 속성이 하나로 정해지면 정비
    v = element(f)
    el = idx.element_at(v["line"]) if v.get("line") else None
    block = el.parent if el is not None and el.kind == "속성" else el
    if block is None or block.kind != "개념":
        return None
    left = {p for c, p in rep.props() if c == block.name} - {p.name for p in block.children if p.name}
    return FIX if len(left) == 1 else None


def key_basis(rep, idx, f):  # GOS61008: 5.1절 식별 속성 칸이 속성 하나면 그것만 남기는 정비
    v = element(f)
    row = row_of(rep, "5.1", "개념", v.get("concept") or v.get("name"))
    keys = dri.split_items(dri.pick(row, "식별 속성")) if row else []
    return FIX if len(keys) == 1 and not dri.is_none(keys[0]) else None


def join_basis(rep, idx, f):  # GOS61108·61110·61109·61111: 6절 그 관계 행의 조인 속성 칸이 차 있으면 정비
    row = relation_row(rep, *relation_of(idx, f))
    return FIX if row is not None and not dri.is_none(dri.pick(row, "조인 속성")) else None


def link_key_basis(rep, idx, f):
    """C-15: 정의 문서 관계 행의 조인 속성이 6절 값과 다르면 6절 값으로 고치는 정비. 같은데 연결 키와 맞지 않으면
    조인 속성을 바꿔야 하므로 설계 변경."""
    name, source, target = relation_of(idx, f)
    row = relation_row(rep, name, source, target)
    joins = dri.split_join(dri.pick(row, "조인 속성")) if row is not None else set()
    have = next((r for r in idx.relations if (r.name, r.source, r.target) == (name, source, target)), None)
    if have is None or not joins or any(dri.is_none(j) for j in joins):
        return None
    return FIX if joins != {have.source_prop, have.target_prop} else None


def squash(name):  # 공백과 규격 이름에 허용되지 않는 글자를 뺀 꼴
    return re.sub(r"[^a-zA-Z0-9가-힣_]", "", name or "")


def concept_name_basis(rep, idx, f):
    """GOS61002·개념 이름 형식: 공백과 허용되지 않는 글자를 뺀 꼴로 5.1절 개념을 찾아 그 이름이 규격 형식을
    지키거나 공백만 어기면(등록할 때 공백을 붙여 씀) 정비."""
    head, v = located(f)
    if head != "개념":
        return None
    found = [n for n in rep.col("5.1", "개념") if squash(n) == squash(v["name"])]
    return FIX if len(found) == 1 and NAME_RE.match(found[0].replace(" ", "")) else None


def mapping_concept_basis(rep, idx, f):
    """GOS61021: 5.1절 원천 칸이 그 데이터 구조를 가리키는 개념이 하나로 정해지고 정의 문서에 있으면 매핑 제목만
    고치는 정비. 그런 개념이 5.1절에 없으면 설계 리포트가 가리키지 않는 매핑을 지우는 정비."""
    head, v = located(f)
    if head != "매핑":
        return None
    owners = [dri.clean(dri.pick(r, "개념")) for _, r in rep.rows("5.1")
              if label(v["structure"]) in source_tables(dri.pick(r, "원천"))]
    if not owners:
        return FIX
    return FIX if len(owners) == 1 and owners[0] in {c.name for c in idx.concepts} else None


def ends_basis(rep, idx, f):
    """GOS61107·C-14: 6절에서 관계 이름으로 찾은 행의 출발·도착이 5.1절과 정의 문서에 모두 있으면 관계 행 칸만
    고치는 정비."""
    row = relation_row(rep, *relation_of(idx, f))
    if row is None:
        return None
    design, have = set(rep.col("5.1", "개념")), {c.name for c in idx.concepts}
    ends = (dri.clean(row.get("출발", "")), dri.clean(row.get("도착", "")))
    return FIX if all(e and e in design and e in have for e in ends) else None


def relation_basis(rep, idx, f):  # GOS61102: 6절에 그 양끝의 관계 이름이 하나 있으면 정비
    _, source, target = relation_of(idx, f)
    names = {dri.clean(r.get("관계", "")) for _, r in rep.rows("6")
             if dri.clean(r.get("출발", "")) == source and dri.clean(r.get("도착", "")) == target} - {""}
    return FIX if len(names) == 1 else None


def relation_row_basis(rep, idx, f):
    """관계 행 빈 칸: 발생 경로의 '빈 칸 …' 으로 빈 칸을 가려 빈 칸마다 6절 값이 있으면 정비. 방향 칸은 6절에 칸이
    없어 정비."""
    m = re.search(r"빈 칸 ([^)]*)\)", f.get("발생 경로", ""))
    if not m:
        return None
    row = relation_row(rep, *relation_of(idx, f))
    for blank in (b.strip() for b in m.group(1).split(",")):
        if blank == "방향":
            continue
        col = BLANK_CELLS.get(blank)
        value = (row.get(col, "") if col in ("관계", "출발", "도착") else dri.pick(row, col)) if row and col else ""
        if dri.is_none(value):
            return None
    return FIX


def structure_basis(rep, idx, f):
    """코드 없는 데이터 구조 이름 오류: 5.1절 원천이나 7.1·7.2절 이름에 그 구조가 있으면 이름을 맞추거나 Meta Type
    블록을 적는 정비."""
    head, v = located(f)
    name = v.get("structure") if head == "매핑" else v.get("name") if head == "데이터 구조" else None
    if not name:
        return None
    known = {label(n) for n in rep.col("7.1", "이름") + rep.col("7.2", "이름")}
    for _, r in rep.rows("5.1"):
        known |= source_tables(dri.pick(r, "원천"))
    return FIX if label(name) in known else None


def guide_blocked(rep, f):
    """CQS-01~04 지적의 CQ가 설계 리포트 11절(입력 문서 간 불일치)에 스타일 가이드가 막은 것으로 적혔는가.
    11절 표에는 CQ 칸이 없어 행 글자에 그 CQ 번호와 '가이드' 가 함께 든 행을 찾는다."""
    try:
        head, v = located(f)
    except ValueError:
        return False
    if head != "CQ":
        return False
    return any(v["number"] in dri.CQ_ID.findall(dri.clean(" ".join(r.cells))) and "가이드" in " ".join(r.cells)
               for _, r in rep.rows("11"))


CASE_BY_CASE = {  # 건마다 가름: 열쇠 → (맞댈 설계 리포트 절·칸, 맞대는 함수). 함수가 None 을 내면 설계 변경
    "구조 이름": ("7.1절 이름·결정, 7.2절 이름, 5.1절 원천·4.2절 근거 위치", marked_structure),
    "구조 표지": ("7.1절 이름·결정, 7.2절 이름", marked_structure),
    "원천": ("5.1절 원천", concept_source),
    "근거 위치": ("4.2절 근거 위치(조인 속성이면 6절 연결 근거)", column_basis),
    "연결 근거": ("6절 연결 근거, 4.2절 근거 위치(요소 종류 '잇는 값')", link_basis),
    "매핑 근거": ("4.2절 근거 위치·처리, 2절 ※ 외부 수정 매핑 줄", map01_basis),
    "속성 수": ("5.1절 속성 수, 설계 속성 목록", props_basis),
    "빈 속성": ("설계 속성 목록", blank_prop_basis),
    "식별 속성": ("5.1절 식별 속성", key_basis),
    "조인 속성": ("6절 조인 속성", join_basis),
    "연결 키": ("6절 조인 속성·연결 근거", link_key_basis),
    "개념": ("5.1절 개념", concept_name_basis),
    "매핑 개념": ("5.1절 개념·원천", mapping_concept_basis),
    "끝 개념": ("6절 출발 → 도착, 5.1절 개념", ends_basis),
    "관계": ("6절 관계", relation_basis),
    "관계 행": ("6절 관계·출발 → 도착·조인 속성", relation_row_basis),
    "데이터 구조": ("5.1절 원천, 7.1·7.2절 이름", structure_basis),
}


def gde02_section(code):  # GDE-02 외부 코드(서식 가이드 절 번호)를 GDE02 열쇠로. 10장 아래 소절은 '10'
    m = re.match(r"(\d+)(?:\.(\d+))?", code)
    if not m:
        return None
    return "10" if m.group(1) == "10" else ("%s.%s" % m.groups() if m.group(2) else m.group(1))


def nature_of(rep, idx, f):
    rule = f["규칙"]
    codes = [c.strip() for c in re.split(r"[·,]", f.get("외부 코드") or "") if c.strip() and c.strip() != dri.NONE]
    key = next((BY_CODE[c] for c in codes if c in BY_CODE), None)
    if key is None and rule == "GDE-02" and codes:
        key = GDE02.get(gde02_section(codes[0]))
    if key is None and rule == "GDE-01" and codes and not any(re.fullmatch(r"C-\d{2}", c) for c in codes):
        return DESIGN, "다른 스타일 가이드 항목"  # --style 로 준 가이드는 건마다 가름이라 가르지 못하면 설계 변경
    if key is None and not codes:
        key = next((v for k, v in BY_PROBLEM.items() if f.get("문제 설명", "").startswith(k)), None)
    if key is None:
        key = BY_RULE.get(rule)
    if key is None and rule in ("CQS-01", "CQS-02", "CQS-03", "CQS-04") and guide_blocked(rep, f):
        return INPUT, "11절"
    if key is None and rule == "CQS-07":  # 미응답 사유가 원천 선택 미채택이면 채택 답에 따라 갈림
        return (DECIDE if "원천 선택 미채택" in js.unanswered(f) else INPUT), None
    if key is None:
        return FIXED.get(rule, DESIGN), None
    if key in (FIX, DESIGN, INPUT, DECIDE):
        return key, None
    where, judge = CASE_BY_CASE[key]
    try:
        return judge(rep, idx, f) or DESIGN, where
    except (KeyError, ValueError, IndexError, TypeError, AttributeError):  # 위치를 풀지 못하면 가르지 못한 것으로 봄
        return DESIGN, where


def classify_natures(rep, idx, findings_path):
    """구조 판정의 Error·Warning 지적마다 [{지적, 규칙, 성격, 맞댄 곳}]. 구조 판정을 읽지 못하면 입력 쪽 멈춤."""
    try:
        found = js.read_previous(findings_path)["지적"]
    except js.PreviousError as e:
        raise InputStop("구조 판정을 읽지 못함", detail="%s: %s" % (findings_path, e))
    out = []
    for f in found:
        if f.get("등급") in ("Error", "Warning"):
            nature, where = nature_of(rep, idx, f)
            out.append({"지적": f["번호"], "규칙": f["규칙"], "성격": nature, "맞댄 곳": where})
    return out


# ── 보조 출력 ────────────────────────────────────────────────────────────────

def diff_line(prev, rep):
    same_round(rep, prev.path)  # 앞 차수 사본과 맞대지 않음
    d = dri.report_diff(prev, rep)  # {concepts_added, concepts_removed, rels_added, rels_removed, q_changed}
    return "개념 +%d −%d, 관계 +%d −%d, 4.1 바뀐 행 %d" % (
        d["concepts_added"], d["concepts_removed"], d["rels_added"], d["rels_removed"], d["q_changed"])


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def clip(s, limit=120):
    while width(s) > limit:
        s = s[:-2] + "…"
    return s


def render_stage6(rep, stop_path):
    """모델을 부르지 않고 멈춤 질문 파일의 text_md 로 ⑥ 출력을 다시 그린다. 한 줄 120칸(한글 2칸), 30줄 안팎.
    넘치면 말없이 자르지 않고 확인할 항목 건수와 파일 이름 한 줄로 바꾼다."""
    if not stop_path:
        raise InputStop("⑥ 출력을 다시 그릴 멈춤 질문 파일이 없음", detail="--stop-file")
    stop = load_stop(stop_path)
    if not isinstance(stop.get("text_md"), str):
        raise InputStop("멈춤 질문 파일에 ⑥ 출력 글이 없음", detail="%s: text_md" % stop_path)
    upper = stop.get("upper") if isinstance(stop.get("upper"), list) else []
    head = [clip(rep.path), clip("설계안 확인: %s" % rep.summary_value("설계안 확인"))]
    body = [clip(ln) for ln in stop["text_md"].splitlines()]
    if len(upper) > 10 or len(head) + len(body) > 30:
        body = [clip("확인할 항목 %d건, 전체는 %s" % (len(upper), stop_path))]
    print("\n".join(head + body))


# ── 실행 ─────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(
        description="설계 리포트가 다음 단계로 가도 되는지 가리는 관문 검사. 규칙 번호를 내지 않는다.")
    ap.add_argument("report", help="설계 리포트")
    ap.add_argument("--stage", required=True, choices=STAGES,
                    help="설계: 관문 1(⑥ 출력 앞), 확인: 관문 2(⑦ 진입 앞), 검증뒤: 관문 4(판정 앞)")
    ap.add_argument("--definition", metavar="파일", help="정의 문서. --stage 검증뒤 에서 반드시 준다")
    ap.add_argument("--stop-file", metavar="파일",
                    help="멈춤 질문 파일(<이름>-멈춤-<stop>-<seq>.json). 설계 에서 칸과 설계 리포트 해시를 맞대고, "
                         "확인 에서 위층 항목이 있는지 본다")
    ap.add_argument("--last-confirmed", metavar="파일",
                    help="마지막 확인 회차 사본. 검증뒤 에서 확인 뒤 바뀐 이름이 2절에 적혔는지 맞댄다")
    ap.add_argument("--fix-request", nargs=2, metavar=("N차요청서", "N+1차요청서"),
                    help="N차·N+1차 수정 요청서. 단계와 상관없이 N차 요청서 「사람 요청과 CQ 변경」 절에서 옮겨야 할 행이 "
                         "N+1차 요청서에 모두 있는지 맞댄다")
    ap.add_argument("--findings", metavar="파일",
                    help="구조 판정. 검증뒤 끝에서 Error·Warning 지적마다 수정 성격을 갈라 nature 칸에 낸다")
    ap.add_argument("--external", action="store_true",
                    help="검증만 모드의 외부 수정 자리에서 부른다. 검증뒤 에서 설계 차이가 있으면 검사하지 않고 멈춘다")
    ap.add_argument("--diff", metavar="파일",
                    help="같은 차수의 앞 회차 사본이나 증분 앞 사본. 지금 판과의 차이를 한 줄로 낸다. 관문 판정에 영향 없음")
    ap.add_argument("--render-stage6", action="store_true",
                    help="검사하지 않고 멈춤 질문 파일로 ⑥ 출력을 다시 그린다. --stop-file 이 있어야 한다")
    ap.add_argument("--json", action="store_true", help="표준 출력에 JSON 하나를 낸다")
    return ap.parse_args()


def main(args):
    rep = read_report(args.report, "설계 리포트를")
    if args.render_stage6:
        render_stage6(rep, args.stop_file)
        return EXIT_PASS
    res = Result(args.stage)
    res.detail["설계 리포트"] = args.report
    if args.diff:
        res.detail["설계 차이"] = diff_line(read_report(args.diff, "앞 회차 사본을"), rep)
    if args.stage == "설계":
        check_round_copies(rep)
        check_design_stage(rep, res)
        check_pattern_basis(rep, res, args.stage)
        check_input_hashes(rep, res)
        check_cq_refs(rep, res)
        check_definition_absent(rep, res)
        check_personal_data(rep, res)
        filled = fill_cq_hashes(rep, args.report)
        if filled:
            rep = read_report(args.report, "설계 리포트를")
        check_cq_filled(rep, res, filled)
        if args.stop_file:
            check_stop_file(rep, res, args.stop_file)
    elif args.stage == "확인":
        check_confirm_stage(rep, res, args)
        check_personal_data(rep, res)
    else:
        if not args.definition:
            raise InputStop("검증 뒤 관문에 맞댈 정의 문서가 없음", detail="--definition")
        check_after_verify(rep, res, args)
        check_summary_vs_log(rep, res)
        check_pattern_basis(rep, res, args.stage)
        check_personal_data(rep, res)
    if args.fix_request:
        check_request_carryover(args.fix_request[0], args.fix_request[1], res)
    res.detail["설계 리포트 해시"] = sha12(args.report)  # 멈춤 질문 파일 design_report.sha12 에 옮겨 적는 값
    return emit(args, res)


def write_json(body, what):
    """표준 출력에 JSON 하나를 쓴다. 읽는 쪽이 먼저 닫힌 파이프 같은 쓰기 실패면 표준 오류 한 줄을 내고 False.
    표준 출력을 os.devnull 로 돌려 해석기가 끝날 때 버퍼를 다시 비우다 실패하지 않게 한다."""
    try:
        json.dump(body, sys.stdout, ensure_ascii=False)
        print()
        sys.stdout.flush()
    except OSError as err:  # 읽는 쪽이 먼저 닫힌 파이프 → 종료 코드 4
        print("%s를 내지 못함: %s" % (what, err.strerror or err), file=sys.stderr)
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return False
    return True


def fail_out(args, code, message, detail, hint=None):
    if getattr(args, "json", False):
        body = {"code": STOP_CODE[code], "stage": getattr(args, "stage", None), "passed": False,
                "message_ko": message, "model_hint": hint or HINT[code], "detail": {"종료 코드": code, "까닭": detail}}
        if not write_json(body, "관문 결과"):
            return EXIT_ENV
    else:
        print(message, file=sys.stderr)
    return code


def emit(args, res):
    code = res.exit_code()
    res.detail["종료 코드"] = code
    if args.json:
        body = {"code": res.code(), "stage": args.stage, "passed": not res.blocked(), "missing": res.missing,
                "mismatches": res.mismatches, "design_diff": res.design_diff, "cq_changes": res.cq_changes,
                "nature": res.nature, "message_ko": res.message_ko(), "model_hint": res.model_hint(),
                "detail": res.detail}
        if not write_json(body, "관문 결과"):
            return EXIT_ENV
    else:
        res.print_human()
    return code


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(main(args))
    except INPUT_ERRORS as e:  # 입력 쪽 멈춤. 해시·경로는 detail 에만
        if isinstance(e, InputStop):
            msg = e.message
        elif isinstance(e, di.ReadError):
            msg = "입력 파일을 읽지 못함(%s)" % e.problem
        else:
            msg = "입력 파일을 읽지 못함"
        sys.exit(fail_out(args, EXIT_INPUT, msg, getattr(e, "detail", "") or str(e), getattr(e, "hint", None)))
    except OutputFail as e:  # 출력 파일 쓰기 실패
        sys.exit(fail_out(args, EXIT_ENV, e.message, e.detail))
    except Exception as e:  # 처리하지 못한 예외
        sys.exit(fail_out(args, EXIT_SKILL, "관문 검사가 끝나지 못함", repr(e)))
