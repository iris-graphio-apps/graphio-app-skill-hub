#!/usr/bin/env python3
"""설계 리포트 읽기·비교·맞대기 공용 모듈. 도구가 아니다.
check_design_report.py, judge_structure.py --design-report, source_match.py, input_delta.py 가 불러 쓴다.

정의 문서 읽기 공용 모듈 definition_index.py 처럼 설계 리포트를 읽는 코드를 한 곳에 둔다. 표준 출력·출력 파일·
종료 코드가 없다. 읽지 못하거나 부르는 절·칸이 없으면 ReportError 를 올리고, 종료 코드는 부르는 쪽이 정한다.

    import design_report_index as dri          # 스크립트 폴더가 sys.path[0] 이라 그대로 읽힌다
    rep = dri.read_report("설계-리포트.md")      # 읽지 못하면 dri.ReportError
    rep.info["리포트 판"]                         # 문서 정보 표 {항목: 내용}
    dri.section_span(rep, "4.3")                 # 절 범위 (시작 자리, 끝 자리). 없으면 None
    rep.rows("12")                               # 절 첫 표의 [(No., 행)]
    dri.table_4_2(rep), dri.table_4_3(rep)       # {No.(정수): 행}
    dri.verdict("있음(판정 정정: 확인 필요 → 있음)")   # '있음'
    dri.cq_hashes(["CQ.md"])                     # {CQ 번호: '해시 앞 12자/등급'}
    dri.report_diff(prev, rep)                   # 두 리포트의 더함·뺌·바뀐 행 수
    dri.design_diff(rep, di.load("정의.md"))     # 설계 리포트와 정의 문서의 이름 차이

표 행은 칸 이름을 열쇠로 한 사전이다. 열쇠는 칸 이름의 norm 꼴(judge_structure.norm: 공백·백틱을 지우고
소문자)이다. 예: '사용cq'·'판정'·'처리'·'cq'·'뺀꼴요소'·'정한쪽'·'고른값'·'근거cq'.
judge_structure.py 가 이 모듈을 부르고 이 모듈도 judge_structure.py 의 읽기 함수를 쓰므로, 두 파일 모두
상대 모듈의 함수를 모듈을 읽어 들이는 때가 아니라 부를 때만 쓴다.
"""
import hashlib
import os
import re
import unicodedata

import definition_index as di
import judge_structure as js

TABLE_SECTIONS = ("4.1", "4.2", "4.3", "5.1", "6", "7", "12")

NONE = "해당 없음"
PENDING = "정의 문서 작성 뒤 기재"      # 설계 단계 판에서만 쓰는 닫힌 값
FILL = "(관문이 채움)"                  # 4절 CQ 행 '해시/등급' 칸의 자리표시. 관문이 채운다
CQ_COL = "해시/등급"
BASIS_VERDICTS = ("있음", "형태 다름", "경유")     # 근거 위치가 원천 위치를 가리키는 판정

# 4.2절 원천 대조표와 4.3절 구조 꼴 적용표에서 반드시 있어야 하는 칸
COLUMNS_4_2 = ("No.", "답 요소", "요소 종류", "사용 CQ", "판정", "근거 위치", "처리", "결정 No.")
COLUMNS_4_3 = ("No.", "CQ", "뺀 꼴 요소")

# CQ 번호 꼴. 영문자 뒤에 숫자가 붙은 낱말(Q1·CQ-01·N3)과, 번호 사이에 올 수 있는 글자
CQ_ID = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z]+-?\d+)(?![A-Za-z0-9_])")
CQ_GAP = re.compile(r"(?:[\s,，·/;、~]|\([^)]*\)|（[^）]*）)*")
# 문서 정보 표 입력 행의 '(경로) (해시 앞 12자)'
PATH_HASH = re.compile(r"`?([^`,(]+?)`?\s+\(([0-9a-f]{12})\)")
# 4.2절 근거 위치의 '테이블.컬럼'(앞에 스키마가 붙어도 됨)
TABLE_COLUMN = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){1,2})"
                          r"(?![A-Za-z0-9_])")
SEPARATOR = re.compile(r":?-+:?")
DIGITS = re.compile(r"\d+")

# CQ 문서 질문 표의 칸 이름(norm 꼴). CQ 문서 형식은 정해져 있지 않아 흔한 이름을 모은다
CQ_NUMBER_HEADS = ("번호", "id", "no.", "no", "cq", "cqid", "cq번호", "질문번호", "#")
CQ_TEXT_WORDS = ("질문", "물어보는", "question")
CQ_GRADE_WORDS = ("등급", "중요도", "우선순위", "필수여부", "grade", "priority")


class ReportError(di.ReadError):
    """설계 리포트나 CQ 문서를 읽지 못했거나 부르는 절·칸이 없다. di.ReadError 를 받는 쪽도 받는다.
    글자는 di.ReadError 꼴 '<경로> (<까닭>)' 이라 경로가 한 번 들어 있다. 부르는 쪽은 경로를 다시 붙이지 않는다.
    절·칸이 없으면 problem 이 '절·칸 없음' 이고 detail 이 그 까닭 글자다."""


class Row(dict):
    """표 행. 열쇠는 칸 이름의 norm 꼴이고, line 은 줄 자리(0부터), cells 는 칸 글자 차례다."""


