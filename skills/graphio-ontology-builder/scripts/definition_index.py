#!/usr/bin/env python3
"""온톨로지 정의 문서를 요소 색인으로 읽는다.

정의 문서 검사기·수집 스크립트·판정 스크립트가 지적의 위치를 같은 꼴로 적으려고 함께 쓴다.
서식 네 절을 개념·관계·데이터 구조·매핑과 그 아래 속성·컬럼·매핑 속성으로 읽고,
요소마다 제목 줄이나 표 행 줄을 둔다.

표는 변환 스크립트(자매 스킬의 build_graphio_json.py)와 같은 규칙으로 읽는다. 절과
### 블록을 같은 식으로 나누고, 블록마다 첫 표만 읽고, Link Type 은 첫 절의 첫 표만 읽는다.
변환 스크립트가 JSON 으로 옮기는 요소에는 그 배열 안의 첨자를 붙여 두어, 규격 검사기가
짚은 경로(objectTypes[2].properties[3] 등)를 정의 문서의 줄로 되돌린다.
변환 스크립트가 바뀌어 요소·행·설명을 다르게 읽으면 mismatches() 가 알린다.

    import definition_index as di      # 스크립트 폴더가 sys.path[0] 이라 그대로 읽힌다
    idx = di.load("정의.md")            # 읽지 못하면 di.ReadError
    idx.locate_line(47)                 # 47줄을 품은 요소의 위치
    idx.unread_tables()                 # 변환 스크립트가 읽지 않는 표 [(줄, 경우, 블록)]
    idx.resolve("objectTypes[2].properties[3].dataType")   # 경로가 가리키는 요소 목록
    di.location("개념", name="이름", line=12)               # "개념 '이름'(정의 문서 12줄)"
    di.parse_location("개념 '이름'(정의 문서 12줄)")        # ("개념", {"name": "이름", "line": 12})

위치 꼴은 검증 리포트와 판정 문서의 위치 표기 규칙을 옮긴 것이다. 꼴은 FORMS 한 곳에 둔다.
"""
import re

# ── 변환 스크립트와 같은 읽기 규칙 ───────────────────────────────────────────
# build_graphio_json.py 의 값을 옮겼다. 저쪽이 바뀌면 여기도 바꾼다.
# 놓치지 않게 수집 스크립트가 mismatches() 로 변환 결과와 맞대 본다.
SECTIONS = {
    "objecttype": "objectTypes", "오브젝트타입": "objectTypes",
    "linktype": "linkTypes", "링크타입": "linkTypes",
    "metatype": "metaTypes", "메타타입": "metaTypes",
    "objectmapping": "objectMapping", "오브젝트매핑": "objectMapping",
}
COL = {
    "prop_name": ("속성", "속성명", "property", "name", "이름"),
    "prop_title": ("title", "titlekey", "대표", "대표표시"),
    "lt_name": ("관계이름", "이름", "name", "관계"),
    "lt_src": ("source", "소스", "시작"),
    "lt_srcp": ("source속성", "소스속성", "sourceproperty", "시작속성"),
    "lt_tgt": ("target", "타깃", "타겟", "도착"),
    "lt_tgtp": ("target속성", "타깃속성", "타겟속성", "targetproperty", "도착속성"),
    "lt_direct": ("방향", "direct"),
    "mt_name": ("컬럼", "컬럼명", "column", "name", "이름"),
    "mt_type": ("데이터타입", "타입", "datatype", "type"),
    "om_otp": ("objecttype속성", "개념속성", "objecttypepropertyname"),
    "om_mtp": ("metatype컬럼", "데이터컬럼", "metatypepropertyname"),
}
DESC_KEYS = ("설명", "description")
# 참·거짓 칸에서 참으로 읽는 값(_norm 뒤). 대표 표시 속성 칸을 셀 때 쓴다.
TRUE_CELLS = {"o", "y", "yes", "true", "v", "✓", "✔", "예", "○", "●"}
DATA_TYPES = ("INTEGER", "TEXT", "DATETIME", "FLOAT8", "BOOLEAN", "VECTOR", "UNKNOWN")
DIRECTS = ("UNIDIRECTIONAL", "REVERSE_DIRECTIONAL", "BIDIRECTIONAL")
DIRECT_ALIASES = {
    "→": "UNIDIRECTIONAL", "->": "UNIDIRECTIONAL", "-->": "UNIDIRECTIONAL",
    "=>": "UNIDIRECTIONAL", "⇒": "UNIDIRECTIONAL",
    "단방향": "UNIDIRECTIONAL", "정방향": "UNIDIRECTIONAL", "순방향": "UNIDIRECTIONAL",
    "←": "REVERSE_DIRECTIONAL", "<-": "REVERSE_DIRECTIONAL", "<--": "REVERSE_DIRECTIONAL",
    "<=": "REVERSE_DIRECTIONAL", "⇐": "REVERSE_DIRECTIONAL",
    "역방향": "REVERSE_DIRECTIONAL", "반대방향": "REVERSE_DIRECTIONAL",
    "↔": "BIDIRECTIONAL", "<->": "BIDIRECTIONAL", "<-->": "BIDIRECTIONAL",
    "<=>": "BIDIRECTIONAL", "⇔": "BIDIRECTIONAL",
    "양방향": "BIDIRECTIONAL", "쌍방향": "BIDIRECTIONAL",
}
ARROW_RE = re.compile(r"\s*(?:←|<-{1,2}|<=)\s*")

