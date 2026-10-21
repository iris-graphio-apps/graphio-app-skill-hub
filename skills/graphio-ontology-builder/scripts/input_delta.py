#!/usr/bin/env python3
"""⑥ 답 나(입력 문서 수정)에서 CQ 문서만 바뀐 경우 부합 조건의 스크립트 몫 11건 가운데 조건 15를 뺀 10건을 센다.
조건 15(설계 리포트 전체 정합)는 check_design_report.py --stage 설계가 센다.
규칙 번호를 내지 않는다. 걸리면 결과 보고 첫 줄 꼴로 걸린 조건과 까닭을 낸다.

    python3 input_delta.py snapshot <설계 리포트>
    python3 input_delta.py compare <설계 리포트> --map <바꿀 입력 대응표>
    python3 input_delta.py labels <설계 리포트>
    python3 input_delta.py pair <설계 리포트>
    python3 input_delta.py check <설계 리포트> --before <설계-리포트-증분앞.md>

종료 코드: 0 통과, 1 조건에 걸림(①부터 다시), 2 입력 쪽 멈춤, 3 처리하지 못한 예외.
입력-사본/ 아래 출력 파일이나 표준 출력(--json)을 쓰지 못하면 4(멈춤 목록의 출력 쓰기 실패와 같은 뜻)다.

하위 명령과 부합 조건(조건 번호 뒤 괄호가 그 조건의 뜻이다)

    snapshot  ① 답 뒤 한 번. 설계 리포트 3절 입력마다 '(경로) (해시 앞 12자)' 줄을 낸다. 문서 정보 표 입력 행에
              옮겨 적는다. CQ 문서만 입력-사본/<해시>-<파일 이름> 으로 복사하고 필수 CQ 기준을
              입력-사본/필수-CQ-기준.json 에 남긴다. 증분 반영 때는 조건 1~14를 지난 뒤 관문 1 앞에 다시 돌린다
    compare   조건 1(바뀐 입력이 CQ 문서뿐)·2(CQ 문서 짝이 정해짐). 입력을 같음·내용 바뀜·새 파일·뺌·경로만 바뀜으로
              가른다. 지나면 CQ 사본과 새 CQ 문서의 차이를 덩어리마다 입력-사본/CQ-차이.md 에 쓰고, 번호꼴 낱말과
              질문 표 밖 줄을 [표시] 줄로 미리 표시한다
    labels    조건 3(꼬리표가 덩어리마다 하나). 입력-사본/CQ-차이-꼬리표.md 를 센다. 처음 걸리면 한 번 다시 붙이게 한다
    pair      조건 6(CQ 번호 안정). 옛 CQ 사본과 새 CQ 문서의 질문을 짝지어 입력-사본/CQ-짝.json 에 쓴다
    check     조건 5(필수 CQ 기준 그대로)·8(새 답 요소 0건)·9(새 구조 0건)·10(필수 CQ 경로 있음)·11(필수 아닌 CQ
              경로 없음 사유). 모두 지나면 조건 14(근거 CQ 다시 셈)로 근거 CQ를 잃은 요소를 lost_basis 로 낸다

바꿀 입력 대응표(--map)는 JSON 객체다. 열쇠는 설계 리포트 3절 입력 No. 이고, 적지 않은 입력은 그대로 둔다.

    {"2": "<새 경로>"}                             그 입력의 새 경로(내용 바뀜·경로만 바뀜·교체)
    {"5": {"경로": "<새 경로>", "역할": "CQ"}}     3절에 없는 새 파일. 역할을 CQ 로 지정해야 CQ 문서로 본다
    {"1": {"뺌": "<옛 경로>"}}                     입력을 뺌. 옛 경로를 밝힌다

꼬리표 파일에는 덩어리마다 「덩어리 n: 질문 행(CQ 번호)」 또는 「덩어리 n: 질문 밖(종류)」 한 줄을 적고,
CQ-차이.md 의 [표시] 줄을 그대로 옮겨 둔다. 표시 줄을 지우면 조건 3에 걸린다.

--json 이면 표준 출력에 JSON 하나를 낸다. 칸은 code·passed·message_ko·model_hint·detail 과 하위 명령마다
inputs(snapshot)·kinds(compare)·lost_basis(check) 이다. code 는 멈춤 목록 1장 표의 코드 이름이고 통과하면 null 이다.
"""
import argparse
import difflib
import json
import os
import re
import shutil
import sys

import definition_index as di
import design_report_index as dri
import judge_structure as js  # 미응답 사유 닫힌 값과 4.2절 판정·처리로 사유를 정하는 규칙은 판정 스크립트 한 곳

COPIES = "입력-사본"
DIFF_FILE, LABEL_FILE = "CQ-차이.md", "CQ-차이-꼬리표.md"
PAIR_FILE, BASIS_FILE = "CQ-짝.json", "필수-CQ-기준.json"
MATCH_FILE = "CQ-대응.json"       # compare 가 정한 CQ 문서 짝(옛 사본 → 새 경로). pair 가 읽는다
ATTEMPT_FILE = "꼬리표-시도.json"  # labels 시도 횟수. compare 가 새 차이를 쓸 때와 snapshot 때 지운다
CQ_ROLE = "CQ"
KINDS = ("같음", "내용 바뀜", "새 파일", "뺌", "경로만 바뀜")

EXIT_PASS, EXIT_BLOCKED, EXIT_INPUT, EXIT_SKILL, EXIT_ENV = 0, 1, 2, 3, 4
STOP_CODE = {EXIT_BLOCKED: "DELTA_CONDITION", EXIT_INPUT: "DELTA_INPUT", EXIT_SKILL: "SKILL_UNEXPECTED",
             EXIT_ENV: "OUTPUT_WRITE_FAILED"}
