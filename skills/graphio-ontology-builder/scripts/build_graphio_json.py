#!/usr/bin/env python3
"""온톨로지 정의 서식(.md)을 graphio JSON 으로 옮긴다.

표준 라이브러리만 쓴다. 판단하지 않는다 — 서식이 적은 것만 옮기고, 문서가 적지 않은
칸은 만들지 않는다. 규격이 요구하는데 문서에 없는 칸은 정해진 규칙으로 채우고 그 사실을
알린다. 규격을 어기는 자리는 고치지 않고 어느 줄인지 짚어 알린다.

    python3 build_graphio_json.py 정의.md -o 산출물.json
    python3 build_graphio_json.py 정의.md -o 산출물.json --json   # 결과를 JSON 으로

종료 코드: 0 문서 오류 없음, 1 문서 오류 있음, 2 파일을 읽지 못함.
"""

import argparse
import colorsys
import io
import json
import os
import re
import sys

DATA_TYPES = ("INTEGER", "TEXT", "DATETIME", "FLOAT8", "BOOLEAN", "VECTOR", "UNKNOWN")
DIRECTS = ("UNIDIRECTIONAL", "REVERSE_DIRECTIONAL", "BIDIRECTIONAL")
# 방향 칸에 규격 이름 대신 적어도 되는 표기. 뜻을 정해 주는 것이 아니라
# 문서가 이미 적은 방향을 규격 이름으로 옮기는 것뿐이다.
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
META_KINDS = ("CUSTOM", "PARSING", "DOC_TYPE")

NAME_RE = re.compile(r"^[a-zA-Z가-힣][a-zA-Z0-9가-힣_]{0,49}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ARROW_RE = re.compile(r"\s*(?:←|<-{1,2}|<=)\s*")

# 규격이 colorCode 를 필수로 요구하지만 문서가 적지 않을 수 있다. 문서에 나온 순서대로
# 준다. 색에는 뜻이 없고, 서로 겹치지 않는다.
#
# 앞 12개는 색상환을 30도 안팎으로 고르게 나눈 값이다. 처음 둘은 규격서 예시 값과 같다.
# 13번째부터는 황금각(137.508도)으로 색상을 돌리고 밝기를 번갈아 주어 만든다. 이미 쓴 색과
# 같은 값이 나오면 다음 각도로 넘어가므로 몇 개가 되어도 겹치지 않는다.
PALETTE_HEAD = [
    "#4A90D9", "#F5A623", "#36A186", "#B855CE",
    "#6FA136", "#E25A6F", "#746CD0", "#358D41",
    "#CF59A8", "#D85B31", "#2B8DA1", "#7B4EBC",
]
BASE_HUE = 211.0
GOLDEN_ANGLE = 137.508


def hex_of(hue, sat, light):
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, light / 100.0, sat / 100.0)
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def next_color(index, used):
    """문서에 나온 순서대로 색 하나를 돌려준다. used 에 있는 색은 주지 않는다."""
    if index < len(PALETTE_HEAD) and PALETTE_HEAD[index] not in used:
        return PALETTE_HEAD[index]
    step = max(index - len(PALETTE_HEAD), 0)
    for _ in range(1000):
        hue = (BASE_HUE + GOLDEN_ANGLE * (step + 1)) % 360
        sat, light = (58, 46) if step % 2 == 0 else (52, 62)
        candidate = hex_of(hue, sat, light)
        if candidate not in used:
            return candidate
        step += 1
    return "#4A90D9"

TRUE_CELLS = {"o", "y", "yes", "true", "v", "✓", "✔", "예", "○", "●"}
FALSE_CELLS = {"", "-", "n", "no", "false", "아니오", "아니요", "아님", "부",
               "x", "×", "✕", "✗"}
# 숫자 0 은 영문 O 의 오타일 수도 있고 "없음"의 뜻일 수도 있다. 문서가 정할 일이라 알린다.
AMBIGUOUS_CELLS = {"0"}

SECTIONS = {
    "objecttype": "objectTypes", "오브젝트타입": "objectTypes",
    "linktype": "linkTypes", "링크타입": "linkTypes",
    "metatype": "metaTypes", "메타타입": "metaTypes",
    "objectmapping": "objectMapping", "오브젝트매핑": "objectMapping",
}

