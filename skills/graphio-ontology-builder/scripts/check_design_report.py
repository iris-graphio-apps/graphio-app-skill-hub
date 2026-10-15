#!/usr/bin/env python3
"""설계 리포트가 다음 단계로 가도 되는지 가리는 관문 검사.
규칙 번호(DOC·CQS 등)를 내지 않는다. 산출물 품질 지적이 아니라 다음 단계로 가도 되는지 가리는 관문이기 때문이다.

    python3 check_design_report.py <설계 리포트> --stage 설계 [--stop-file <멈춤 질문 파일>] [--json]
    python3 check_design_report.py <설계 리포트> --stage 검증뒤 --definition <정의 문서> [--json]

정의 문서만 보는 검사는 check_design_doc.py 가 맡는다. 이 스크립트는 그 검사를 넓히지 않는다.
종료 코드: 0 통과, 1 빠짐·어긋남(다음 단계로 가지 않음), 2 입력 쪽 멈춤, 3 처리하지 못한 예외, 4 출력 파일 쓰기 실패.

관문은 --stage 로 고른다.

    설계     관문 1(⑥ 출력 앞). 문서 정보 표, 리포트 판 「설계 단계」, 2절 설계안 확인 「확인 대기」, 12절 정한 쪽,
             2절 건수와 뒤 절 줄 수, 입력 해시, CQ 번호 참조, 정의 문서가 아직 없음, 자료 등급과 개인정보 꼴.
             CQ 문서를 직접 읽어 4절 CQ 행 '해시/등급' 칸의 자리표시를 채워 쓴다. 설계 리포트에서 이 칸만 고쳐 쓰고
             그 밖의 결과는 표준 출력으로만 낸다
    확인     관문 2(⑦ 진입 앞). 설계안 확인 결과, 2절 사유와 12절 답이 온 길, 2절 회차·건수와 회차 사본·12절 행,
             입력 해시
    검증뒤   관문 4(판정 앞). 리포트 판 「검증 뒤」, 남은 「정의 문서 작성 뒤 기재」·「확인 대기」, 2절 건수와 정의 문서
             규모 표, 정의 문서와의 이름 맞대기(설계 리포트 먼저 차례), 입력 해시, CQ 문서에서 다시 셈한 '해시/등급'

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

EXIT_PASS, EXIT_BLOCKED, EXIT_INPUT, EXIT_SKILL, EXIT_ENV = 0, 1, 2, 3, 4  # 4는 출력 파일 쓰기 실패만, 10은 내지 않음
# 멈춤 JSON code. 멈춤 목록 1장 표의 코드 이름이다. 같은 종료 코드라도 어느 자리인지 이 이름으로 가른다
GATE_FAILED, GATE_CQ_HASH, DESIGN_FIRST_ORDER = "GATE_FAILED", "GATE_CQ_HASH", "DESIGN_FIRST_ORDER"
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
    """입력 쪽 멈춤(종료 코드 2). message 는 사람용 문장이고 해시·경로는 detail 에만 둔다."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message, self.detail = message, detail