# ── 글자 다듬기 ───────────────────────────────────────────────────────────────

def clean(text):
    """칸 글자에서 서식 표지(백틱·굵게·낫표·줄바꿈 표지)를 걷는다."""
    s = re.sub(r"<br\s*/?>", " ", text or "").replace("`", "").replace("**", "")
    return s.strip().strip("「」").strip()


def is_none(text):
    """빈 값·'-'·'해당 없음'(뒤에 괄호가 붙어도)·'없음'."""
    s = clean(text)
    return s in ("", "-", "없음") or s.startswith(NONE)


def verdict(cell):
    """4.2절 판정 칸 값. 괄호 앞 낱말로 가른다. 「있음(판정 정정: 확인 필요 → 있음)」은 「있음」이다."""
    return re.split(r"[(（]", cell or "", 1)[0].strip()


def sha12_text(text):
    """글자의 SHA-256 앞 12자."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def sha12_file(path):
    """파일 바이트의 SHA-256 앞 12자. 텍스트로 읽지 않는다."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def cq_list(cell):
    """CQ 칸 글자 앞머리의 CQ 번호를 나온 차례로. 번호 사이에는 구분 글자(쉼표·가운뎃점·빗금)와 괄호 묶음만 올 수
    있고, 그 밖의 글자가 나오면 거기서 멈춘다. 'CQ-01 교육별 참석 사원' 처럼 번호 뒤에 짧은 내용이 붙은 칸에서
    내용 속 낱말을 번호로 읽지 않기 위함이다. 영문자가 붙은 번호가 없고 첫 낱말이 숫자면 그 숫자 하나."""
    s = clean(cell)
    found, pos = [], 0
    for m in CQ_ID.finditer(s):
        if not CQ_GAP.fullmatch(s[pos:m.start()]):
            break
        found.append(m.group(1))
        pos = m.end()
    if not found:
        m = re.match(r"^(\d+)(?![\d.])", s)
        if m:
            found = [m.group(1)]
    return list(dict.fromkeys(found))


def cq_set(cell):
    """CQ 칸 글자(사용 CQ·근거 CQ·CQ 칸)에서 CQ 번호 집합."""
    return set(cq_list(cell))


def cq_number(cell):
    """CQ 칸(CQ 번호와 짧은 내용)의 첫 CQ 번호. 없으면 None."""
    found = cq_list(cell)
    return found[0] if found else None


def split_items(cell):
    """한 칸에 쉼표로 이어 적은 값을 나눈다. 괄호 안의 쉼표로는 나누지 않는다."""
    out, cur, depth = [], "", 0
    for ch in clean(cell):
        if ch in "(（":
            depth += 1
        elif ch in ")）":
            depth = max(0, depth - 1)
        if ch in ",，;" and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out if x.strip()]


def split_join(cell):
    """6절 조인 속성 칸. 'a = b' 꼴이면 양쪽, 이름 하나면 그 이름 하나의 집합."""
    return {x.strip() for x in re.split(r"\s*(?:=|↔|⇔)\s*", clean(cell)) if x.strip()}


def concept_props(cell):
    """'개념 · 속성' 꼴을 쉼표로 이은 칸에서 (개념, 속성) 짝. 개념이 빠진 조각은 앞 조각의 개념을 잇는다."""
    out, current = [], None
    for piece in split_items(cell):
        if " · " in piece:
            current, prop = [x.strip() for x in piece.split(" · ", 1)]
        else:
            prop = piece
        if current and prop and not is_none(prop):
            out.append((current, prop))
    return out


def pick(row, name):
    """행에서 칸 이름 name 의 글자. 같은 이름을 먼저, 없으면 이름이 든 칸을 찾는다. 없으면 ''."""
    key = js.norm(name)
    if key in row:
        return row[key]
    for k, v in row.items():
        if key and key in k:
            return v
    return ""


def nfc(text):
    """파일 이름 글자를 NFC 로 맞춘다. 운영체제가 한글 이름을 풀어쓴 꼴(NFD)로 돌려줄 때가 있다."""
    return unicodedata.normalize("NFC", text or "")


def element_name(cell):
    """4.2절 답 요소 칸(값 이름과 짧은 뜻)에서 이름만. 괄호·대시·쌍점 앞 글자다."""
    return re.split(r"[(（]|\s+[—–-]\s+|:\s", clean(cell), 1)[0].strip()


def first_int(text):
    m = DIGITS.search(text or "")
    return int(m.group(0)) if m else None


# ── 표 읽기 ──────────────────────────────────────────────────────────────────

def _tables(lines, span):
    """span(시작 자리, 끝 자리) 안의 표 [(머리글 norm 칸, [Row])]. 구분 줄은 건너뛰고 빈 행은 넣지 않는다."""
    out, head, rows = [], None, []
    start, end = span
    for i in range(start, end + 1):
        s = lines[i].strip() if i < end else ""
        if s.startswith("|"):
            cells = js.split_row(s)
            if all(SEPARATOR.fullmatch(c or "-") for c in cells):
                continue
            if head is None:
                head = [js.norm(c) for c in cells]
            elif any(cells):
                row = Row((k, cells[n] if n < len(cells) else "") for n, k in enumerate(head) if k)
                for k in head:      # '출발 → 도착' 처럼 화살표로 이은 칸은 양쪽 이름으로도 나눠 둔다
                    if "→" in k and row.get(k):
                        a, b = k.split("→", 1)
                        parts = [x.strip() for x in row[k].split("→", 1)]
                        if len(parts) == 2:
                            row.setdefault(a, parts[0])
                            row.setdefault(b, parts[1])
                row.line, row.cells = i, cells
                rows.append(row)
        elif head is not None:
            out.append((head, rows))
            head, rows = None, []
    return out