HINT = {EXIT_BLOCKED: "증분 반영을 하지 않음. 입력 목록을 고쳐 ①부터 다시 함",
        EXIT_INPUT: "증분 반영을 하지 않음. 입력 목록을 고쳐 ①부터 다시 함",
        EXIT_SKILL: "스크립트를 고치지 말고 사용자에게 알림",
        EXIT_ENV: "출력 폴더의 쓰기 권한과 남은 공간을 확인한 뒤 같은 하위 명령을 다시 수행함"}
NEXT = {"snapshot": "출력 줄을 설계 리포트 문서 정보 표 입력 행에 옮겨 적음",
        "compare": "CQ-차이.md 의 덩어리마다 꼬리표를 붙여 CQ-차이-꼬리표.md 에 쓰고 labels 를 수행함",
        "labels": "pair 를 수행함",
        "pair": "설계 리포트를 증분 앞 사본으로 복사하고 바뀐 CQ의 행을 다시 적은 뒤 check 를 수행함",
        "check": "lost_basis 요소를 ⑥ 위층에 한 건씩 올리고(기본값 「지움」) 설계 리포트를 고친 뒤 snapshot 을 다시 "
                 "돌리고 관문 1을 수행함"}

ARROW = re.compile(r"\s*(→|←)\(([^)]*)\)\s*")
NO_PATH = "경로 없음"
REASONS = tuple(r for r in js.CQ_REASONS if r != dri.NONE)   # 미응답 사유 닫힌 값('해당 없음' 뺌)