# 표 머리글 별칭. 서식이 한글로 적히지만 영문 머리글도 받는다.
COL = {
    "prop_name": ("속성", "속성명", "property", "name", "이름"),
    "prop_type": ("데이터타입", "타입", "datatype", "type"),
    "prop_desc": ("설명", "description", "desc"),
    "prop_pk": ("pk", "primarykey", "식별", "식별속성"),
    "prop_title": ("title", "titlekey", "대표", "대표표시"),
    "lt_name": ("관계이름", "이름", "name", "관계"),
    "lt_src": ("source", "소스", "시작"),
    "lt_srcp": ("source속성", "소스속성", "sourceproperty", "시작속성"),
    "lt_tgt": ("target", "타깃", "타겟", "도착"),
    "lt_tgtp": ("target속성", "타깃속성", "타겟속성", "targetproperty", "도착속성"),
    "lt_direct": ("방향", "direct"),
    "lt_desc": ("설명", "description"),
    "mt_name": ("컬럼", "컬럼명", "column", "name", "이름"),
    "mt_type": ("데이터타입", "타입", "datatype", "type"),
    "mt_raw": ("원천컬럼명", "원천컬럼", "rawdatapropertyname", "raw"),
    "mt_desc": ("설명", "description"),
    "om_otp": ("objecttype속성", "개념속성", "objecttypepropertyname"),
    "om_mtp": ("metatype컬럼", "데이터컬럼", "metatypepropertyname"),
}

BULLET = {
    "desc": ("설명", "description"),
    "color": ("색", "색상", "colorcode", "color"),
    "public": ("공개", "공개여부", "ispublic"),
    "kind": ("종류", "metatypekind", "kind"),
}


def norm(text):
    return re.sub(r"[\s\-_·.]", "", (text or "")).lower()


class Findings:
    def __init__(self):
        self.items = []

    def error(self, where, message, fix=None):
        self.items.append({"level": "error", "where": where, "message": message, "fix": fix})

    def filled(self, where, message):
        self.items.append({"level": "filled", "where": where, "message": message, "fix": None})

    def count(self, level):
        return sum(1 for f in self.items if f["level"] == level)


# ------------------------------------------------------------------ 표 읽기

def is_separator(row):
    return bool(row) and all(re.fullmatch(r":?-{1,}:?", c.strip() or "-") for c in row)


def split_row(line):
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [c.strip() for c in body.split("|")]


def read_table(lines, start):
    """start 줄부터 표 하나를 읽는다. (머리글, 데이터행, 다음 줄번호) 를 돌려준다."""
    i = start
    while i < len(lines) and not lines[i].strip().startswith("|"):
        if lines[i].strip().startswith("#"):
            return None, [], i
        i += 1
    if i >= len(lines):
        return None, [], i
    header = split_row(lines[i])
    i += 1
    if i < len(lines) and lines[i].strip().startswith("|") and is_separator(split_row(lines[i])):
        i += 1
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = split_row(lines[i])
        if not is_separator(cells) and any(c for c in cells):
            rows.append((i + 1, cells))
        i += 1
    return header, rows, i


def column_index(header, keys):
    """머리글에서 별칭에 맞는 칸 번호를 찾는다. 없으면 None."""
    wanted = {norm(k) for k in keys}
    for idx, cell in enumerate(header or []):
        if norm(cell) in wanted:
            return idx
    return None


def cell(cells, idx):
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def read_flag(value, where, column, find):
    v = norm(value)
    if v in TRUE_CELLS:
        return True
    if v in FALSE_CELLS:
        return False
    if v in AMBIGUOUS_CELLS:
        find.error(where, "%s 칸의 값 %r 이 영문 O 인지 숫자 0 인지 가릴 수 없다." % (column, value),
                   "표시하려면 O, 비우려면 빈칸으로 둔다.")
        return False
    find.error(where, "%s 칸의 값 %r 을 참·거짓으로 읽을 수 없다." % (column, value),
               "표시하려면 O, 비우려면 빈칸으로 둔다.")
    return False


def read_direct(value):
    """방향 칸을 규격의 direct 값으로 옮긴다. 읽을 수 없으면 None 을 준다."""
    raw = (value or "").strip()
    long_name = raw.upper().replace("-", "_")
    if long_name in DIRECTS:
        return long_name
    return DIRECT_ALIASES.get(re.sub(r"\s", "", raw))


def read_bullets(lines, start):
    """### 제목 아래의 '- 키: 값' 줄을 모은다."""
    out, i = {}, start
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("#") or s.startswith("|"):
            break
        m = re.match(r"^[-*]\s*([^:：]+)[:：]\s*(.*)$", s)
        if m:
            key, value = norm(m.group(1)), m.group(2).strip()
            for canon, aliases in BULLET.items():
                if key in {norm(a) for a in aliases}:
                    out[canon] = value
        i += 1
    return out