def _row_number(row):
    text = clean(row.get("no.", ""))
    return int(text) if text.isdigit() else (text or row.line + 1)


def section_span(rep, no):
    """no 절(예: '4.3'·'6'·'12')의 (시작 자리, 끝 자리). 시작은 제목 다음 줄 자리(0부터), 끝은 같거나 높은 단계의
    다음 제목 줄 자리다. 4.3절은 다음 ### 제목(4.4 구조 꼴 선택 근거 소절) 앞에서 끝나 그 소절 줄이 들지 않는다.
    절이 없으면 None."""
    pat = re.compile(r"^%s(?:\.(?!\d)|\s|$)" % re.escape(no))
    for title, start, end in rep.heads:
        if pat.match(title):
            return start, end
    return None


def _need_columns(rep, where, head, names):
    missing = [n for n in names if js.norm(n) not in head]
    if missing:
        raise ReportError(rep.path, "절·칸 없음", "%s 표에 %s 칸이 없음" % (where, "·".join(missing)))


def _numbered_table(rep, no, words, names):
    """no 소절의 첫 표를 {No.(정수): 행} 으로. 소절은 번호로, 없으면 제목 낱말로 찾는다."""
    where = "설계 리포트 %s절" % no
    span = section_span(rep, no)
    if span is None:
        for title, start, end in rep.heads:
            if all(w in title for w in words) and not re.match(r"^\d+\.\s", title):
                span = (start, end)
                break
    if span is None:
        raise ReportError(rep.path, "절·칸 없음", "설계 리포트에 %s절이 없음: %s" % (no, " ".join(words)))
    found = _tables(rep.lines, span)
    if not found:
        raise ReportError(rep.path, "절·칸 없음", "%s에 표가 없음" % where)
    head, rows = found[0]
    _need_columns(rep, where, head, names)
    out = {}
    for row in rows:
        text = clean(row.get("no.", ""))
        if not text.isdigit():
            raise ReportError(rep.path, "절·칸 없음", "%s No. 칸이 정수가 아님: '%s'" % (where, text))
        out[int(text)] = row
    return out


def table_4_2(rep):
    """4.2절 원천 대조표를 {No.(정수): 행} 으로. 소절이나 칸이 없으면 ReportError."""
    return _numbered_table(rep, "4.2", ("원천", "대조표"), COLUMNS_4_2)


def table_4_3(rep):
    """4.3절 구조 꼴 적용표를 {No.(정수): 행} 으로. 4.3절 끝은 다음 ### 제목 앞이라 4.4 소절 줄이 들지 않는다.
    소절이나 칸('CQ'·'뺀 꼴 요소')이 없으면 ReportError."""
    return _numbered_table(rep, "4.3", ("구조", "꼴", "적용"), COLUMNS_4_3)


def _4_1_table(rep):
    span = section_span(rep, "4.1")
    if span is None:
        return None, []
    for head, rows in _tables(rep.lines, span):
        if "cq" in head:
            return head, rows
    return None, []


def has_cq_hash(rep):
    """4절 CQ 행 표(4.1절)에 '해시/등급' 칸이 있는가."""
    head, _ = _4_1_table(rep)
    return head is not None and js.norm(CQ_COL) in head


# ── 설계 리포트 ──────────────────────────────────────────────────────────────