class OutputFail(Exception):
    """출력 파일 쓰기 실패(종료 코드 4). 관문 1이 설계 리포트 4절 CQ 행 칸을 쓰다 실패할 때만 난다."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message, self.detail = message, detail


INPUT_ERRORS = (InputStop, di.ReadError, js.PreviousError, json.JSONDecodeError)


class Result:
    """관문 한 번의 결과. missing 은 빠진 칸, mismatches 는 어긋난 자리, blocks 는 차례 위반 같은 멈춤이다."""

    def __init__(self, stage):
        self.stage = stage
        self.missing, self.mismatches, self.design_diff, self.cq_changes, self.nature = [], [], [], [], []
        self.blocks, self.detail = [], {}

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
        if self.hash_changed():
            return GATE_CQ_HASH
        return DESIGN_FIRST_ORDER if self.blocks else GATE_FAILED

    def message_ko(self):
        gate = GATES[self.stage]
        code = self.code()
        if code is None:
            return "%s 통과" % gate
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
                print("- 어긋남: %s: %s" % (m.get("자리") or m.get("대상 키"), m["까닭"]))
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
    res.design_diff = dri.design_diff(rep, di.DefinitionIndex(lines))
    check_order(res, args)
    if args.last_confirmed:
        check_after_confirm(rep, read_report(args.last_confirmed, "마지막 확인 회차 사본을"), res)


def check_order(res, args):
    """1차 생성과 설계 수정 차수에서 설계 리포트와 정의 문서의 설계 차이가 한 건이라도 있으면 차례 위반으로 멈춘다.
    어긋남을 정의 문서 쪽으로 맞추라는 안내는 내지 않는다."""
    if not res.design_diff:
        return
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

def fill_cq_hashes(rep, path):  # 관문 1(--stage 설계, ⑥ 출력 앞)
    cq_paths = rep.input_paths("CQ 문서")
    if not cq_paths:
        return False
    now = dri.cq_hashes(cq_paths)  # {CQ 번호: "해시 앞 12자/등급"}
    text = rep.with_cells("4", CQ_COL, now, only=FILL, dups=dri.cq_duplicates(cq_paths))  # 자리표시 칸만 바꿈
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
    dups = dri.cq_duplicates(rep.input_paths("CQ 문서"))
    for no, value in sorted(rep.cells("4", CQ_COL, dups).items()):
        if value == FILL:
            res.missing.append("4절 CQ %s %s(CQ 문서에서 그 번호를 찾지 못함)" % (no, CQ_COL))


def check_cq_hashes(rep, res):  # 관문 4(--stage 검증뒤, 판정 앞)
    cq_paths = rep.input_paths("CQ 문서")
    if not cq_paths:
        res.detail["CQ 확인 값"] = "CQ 문서 파일이 없어 맞대지 않음"
        return
    dups = dri.cq_duplicates(cq_paths)
    now, kept = dri.cq_hashes(cq_paths), rep.cells("4", CQ_COL, dups)
    for no in sorted(set(now) | set(kept)):
        kind = dri.cq_change(kept.get(no), now.get(no))  # 더함·뺌·문장 바뀜·등급 바뀜, 자리표시 남음
        if kind:
            res.cq_changes.append({"cq": no, "갈래": kind})
            res.mismatch("4절 CQ %s 해시/등급" % (no,), kept.get(no), now.get(no))


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
    res.detail["설계 리포트 해시"] = sha12(args.report)  # 멈춤 질문 파일 design_report.sha12 에 옮겨 적는 값
    return emit(args, res)


def fail_out(args, code, message, detail):
    if getattr(args, "json", False):
        json.dump({"code": STOP_CODE[code], "stage": getattr(args, "stage", None), "passed": False,
                   "message_ko": message, "model_hint": HINT[code], "detail": {"종료 코드": code, "까닭": detail}},
                  sys.stdout, ensure_ascii=False)
        print()
    else:
        print(message, file=sys.stderr)
    return code


def emit(args, res):
    code = EXIT_BLOCKED if res.blocked() else EXIT_PASS
    res.detail["종료 코드"] = code
    if args.json:
        json.dump({"code": res.code(), "stage": args.stage, "passed": not res.blocked(), "missing": res.missing,
                   "mismatches": res.mismatches, "design_diff": res.design_diff, "cq_changes": res.cq_changes,
                   "nature": res.nature, "message_ko": res.message_ko(), "model_hint": res.model_hint(),
                   "detail": res.detail}, sys.stdout, ensure_ascii=False)
        print()
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
        sys.exit(fail_out(args, EXIT_INPUT, msg, getattr(e, "detail", "") or str(e)))
    except OutputFail as e:  # 출력 파일 쓰기 실패
        sys.exit(fail_out(args, EXIT_ENV, e.message, e.detail))
    except Exception as e:  # 처리하지 못한 예외
        sys.exit(fail_out(args, EXIT_SKILL, "관문 검사가 끝나지 못함", repr(e)))