class InputStop(Exception):
    """입력 쪽 멈춤(종료 코드 2). message 는 사람용 문장이고 해시·경로는 detail 에만 둔다."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message, self.detail = message, detail


class OutputFail(Exception):
    """입력-사본/ 아래 출력 파일 쓰기 실패(종료 코드 4)."""

    def __init__(self, message, detail=""):
        super().__init__(message)
        self.message, self.detail = message, detail


INPUT_ERRORS = (InputStop, di.ReadError, json.JSONDecodeError)


class Blocked:
    """부합 조건에 걸림(종료 코드 1). 결과 보고 첫 줄 꼴로 걸린 조건과 까닭을 낸다."""

    def __init__(self, no, meaning, why, retry=False):
        self.no, self.meaning, self.why, self.retry = no, meaning, why, retry

    def line(self):
        tail = "꼬리표를 덩어리마다 한 번 다시 붙임" if self.retry else "①부터 다시 함"
        return "부합 조건 %d(%s)에 걸림: %s. %s" % (self.no, self.meaning, self.why, tail)


def fail(no, meaning, why, retry=False):
    return Blocked(no, meaning, why, retry)


class Outcome:
    """하위 명령 한 번의 결과. lines 는 표준 출력 줄이고 첫 줄이 결과 보고 첫 줄이다."""

    def __init__(self, code, lines, data=None, message=None, hint=None):
        self.code, self.lines, self.data = code, lines, data or {}
        self.message = message if message is not None else (lines[0] if lines else "")
        self.hint = hint


# ── 파일 ─────────────────────────────────────────────────────────────────────

def sha12(path):
    return dri.sha12_file(path)


def write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
    except OSError as e:
        raise OutputFail("입력 사본 폴더에 기록 파일을 쓰지 못함", detail="%s: %s" % (path, e))


def write_text(path, text):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError as e:
        raise OutputFail("입력 사본 폴더에 차이 파일을 쓰지 못함", detail="%s: %s" % (path, e))


def read_json(path, what):
    """입력-사본/ 의 기록 파일을 읽는다. 없거나 JSON 이 아니면 입력 쪽 멈춤. what 은 '…을/를' 까지 적은 이름이다."""
    try:
        return json.loads(di.read_text(path))
    except di.ReadError as e:  # 읽기 오류 문장에는 경로가 이미 있음(경로 한 번)
        raise InputStop("%s 읽지 못함" % what, detail=str(e))
    except ValueError as e:
        raise InputStop("%s 읽지 못함" % what, detail="%s: %s" % (path, e))


def copies_of(rep):
    return os.path.join(rep.folder, COPIES)


def copy_path(rep, entry):
    """① 의 CQ 사본 경로. entry 는 (경로, 해시)."""
    path, h = entry
    return os.path.join(copies_of(rep), "%s-%s" % (h, os.path.basename(path)))


def reset_attempts(copies):  # 꼬리표 시도 횟수 파일을 지움
    try:
        os.remove(os.path.join(copies, ATTEMPT_FILE))
    except FileNotFoundError:
        pass
    except OSError as e:
        raise OutputFail("꼬리표 시도 기록을 지우지 못함", detail=str(e))


def bump_attempt(rep):
    """꼬리표 시도 횟수를 하나 올려 돌려준다."""
    path = os.path.join(copies_of(rep), ATTEMPT_FILE)
    n = 0
    if os.path.exists(path):
        n = int(read_json(path, "꼬리표 시도 기록을").get("시도", 0))
    write_json(path, {"시도": n + 1})
    return n + 1


# ── 설계 리포트 읽기(증분 반영 몫) ────────────────────────────────────────────

class Item:
    """설계 리포트 3절 입력 하나. role 은 역할 칸(CQ 문서면 'CQ'), path 는 연 경로다."""

    def __init__(self, role, path):
        self.role, self.path = role, path


class Route:
    """4.1절 응답 경로. props 는 (개념, 속성), hops 는 (관계, 출발, 도착), concepts 는 거치는 개념이다."""

    def __init__(self):
        self.props, self.hops, self.concepts, self.hop_counts = set(), [], set(), []

    def elements(self):  # 개념 이름, (관계, 출발, 도착)
        return set(self.concepts) | set(self.hops)


def route(cell):
    """4.1절 응답 경로 칸을 읽는다. 경로가 여럿이면 백틱으로 가른 조각마다 읽어 합친다."""
    out = Route()
    text = cell or ""
    pieces = re.findall(r"`([^`]+)`", text) or [text]
    for piece in pieces:
        piece = dri.clean(piece)
        if not piece or piece.startswith(NO_PATH):
            continue
        parts = ARROW.split(piece)
        nodes, links = parts[0::3], list(zip(parts[1::3], parts[2::3]))
        names = []
        for node in nodes:
            concept, _, props = node.partition(" · ")
            concept = concept.strip()
            names.append(concept)
            out.concepts.add(concept)
            out.props |= {(concept, p) for p in dri.split_items(props) if not dri.is_none(p)}
        for k, (arrow, rel) in enumerate(links):
            a, b = names[k], names[k + 1]
            out.hops.append((rel.strip(), a, b) if arrow == "→" else (rel.strip(), b, a))
        out.hop_counts.append(len(links))
    return out


class DeltaReport(dri.Report):
    """증분 반영이 읽는 설계 리포트. 3절 입력, 4.1절 경로, 절별 열쇠 행을 더 읽는다."""
    rule, grades = None, {}

    def inputs(self):
        """3절 입력 [(입력 No., Item)]."""
        out = []
        for no, r in self.rows("3", "문서"):
            cell = dri.pick(r, "문서")
            quoted = re.findall(r"`([^`]+)`", cell)
            raw = quoted[0] if quoted else re.split(r",\s|\s\(", dri.clean(cell))[0]
            role = dri.clean(dri.pick(r, "역할"))
            if raw and not dri.is_none(raw):
                out.append((no, Item(CQ_ROLE if role.upper().startswith(CQ_ROLE) else role, self.resolve(raw))))
        return out

    def roles(self):
        return {no: item.role for no, item in self.inputs()}

    def required_cq_rule(self):
        """설계 리포트에 적힌 필수 CQ 기준의 등급 말. 적은 자리가 없으면 None."""
        for ln in self.lines:
            if "필수 CQ 기준" in ln or "필수 질문은" in ln:
                m = re.search(r"`([^`]+)`", ln)
                if m:
                    return m.group(1).strip()
        return None

    def cq_row(self, cq):
        return next((r for _, r in self.rows("4.1") if dri.cq_number(dri.pick(r, "CQ")) == cq), None)

    def paths(self, cqs):
        return [(c, route(dri.pick(self.cq_row(c), "응답 경로")) if self.cq_row(c) is not None else None)
                for c in cqs]

    def paths_all(self):
        return [(dri.cq_number(dri.pick(r, "CQ")), route(dri.pick(r, "응답 경로"))) for _, r in self.rows("4.1")
                if dri.cq_number(dri.pick(r, "CQ"))]

    def keyed_rows(self, sec):
        """절별 열쇠 행. 4.1 CQ 번호, 5.1 개념 이름, 6 (관계, 출발, 도착), 7.1·7.2 이름."""
        out = []
        for _, r in self.rows(sec):
            if sec == "4.1":
                key = dri.cq_number(dri.pick(r, "CQ"))
            elif sec == "5.1":
                key = dri.clean(dri.pick(r, "개념"))
            elif sec == "6":
                key = (dri.clean(r.get("관계", "")), dri.clean(r.get("출발", "")), dri.clean(r.get("도착", "")))
            else:
                key = dri.clean(dri.pick(r, "이름"))
            if key:
                out.append((key, r))
        return out

    def keyed_row(self, sec, key):
        return next((r for k, r in self.keyed_rows(sec) if k == key), None)

    def path_of(self, c):
        cell = dri.clean(dri.pick(self.cq_row(c) or {}, "응답 경로"))
        return NO_PATH if cell.startswith(NO_PATH) else cell

    def unanswered_reason(self, c):  # 4.1 행 '경로 없음(사유: …)' 의 사유
        cell = dri.clean(dri.pick(self.cq_row(c) or {}, "응답 경로"))
        return next((w for w in REASONS if w in cell), cell[len(NO_PATH):].strip("()（） :사유"))

    def reasons_from_42(self, c):
        return {js.expected_reason(dri.verdict(dri.pick(r, "판정")), dri.clean(dri.pick(r, "처리")))
                for _, r in self.rows("4.2") if c in dri.cq_set(dri.pick(r, "사용 CQ"))} - {None}

    def is_required(self, c):
        """필수 CQ인가. 기준 등급을 모르면 모든 CQ를 필수로 본다(걸리면 ①부터 다시 하는 쪽)."""
        return self.rule is None or self.grades.get(c) == self.rule


def read_report(path, what="설계 리포트를"):
    try:
        return dri.read_report(path, cls=DeltaReport)
    except dri.ReportError as e:
        raise InputStop("%s 읽지 못함(%s)" % (what, e.problem), detail=str(e))


def old_inputs(rep):
    """{입력 No.: (경로, 해시)}. 경로는 3절, 해시는 문서 정보 표 입력 행에서 같은 파일을 찾아 읽는다."""
    rows = ("CQ 문서", "참고 문서", "스타일 가이드", "서식 가이드")
    written = {os.path.realpath(rep.resolve(p)): h for _, p, h in rep.input_hashes(rows) if h}
    out = {}
    for no, item in rep.inputs():
        h = written.get(os.path.realpath(item.path))
        if h is None:
            raise InputStop("문서 정보 표에 입력 해시가 없음", detail="입력 No.%s %s" % (no, item.path))
        out[no] = (item.path, h)
    return out


# ── snapshot ─────────────────────────────────────────────────────────────────

def snapshot(rep):
    copies = os.path.join(rep.folder, COPIES)
    try:
        os.makedirs(copies, exist_ok=True)
    except OSError as e:
        raise OutputFail("입력 사본 폴더를 만들지 못함", detail=str(e))
    reset_attempts(copies)  # 꼬리표 시도 횟수 파일을 지움(재스냅숏)
    lines = []
    for no, item in rep.inputs():  # 3절: 입력 No.·역할·경로
        if not os.path.exists(item.path):
            raise InputStop("입력 파일 없음", detail="입력 No.%s %s" % (no, item.path))
        h = sha12(item.path)
        lines.append("%s (%s)" % (os.path.abspath(item.path), h))
        if item.role == CQ_ROLE:
            try:
                shutil.copyfile(item.path, os.path.join(copies, "%s-%s" % (h, os.path.basename(item.path))))
            except OSError as e:
                raise OutputFail("CQ 문서 사본을 쓰지 못함", detail=str(e))
    write_json(os.path.join(copies, BASIS_FILE), {"기준": rep.required_cq_rule()})
    return Outcome(EXIT_PASS, lines, {"inputs": lines}, message="입력 %d건을 기록함" % len(lines))


# ── compare: 조건 1·2 ────────────────────────────────────────────────────────

class Mapping:
    """바꿀 입력 대응표. 열쇠는 3절 입력 No.(정수로 맞춤)다."""

    def __init__(self, data, rep):
        self.data = {int(k) if str(k).isdigit() else k: v for k, v in data.items()}
        self.rep = rep

    @classmethod
    def load(cls, path, rep):
        data = read_json(path, "바꿀 입력 대응표를")
        if not isinstance(data, dict):
            raise InputStop("바꿀 입력 대응표를 읽지 못함", detail="%s: JSON 객체가 아님" % path)
        return cls(data, rep)

    def path_of(self, no):
        e = self.data.get(no)
        p = e if isinstance(e, str) else (e.get("경로") if isinstance(e, dict) else None)
        return self.rep.resolve(p) if p else None

    def removed(self, no):
        e = self.data.get(no, "")
        return e is None or (isinstance(e, dict) and "뺌" in e)

    def designated_cq(self, no):
        e = self.data.get(no)
        return isinstance(e, dict) and (dri.clean(str(e.get("역할", ""))).upper() == CQ_ROLE or e.get("CQ") is True)

    def names_old(self, no):
        e = self.data.get(no)
        return isinstance(e, dict) and isinstance(e.get("뺌"), str) and bool(e["뺌"].strip())

    def new_numbers(self, old=()):
        return [no for no in self.data if no not in old and self.path_of(no)]

    def apply(self, old):
        """대응표를 적용한 {입력 No.: 경로}. 뺀 입력은 넣지 않는다."""
        new = {}
        for no, (path, _) in old.items():
            if self.removed(no):
                continue
            new[no] = self.path_of(no) or path
        new.update({no: self.path_of(no) for no in self.new_numbers(old)})
        return new


def classify(old, new):  # old: {입력 No.: (경로, 해시)}, new: 대응표를 적용한 {입력 No.: 경로}
    out = {}
    for no, (path, h) in old.items():
        if no not in new:
            out[no] = "뺌"
            continue
        if not os.path.exists(new[no]):
            raise InputStop("바꾼 입력 파일이 없음", detail="입력 No.%s %s" % (no, new[no]))
        h2 = sha12(new[no])
        same_path = os.path.realpath(new[no]) == os.path.realpath(path)
        out[no] = "같음" if (h2 == h and same_path) else ("경로만 바뀜" if h2 == h else "내용 바뀜")
    for no in new:
        if no not in old:
            if not os.path.exists(new[no]):
                raise InputStop("새 입력 파일이 없음", detail="입력 No.%s %s" % (no, new[no]))
            out[no] = "새 파일"
    return out


def merged_roles(rep, mapping):  # compare 안, cond1 앞
    roles = dict(rep.roles())  # 3절 입력 No. → 역할
    roles.update({no: CQ_ROLE for no in mapping.new_numbers(roles) if mapping.designated_cq(no)})
    return roles


def cond1(kinds, roles):
    bad = [no for no, k in sorted(kinds.items(), key=lambda x: str(x[0]))
           if k not in ("같음", "경로만 바뀜") and roles.get(no) != CQ_ROLE]
    if bad:
        return fail(1, "바뀐 입력이 CQ 문서뿐", "CQ 문서가 아닌 입력이 바뀜: 입력 No. %s" % ", ".join(map(str, bad)))
    return None


def cond2(kinds, roles, old, mapping, rep):
    for no, k in sorted(kinds.items(), key=lambda x: str(x[0])):
        if roles.get(no) != CQ_ROLE or k == "같음":
            continue
        if k == "새 파일" and not mapping.designated_cq(no):
            return fail(2, "CQ 문서 짝이 정해짐", "새 파일 입력 No.%s를 CQ 문서로 지정하지 않음" % no)
        if k == "뺌" and not mapping.names_old(no):
            return fail(2, "CQ 문서 짝이 정해짐", "뺀 CQ 문서의 옛 경로를 밝히지 않음: 입력 No.%s" % no)
        if k == "내용 바뀜":
            copy = copy_path(rep, old[no])
            if not os.path.exists(copy):
                raise InputStop("①의 CQ 사본이 없음", detail=copy)  # 종료 코드 2
            di.read_text(copy)  # UTF-8 이 아니면 ReadError, 종료 코드 2
    return None


def read_lines(path):
    return di.read_text(path).splitlines() if path else []


def cq_lines(path):
    """질문 표 행의 {줄 번호(1부터): 문서가 적은 CQ 번호}. 번호를 스킬이 매긴 행은 번호 자리가 None 이다."""
    return {r.line: (None if r.by_skill else r.no) for r in dri.read_cq_rows(path)} if path else {}


def number_words(body, own=None):
    """차이 줄의 번호꼴 낱말(Q3·CQ-01 꼴). 표 행·글머리 줄 어디에 있든 줄 전체에서 찾는다.
    질문 행이면 문서가 그 행에 적은 CQ 번호(own)를 앞에 둔다. 숫자만 적은 번호는 own 으로만 표시된다."""
    return ([own] if own else []) + dri.CQ_ID.findall(dri.clean(body))


def diff_hunks(no, old_path, new_path, start):
    """옛 사본과 새 CQ 문서의 차이 덩어리. [(덩어리 번호, 머리, 차이 줄, [표시])]."""
    a, b = read_lines(old_path), read_lines(new_path)
    inside_a, inside_b = cq_lines(old_path), cq_lines(new_path)
    out, n, cur = [], start, None
    la = lb = 0
    for ln in difflib.unified_diff(a, b, lineterm="", n=1):
        if ln.startswith(("---", "+++")):
            continue
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
        if m:
            n += 1
            la, lb = int(m.group(1)), int(m.group(2))
            cur = (n, "입력 No.%s 옛 %d줄 · 새 %d줄부터" % (no, la, lb), [], [])
            out.append(cur)
            continue
        cur[2].append(ln)
        sign, body = ln[:1], ln[1:]
        if sign == " ":
            la, lb = la + 1, lb + 1
            continue
        side, at, inside = ("옛", la, inside_a) if sign == "-" else ("새", lb, inside_b)
        cur[3].extend("[표시] 덩어리 %d 번호꼴 낱말 %s" % (n, w) for w in number_words(body, inside.get(at)))
        if at not in inside and body.strip():
            cur[3].append("[표시] 덩어리 %d 질문 표 밖 줄 %s %d줄" % (n, side, at))
        if sign == "-":
            la += 1
        else:
            lb += 1
    return [(k, head, lines, list(dict.fromkeys(marks))) for k, head, lines, marks in out]


def write_diff(rep, kinds, roles, old, new):
    """CQ 문서 차이를 덩어리마다 CQ-차이.md 에 쓰고, CQ 문서 짝을 CQ-대응.json 에 남긴다. 덩어리 수를 돌려준다."""
    copies = copies_of(rep)
    pairs, hunks = [], []
    for no in sorted(kinds, key=str):
        if roles.get(no) != CQ_ROLE:
            continue
        k = kinds[no]
        old_copy = copy_path(rep, old[no]) if no in old else None
        new_path = new.get(no)
        pairs.append({"입력 No.": no, "옛 사본": old_copy, "새 경로": new_path, "갈래": k})
        if k in ("내용 바뀜", "새 파일", "뺌"):
            hunks += diff_hunks(no, old_copy if k != "새 파일" else None, new_path if k != "뺌" else None,
                                len(hunks))
    text = ["# CQ 차이", "",
            "- 덩어리마다 꼬리표 한 줄을 %s 에 적는다. 「덩어리 n: 질문 행(CQ 번호)」 또는 「덩어리 n: 질문 밖(종류)」"
            % LABEL_FILE,
            "- [표시] 줄은 스크립트가 미리 표시한 번호꼴 낱말과 질문 표 밖 줄이다. 꼬리표 파일에 그대로 옮기고 지우지 않는다", ""]
    for n, head, lines, marks in hunks:
        text += ["## 덩어리 %d" % n, "", "- %s" % head, ""] + marks + ([""] if marks else []) + \
                ["```diff"] + lines + ["```", ""]
    try:
        os.makedirs(copies, exist_ok=True)
    except OSError as e:
        raise OutputFail("입력 사본 폴더를 만들지 못함", detail=str(e))
    write_text(os.path.join(copies, DIFF_FILE), "\n".join(text))
    write_json(os.path.join(copies, MATCH_FILE), {"짝": pairs})
    reset_attempts(copies)
    return len(hunks)


def compare(rep, args):
    mapping = Mapping.load(args.map, rep)
    old = old_inputs(rep)
    kinds = classify(old, mapping.apply(old))
    if all(k == "같음" for k in kinds.values()):
        return Outcome(EXIT_PASS, ["바뀐 입력 없음"], {"kinds": {}}, hint="⑥ 답을 다시 받음")
    roles = merged_roles(rep, mapping)
    blocked = cond1(kinds, roles) or cond2(kinds, roles, old, mapping, rep)
    if blocked:
        return blocked
    new = mapping.apply(old)
    n = write_diff(rep, kinds, roles, old, new)
    changed = ["입력 No.%s(%s)" % (no, k) for no, k in sorted(kinds.items(), key=lambda x: str(x[0])) if k != "같음"]
    moved = ["%s (%s)" % (os.path.abspath(new[no]), sha12(new[no]))
             for no, k in sorted(kinds.items(), key=lambda x: str(x[0])) if k == "경로만 바뀜"]
    first = "부합 조건 1·2를 지남: %s. 차이 덩어리 %d건" % (", ".join(changed), n)
    return Outcome(EXIT_PASS, [first] + moved, {"kinds": {str(k): v for k, v in kinds.items()}, "paths": moved})


# ── labels: 조건 3 ───────────────────────────────────────────────────────────

LABEL = re.compile(r"^덩어리 (\d+): (질문 [행밖]\(.+\))\s*$")  # 질문 행(CQ 번호)·질문 밖(종류)


class Hunks:
    def __init__(self, numbers, marks):
        self.numbers, self.marks = numbers, marks


def read_hunks(rep):  # CQ-차이.md 의 덩어리 번호와 미리 표시
    text = di.read_text(os.path.join(copies_of(rep), DIFF_FILE))  # 없으면 ReadError, 종료 코드 2
    lines = text.splitlines()
    numbers = [int(m.group(1)) for ln in lines if (m := re.match(r"^## 덩어리 (\d+)\s*$", ln))]
    marks = [ln.strip() for ln in lines if ln.strip().startswith("[표시] ")]
    return Hunks(numbers, marks)


def label_path(rep):
    return os.path.join(copies_of(rep), LABEL_FILE)


def detail(missing, dup, lost):
    parts = []
    if missing:
        parts.append("꼬리표 없는 덩어리 %s" % ", ".join(map(str, missing)))
    if dup:
        parts.append("꼬리표가 둘 이상인 덩어리 %s" % ", ".join(map(str, sorted(dup))))
    if lost:
        parts.append("지운 [표시] 줄 %d건" % len(lost))
    return " · ".join(parts)


def labels(rep):
    hunks = read_hunks(rep)                      # CQ-차이.md 의 덩어리 번호와 미리 표시
    text = di.read_text(label_path(rep))         # 꼬리표 파일이 없거나 UTF-8 이 아니면 ReadError, 종료 코드 2
    seen = {}
    for m in filter(None, (LABEL.match(ln.strip()) for ln in text.splitlines())):
        seen.setdefault(int(m.group(1)), []).append(m.group(2))
    missing = [n for n in hunks.numbers if n not in seen]
    dup = [n for n, v in seen.items() if len(v) > 1]
    lost = [mark for mark in hunks.marks if mark not in text]
    if missing or dup or lost:
        return fail(3, "꼬리표가 덩어리마다 하나", detail(missing, dup, lost), retry=bump_attempt(rep) == 1)
    return Outcome(EXIT_PASS, ["부합 조건 3을 지남: 덩어리 %d건에 꼬리표가 하나씩 있음" % len(hunks.numbers)])


# ── pair: 조건 6 ─────────────────────────────────────────────────────────────

class CQ:
    """짝지을 CQ 행: (출처, 번호, 질문 글자, 등급, 스킬이 매김). 출처는 그 CQ 문서의 3절 입력 No. 다."""

    def __init__(self, src, row):
        self.src, self.no, self.text, self.grade, self.by_skill = src, row.no, row.text, row.grade, row.by_skill

    def key(self):
        return self.no

    def as_dict(self):
        return {"출처": self.src, "번호": self.no, "질문": self.text, "등급": self.grade, "스킬이 매김": self.by_skill}


def pair_cqs(old_rows, new_rows, rep_folder):  # 행: (출처, 번호, 질문 글자, 등급, 스킬이 매김)
    by_key = {(r.src, r.no): r for r in old_rows if not r.by_skill}
    by_text = {r.text: r for r in old_rows if r.by_skill}
    pairs, added = [], []
    for r in new_rows:
        hit = by_text.get(r.text) if r.by_skill else by_key.get((r.src, r.no))
        (pairs.append((hit, r)) if hit else added.append(r))
    used = {id(p[0]) for p in pairs}
    removed = [r for r in old_rows if id(r) not in used]
    clash = {(r.src, r.no) for r in added} & {(r.src, r.no) for r in old_rows}
    if clash:
        return fail(6, "CQ 번호 안정", "더한 번호가 기존 번호와 겹침: %s" % ", ".join("%s" % no for _, no in sorted(clash, key=str)))
    changed = [{"cq": n.key(), "갈래": "문장 바뀜" if o.text != n.text else "등급 바뀜"}
               for o, n in pairs if o.text != n.text or o.grade != n.grade]
    write_json(os.path.join(rep_folder, COPIES, PAIR_FILE),  # check 가 읽음
               {"pairs": [[o.as_dict(), n.as_dict()] for o, n in pairs], "added": [r.as_dict() for r in added],
                "removed": [r.as_dict() for r in removed], "changed": changed})
    return pairs, added, removed


def pair(rep):
    match = read_json(os.path.join(copies_of(rep), MATCH_FILE), "CQ 문서 짝 기록을")
    old_rows, new_rows = [], []
    for e in match.get("짝", []):
        if e.get("옛 사본"):
            old_rows += [CQ(e["입력 No."], r) for r in dri.read_cq_rows(e["옛 사본"])]
        if e.get("새 경로"):
            new_rows += [CQ(e["입력 No."], r) for r in dri.read_cq_rows(e["새 경로"])]
    result = pair_cqs(old_rows, new_rows, rep.folder)
    if isinstance(result, Blocked):
        return result
    pairs, added, removed = result
    changed = sum(1 for o, n in pairs if o.text != n.text or o.grade != n.grade)
    return Outcome(EXIT_PASS, ["부합 조건 6을 지남: 짝 %d건(바뀜 %d건), 더함 %d건, 뺌 %d건"
                               % (len(pairs), changed, len(added), len(removed))])


# ── check: 조건 5·8·9·10·11, 그리고 14 ───────────────────────────────────────

class CQs:
    """pair 가 쓴 CQ-짝.json."""

    def __init__(self, data):
        self.data = data

    def new_rows(self):
        return [p[1] for p in self.data.get("pairs", [])] + self.data.get("added", [])

    def changed(self):  # 더함·문장 바뀜·등급 바뀜 CQ
        return list(dict.fromkeys([r["번호"] for r in self.data.get("added", [])] +
                                  [c["cq"] for c in self.data.get("changed", [])]))

    def grades(self):
        return {r["번호"]: r["등급"] for r in self.new_rows()}

    def grade_words(self):  # 새 CQ 문서가 매긴 등급 말
        return sorted({r["등급"] for r in self.new_rows() if r["등급"] != "-"})


def grade_name(rule):  # '상 n건' 에서 등급 이름만
    return re.sub(r"\s*\d+\s*건.*$", "", (rule or "").strip().strip("`")) or None


def cond5(rep, before, cqs):
    """필수 CQ 기준이 그대로인가. snapshot 이 남긴 기준 등급 이름 하나(문서가 가장 높게 매긴 등급)가 새 CQ 문서가
    매긴 등급 말에 그대로 있으면 지난다. 건수는 맞대지 않는다(CQ를 더하면 건수는 바뀜). 옛 CQ 사본과 새 CQ 문서의
    등급 말 묶음도 맞대지 않는다(낮은 등급 CQ를 더하거나 다른 CQ의 등급만 바뀌어도 기준 등급이 그대로면 지남).
    더 높은 등급 말이 새로 생긴 경우는 조건 4(질문 밖 변경)에 먼저 걸려 ①부터 다시 한다.
    기준이 기록되지 않았으면 맞대지 않는다."""
    rule = grade_name(read_json(os.path.join(rep.folder, COPIES, BASIS_FILE), "필수 CQ 기준 기록을").get("기준"))  # '상 n건' 에서 등급 이름만
    if rule and rule not in cqs.grade_words():  # 새 CQ 문서가 매긴 등급 말
        return "새 CQ 문서에 기준 등급(%s) 없음" % rule
    return None


def cond8(rep, before, cqs):
    now, old = {n for n, _ in rep.rows("4.2")}, {n for n, _ in before.rows("4.2")}
    if now != old:
        return "4.2절 행이 늘거나 줄어듦(No. %s)" % ", ".join(map(str, sorted(now.symmetric_difference(old), key=str)))
    for cq in cqs.changed():
        if not [n for n, r in rep.rows("4.2") if cq in dri.cq_set(dri.pick(r, "사용 CQ"))]:
            return "%s에 짝지은 4.2절 행이 없음" % cq
    return None


def cond9(rep, before, cqs):
    props = before.names("4.1", "사용 속성").union(before.names("5.3", "속성"))
    rels = set(before.rel_keys("6"))  # (관계, 출발, 도착)
    for cq, path in rep.paths(cqs.changed()):  # 4.1 경로: 사용 속성과 홉 (관계, 출발, 도착)
        if path is None:
            return "%s의 4.1절 행이 없음" % cq
        if [p for p in path.props if p not in props]:
            return "%s 경로에 기존에 없는 속성" % cq
        if [h for h in path.hops if h not in rels]:
            return "%s 경로의 홉이 6절 관계와 다름" % cq
        written = dri.first_int(dri.pick(rep.cq_row(cq), "홉 수"))
        if written is not None and path.hop_counts and written != max(path.hop_counts):
            return "%s 홉 수 칸이 응답 경로의 홉 수와 다름" % cq
    for sec in ("5.1", "5.3", "6", "7.1", "9.1", "9.2"):
        if rep.section_text(sec) != before.section_text(sec):
            return "%s절이 증분 앞 사본과 다름" % sec
    if [k for k, r in rep.keyed_rows("4.1") if k not in cqs.changed() and r != before.keyed_row("4.1", k)]:
        return "바뀌지 않은 CQ의 4.1 행이 바뀜"
    return None


def cond10(rep, before, cqs):
    bad = [c for c in cqs.changed() if rep.is_required(c) and rep.path_of(c) == NO_PATH]
    return ("필수 CQ %s가 경로 없음" % ", ".join(bad)) if bad else None


def cond11(rep, before, cqs):
    for c in cqs.changed():
        if rep.is_required(c) or rep.path_of(c) != NO_PATH:
            continue
        reason = rep.unanswered_reason(c)  # 4.1 행 사유
        if reason == "설계 누락" or reason not in rep.reasons_from_42(c):
            return "%s 경로 없음 사유(%s)가 4.2절 판정과 다름" % (c, reason)
    return None


def mt_basis(row, basis):
    """7.1·7.2절 행의 근거 CQ 다시 셈. 쓰는 요소 칸에 적힌 개념·관계의 근거 CQ를 합친다. 칸이 없으면 None."""
    used = dri.pick(row, "쓰는 요소")
    if not used:
        return None
    names = set(dri.split_items(re.sub(r"\s*[·]\s*", ", ", used)))
    out = set()
    for key, cqs in basis.items():
        if (key if isinstance(key, str) else key[0]) in names:
            out |= cqs
    return out


def cond14(rep):
    basis = {}
    for cq, path in rep.paths_all():
        for key in path.elements():  # 개념 이름, (관계, 출발, 도착)
            basis.setdefault(key, set()).add(cq)
    lost = []
    for sec in ("5.1", "6", "7.1", "7.2"):
        for key, row in rep.keyed_rows(sec):
            again = mt_basis(row, basis) if sec in ("7.1", "7.2") else basis.get(key, set())
            if again is None:
                continue
            written = dri.cq_set(dri.pick(row, "근거 CQ"))
            if written != again:
                lost.append({"절": sec, "대상 키": dri.key_text(("관계",) + key) if sec == "6" else key,
                             "적힌 값": sorted(written), "다시 셈": sorted(again)})
    return lost


CONDITIONS = ((5, "필수 CQ 기준 그대로", cond5), (8, "새 답 요소 0건", cond8), (9, "새 구조 0건", cond9),
              (10, "필수 CQ 경로 있음", cond10), (11, "필수 아닌 CQ 경로 없음 사유", cond11))


def check(rep, before, cqs):
    rep.grades = cqs.grades()
    rep.rule = grade_name(read_json(os.path.join(rep.folder, COPIES, BASIS_FILE), "필수 CQ 기준 기록을").get("기준"))
    for no, meaning, fn in CONDITIONS:
        why = fn(rep, before, cqs)
        if why:
            return fail(no, meaning, why)
    lost = cond14(rep)
    return Outcome(EXIT_PASS, [json.dumps({"passed": True, "lost_basis": lost}, ensure_ascii=False)],
                   {"lost_basis": lost}, message="부합 조건 5·8·9·10·11을 지남. 근거 CQ를 잃은 요소 %d건" % len(lost))


# ── 실행 ─────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(
        description="⑥ 에서 CQ 문서만 바뀐 경우 증분 반영 부합 조건의 스크립트 몫을 센다. 규칙 번호를 내지 않는다.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    helps = {"snapshot": "① 답 뒤 입력 해시와 CQ 문서 사본을 남김",
             "compare": "부합 조건 1·2: 바뀐 입력 가르기와 CQ 문서 짝",
             "labels": "부합 조건 3: 차이 덩어리마다 꼬리표 하나",
             "pair": "부합 조건 6: CQ 짝짓기와 번호 안정",
             "check": "부합 조건 5·8·9·10·11과 14"}
    for name in ("snapshot", "compare", "labels", "pair", "check"):
        sp = sub.add_parser(name, help=helps[name]); sp.add_argument("report", help="설계 리포트")
        sp.add_argument("--json", action="store_true", help="표준 출력에 JSON 하나를 낸다")
        if name == "compare":
            sp.add_argument("--map", required=True, metavar="파일", help="바꿀 입력 대응표(JSON). 3절 입력 No. → 새 경로")
        if name == "check":
            sp.add_argument("--before", required=True, metavar="파일", help="증분 앞 사본(설계-리포트-증분앞.md)")
    return ap.parse_args()


def main(args):
    rep = read_report(args.report)
    if args.cmd == "snapshot":
        return snapshot(rep)
    if args.cmd == "compare":
        return compare(rep, args)
    if args.cmd == "labels":
        return labels(rep)
    if args.cmd == "pair":
        return pair(rep)
    before = read_report(args.before, "증분 앞 사본을")
    cqs = CQs(read_json(os.path.join(copies_of(rep), PAIR_FILE), "CQ 짝 기록을"))  # 없으면 종료 코드 2
    return check(rep, before, cqs)


def emit(args, out):
    if isinstance(out, Blocked):
        code, lines, data = EXIT_BLOCKED, [out.line()], {}
        message, hint = lines[0], ("꼬리표를 덩어리마다 하나씩 다시 붙이고 labels 를 한 번 더 수행함" if out.retry
                                   else HINT[EXIT_BLOCKED])
    else:
        code, lines, data, message = out.code, out.lines, out.data, out.message
        hint = out.hint or NEXT[args.cmd]
    if args.json:
        body = {"code": STOP_CODE.get(code), "passed": code == EXIT_PASS, "message_ko": message, "model_hint": hint,
                "detail": {"종료 코드": code, "하위 명령": args.cmd}}
        body.update(data)
        if not write_stdout_json(body):
            return EXIT_ENV
    else:
        print("\n".join(lines))
    return code


def write_stdout_json(body):
    """표준 출력에 JSON 하나를 쓴다. 읽는 쪽이 먼저 닫힌 파이프 같은 쓰기 실패면 표준 오류 한 줄을 내고 False.
    표준 출력을 os.devnull 로 돌려 해석기가 끝날 때 버퍼를 다시 비우다 실패하지 않게 한다."""
    try:
        json.dump(body, sys.stdout, ensure_ascii=False)
        print()
        sys.stdout.flush()
    except OSError as err:  # 읽는 쪽이 먼저 닫힌 파이프 → 종료 코드 4
        print("증분 반영 결과를 내지 못함: %s" % (err.strerror or err), file=sys.stderr)
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return False
    return True


def fail_out(args, code, message, detail):
    if getattr(args, "json", False):
        body = {"code": STOP_CODE[code], "passed": False, "message_ko": message, "model_hint": HINT[code],
                "detail": {"종료 코드": code, "하위 명령": getattr(args, "cmd", None), "까닭": detail}}
        if not write_stdout_json(body):
            return EXIT_ENV
    else:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    args = parse_args()
    try:
        sys.exit(emit(args, main(args)))
    except INPUT_ERRORS as e:  # 입력 쪽 멈춤. 해시·경로는 detail 에만
        if isinstance(e, InputStop):
            msg = e.message
        elif isinstance(e, di.ReadError):
            msg = "입력 사본이나 기록 파일을 읽지 못함(%s)" % e.problem
        else:
            msg = "입력 사본이나 기록 파일을 읽지 못함"
        sys.exit(fail_out(args, EXIT_INPUT, msg, getattr(e, "detail", "") or str(e)))
    except OutputFail as e:  # 출력 파일 쓰기 실패
        sys.exit(fail_out(args, EXIT_ENV, e.message, e.detail))
    except Exception as e:  # 처리하지 못한 예외
        sys.exit(fail_out(args, EXIT_SKILL, "증분 반영 셈이 끝나지 못함", repr(e)))