class Report:
    """설계 리포트 한 벌. lines 는 splitlines() 로 나눈 줄, info 는 문서 정보 표, heads 는 ##·### 제목이다."""

    def __init__(self, path, lines, info, heads, text=None):
        self.path, self.lines, self.info, self.heads = path, list(lines), info, heads
        self.text = text if text is not None else "\n".join(lines) + "\n"
        self.folder = os.path.dirname(os.path.abspath(path))

    # ── 절과 표
    def span(self, no):
        return section_span(self, no)

    def has_section(self, no):
        return section_span(self, no) is not None

    def rows(self, no, col=None):
        """no 절의 첫 표(col 을 주면 그 칸이 있는 첫 표)를 [(No., 행)] 으로. 절이나 표가 없으면 []."""
        span = section_span(self, no)
        if span is None:
            return []
        found = _tables(self.lines, span)
        if col is not None:
            found = [t for t in found if js.column(t[0], col) is not None]
        if not found:
            return []
        return [(_row_number(r), r) for r in found[0][1]]

    def count_rows(self, no):
        return len(self.rows(no))

    def section_text(self, no):
        span = section_span(self, no)
        return "\n".join(self.lines[span[0]:span[1]]).strip() if span else None

    def is_pending(self, no):
        """절 전체가 「정의 문서 작성 뒤 기재」 한 줄인가(표 대신 그 줄을 둔 절)."""
        span = section_span(self, no)
        if span is None:
            return False
        body = [ln.strip() for ln in self.lines[span[0]:span[1]] if ln.strip()]
        return any(clean(ln.lstrip("-* ")) == PENDING for ln in body if not ln.startswith("|"))

    def section_of(self, index):
        """줄 자리(0부터)가 든 가장 안쪽 절의 번호. 절 밖이면 None."""
        best = None
        for title, start, end in self.heads:
            if start - 1 <= index < end and (best is None or start > best[1]):
                best = (title, start)
        if best is None:
            return None
        m = re.match(r"^(\d+(?:\.\d+)*)", best[0])
        return m.group(1) if m else None

    # ── 2절 설계 결과 요약
    def summary(self):
        out = {}
        for _, r in self.rows("2"):
            if len(r.cells) >= 2:
                out[clean(r.cells[0])] = r.cells[1]
        return out

    def summary_value(self, name):
        return self.summary().get(name)

    def summary_has(self, name):
        return name in self.summary()

    def summary_count(self, name):
        """2절 값의 건수(첫 'n건'). '해당 없음'이면 0, 행이 없거나 셀 수 없으면 None."""
        value = self.summary_value(name)
        if value is None:
            return None
        if clean(value).startswith(NONE):
            return 0
        m = re.search(r"(\d+)\s*건", value)
        return int(m.group(1)) if m else None

    def summary_number(self, name):
        """2절 값에서 첫 숫자(회·건). 행이 없거나 숫자가 없으면 None."""
        value = self.summary_value(name)
        m = re.search(r"(\d+)\s*(?:회|건)", value or "")
        return int(m.group(1)) if m else None

    # ── 문서 정보 표
    def info_paths(self, key):
        """문서 정보 표 key 행에 적힌 경로들. 해시가 붙은 꼴을 먼저 읽고, 없으면 백틱 안 글자나 쉼표 앞 글자."""
        value = self.info.get(key, "")
        if is_none(value):
            return []
        pairs = [p.strip() for p, _ in PATH_HASH.findall(value)]
        if pairs:
            return pairs
        quoted = [q.strip() for q in re.findall(r"`([^`]+)`", value) if not q.strip().startswith("-")]
        if quoted:
            return quoted
        head = value.split(",")[0].strip()
        return [] if is_none(head) or head.startswith("(") else [head]

    def info_path(self, key):
        found = self.info_paths(key)
        return found[0] if found else None

    def resolve(self, path):
        """리포트에 적힌 경로를 연다. 절대 경로는 그대로, 상대 경로는 설계 리포트 폴더 기준을 먼저 보고,
        거기 없고 작업 폴더 기준으로 있으면 그것을 쓴다."""
        p = os.path.expanduser(clean(path or ""))
        if os.path.isabs(p):
            return p
        here = os.path.join(self.folder, p)
        if os.path.exists(here) or not os.path.exists(p):
            return here
        return os.path.abspath(p)

    def input_hashes(self, labels):
        """입력 행마다 [(행 이름, 경로, 적힌 해시)]. 경로는 있는데 해시가 없으면 해시 자리가 None 이다."""
        out = []
        for label in labels:
            value = self.info.get(label)
            if value is None or is_none(value):
                continue
            pairs = PATH_HASH.findall(value)
            if pairs:
                out += [(label, p.strip(), h) for p, h in pairs]
            else:
                out += [(label, p, None) for p in self.info_paths(label)]
        return out

    def input_paths(self, label):
        return [self.resolve(p) for p in self.info_paths(label)]

    def round_no(self):
        """이 리포트의 차수. 문서 정보 표 「차수」, 없으면 파일 이름의 '-N차', 둘 다 없으면 1."""
        m = re.search(r"(\d+)\s*차", self.info.get("차수", ""))
        if m:
            return int(m.group(1))
        n = round_of_name(self.path)
        return n if n is not None else 1

    def round_copies(self):
        """같은 폴더의 이번 차수 회차 사본 <이름>-온톨로지-설계-리포트-N차-r<n>.md 목록."""
        stem = nfc(os.path.splitext(os.path.basename(self.path))[0])
        base = re.sub(r"(?:-\d+차)?(?:-r\d+)?$", "", stem)
        pat = re.compile(r"^%s-%d차-r\d+\.md$" % (re.escape(base), self.round_no()))
        try:
            names = os.listdir(self.folder)
        except OSError:
            return []
        return sorted(os.path.join(self.folder, n) for n in names if pat.match(nfc(n)))

    # ── 닫힌 값 자리
    def marks(self, mark):
        """mark 가 표 칸 값이거나 줄 전체인 자리 [(줄 번호, 절 번호, 칸 이름, 행 첫 칸)].
        표 칸은 칸 글자가 mark 로 시작하면, 표 밖 줄은 글머리를 뗀 줄 전체가 mark 이면 친다.
        설명 문장 안에 든 같은 낱말은 치지 않는다."""
        out = []
        for i, ln in enumerate(self.lines):
            s = ln.strip()
            if s.startswith("|"):
                cells = js.split_row(s)
                if all(SEPARATOR.fullmatch(c or "-") for c in cells):
                    continue
                head = self._head_of(i)
                for n, c in enumerate(cells):
                    if clean(c).startswith(mark):
                        col = head[n] if head and n < len(head) else None
                        out.append((i + 1, self.section_of(i), col, clean(cells[0]) if cells else ""))
            elif clean(s.lstrip("-* ")) == mark:
                out.append((i + 1, self.section_of(i), None, ""))
        return out

    def _head_of(self, index):
        """index 줄이 든 표의 머리글 norm 칸."""
        i = index
        while i > 0 and self.lines[i - 1].strip().startswith("|"):
            i -= 1
        return [js.norm(c) for c in js.split_row(self.lines[i].strip())]

    def find_lines(self, mark):
        """mark 가 표 칸 값이거나 줄 전체인 줄 번호(1부터)."""
        return sorted({n for n, _, _, _ in self.marks(mark)})

    def pending_outside(self, mark, sections, allow=None, res=None):
        """mark 가 sections 밖에 남은 자리를 res.mismatches 에 더한다. allow 는 (절, 칸 이름) 예외 한 쌍이다.
        2절 「문서 타입」 행도 설계 단계 판에서는 이 값을 쓰므로 받는다."""
        bad = []
        for n, sec, col, first in self.marks(mark):
            if sec in sections:
                continue
            if allow and sec == allow[0] and col and col.startswith(js.norm(allow[1])):
                continue
            if sec == "2" and first == "문서 타입":
                continue
            bad.append(n)
        where = "%s절 전체" % "·".join(sections)
        if allow:
            where += ", %s절 %s 칸" % (allow[0], {"대표표시": "대표 표시 속성"}.get(allow[1], allow[1]))
        if res is not None:
            res.mismatches += [{"자리": "설계 리포트 %d줄" % n,
                                "까닭": "「%s」는 %s, 2절 「문서 타입」 행에서만 씀" % (mark, where)} for n in bad]
        return bad

    def note_lines(self, prefix):
        return [ln.strip() for ln in self.lines if ln.strip().startswith(prefix)]

    # ── 이름 집합
    def col(self, no, name):
        return [clean(pick(r, name)) for _, r in self.rows(no) if clean(pick(r, name))]

    def names(self, no, name):
        """no 절 name 칸('개념 · 속성' 꼴)의 (개념, 속성) 짝 집합."""
        return {pair for _, r in self.rows(no) for pair in concept_props(pick(r, name))}

    def props(self, include_title=True):
        """설계 리포트가 밝힌 (개념, 속성) 이름 집합. 4.1절 사용 속성, 5.3절 개념·속성, 5.1절 식별 속성
        (include_title 이면 대표 표시 속성도), 6절 조인 속성(출발·도착 개념의 속성)을 모은다."""
        out = self.names("4.1", "사용 속성") | self.names("5.3", "개념·속성")
        cols = ("식별 속성", "대표 표시 속성") if include_title else ("식별 속성",)
        for _, r in self.rows("5.1"):
            concept = clean(pick(r, "개념"))
            for c in cols:
                cell = pick(r, c)
                if concept and not is_none(cell) and not clean(cell).startswith(PENDING):
                    out |= {(concept, p) for p in split_items(cell) if not is_none(p)}
        for _, r in self.rows("6"):
            joins = sorted(split_join(pick(r, "조인 속성")))
            src, dst = clean(r.get("출발", "")), clean(r.get("도착", ""))
            if len(joins) == 1 and not is_none(joins[0]):
                out |= {(src, joins[0]), (dst, joins[0])}
            elif len(joins) == 2:
                a, b = [x.strip() for x in re.split(r"\s*(?:=|↔|⇔)\s*", clean(pick(r, "조인 속성")), 1)]
                out |= {(src, a), (dst, b)}
        return {(c, p) for c, p in out if c and p}

    def rel_keys(self, no="6"):
        return [(clean(r.get("관계", "")), clean(r.get("출발", "")), clean(r.get("도착", "")))
                for _, r in self.rows(no)]

    def cq_keys(self, no="4.1"):
        return {cq_number(pick(r, "CQ")) for _, r in self.rows(no)} - {None}

    def cited_cqs(self, no, name):
        """no 절 name 칸(근거 CQ)에 적힌 CQ 번호 [(No., CQ 번호)]."""
        return [(n, cq) for n, r in self.rows(no) for cq in cq_list(pick(r, name))]

    @staticmethod
    def int_cell(row, name):
        return first_int(pick(row, name))

    def source_basis(self, no="4.2"):
        """근거 위치가 원천 위치를 가리키는 4.2절 행의 {답 요소 이름: {(테이블, 컬럼)}}. 테이블·컬럼은 소문자로 맞춘다."""
        out = {}
        for _, r in self.rows(no):
            if verdict(pick(r, "판정")) not in BASIS_VERDICTS:
                continue
            element = element_name(pick(r, "답 요소"))
            for name in TABLE_COLUMN.findall(clean(pick(r, "근거 위치"))):
                parts = name.lower().split(".")
                out.setdefault(element, set()).add((parts[-2], parts[-1]))
        return out

    def adopted_mts(self, no="7.1"):
        """7.1절 매핑 테이블 [(이름, 채택했는가)]. 결정 칸이 없는 표면 채택 여부를 None 으로 둔다."""
        out = []
        for _, r in self.rows(no):
            name = clean(pick(r, "이름"))
            if name:
                taken = clean(pick(r, "결정")).startswith("채택") if "결정" in r else None
                out.append((name, taken))
        return out

    # ── 4절 CQ 행 '해시/등급' 칸
    def cq_rows(self, no="4", col=CQ_COL):
        """no 절에서 col 칸이 있는 표의 행 [(행, 칸 자리)]."""
        span = section_span(self, no)
        if span is None:
            return []
        out = []
        for head, rows in _tables(self.lines, span):
            if js.norm(col) in head and "cq" in head:
                out += [(r, head.index(js.norm(col))) for r in rows]
        return out

    def cells(self, no="4", col=CQ_COL, dups=None):
        """{CQ 번호: col 칸 글자}. dups 는 여러 CQ 문서에 겹친 번호의 {번호: [문서 이름]}."""
        out = {}
        for r, idx in self.cq_rows(no, col):
            key = cq_key(r, dups)
            if key is not None:
                out[key] = clean(r.cells[idx]) if idx < len(r.cells) else ""
        return out

    def with_cells(self, no, col, values, only=FILL, dups=None):
        """col 칸이 only 인 CQ 행에 values[CQ 번호] 를 채운 리포트 글자. 다른 줄과 칸은 그대로 둔다."""
        lines = list(self.lines)
        for r, idx in self.cq_rows(no, col):
            key = cq_key(r, dups)
            if key in values and idx < len(r.cells) and clean(r.cells[idx]) == only:
                lines[r.line] = _replace_cell(lines[r.line], idx, values[key])
        text = "\n".join(lines)
        return text + "\n" if self.text.endswith("\n") else text