# ── 위치 꼴 ──────────────────────────────────────────────────────────────────
# (머리말, 꼴). {line} 은 줄 번호, 나머지 {…} 는 이름이다.
# 해석은 이 차례로 맞춰 본다. 상위 요소가 붙은 꼴(›)을 먼저 두어야 이름이 짧게 잘리지 않는다.
FORMS = (
    ("개념 › 속성", "개념 '{concept}' › 속성 '{name}'(정의 문서 {line}줄)"),
    ("개념 › 속성(없음)", "개념 '{concept}' › 속성 '{name}'(없음)"),
    ("개념", "개념 '{name}'(정의 문서 {line}줄)"),
    ("개념(없음)", "개념 '{name}'(없음)"),
    ("관계", "관계 '{name}'({source} → {target}, 정의 문서 {line}줄)"),
    ("관계(없음)", "관계(없음) 개념 '{source}' → 개념 '{target}'"),
    ("데이터 구조 › 컬럼", "데이터 구조 '{structure}' › 컬럼 '{name}'(정의 문서 {line}줄)"),
    ("데이터 구조", "데이터 구조 '{name}'(정의 문서 {line}줄)"),
    ("데이터 구조(없음)", "데이터 구조 '{name}'(없음)"),
    ("매핑 › 속성", "매핑 '{concept} ← {structure}' › 속성 '{name}'(정의 문서 {line}줄)"),
    ("매핑", "매핑 '{concept} ← {structure}'(정의 문서 {line}줄)"),
    ("매핑(없음)", "매핑 '{concept} ← {structure}'(없음)"),
    ("CQ", "CQ {number}"),
    ("입력 문서", "입력 문서 '{name}' {part}"),
    ("정의 문서", "정의 문서 {line}줄"),
)
HEADS = tuple(dict.fromkeys(head for head, _ in FORMS))
# 관계(없음) 뒤에 붙이는 조인 속성. 두 개념 사이에 다른 관계가 있을 때 붙인다.
JOIN_SUFFIX = "(조인 속성 '{join}')"

KINDS = ("개념", "속성", "관계", "데이터 구조", "컬럼", "매핑", "매핑 속성")
# 규격 검사기 경로의 맨 앞 키와 그 아래 행 배열
TOP_KEYS = ("objectTypes", "linkTypes", "metaTypes", "objectMapping")
SUB_KEYS = {"objectTypes": "properties", "metaTypes": "properties",
            "objectMapping": "propertyMappings"}

# 문서를 읽지 못한 까닭. 수집 스크립트가 이 말로 멈출지 대조 불가로 둘지 가른다.
NOT_UTF8 = "UTF-8로 읽을 수 없음"
READ_PROBLEMS = ("파일 없음", NOT_UTF8, "읽기 실패")


class ReadError(Exception):
    """문서를 텍스트로 읽지 못했다. problem 은 READ_PROBLEMS 가운데 하나다."""

    def __init__(self, path, problem, detail=""):
        self.path, self.problem, self.detail = path, problem, detail
        super().__init__("%s (%s)" % (path, problem + (": " + detail if detail else "")))


class PathError(ValueError):
    """규격 검사기의 경로를 정의 문서 요소로 되돌릴 수 없다."""


class LocationError(ValueError):
    """위치 문자열이 머리말 목록 밖이다."""