# --------------------------------------------------------------- 문서 나누기

def split_sections(lines, find):
    """## 절과 그 안의 ### 항목으로 나눈다."""
    sections, current = {}, None
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m:
            key = SECTIONS.get(norm(m.group(1)))
            current = key
            if key and key not in sections:
                sections[key] = []
            continue
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and current:
            sections[current].append({"title": m.group(1).strip(), "line": i + 1, "start": i + 1})
    return sections


def section_bounds(lines, start):
    """### 항목 하나가 끝나는 줄을 찾는다."""
    i = start
    while i < len(lines) and not re.match(r"^#{2,3}\s+(?!#)", lines[i]):
        i += 1
    return i


# ------------------------------------------------------------------- 옮기기

def build_object_types(lines, entries, find):
    out = []
    used_colors = {c for c in (read_bullets(lines, e["start"]).get("color", "") for e in entries)
                   if COLOR_RE.match(c or "")}
    for entry in entries:
        name, where = entry["title"], "%d줄 (### %s)" % (entry["line"], entry["title"])
        end = section_bounds(lines, entry["start"])
        body = lines[:end]
        bullets = read_bullets(lines, entry["start"])
        header, rows, _ = read_table(body, entry["start"])

        if not NAME_RE.match(name):
            find.error(where, "Object Type 이름 %r 이 규격 형식을 어긴다." % name,
                       "영문·한글로 시작하고 영문·숫자·한글·밑줄만, 50자까지. 문서에서 고친다.")

        ot = {"name": name}
        if bullets.get("desc"):
            ot["description"] = bullets["desc"]

        color = bullets.get("color", "")
        if color:
            if COLOR_RE.match(color):
                ot["colorCode"] = color
            else:
                find.error(where, "색 %r 이 #RRGGBB 꼴이 아니다." % color, "문서에서 고친다.")
                ot["colorCode"] = next_color(len(out), used_colors)
                used_colors.add(ot["colorCode"])
        else:
            ot["colorCode"] = next_color(len(out), used_colors)
            used_colors.add(ot["colorCode"])
            find.filled(where, "문서에 색이 없어 규격 필수값을 채웠다 (%s). 뜻은 없고 다른 색과 겹치지 않는다."
                        % ot["colorCode"])

        if bullets.get("public"):
            ot["isPublic"] = read_flag(bullets["public"], where, "공개", find)

        if not rows:
            find.error(where, "속성 표가 없다. 규격이 속성을 1건 이상 요구한다.",
                       "속성 표를 문서에 적는다.")
            ot["properties"] = []
            out.append(ot)
            continue

        ci = {k: column_index(header, COL[k]) for k in
              ("prop_name", "prop_type", "prop_desc", "prop_pk", "prop_title")}
        if ci["prop_name"] is None or ci["prop_type"] is None:
            find.error(where, "속성 표에 '속성' 또는 '데이터 타입' 머리글이 없다.",
                       "서식의 표 머리글을 그대로 쓴다.")

        props = []
        for lineno, cells in rows:
            rwhere = "%d줄" % lineno
            pname = cell(cells, ci["prop_name"])
            if not pname:
                find.error(rwhere, "속성 이름이 비어 있다.", "문서에서 채운다.")
                continue
            dtype = cell(cells, ci["prop_type"]).upper()
            if dtype not in DATA_TYPES:
                find.error(rwhere, "%s 의 데이터 타입 %r 이 7종에 없다." % (pname, dtype or ""),
                           "INTEGER·TEXT·DATETIME·FLOAT8·BOOLEAN·VECTOR·UNKNOWN 중에서 문서에 적는다.")
                dtype = None
            # 키 순서를 규격서 예시와 맞춘다 — 반출물과 나란히 놓고 볼 수 있게.
            prop = {"name": pname}
            if dtype:
                prop["dataType"] = dtype
            prop["orderNo"] = len(props) + 1
            pdesc = cell(cells, ci["prop_desc"])
            if pdesc:
                prop["description"] = pdesc
            prop["isTitleKey"] = read_flag(cell(cells, ci["prop_title"]), rwhere, "Title", find) \
                if ci["prop_title"] is not None else False
            prop["isPrimaryKey"] = read_flag(cell(cells, ci["prop_pk"]), rwhere, "PK", find) \
                if ci["prop_pk"] is not None else False
            props.append(prop)

        ot["properties"] = props
        out.append(ot)
    return out