def _replace_cell(line, idx, value):
    """표 줄의 idx 칸(0부터) 글자만 바꾼다. 막은 세로줄(\\|)은 칸을 가르지 않는다."""
    bars, i = [], 0
    while i < len(line):
        if line[i] == "\\" and line[i + 1:i + 2] in ("\\", "|"):
            i += 2
            continue
        if line[i] == "|":
            bars.append(i)
        i += 1
    lead = 1 if line.strip().startswith("|") else 0
    left = bars[idx + lead - 1] if idx + lead - 1 >= 0 else -1
    right = bars[idx + lead] if idx + lead < len(bars) else len(line)
    return line[:left + 1] + " %s " % value.replace("|", "\\|") + line[right:]


def cq_key(row, dups=None):
    """4절 CQ 행의 열쇠. CQ 번호이고, 여러 CQ 문서에 겹친 번호면 출처 칸에 적힌 문서 이름으로 가른다."""
    no = cq_number(pick(row, "CQ"))
    if no is None or not dups or no not in dups:
        return no
    source = clean(pick(row, "출처"))
    for k, name in enumerate(dups[no]):
        if k and (name in source or os.path.splitext(name)[0] in source):
            return "%s(%s)" % (no, name)
    return no


def round_of_name(path):
    """파일 이름의 차수. '-N차' 나 '-N차-r<n>' 꼴이 아니면 None."""
    m = re.search(r"-(\d+)차(?:-r\d+)?\.md$", nfc(os.path.basename(path or "")))
    return int(m.group(1)) if m else None