def read_text(path):
    """문서를 UTF-8 텍스트로 읽는다. 다른 인코딩을 짐작해 읽지 않는다.

    짐작이 틀리면 조용히 잘못 읽기 때문이다. 읽지 못하면 ReadError 를 낸다.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise ReadError(path, "파일 없음")
    except UnicodeDecodeError:
        raise ReadError(path, NOT_UTF8)
    except OSError as e:
        raise ReadError(path, "읽기 실패", e.strerror or str(e))


def load(path):
    """정의 문서를 읽어 색인을 만든다. 줄은 변환 스크립트처럼 splitlines() 로 나눈다."""
    return DefinitionIndex(read_text(path).splitlines())


# ── 위치 문자열 ───────────────────────────────────────────────────────────────

def location(head, **values):
    """머리말 꼴의 위치 문자열을 만든다.

    값은 꼴에 든 이름으로 준다(name·concept·structure·source·target·join·number·part·line).
    관계(없음)은 join 을 주면 조인 속성을 붙인다. 칸이 모자라거나 남거나 비었으면 ValueError.
    """
    forms = dict(FORMS)
    if head not in forms:
        raise ValueError("모르는 머리말: %s" % head)
    template = forms[head]
    if head == "관계(없음)":
        join = values.pop("join", None)
        if join:
            template += JOIN_SUFFIX
            values["join"] = join
    fields = re.findall(r"\{(\w+)\}", template)
    if set(values) != set(fields):
        raise ValueError("%s 꼴의 칸은 %s 임: %s" % (head, ", ".join(fields), ", ".join(sorted(values))))
    for key in fields:
        value = values[key]
        if key == "line":
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("줄 번호는 1 이상의 정수여야 함: %r" % (value,))
        elif not isinstance(value, str) or not value.strip():
            raise ValueError("%s 꼴의 %s 칸이 비었음" % (head, key))
    return template.format(**values)


def _pattern(template):
    out = []
    for k, part in enumerate(re.split(r"\{(\w+)\}", template)):
        if k % 2 == 0:
            out.append(re.escape(part))
        elif part == "line":
            out.append(r"(?P<line>[1-9]\d*)")
        else:
            out.append(r"(?P<%s>.+?)" % part)
    return re.compile("".join(out))


def _patterns():
    """해석할 꼴 목록. 줄 번호를 빼고 적은 꼴도 받는다. 빠진 줄은 판정 스크립트가 채운다."""
    out = []
    for head, template in FORMS:
        variants = [template]
        if head == "관계(없음)":
            variants.insert(0, template + JOIN_SUFFIX)
        bare = template.replace("(정의 문서 {line}줄)", "").replace(", 정의 문서 {line}줄)", ")")
        if "{line}" not in bare:
            variants.append(bare)
        out += [(head, "{line}" in template, _pattern(v)) for v in dict.fromkeys(variants)]
    return out


_PARSE = _patterns()


# 위치 꼴의 첫머리(첫 {…} 앞의 글자). '; ' 뒤가 이 가운데 하나로 시작해야 위치를 나눈다.
_STARTS = tuple(dict.fromkeys(template.split("{")[0] for _, template in FORMS))


def split_locations(text):
    """'; ' 로 이은 위치를 나눈다. '; ' 뒤가 위치 꼴의 첫머리(개념 '·CQ ·정의 문서 등)로 시작할 때만 나눈다.

    작은따옴표 짝으로 가르지 않는다. 이름에 작은따옴표나 '; ' 가 들어도 뒤 조각이 합쳐지지 않게 하기 위해서다.
    """
    s = text or ""
    parts, start, i = [], 0, 0
    while True:
        i = s.find("; ", i)
        if i < 0:
            break
        if s.startswith(_STARTS, i + 2):
            parts.append(s[start:i])
            start = i + 2
        i += 2
    parts.append(s[start:])
    return [p.strip() for p in parts]


def parse_location(text):
    """위치 문자열 하나를 (머리말, 값) 으로 푼다.

    값의 line 은 정수다. 줄 번호를 쓰는 꼴인데 빠졌으면 None 이다.
    머리말 목록 밖이거나 '; ' 로 이은 값이면 LocationError. 이은 값은 split_locations() 로 먼저 나눈다.
    """
    s = (text or "").strip()
    if len(split_locations(s)) > 1:
        raise LocationError("위치를 여러 개 이은 값임. 나눈 뒤 풀어야 함: %s" % s)
    for head, has_line, pat in _PARSE:
        m = pat.fullmatch(s)
        if m:
            values = {k: v for k, v in m.groupdict().items() if v is not None}
            blank = [k for k, v in values.items() if k != "line" and not v.strip()]
            if blank:       # 공백뿐인 이름은 요소를 가리키지 못한다. location() 도 받지 않는다
                raise LocationError("위치의 이름이 공백뿐임: %s" % s)
            if has_line:
                values["line"] = int(values["line"]) if "line" in values else None
            return head, values
    raise LocationError("위치 머리말 목록 밖: %s" % s)


# ── 표 읽기 (변환 스크립트와 같은 규칙) ─────────────────────────────────────────

def _norm(text):
    return re.sub(r"[\s\-_·.]", "", (text or "")).lower()


def _is_separator(row):
    return bool(row) and all(re.fullmatch(r":?-{1,}:?", c.strip() or "-") for c in row)


def split_row(line):
    """표 한 줄을 칸으로 나눈다. 변환 스크립트처럼 양끝 세로줄을 하나씩 떼고 세로줄마다 나눈다.

    정의 문서와 규칙 목록 문서의 표를 읽는 규칙이다. 역슬래시로 막은 세로줄도 나눈다(변환 스크립트가 그렇다).
    """
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def _read_table(lines, start):
    """start(0부터) 줄부터 표 하나를 읽는다. (머리글, 머리글 줄, [(줄, 칸)]) 를 돌려준다.

    표보다 제목(#)이 먼저 나오면 표가 없는 것으로 본다. 빈 줄이 나오면 표가 끝난다.
    """
    i = start
    while i < len(lines) and not lines[i].strip().startswith("|"):
        if lines[i].strip().startswith("#"):
            return None, None, []
        i += 1
    if i >= len(lines):
        return None, None, []
    header, header_line = split_row(lines[i]), i + 1
    i += 1
    if i < len(lines) and lines[i].strip().startswith("|") and _is_separator(split_row(lines[i])):
        i += 1
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = split_row(lines[i])
        if not _is_separator(cells) and any(c for c in cells):
            rows.append((i + 1, cells))
        i += 1
    return header, header_line, rows


def _column(header, key):
    wanted = {_norm(k) for k in COL[key]}
    for idx, c in enumerate(header or []):
        if _norm(c) in wanted:
            return idx
    return None


def _cell(cells, idx):
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def _read_direct(value):
    raw = (value or "").strip()
    long_name = raw.upper().replace("-", "_")
    if long_name in DIRECTS:
        return long_name
    return DIRECT_ALIASES.get(re.sub(r"\s", "", raw))


def _table_starts(rows):
    """표 줄 [(줄, 원문)] 을 이어진 묶음으로 나눠 묶음마다 첫 줄(머리글 줄)을 준다."""
    return [n for k, (n, _) in enumerate(rows) if k == 0 or rows[k - 1][0] != n - 1]


def _block_end(lines, start):
    """### 블록이 끝나는 자리(0부터, 다음 ##·### 제목 줄). 없으면 문서 끝."""
    i = start
    while i < len(lines) and not re.match(r"^#{2,3}\s+(?!#)", lines[i]):
        i += 1
    return i


def _desc_bullet(lines, start, past_headings=False):
    """### 제목 아래 '- 설명:' 줄의 (설명, 줄). 표나 제목 앞까지만 보고, 여럿이면 마지막 줄.

    past_headings 이면 제목 줄(#)에서 멈추지 않고 건너뛴다. lines 는 블록 끝에서 잘라 준다.
    """
    keys = {_norm(k) for k in DESC_KEYS}
    desc, at, i = None, None, start
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("|") or s.startswith("#") and not past_headings:
            break
        m = re.match(r"^[-*]\s*([^:：]+)[:：]\s*(.*)$", s)
        if m and _norm(m.group(1)) in keys:
            desc, at = m.group(2).strip(), i + 1
        i += 1
    return desc, at


# ── 요소 ─────────────────────────────────────────────────────────────────────

class Element:
    """정의 문서의 요소 하나.

    모든 요소
      kind      KINDS 가운데 하나
      name      이름. 매핑은 '개념 ← 데이터 구조'(화살표는 ← 로 맞춤). 이름 칸이 비었으면 ''
      line      제목 줄이나 표 행 줄(1부터)
      parent    속성·컬럼·매핑 속성의 상위 요소. 나머지는 None
      json      변환 스크립트가 JSON 으로 옮기면 그 배열 안의 첨자, 옮기지 않으면 None
      cells     표 행의 칸(관계·속성·컬럼·매핑 속성)
    블록(개념·데이터 구조·매핑)
      end          블록 끝 줄. 다음 ##·### 제목의 앞 줄
      children     첫 표의 데이터 행. 개념은 속성, 데이터 구조는 컬럼, 매핑은 매핑 속성
      header, header_line   첫 표의 머리글 칸과 그 줄
      table_lines  블록 안의 표 줄 전부 [(줄, 원문)]. 첫 표 밖의 줄은 변환 스크립트가 읽지 않는다
      desc, desc_line       '- 설명:' 줄(개념·데이터 구조). 첫 표 앞에 있는 것만 읽는다
    표 칸 그대로 둔 값
      관계 source·source_prop·target·target_prop·direct, 매핑 concept·structure
      (제목이 '개념 ← 데이터 구조' 꼴이 아니면 None), 매핑 속성 column, 컬럼 data_type
    """
    __slots__ = ("kind", "name", "line", "end", "parent", "children", "json", "cells",
                 "header", "header_line", "table_lines", "desc", "desc_line",
                 "source", "source_prop", "target", "target_prop", "direct",
                 "concept", "structure", "column", "data_type")

    def __init__(self, kind, name, line, parent=None):
        for key in self.__slots__:
            setattr(self, key, None)
        self.kind, self.name, self.line, self.parent = kind, name, line, parent
        self.end, self.children, self.cells, self.table_lines = line, [], [], []

    def __repr__(self):
        return "<%s %r %d줄>" % (self.kind, self.name, self.line)

    def named(self):
        """요소 이름으로 위치를 적을 수 있는가. 적을 수 없으면 '정의 문서 n줄' 로 적는다."""
        if self.kind == "관계":
            return bool(self.name and self.source and self.target)
        if self.kind == "매핑":
            return bool(self.concept and self.structure)
        if not self.name:
            return False
        return self.parent is None or self.parent.named()

    def location(self, line=None):
        """이 요소의 위치 문자열. line 을 주면 그 줄로 적는다(줄 단위 규칙)."""
        line = self.line if line is None else line
        if not self.named():
            return location("정의 문서", line=line)
        p = self.parent
        if self.kind == "개념":
            return location("개념", name=self.name, line=line)
        if self.kind == "속성":
            return location("개념 › 속성", concept=p.name, name=self.name, line=line)
        if self.kind == "관계":
            return location("관계", name=self.name, source=self.source,
                            target=self.target, line=line)
        if self.kind == "데이터 구조":
            return location("데이터 구조", name=self.name, line=line)
        if self.kind == "컬럼":
            return location("데이터 구조 › 컬럼", structure=p.name, name=self.name, line=line)
        if self.kind == "매핑":
            return location("매핑", concept=self.concept, structure=self.structure, line=line)
        return location("매핑 › 속성", concept=p.concept, structure=p.structure,
                        name=self.name, line=line)

    def converted_children(self):
        """변환 스크립트가 JSON 으로 옮기는 하위 행. 첨자 차례다."""
        return [c for c in self.children if c.json is not None]


# 색인 요소와 변환 결과를 맞댈 때 보는 값. (JSON 키들, 요소 속성들)
_MATCH = {
    "objectTypes": (("name",), ("name",)),
    "linkTypes": (("name", "sourceObjectTypeName", "sourcePropertyName",
                   "targetObjectTypeName", "targetPropertyName"),
                  ("name", "source", "source_prop", "target", "target_prop")),
    "metaTypes": (("name",), ("name",)),
    "objectMapping": (("objectTypeName", "metaTypeName"), ("concept", "structure")),
    "properties": (("name",), ("name",)),
    "propertyMappings": (("objectTypePropertyName", "metaTypePropertyName"), ("name", "column")),
}


def _same(key, obj, el):
    keys, attrs = _MATCH[key]
    return (isinstance(obj, dict)
            and tuple(obj.get(k) for k in keys) == tuple(getattr(el, a) for a in attrs))


class DefinitionIndex:
    """정의 문서 한 벌의 요소 색인. lines 는 splitlines() 로 나눈 줄이다.

    concepts·relations·structures·mappings 는 문서에 적힌 차례의 요소 목록이다.
    변환 스크립트가 옮기지 않는 행(이름 칸이 빈 행 등)도 들어 있고, json 이 None 이다.
    sections 는 서식 네 절의 (JSON 키, 제목, 제목 줄, 끝 줄) 이다. 같은 절이 두 번 나오면 둘 다 둔다.
    """

    def __init__(self, lines):
        self.lines = list(lines)
        self.sections = []
        self.concepts, self.relations, self.structures, self.mappings = [], [], [], []

        marks = []      # (0부터 센 줄, JSON 키 또는 None, 제목)
        entries = {"objectTypes": [], "metaTypes": [], "objectMapping": []}
        current = None
        for i, line in enumerate(self.lines):
            m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
            if m:
                current = SECTIONS.get(_norm(m.group(1)))
                marks.append((i, current, m.group(1).strip()))
                continue
            m = re.match(r"^###\s+(.+?)\s*$", line)
            if m and current in entries:
                entries[current].append((i, m.group(1).strip()))
        for n, (i, key, title) in enumerate(marks):
            if key:
                end = marks[n + 1][0] if n + 1 < len(marks) else len(self.lines)
                self.sections.append((key, title, i + 1, end))

        for k, (i, title) in enumerate(entries["objectTypes"]):
            c, rows = self._block("개념", title, i)
            c.json = k      # 변환 스크립트는 개념 블록을 모두 옮긴다
            ni = _column(c.header, "prop_name")
            n = 0
            for ln, cells in rows:
                p = self._row(c, "속성", _cell(cells, ni), ln, cells)
                if p.name:  # 이름 칸이 빈 행은 옮기지 않는다
                    p.json, n = n, n + 1
            self.concepts.append(c)

        self.link_header_line = None    # Link Type 절에서 변환 스크립트가 읽는 표의 머리글 줄
        start = next((i + 1 for i, key, _ in marks if key == "linkTypes"), None)
        if start is not None:
            header, self.link_header_line, rows = _read_table(self.lines, start)
            ci = {k: _column(header, k) for k in
                  ("lt_name", "lt_src", "lt_srcp", "lt_tgt", "lt_tgtp", "lt_direct")}
            n = 0
            for ln, cells in rows:
                r = Element("관계", _cell(cells, ci["lt_name"]), ln)
                r.cells = cells
                r.source, r.source_prop = _cell(cells, ci["lt_src"]), _cell(cells, ci["lt_srcp"])
                r.target, r.target_prop = _cell(cells, ci["lt_tgt"]), _cell(cells, ci["lt_tgtp"])
                r.direct = _cell(cells, ci["lt_direct"])
                # 여섯 칸이 모두 있고 방향을 읽을 수 있어야 옮긴다
                if (all((r.name, r.source, r.source_prop, r.target, r.target_prop, r.direct))
                        and _read_direct(r.direct)):
                    r.json, n = n, n + 1
                self.relations.append(r)

        for k, (i, title) in enumerate(entries["metaTypes"]):
            s, rows = self._block("데이터 구조", title, i)
            s.json = k      # 데이터 구조 블록도 모두 옮긴다
            ni, ti = _column(s.header, "mt_name"), _column(s.header, "mt_type")
            n = 0
            for ln, cells in rows:
                col = self._row(s, "컬럼", _cell(cells, ni), ln, cells)
                col.data_type = _cell(cells, ti)
                # 이름이 있고 데이터 타입이 7종 가운데 하나여야 옮긴다
                if col.name and col.data_type.upper() in DATA_TYPES:
                    col.json, n = n, n + 1
            self.structures.append(s)

        n_map = 0
        for i, title in entries["objectMapping"]:
            m, rows = self._block("매핑", title, i)
            parts = ARROW_RE.split(title)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                m.concept, m.structure = parts[0].strip(), parts[1].strip()
                m.name = "%s ← %s" % (m.concept, m.structure)
                # 개념 속성·데이터 컬럼 머리글이 없으면 앞 두 칸으로 읽는다
                oi, mi = _column(m.header, "om_otp"), _column(m.header, "om_mtp")
                if oi is None or mi is None:
                    oi, mi = 0, 1
                n = 0
                for ln, cells in rows:
                    r = self._row(m, "매핑 속성", _cell(cells, oi), ln, cells)
                    r.column = _cell(cells, mi)
                    if r.name and r.column:     # 한쪽이 빈 행은 옮기지 않는다
                        r.json, n = n, n + 1
                if n:       # 옮길 행이 하나라도 있어야 매핑을 옮긴다
                    m.json, n_map = n_map, n_map + 1
            else:
                # 제목이 '개념 ← 데이터 구조' 꼴이 아니면 변환 스크립트는 표를 읽지 않는다
                m.header, m.header_line = None, None
            self.mappings.append(m)

        self._heads = {e.line: e for e in self.concepts + self.structures + self.mappings}
        self._rows = {r.line: r for r in self.relations}
        for b in self.concepts + self.structures + self.mappings:
            for r in b.children:
                self._rows[r.line] = r

    def _block(self, kind, title, i):
        """i(0부터) 줄의 ### 블록. (블록 요소, 첫 표의 [(줄, 칸)]) 을 돌려준다."""
        b = Element(kind, title, i + 1)
        b.end = _block_end(self.lines, i + 1)
        b.table_lines = [(n + 1, self.lines[n].strip()) for n in range(i + 1, b.end)
                         if self.lines[n].strip().startswith("|")]
        b.header, b.header_line, rows = _read_table(self.lines[:b.end], i + 1)
        if kind != "매핑":
            b.desc, b.desc_line = _desc_bullet(self.lines, i + 1)
        return b, rows

    @staticmethod
    def _row(block, kind, name, line, cells):
        r = Element(kind, name, line, parent=block)
        r.cells = cells
        block.children.append(r)
        return r

    # ── 줄로 찾기
    def element_at(self, line):
        """line 을 품은 요소. 제목 줄, 표 행 줄, 블록 안의 줄 차례로 본다. 없으면 None."""
        if line in self._heads:
            return self._heads[line]
        if line in self._rows:
            return self._rows[line]
        inside = [b for b in self.concepts + self.structures + self.mappings
                  if b.line <= line <= b.end]
        return max(inside, key=lambda b: b.line) if inside else None

    def locate_line(self, line):
        """line 을 품은 요소의 위치를 그 줄로 적는다.

        요소를 특정할 수 없거나 이름 칸이 빈 행이면 '정의 문서 n줄' 이다.
        """
        if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(self.lines):
            raise ValueError("정의 문서에 없는 줄: %r (전체 %d줄)" % (line, len(self.lines)))
        el = self.element_at(line)
        return el.location(line) if el else location("정의 문서", line=line)

    def unread_tables(self):
        """변환 스크립트가 읽지 않는 표. [(줄, 경우, 블록 요소 또는 None)] 을 줄 차례로 준다.

        변환 스크립트는 개념·데이터 구조·매핑 블록마다 첫 표만 읽고, Link Type 은 첫 절의 첫 표만 읽는다.
        첫 표를 찾다가 제목 줄(#로 시작하는 줄)을 먼저 만나면 그 블록의 표를 하나도 읽지 않는다.
          '둘째 표'      블록의 첫 표 뒤의 표, Link Type 둘째 절부터의 표. 줄은 그 표의 머리글 줄이다
          '소제목 뒤 표'  블록 제목과 첫 표 사이에 제목 줄이 있어 읽지 않은 첫 표. 줄은 표 읽기를 멈춘
                         첫 제목 줄이다. 조치가 그 줄을 지우는 것이라 그 줄로 짚는다
        표는 이어진 표 줄 묶음 하나이고 표마다 많아야 한 번 나온다. 블록마다 '소제목 뒤 표'는 많아야 하나이고,
        첫 표 뒤의 표는 첫 표를 읽었든 못 읽었든 '둘째 표'다.
        Link Type 은 블록이 None 이다. 제목이 '개념 ← 데이터 구조' 꼴이 아닌 매핑은 변환 스크립트가
        블록째 버리고 표를 보지 않으므로 짚지 않는다.
        """
        out = []
        for b in self.concepts + self.structures + self.mappings:
            if b.kind == "매핑" and not b.concept:
                continue
            out += [(n, case, b) for n, case in self._unread(b.line, b.header_line, b.table_lines)]
        links = [(start, end) for key, _, start, end in self.sections if key == "linkTypes"]
        for k, (start, end) in enumerate(links):
            rows = [(n, self.lines[n - 1].strip()) for n in range(start + 1, end + 1)
                    if self.lines[n - 1].strip().startswith("|")]
            if k == 0:
                out += [(n, case, None) for n, case in self._unread(start, self.link_header_line, rows)]
            else:
                out += [(n, "둘째 표", None) for n in _table_starts(rows)]
        return sorted(out, key=lambda x: x[0])

    def _unread(self, heading, header_line, rows):
        """heading 줄의 블록(또는 절) 표 줄 rows 가운데 변환 스크립트가 읽지 않는 표. [(줄, 경우)]."""
        starts = _table_starts(rows)
        if not starts:
            return []
        if header_line is not None:     # 첫 표를 읽었다. 첫 표의 머리글 줄이 starts[0] 이다
            return [(n, "둘째 표") for n in starts[1:]]
        # 표가 있는데 읽지 않았으면 첫 표 앞에 제목 줄이 있다(_read_table 이 거기서 멈춘다)
        stop = next(n for n in range(heading + 1, starts[0]) if self.lines[n - 1].strip().startswith("#"))
        return [(stop, "소제목 뒤 표")] + [(n, "둘째 표") for n in starts[1:]]

    def desc_without_headings(self, block):
        """블록 제목과 첫 표 사이의 제목 줄(#)을 지웠을 때 변환 스크립트가 읽을 설명. (설명, 줄).

        DOC-11 소제목 뒤 표의 조치(소제목 줄을 지움)로 설명 줄까지 읽히게 되는지 볼 때 쓴다.
        """
        return _desc_bullet(self.lines[:block.end], block.line, past_headings=True)

    def title_rows(self, concept):
        """개념에서 변환 스크립트가 대표 표시 속성으로 읽는 속성 행. 첫 표를 읽지 않았으면 None.

        변환 스크립트처럼 첫 표만 보고, 머리글은 별칭(COL)으로, 칸 값은 참으로 읽는 값(TRUE_CELLS)으로 가린다.
        옮기지 않는 행(이름 칸이 빈 행)은 세지 않는다. 대표 표시 속성 칸이 없으면 빈 목록이다.
        """
        if concept.header_line is None:
            return None
        ti = _column(concept.header, "prop_title")
        if ti is None:
            return []
        return [p for p in concept.children if p.json is not None and _norm(_cell(p.cells, ti)) in TRUE_CELLS]

    def section_at(self, line):
        """line 이 든 서식 절의 JSON 키. 네 절 밖이면 None."""
        for key, _, start, end in self.sections:
            if start <= line <= end:
                return key
        return None

    # ── 규격 검사기 경로로 찾기
    def converted(self, key):
        """변환 스크립트가 JSON 의 key 배열로 옮기는 요소. 첨자 차례다."""
        pools = {"objectTypes": self.concepts, "linkTypes": self.relations,
                 "metaTypes": self.structures, "objectMapping": self.mappings}
        if key not in pools:
            raise PathError("모르는 배열: %s" % key)
        return [e for e in pools[key] if e.json is not None]

    def resolve(self, path, row_names=False):
        """규격 검사기의 경로가 가리키는 요소 목록.

        첨자 경로(objectTypes[2], .properties[3], linkTypes[1].direct 등)는 요소 하나,
        이름 경로([name=이름], objectMapping[개념, 데이터 구조], propertyMappings[속성])는
        같은 이름의 요소 모두를 돌려준다. 맨 앞 키만 있으면(metaTypes 등) 그 배열의 요소 모두다.
        .properties·.propertyMappings 뒤에 첨자가 없으면 그 윗 요소다.
        풀 수 없는 꼴이거나 첨자가 범위 밖이면 PathError.
        row_names 면 .properties·.propertyMappings 뒤의 괄호 안을 숫자여도 이름으로 읽는다. 규격 검사기가
        이름으로만 적는 코드(GOS61020)에 쓴다. 숫자만으로 된 속성 이름을 첨자로 잘못 읽지 않게 한다.
        """
        m = re.match(r"(%s)(?![A-Za-z])" % "|".join(TOP_KEYS), path or "")
        if not m:
            raise PathError("풀 수 없는 경로: %s" % path)
        key, rest = m.group(1), path[m.end():]
        items = self.converted(key)
        if rest == "":
            return list(items)
        m = re.match(r"\[(\d+)\]", rest)
        if not m:
            return self._by_name(path, key, items, rest)
        i = int(m.group(1))
        if i >= len(items):
            raise PathError("첨자가 범위 밖: %s (%s %d건)" % (path, key, len(items)))
        el, rest = items[i], rest[m.end():]
        sub = SUB_KEYS.get(key)
        if sub and rest.startswith("." + sub) and not re.match(r"\.%s\w" % sub, rest):
            rest = rest[len(sub) + 1:]
            if rest == "" or rest.startswith("[]"):
                return [el]
            rows = el.converted_children()
            m = None if row_names else re.fullmatch(r"\[(\d+)\](?:\.\w+)?", rest)
            if m:
                j = int(m.group(1))
                if j >= len(rows):
                    raise PathError("첨자가 범위 밖: %s (%s %d건)" % (path, sub, len(rows)))
                return [rows[j]]
            return self._by_name(path, sub, rows, rest)
        if rest == "" or re.fullmatch(r"\.\w+", rest):
            return [el]
        raise PathError("풀 수 없는 경로: %s" % path)

    @staticmethod
    def _by_name(path, key, items, rest):
        if not (rest.startswith("[") and rest.endswith("]")):
            raise PathError("풀 수 없는 경로: %s" % path)
        inner = rest[1:-1]
        if key == "objectMapping":
            concept, sep, structure = inner.partition(", ")
            if sep:
                return [e for e in items if e.concept == concept and e.structure == structure]
        elif key == "propertyMappings":
            return [e for e in items if e.name == inner]
        elif inner.startswith("name="):
            return [e for e in items if e.name == inner[len("name="):]]
        raise PathError("풀 수 없는 경로: %s" % path)

    def unmapped_concepts(self):
        """변환 뒤 데이터가 붙지 않는 개념(규격 검사기 GOS61017 이 이름으로 묶어 내는 것)."""
        mapped = {m.concept for m in self.converted("objectMapping")}
        return [c for c in self.concepts if c.name not in mapped]

    def mismatches(self, document):
        """변환 스크립트 --json 출력의 document 와 이 색인을 맞대 본다.

        어긋난 곳을 문장 목록으로 돌려준다. 비어 있으면 같은 첨자가 같은 요소를 가리킨다.
        어긋나면 변환 스크립트의 읽기 규칙이 바뀐 것이므로 첨자 경로를 줄로 바꾸지 않는다.
        """
        doc = document if isinstance(document, dict) else {}
        out = []
        for key in TOP_KEYS:
            theirs, mine = doc.get(key) or [], self.converted(key)
            if len(theirs) != len(mine):
                out.append("%s 건수가 다름(변환 %d건, 색인 %d건)" % (key, len(theirs), len(mine)))
                continue
            sub = SUB_KEYS.get(key)
            for i, (obj, el) in enumerate(zip(theirs, mine)):
                if not _same(key, obj, el):
                    out.append("%s[%d] 이 가리키는 요소가 다름(정의 문서 %d줄)" % (key, i, el.line))
                    continue
                if not sub:
                    continue
                rows = obj.get(sub) or []
                own = el.converted_children()
                if len(rows) != len(own) or not all(_same(sub, a, b) for a, b in zip(rows, own)):
                    out.append("%s[%d].%s 가 가리키는 행이 다름(정의 문서 %d줄)"
                               % (key, i, sub, el.line))
                # 설명을 읽는 규칙(자리·머리)이 바뀌면 DOC-05 '읽히지 않는 설명' 이 틀리므로 설명도 맞대 본다
                if key in ("objectTypes", "metaTypes") and obj.get("description") != (el.desc or None):
                    out.append("%s[%d] 의 설명이 다름(정의 문서 %d줄)" % (key, i, el.line))
        return out

    # ── 이름으로 찾기 (같은 이름이 여럿이면 모두)
    def find_concepts(self, name):
        return [c for c in self.concepts if c.name == name]

    def find_properties(self, concept, name):
        return [p for c in self.find_concepts(concept) for p in c.children if p.name == name]

    def find_relations(self, name=None, source=None, target=None):
        """조건을 준 칸만 맞대 본다. 이름 없이 양끝만 주면 두 개념 사이의 관계 모두다."""
        return [r for r in self.relations
                if (name is None or r.name == name)
                and (source is None or r.source == source)
                and (target is None or r.target == target)]

    def find_structures(self, name):
        return [s for s in self.structures if s.name == name]

    def find_columns(self, structure, name):
        return [c for s in self.find_structures(structure) for c in s.children if c.name == name]

    def find_mappings(self, concept=None, structure=None):
        return [m for m in self.mappings if m.concept is not None
                and (concept is None or m.concept == concept)
                and (structure is None or m.structure == structure)]

    def find_mapping_rows(self, concept, structure, name):
        return [r for m in self.find_mappings(concept, structure) for r in m.children
                if r.name == name]