def build_link_types(lines, sections, find):
    """Link Type 절의 표 하나를 읽는다."""
    out = []
    start = None
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m and SECTIONS.get(norm(m.group(1))) == "linkTypes":
            start = i + 1
            break
    if start is None:
        return out
    header, rows, _ = read_table(lines, start)
    if not rows:
        return out

    ci = {k: column_index(header, COL[k]) for k in
          ("lt_name", "lt_src", "lt_srcp", "lt_tgt", "lt_tgtp", "lt_direct", "lt_desc")}
    for lineno, cells in rows:
        where = "%d줄" % lineno
        name = cell(cells, ci["lt_name"])
        src, srcp = cell(cells, ci["lt_src"]), cell(cells, ci["lt_srcp"])
        tgt, tgtp = cell(cells, ci["lt_tgt"]), cell(cells, ci["lt_tgtp"])
        direct_raw = cell(cells, ci["lt_direct"])

        missing = [label for label, value in
                   (("관계 이름", name), ("source", src), ("source 속성", srcp),
                    ("target", tgt), ("target 속성", tgtp), ("방향", direct_raw)) if not value]
        if missing:
            find.error(where, "%s 칸이 비어 있어 이 관계를 만들 수 없다." % ", ".join(missing),
                       "문서에서 채운다. 규격이 관계에 양쪽 조인 속성과 방향을 요구한다.")
            continue
        direct = read_direct(direct_raw)
        if direct is None:
            find.error(where, "방향 %r 을 3종 중 하나로 읽을 수 없다." % direct_raw,
                       "UNIDIRECTIONAL(→·단방향) · REVERSE_DIRECTIONAL(←·역방향) · "
                       "BIDIRECTIONAL(↔·양방향) 중에서 문서에 적는다.")
            continue

        lt = {"name": name, "sourceObjectTypeName": src, "sourcePropertyName": srcp,
              "targetObjectTypeName": tgt, "targetPropertyName": tgtp, "direct": direct}
        desc = cell(cells, ci["lt_desc"])
        if desc:
            lt["description"] = desc
        out.append(lt)
    return out


def build_meta_types(lines, entries, find):
    out = []
    for entry in entries:
        name, where = entry["title"], "%d줄 (### %s)" % (entry["line"], entry["title"])
        end = section_bounds(lines, entry["start"])
        bullets = read_bullets(lines, entry["start"])
        header, rows, _ = read_table(lines[:end], entry["start"])

        mt = {"name": name}
        if bullets.get("desc"):
            mt["description"] = bullets["desc"]
        kind = (bullets.get("kind") or "").upper()
        if kind:
            if kind in META_KINDS:
                mt["metaTypeKind"] = kind
            else:
                find.error(where, "종류 %r 이 3종에 없다." % kind,
                           "CUSTOM·PARSING·DOC_TYPE 중에서 문서에 적는다.")

        props = []
        if rows:
            ci = {k: column_index(header, COL[k]) for k in
                  ("mt_name", "mt_type", "mt_raw", "mt_desc")}
            for lineno, cells in rows:
                cname = cell(cells, ci["mt_name"])
                if not cname:
                    find.error("%d줄" % lineno, "컬럼 이름이 비어 있다.", "문서에서 채운다.")
                    continue
                ctype = cell(cells, ci["mt_type"]).upper()
                if ctype not in DATA_TYPES:
                    find.error("%d줄" % lineno,
                               "%s 의 데이터 타입 %r 이 7종에 없다." % (cname, ctype or ""),
                               "7종 중에서 문서에 적는다.")
                    continue
                prop = {"name": cname, "dataType": ctype}
                raw = cell(cells, ci["mt_raw"])
                if raw:
                    prop["rawDataPropertyName"] = raw
                cdesc = cell(cells, ci["mt_desc"])
                if cdesc:
                    prop["description"] = cdesc
                props.append(prop)
        if props:
            mt["properties"] = props
        out.append(mt)
    return out