def read_report(path, cls=None):
    """설계 리포트를 읽는다. 읽지 못하면 ReportError. cls 를 주면 Report 를 이은 그 꼴로 돌려준다."""
    try:
        text = di.read_text(path)
    except ReportError:
        raise
    except di.ReadError as e:
        raise ReportError(e.path, e.problem, e.detail)
    lines = text.splitlines()
    return (cls or Report)(path, lines, js.info_table(lines), js.headings(lines), text)


# ── CQ 문서와 CQ 해시 ─────────────────────────────────────────────────────────

class CQRow:
    """CQ 문서의 질문 한 줄. no 는 CQ 번호, text 는 질문 글자, grade 는 등급(없으면 '-'),
    by_skill 은 번호가 없어 스킬 규칙으로 매긴 번호인가, line 은 줄 번호(1부터)다."""
    __slots__ = ("no", "text", "grade", "by_skill", "line")

    def __init__(self, no, text, grade, by_skill, line):
        self.no, self.text, self.grade, self.by_skill, self.line = no, text, grade, by_skill, line

    def value(self):
        return "%s/%s" % (sha12_text(self.text), self.grade or "-")


def _find(head, words, exact=()):
    for n, h in enumerate(head):
        if h in exact or any(w in h for w in words):
            return n
    return None


def read_cq_rows(path):
    """CQ 문서의 질문 행 [CQRow]. 질문 칸이 있는 표를 읽고, 등급 칸이 있는 질문 표가 있으면 그 표들만 읽는다.
    번호 칸이 없거나 빈 행은 받은 차례대로 Q1·Q2 … 를 매기고, 그 문서가 이미 Q 로 시작하는 번호를 쓰면 N1·N2 …
    로 매긴다. 질문 표가 없으면 번호로 시작하는 줄('Q1. 질문' 꼴)을 읽는다. 읽지 못하면 ReportError."""
    try:
        lines = di.read_text(path).splitlines()
    except di.ReadError as e:
        raise ReportError(e.path, e.problem, e.detail)
    tables = []
    for head, rows in _tables(lines, (0, len(lines))):
        ti = next((n for n, h in enumerate(head) if any(w in h for w in CQ_TEXT_WORDS) and "번호" not in h), None)
        ni = _find(head, ("번호",), tuple(h for h in CQ_NUMBER_HEADS if h != "cq"))
        ci = head.index("cq") if "cq" in head else None
        if ti is None and ni is not None:       # 'No. | CQ' 꼴이면 CQ 칸이 질문 글자다
            ti = ci
        elif ni is None and ci is not None and ci != ti:        # 'CQ | 질문' 꼴이면 CQ 칸이 번호다
            ni = ci
        if ti is None:
            continue
        if ni == ti:
            ni = None
        gi = _find(head, CQ_GRADE_WORDS)
        tables.append((ni, ti, gi, rows))
    if any(gi is not None for _, _, gi, _ in tables):
        tables = [t for t in tables if t[2] is not None]
    raw = []
    for ni, ti, gi, rows in tables:
        for r in rows:
            text = r.cells[ti].strip() if ti < len(r.cells) else ""
            if not text:
                continue
            no = clean(r.cells[ni]) if ni is not None and ni < len(r.cells) else ""
            grade = clean(r.cells[gi]) if gi is not None and gi < len(r.cells) else ""
            raw.append([no, text, grade or "-", r.line + 1])
    if not tables:
        pat = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?([A-Za-z]+-?\d+)(?:\*\*)?[.:)]?\s+(.+?)\s*$")
        raw = [[m.group(1), m.group(2), "-", i + 1] for i, ln in enumerate(lines) if (m := pat.match(ln))]
    prefix = "N" if any(no.upper().startswith("Q") for no, _, _, _ in raw if no) else "Q"
    out, n = [], 0
    for no, text, grade, line in raw:
        by_skill = not no
        if by_skill:
            n += 1
            no = "%s%d" % (prefix, n)
        out.append(CQRow(no, text, grade, by_skill, line))
    return out


def cq_duplicates(cq_paths):
    """여러 CQ 문서에 겹친 번호의 {번호: [문서 이름]}. 문서 이름 차례로 둔다."""
    seen = {}
    for path in sorted(cq_paths, key=os.path.basename):
        for r in read_cq_rows(path):
            names = seen.setdefault(r.no, [])
            if os.path.basename(path) not in names:
                names.append(os.path.basename(path))
    return {no: names for no, names in seen.items() if len(names) > 1}


def cq_hashes(cq_paths):
    """CQ 문서들을 직접 읽어 {CQ 번호: '문장 해시 앞 12자/등급'}. 등급이 없으면 빗금 뒤가 '-' 다.
    여러 문서에 같은 번호가 있으면 문서 이름 차례로 둘째 문서부터 '번호(문서 이름)' 으로 가른다.
    한 문서 안에 같은 번호가 또 나오면 앞 행을 쓴다."""
    out = {}
    for path in sorted(cq_paths, key=os.path.basename):
        name = os.path.basename(path)
        for r in read_cq_rows(path):
            key = r.no if r.no not in out or name == _owner(out, r.no) else "%s(%s)" % (r.no, name)
            out.setdefault(key, (r.value(), name))
    return {k: v for k, (v, _) in out.items()}


def _owner(found, no):
    return found[no][1] if no in found else None


def cq_change(kept, now):
    """4절 칸 값(kept)과 다시 셈한 값(now)의 갈래. 같으면 None.
    더함(CQ 문서에만 있음)·뺌(4절에만 있음)·자리표시 남음·문장 바뀜·등급 바뀜 가운데 하나다."""
    if kept == now:
        return None
    if kept is None:
        return "더함"
    if now is None:
        return "뺌"
    old = re.match(r"^([0-9a-f]{12})\s*/\s*(.*)$", kept.strip())
    if not old:
        return "자리표시 남음"
    new_hash, new_grade = now.split("/", 1)
    if old.group(1) != new_hash:
        return "문장 바뀜"
    return "등급 바뀜" if old.group(2).strip() != new_grade else None


def cq_hash_diff(rep, cq_paths):
    """CQ 문서를 다시 셈한 번호별 '해시/등급' 이 4절 CQ 행 칸과 다른 CQ 번호 목록(정렬)."""
    now = cq_hashes(cq_paths)
    kept = rep.cells("4", CQ_COL, cq_duplicates(cq_paths))
    return sorted(k for k in set(now) | set(kept) if cq_change(kept.get(k), now.get(k)))


# ── 이름 집합과 두 리포트 차이 ────────────────────────────────────────────────

def names(rep):
    """설계 리포트의 이름 집합. ('개념', 이름)·('속성', 개념, 속성)·('관계', 관계, 출발, 도착).
    대표 표시 속성 칸은 설계 단계 판에서 비워 두는 칸이라 넣지 않는다."""
    return ({("개념", n) for n in rep.col("5.1", "개념")}
            | {("속성", c, p) for c, p in rep.props(include_title=False)}
            | {("관계",) + k for k in rep.rel_keys("6")})


def key_text(key):
    """대상 키 글자. 개념 이름, '개념 › 속성', '관계(출발 → 도착)', '개념 ← 데이터 구조'."""
    kind, rest = key[0], key[1:]
    if kind == "속성":
        return "%s › %s" % rest
    if kind == "관계":
        return "%s(%s → %s)" % rest
    if kind == "매핑":
        return "%s ← %s" % rest
    return rest[0] if len(rest) == 1 else " · ".join(rest)