def build_object_mapping(lines, entries, find):
    out = []
    for entry in entries:
        title, where = entry["title"], "%d줄 (### %s)" % (entry["line"], entry["title"])
        parts = ARROW_RE.split(title)
        if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
            find.error(where, "제목이 'Object Type 이름 ← Meta Type 이름' 꼴이 아니다.",
                       "서식대로 화살표로 두 이름을 잇는다.")
            continue
        ot_name, mt_name = parts[0].strip(), parts[1].strip()
        end = section_bounds(lines, entry["start"])
        header, rows, _ = read_table(lines[:end], entry["start"])
        if not rows:
            find.error(where, "속성 매핑 표가 없어 이 연결을 만들 수 없다.",
                       "규격이 속성 매핑을 1건 이상 요구한다. 문서에 표를 적는다.")
            continue

        ci = {"otp": column_index(header, COL["om_otp"]), "mtp": column_index(header, COL["om_mtp"])}
        if ci["otp"] is None or ci["mtp"] is None:
            ci["otp"], ci["mtp"] = 0, 1
        pms = []
        for lineno, cells in rows:
            a, b = cell(cells, ci["otp"]), cell(cells, ci["mtp"])
            if not a or not b:
                find.error("%d줄" % lineno, "속성 매핑의 한쪽이 비어 있다.", "문서에서 채운다.")
                continue
            pms.append({"objectTypePropertyName": a, "metaTypePropertyName": b})
        if pms:
            out.append({"objectTypeName": ot_name, "metaTypeName": mt_name,
                        "propertyMappings": pms})
    return out


# --------------------------------------------------------------------- 출력

def render(doc, find, md_path, out_path):
    lines = ["온톨로지 정의 서식 옮기기 — %s" % md_path, ""]
    lines.append("  Object Type %d개 · Link Type %d개 · Meta Type %d개 · Object Mapping %d개"
                 % (len(doc["objectTypes"]), len(doc["linkTypes"]),
                    len(doc["metaTypes"]), len(doc["objectMapping"])))
    lines.append("")

    errors = [f for f in find.items if f["level"] == "error"]
    filled = [f for f in find.items if f["level"] == "filled"]

    if errors:
        lines.append("문서 오류 %d건 — 문서를 고쳐야 한다" % len(errors))
        for f in errors:
            lines.append("  %s  %s" % (f["where"], f["message"]))
            if f["fix"]:
                lines.append("      → %s" % f["fix"])
        lines.append("")
    if filled:
        lines.append("규격 필수값을 채운 곳 %d건 — 리포트에 적는다" % len(filled))
        for f in filled:
            lines.append("  %s  %s" % (f["where"], f["message"]))
        lines.append("")

    if out_path:
        lines.append("파일을 썼다: %s" % out_path)
    if errors:
        lines.append("결과: 문서 오류 %d건. 문서를 고친 뒤 다시 돌린다." % len(errors))
    else:
        lines.append("결과: 문서 오류 없음. 이어서 validate_graphio_json.py 로 규격을 확인한다.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="온톨로지 정의 서식(.md)을 graphio JSON 으로 옮긴다.")
    ap.add_argument("md", help="온톨로지 정의 서식 파일 (.md)")
    ap.add_argument("-o", "--out", help="쓸 graphio JSON 경로")
    ap.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON 으로 낸다")
    args = ap.parse_args()

    try:
        text = io.open(args.md, encoding="utf-8").read()
    except FileNotFoundError:
        print("파일을 찾을 수 없다: %s" % args.md, file=sys.stderr)
        return 2
    lines = text.splitlines()

    find = Findings()
    sections = split_sections(lines, find)
    if "objectTypes" not in sections:
        find.error("문서 전체", "'## Object Type' 절이 없다. 서식이 아닌 문서로 보인다.",
                   "assets 의 서식을 받아 문서를 그 꼴로 적는다.")

    doc = {
        "objectTypes": build_object_types(lines, sections.get("objectTypes", []), find),
        "linkTypes": build_link_types(lines, sections, find),
        "metaTypes": build_meta_types(lines, sections.get("metaTypes", []), find),
        "objectMapping": build_object_mapping(lines, sections.get("objectMapping", []), find),
    }

    out_path = args.out
    if out_path and not find.count("error"):
        d = os.path.dirname(os.path.abspath(out_path))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        io.open(out_path, "w", encoding="utf-8").write(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    elif out_path:
        out_path = None

    if args.as_json:
        print(json.dumps({"source": args.md, "out": out_path,
                          "counts": {k: len(v) for k, v in doc.items()},
                          "findings": find.items, "document": doc},
                         ensure_ascii=False, indent=2))
    else:
        print(render(doc, find, args.md, out_path))

    return 1 if find.count("error") else 0


if __name__ == "__main__":
    sys.exit(main())