def keys(rep):
    """두 리포트를 맞댈 절별 열쇠. 4.1절 (출처, CQ 번호) → 행, 5.1절 개념 이름, 6절 (관계, 출발, 도착)."""
    q = {(clean(pick(r, "출처")), cq_number(pick(r, "CQ"))): r for _, r in rep.rows("4.1")}
    return q, set(rep.col("5.1", "개념")), set(rep.rel_keys("6"))


def report_diff(prev, rep):
    """앞 판(prev)과 지금 판(rep)의 차이 건수. 4.1절은 더함·뺌·바뀐 행을 모두 바뀐 행으로 센다."""
    pq, pc, pr = keys(prev)
    q, c, r = keys(rep)
    return {"concepts_added": len(c - pc), "concepts_removed": len(pc - c),
            "rels_added": len(r - pr), "rels_removed": len(pr - r),
            "q_changed": sum(1 for k in set(pq) | set(q) if pq.get(k) != q.get(k))}


# ── 정의 문서와 맞대기 ───────────────────────────────────────────────────────

def diff_row(kind, key, branch, form=None):
    """설계 차이 한 건. 종류·대상 키·갈래와, 구조 꼴 갈래면 꼴 이름."""
    text = key_text((kind,) + (tuple(key) if isinstance(key, tuple) else (key,)))
    row = {"종류": kind, "대상 키": text, "갈래": branch}
    if form:
        row["꼴"] = form
    return row


def prop_keys(pairs):
    """names() 와 같은 속성 열쇠 (개념, 속성)."""
    return {(c, p) for c, p in pairs}


def mt_diff(adopted, structures):
    """7.1절 매핑 테이블과 정의 문서 데이터 구조. 채택했는데 없으면 뺌, 채택하지 않았는데 있으면 더함.
    결정 칸이 없어 채택 여부를 모르는 행은 맞대지 않는다."""
    have = set(structures)
    out = [diff_row("데이터 구조", name, "뺌") for name, taken in adopted if taken is True and name not in have]
    out += [diff_row("데이터 구조", name, "더함") for name, taken in adopted if taken is False and name in have]
    return out


def design_diff(rep, idx):
    """설계 리포트(5.1·속성·6·7.1·4.2절)와 정의 문서 색인(DefinitionIndex)의 이름 차이 [차이 한 건].
    이름이 바뀌면 짝짓지 않고 뺌·더함 두 건으로 낸다. 갈래는 더함·뺌·관계 방향·조인 속성·속성 수·구조 꼴·
    원천 선택 가운데 하나다. 원천 선택은 매핑 속성과 이름이 같은 4.2절 답 요소의 근거 위치(테이블.컬럼)에
    매핑의 데이터 구조·컬럼이 없을 때 매핑마다 한 건이다. 이름이 같은 답 요소가 없는 매핑 속성은 맞대지 않는다."""
    out = []
    want = {clean(pick(r, "개념")): r for _, r in rep.rows("5.1") if clean(pick(r, "개념"))}
    have = {c.name: c for c in idx.concepts if c.name}
    out += [diff_row("개념", n, "더함") for n in sorted(set(have) - set(want))]
    out += [diff_row("개념", n, "뺌") for n in sorted(set(want) - set(have))]
    p_want = prop_keys(rep.props())
    p_have = prop_keys((c.name, p.name) for c in idx.concepts for p in c.children if c.name and p.name)
    out += [diff_row("속성", k, "더함") for k in sorted(p_have - p_want)]
    out += [diff_row("속성", k, "뺌") for k in sorted(p_want - p_have)]
    for n in sorted(set(want) & set(have)):      # 보조 갈래
        written = rep.int_cell(want[n], "속성 수")
        if written is not None and written != len([p for p in have[n].children if p.name]):
            out.append(diff_row("개념", n, "속성 수"))
    rels = {k: r for k, (_, r) in zip(rep.rel_keys("6"), rep.rows("6"))}
    got = {(e.name, e.source, e.target): e for e in idx.relations}
    for k in sorted(set(got) - set(rels)):
        out.append(diff_row("관계", k, "관계 방향" if (k[0], k[2], k[1]) in rels else "더함"))
    for k in sorted(set(rels) - set(got)):
        if (k[0], k[2], k[1]) not in got:
            form = clean(pick(rels[k], "구조 꼴"))
            out.append(diff_row("관계", k, "구조 꼴" if form and not is_none(form) else "뺌",
                                form if form and not is_none(form) else None))
    for k in sorted(set(rels) & set(got)):
        joins = split_join(pick(rels[k], "조인 속성"))
        if joins and joins != {got[k].source_prop, got[k].target_prop}:
            out.append(diff_row("관계", k, "조인 속성"))
    basis = rep.source_basis("4.2")     # {답 요소 이름: {(테이블, 컬럼)}}
    for m in idx.mappings:
        if not (m.concept and m.structure):
            continue
        table = m.structure.split(".")[-1].lower()
        for r in m.children:
            want = basis.get(r.name)
            if r.column and want and (table, r.column.split(".")[-1].lower()) not in want:
                out.append(diff_row("매핑", (m.concept, m.structure), "원천 선택"))
                break
    out += mt_diff(rep.adopted_mts("7.1"), [s.name for s in idx.structures])
    return out
