#!/usr/bin/env python3
"""온톨로지 정의 문서에서 '오류 없이 사라지는 것'을 찾는다.

변환 스크립트는 서식 오류를 잡는다. 이 스크립트는 서식은 맞는데
내용이 새어 나가는 자리를 잡는다 — 오류가 나지 않아 아무도 모르는 것들이다.

    python3 check_design_doc.py <온톨로지-정의.md>

경고 기호가 가이드마다 다르므로 필요하면 지정한다.

    python3 check_design_doc.py <문서.md> --warn-mark ※

원천 구조 문서를 주면 데이터 구조 이름이 거기 있는지 대조한다. 하나라도 UTF-8 텍스트로
읽지 못하면 대조하지 않고 멈춘다. 읽지 못한 파일이 빠진 채 대조하면 그 파일에만 있는
이름이 모두 경고로 올라가기 때문이다.

    python3 check_design_doc.py <문서.md> --source <원천 구조 문서> [...]

지적마다 규칙 번호(DOC-01~09, DOC-11)를 붙인다. 규칙의 이름과 등급은 references/검사-규칙.md 에 있다.
'확인 필요' 표기(DOC-10)는 건수만 세는 규칙이라 지적으로 내지 않고 --stats 통계로 낸다.
지적은 규칙 번호, 줄 번호, 발췌 차례로 낸다. 같은 입력이면 늘 같은 출력이다.

--json 이면 지적마다 아래 칸을 낸다. 수집 스크립트가 읽는다(판정 스크립트는 수집 스크립트를 거쳐 쓴다).

    규칙      DOC-01~09, DOC-11
    경우      한 규칙 안에서 문제 설명·조치가 갈리는 경우. DOC-04 는 '0건'·'2건 이상',
              DOC-05 는 ''(설명 줄 없음)·'읽히지 않는 설명', DOC-11 은 '둘째 표'·'소제목 뒤 표', 나머지는 ''
    위치      요소 이름과 줄 번호로 적은 위치. 꼴은 definition_index.py 의 FORMS
    줄        위치에 적은 줄 번호. 요소의 제목 줄이고, 줄 단위 규칙(DOC-01~03, DOC-11)과
              DOC-05 '읽히지 않는 설명'은 문제가 된 줄 자체다
    발췌      문제를 보이는 원문 조각. 발생 경로로 쓴다. 발췌 줄은 그 조각이 있는 줄이다
    등급·자리·무엇·어떻게·종류   앞 판의 칸. 앞 판과 맞추려고 한동안 둔다. 등급 값도 앞 판의 오류·경고·확인이다.
              스킬 스크립트는 이 칸들을 읽지 않는다. 등급은 규칙 번호로 references/검사-규칙.md 에서 찾는다

문서를 읽지 못하면 --json 은 {"읽힘": false, "까닭", "문서", "경로", "문제"} 를 낸다.
문서는 '정의 문서'·'원천 구조 문서', 문제는 '파일 없음'·'UTF-8로 읽을 수 없음'·'읽기 실패'·'개념 없음'
가운데 하나다.

종료 코드: 0 Error 없음, 1 Error 있음, 2 문서를 읽지 못함(개념을 찾지 못한 경우 포함).
"""
import argparse
import json
import re
import sys

import definition_index as di

# 설명 줄이 잘렸는지 알아보는 표지. 대괄호로 시작하는 줄은 대개
# [SQL]·[별칭]·[출처] 같은 구획 표지라 설명 줄에 붙어 있어야 한다.
STRANDED = re.compile(r"^(\[|FK\s*JOIN|SQL\s*:)")
# 표에서 "그렇다"로 읽는 값. 가이드마다 표기가 달라 흔한 것을 모아 둔다.
TRUE_VALS = ("O", "예", "Y", "YES", "TRUE", "V", "✓", "✔", "○", "●")
JOSA = re.compile(r"[가-힣]\s*(이\(가\)|은\(는\)|을\(를\)|과\(와\)|와\(과\))")
# 서식 네 절의 제목. 제목은 공백·하이픈·밑줄·가운뎃점·마침표를 지우고 소문자로 맞춰 읽는다.
FOUR_SECTIONS = {"objecttype", "오브젝트타입", "linktype", "링크타입",
                 "metatype", "메타타입", "objectmapping", "오브젝트매핑"}
# 경고문에서 상대 개념을 뽑는 꼴: "A 가 아니라 B 를 써야 한다"
PAIR = re.compile(r"아니라\s*(\S+?)\s*(?:을|를)\s*(?:써야|사용)")
# 데이터 구조 설명에 대상 환경에 아직 없다고 적은 표지
ABSENT = re.compile(r"(아직\s*(없|등록되지)|존재하지\s*않|전처리가\s*(필요|선행)|만들어야|생성해야)")
EXCERPT = 60    # 발췌 길이(글자). 넘치면 줄이고 … 를 붙인다


def read_blocks(lines):
    """Object Type 절의 개념 블록을 모은다."""
    blocks, cur, in_ot = [], None, False
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m:
            key = re.sub(r"[\s_.\-·]", "", m.group(1)).lower()
            in_ot = key in ("objecttype", "오브젝트타입")
            if cur:
                blocks.append(cur)
                cur = None
            continue
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and in_ot:
            if cur:
                blocks.append(cur)
            cur = {"name": m.group(1).strip(), "line": i + 1,
                   "desc": None, "desc_line": None, "after": [], "rows": []}
            continue
        if cur is None:
            continue
        s = line.strip()
        if s.startswith("|"):
            cur["rows"].append((i + 1, s))
        elif re.match(r"^[-*]\s*(설명|description|desc)\s*[:：]", s, re.I):
            cur["desc"] = re.sub(r"^[-*]\s*[^:：]+[:：]\s*", "", s)
            cur["desc_line"] = i + 1
        elif s and cur["desc"] is not None and not s.startswith("#"):
            cur["after"].append((i + 1, s))
    if cur:
        blocks.append(cur)
    return blocks


def meta_types(lines):
    """Meta Type 절의 (이름, 줄번호, 설명, 설명 줄번호) 를 모은다."""
    out, sec, cur = [], None, None
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m:
            key = re.sub(r"[\s_.\-·]", "", m.group(1)).lower()
            sec = key in ("metatype", "메타타입")
            cur = None
            continue
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m and sec:
            cur = [m.group(1).strip(), i + 1, "", None]
            out.append(cur)
            continue
        if cur is not None:
            m = re.match(r"^[-*]\s*(설명|description|desc)\s*[:：]\s*(.*)$", line.strip(), re.I)
            if m:
                cur[2], cur[3] = m.group(2).strip(), i + 1
    return [tuple(x) for x in out]


def section_items(lines, names):
    """절 안의 ### 제목과 표 데이터 행을 센다. (제목 목록, 표 행 수) 를 돌려준다."""
    titles, rows, inside = [], 0, False
    for raw in lines:
        line = raw.rstrip()
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", line)
        if m:
            inside = re.sub(r"[\s_.\-·]", "", m.group(1)).lower() in names
            continue
        if not inside:
            continue
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            titles.append(m.group(1).strip())
            continue
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
                continue
            head = cells[0].lower() if cells else ""
            if head in ("관계 이름", "이름", "관계", "name", "object type 속성", "개념 속성",
                        "objecttypepropertyname", "속성", "컬럼", "속성명", "컬럼명"):
                continue
            if any(cells):
                rows += 1
    return titles, rows


def tables_of(rows):
    """블록의 표 줄 [(줄번호, 원문)] 을 이어진 묶음(표 하나)마다 나눈다."""
    out = []
    for ln, row in rows:
        if out and out[-1][-1][0] == ln - 1:
            out[-1].append((ln, row))
        else:
            out.append([(ln, row)])
    return out


def four_sections(lines):
    """서식 네 절 안의 줄만 이어 붙인다. 규모 표나 서식 밖 절은 뺀다."""
    out, inside = [], False
    for raw in lines:
        m = re.match(r"^##\s+(?!#)(.+?)\s*$", raw)
        if m:
            inside = re.sub(r"[\s_.\-·]", "", m.group(1)).lower() in FOUR_SECTIONS
            continue
        if inside:
            out.append(raw)
    return "\n".join(out)


def collect_stats(lines, blocks):
    """사람이 한눈에 볼 통계를 모은다."""
    _, link_rows = section_items(lines, {"linktype", "링크타입"})
    map_titles, map_rows = section_items(lines, {"objectmapping", "오브젝트매핑"})
    metas = meta_types(lines)

    props, types, pk_ok, title_bad = 0, {}, 0, 0
    for b in blocks:
        if not b["rows"]:
            continue
        header = [c.strip().lower() for c in b["rows"][0][1].strip("|").split("|")]
        ti = next((i for i, h in enumerate(header)
                   if h in ("title", "title key", "대표", "대표 표시")), None)
        pi = next((i for i, h in enumerate(header)
                   if h in ("pk", "primary key", "식별", "식별 속성")), None)
        di = next((i for i, h in enumerate(header)
                   if h in ("데이터 타입", "타입", "datatype", "type")), None)
        n_title, n_pk = 0, 0
        for _, row in b["rows"][1:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", c or "-") for c in cells) or not any(cells):
                continue
            props += 1
            if di is not None and di < len(cells) and cells[di]:
                types[cells[di].upper()] = types.get(cells[di].upper(), 0) + 1
            if ti is not None and ti < len(cells) and cells[ti].upper() in TRUE_VALS:
                n_title += 1
            if pi is not None and pi < len(cells) and cells[pi].upper() in TRUE_VALS:
                n_pk += 1
        if n_pk:
            pk_ok += 1
        if n_title != 1:
            title_bad += 1

    mapped = {t.split("←")[0].strip() for t in map_titles if "←" in t}
    unmapped = [b["name"] for b in blocks if b["name"] not in mapped]

    return {
        "개념": len(blocks),
        "속성": props,
        "관계": link_rows,
        "데이터 구조": len(metas),
        "매핑": len(map_titles),
        "매핑 줄": map_rows,
        "식별 속성이 있는 개념": "%d / %d" % (pk_ok, len(blocks)),
        "대표 표시 속성이 1건이 아닌 개념": title_bad,
        "데이터가 붙지 않은 개념": len(unmapped),
        "미확정 개념": ", ".join(unmapped) if unmapped else "없음",
        # 네 절 안만 센다. 규모 표나 서식 밖 절이 "확인 필요"를 말해도 남은 표기가 아니다.
        "확인 필요 표기": len(re.findall(r"확인\s*필요", four_sections(lines))),
        "자료형": " · ".join("%s %d" % (k, v) for k, v in sorted(types.items(), key=lambda x: -x[1])),
    }


def report_value(key, value):
    """통계 값을 리포트 표기로 바꾼다. JSON 으로 내는 값은 숫자 그대로 둔다."""
    if isinstance(value, int):
        return "%d건" % value
    m = re.fullmatch(r"(\d+) / (\d+)", str(value))
    if m:
        return "%s건 중 %s건" % (m.group(2), m.group(1))
    if key == "자료형":
        return re.sub(r"(\S+) (\d+)", r"\1 \2건", str(value)) or "해당 없음"
    return value


def print_stats(st, as_markdown):
    keys = ["개념", "속성", "관계", "데이터 구조", "매핑",
            "식별 속성이 있는 개념", "대표 표시 속성이 1건이 아닌 개념",
            "데이터가 붙지 않은 개념", "확인 필요 표기", "자료형"]
    if as_markdown:
        # 리포트에 그대로 붙는 표다. 리포트 작성 규칙대로 단위는 '건', 비율은 'n건 중 n건' 꼴로 낸다.
        print("| 항목 | 값 |")
        print("|---|---|")
        for k in keys:
            print("| %s | %s |" % (k, report_value(k, st[k])))
        if st["데이터가 붙지 않은 개념"]:
            print("| 데이터가 붙지 않은 개념 목록 | %s |" % st["미확정 개념"])
    else:
        for k in keys:
            print("  %-22s %s" % (k, st[k]))


def clip(text):
    """원문을 앞에서부터 EXCERPT 자까지 남긴다."""
    text = text.strip()
    return text if len(text) <= EXCERPT else text[:EXCERPT - 1] + "…"


def around(text, start, end, side=20):
    """text 의 [start, end) 구간과 앞뒤 side 자. 표 칸 경계(|)는 넘지 않고, 잘린 쪽에 … 를 붙인다."""
    left = text.rfind("|", 0, start) + 1
    right = text.find("|", end)
    right = len(text) if right < 0 else right
    a, b = max(left, start - side), min(right, end + side)
    return ("…" if a > left else "") + text[a:b].strip() + ("…" if b < right else "")


def sentence(text, start, pos):
    """start 부터 pos 뒤 첫 마침표까지. 경고문 한 문장을 발췌한다."""
    stop = text.find(".", pos)
    return clip(text[start:stop + 1 if stop >= 0 else len(text)])


def check(lines, blocks, idx, mark, source):
    """지적을 모은다. source 가 None 이면 원천 구조 문서 대조(DOC-08)를 하지 않는다.

    위치는 색인으로 적는다. line 은 위치에 쓸 줄, at 은 발췌한 줄이다.
    """
    findings = []

    def add(rule, kind, where, what, how, line, excerpt, at, case="", tag=""):
        # tag 는 앞 판의 '종류' 칸이다. 앞 판과 맞추려고 한동안 둔다.
        findings.append({"등급": kind, "자리": where, "무엇": what, "어떻게": how, "종류": tag,
                         "규칙": rule, "경우": case, "위치": idx.locate_line(line), "줄": line,
                         "발췌": excerpt, "발췌 줄": at})

    # DOC-01 설명 줄에서 떨어져 나간 줄 — 변환할 때 조용히 버려진다
    for b in blocks:
        for ln, s in b["after"]:
            if STRANDED.match(s):
                add("DOC-01", "오류", "%d줄" % ln,
                    "설명 줄에서 분리된 줄: %s. 변환 시 누락됨" % s[:50],
                    "앞 `- 설명:` 줄 끝에 이어 붙임", ln, clip(s), ln)

    # DOC-02 템플릿의 조사 괄호가 그대로 남았다
    for i, line in enumerate(lines):
        m = JOSA.search(line)
        if m:
            add("DOC-02", "오류", "%d줄" % (i + 1),
                "조사 괄호 잔존: %s" % m.group(0),
                "앞말 받침 유무에 맞는 조사 하나만 남김(받침 있음: 이/은/을/과, 없음: 가/는/를/와)",
                i + 1, around(line, m.start(), m.end()), i + 1)

    # DOC-03 표 안에 세로줄이 새어 칸 수가 어긋났다
    #      표마다 그 표의 머리글과 맞대 본다. 블록 안 둘째 표는 DOC-11 이 따로 잡는다.
    #      칸은 변환 스크립트처럼 나눈다(di.split_row). 양끝 세로줄은 하나씩만 떼므로 빈 끝 칸(||)도 칸이다.
    for b in blocks:
        for table in tables_of(b["rows"]):
            ncol = len(di.split_row(table[0][1]))
            for ln, row in table[1:]:
                if len(di.split_row(row)) != ncol:
                    add("DOC-03", "오류", "%d줄" % ln,
                        "표의 칸 수가 머리글과 다름. 설명 안의 세로줄이 칸을 분할함",
                        "설명 안 세로줄을 쉼표나 가운뎃점으로 변경", ln, clip(row), ln)

    # DOC-04 대표 표시 속성이 정확히 1개가 아니다
    #      통계로만 세면 아무도 보지 않는다. 0개면 무엇으로 보여 줄지 정해지지 않고,
    #      2개 이상이면 반입이 막힌다. 둘 다 문서가 만들어진 뒤에 드러난다.
    #      2건 이상이면 표시한 속성 이름을, 0건이면 머리글을 발췌한다.
    #      변환 스크립트처럼 첫 표만 보고 머리글 별칭과 참 값을 가린다(색인의 title_rows). 규격 검사기의
    #      GOS61006·61007 과 같은 결함으로 합치므로(검사-규칙.md 4절) 두 쪽이 같게 세어야 한다.
    for b in blocks:
        c = idx.element_at(b["line"])
        marked = idx.title_rows(c) if c is not None and c.kind == "개념" else None
        if marked is None or len(marked) == 1:
            continue
        if marked:
            excerpt, at = " · ".join(p.name for p in marked), marked[0].line
        else:
            at, excerpt = c.header_line, lines[c.header_line - 1].strip()
        add("DOC-04", "오류", "%d줄(%s)" % (b["line"], b["name"]),
            "대표 표시 속성 %d건. 개념마다 1건이어야 하며 0건이면 표시값 미정, 2건 이상이면 반입 불가"
            % len(marked),
            "서식 가이드의 대표 표시 속성 규칙에 따라 1건만 지정", b["line"], clip(excerpt), at,
            case="2건 이상" if marked else "0건", tag="대표 표시 속성")

    # DOC-05 설명이 아예 없는 개념, 또는 설명 줄은 있으나 변환 스크립트가 설명을 읽지 않는 개념
    #      변환 스크립트는 제목 아래부터 첫 표·제목 줄(#) 앞까지만, 머리가 '설명'·'description' 인 줄만
    #      설명으로 읽는다(색인의 desc). 표나 소제목 뒤의 설명 줄과 '- desc:' 줄은 오류 없이 버려져
    #      변환된 개념에 설명이 없다. 이때는 이 검사기가 설명으로 본 줄(여럿이면 마지막 줄)로 짚는다.
    #      다만 DOC-11 소제목 뒤 표가 있는 블록에서 그 소제목을 지우면 설명도 읽히면 DOC-11 행만 낸다
    #      (검사-규칙.md 4절). 한 결함(소제목)을 두 건으로 세지 않기 위해서다.
    unread = idx.unread_tables()
    headed = {id(el) for _, case, el in unread if case == "소제목 뒤 표" and el is not None}
    for b in blocks:
        if not b["desc"]:
            add("DOC-05", "경고", "%d줄(%s)" % (b["line"], b["name"]),
                "설명 없음. 설명은 임베딩되어 검색에 사용됨", "가이드 형식에 따라 설명 작성",
                b["line"], clip(lines[b["line"] - 1]), b["line"])
            continue
        c = idx.element_at(b["line"])
        if c is not None and c.kind == "개념" and not c.desc:
            if id(c) in headed and idx.desc_without_headings(c)[0]:
                continue
            ln = b["desc_line"]
            add("DOC-05", "경고", "%d줄(%s)" % (ln, b["name"]),
                "설명 줄이 첫 표나 소제목 뒤에 있거나 '- desc:' 꼴이라 변환 시 누락됨. 설명은 임베딩되어 검색에 사용됨",
                "설명 줄을 '- 설명:' 꼴로 개념 제목 바로 아래에 둠", ln, clip(lines[ln - 1]), ln,
                case="읽히지 않는 설명")

    # DOC-06·07 경고문이 한쪽에만 있거나 가리키는 개념을 알 수 없다
    #    경고문의 핵심은 "A 가 아니라 B 를 써야 한다" 이므로 그 자리에서 상대를 뽑는다.
    #    본문에 스쳐 지나간 다른 개념 이름까지 상대로 보면 없는 짝을 만들어 낸다.
    #    이름은 (길이 역순, 이름) 차례로 맞춰 본다. 같은 입력이면 늘 같은 상대가 나온다.
    #    같은 이름의 개념이 여럿이면 블록마다 따로 본다.
    names = sorted({b["name"] for b in blocks}, key=lambda n: (-len(n), n))
    warned = []         # (블록, 경고문 시작, {상대 이름: 경고문 안의 자리}) — 문서 차례
    for b in blocks:
        d = b["desc"] or ""
        base = d.find(mark)
        if base < 0:
            continue
        found = {}
        for m in PAIR.finditer(d, base):
            n = next((n for n in names if n != b["name"] and
                      (m.group(1) == n or m.group(1).startswith(n) or n in m.group(1))), None)
            if n:
                found.setdefault(n, m.start())
        warned.append((b, base, found))
    points_to = {b["line"]: set(found) for b, _, found in warned}

    for b, base, found in warned:
        d = b["desc"]
        for tgt in sorted(found):
            for t in (x for x in blocks if x["name"] == tgt):
                if b["name"] in points_to.get(t["line"], set()):
                    continue
                add("DOC-06", "경고", "개념 '%s'" % tgt,
                    "경고문 단방향: %s → %s 경고는 있으나 %s → %s 경고 없음. 반대 방향 질의에서 오답 발생"
                    % (b["name"], tgt, tgt, b["name"]),
                    "%s 설명에 경고 추가 또는 미추가 근거를 설계 리포트에 기재" % tgt, t["line"],
                    sentence(d, max(d.rfind(mark, 0, found[tgt]), base), found[tgt]),
                    b["desc_line"])
        if not found:
            add("DOC-07", "경고", "개념 '%s'" % b["name"],
                "경고 기호는 있으나 가리키는 개념 식별 불가. 가이드 경고문 형식과 다르게 작성된 경우일 수 있음",
                "경고문에 상대 개념 이름 포함 여부 확인", b["line"], sentence(d, base, base),
                b["desc_line"])

    # DOC-09 대상 환경에 아직 없는 데이터 구조를 짚는다
    #    문서 타입과 전처리 산출물은 여기 나오는 것이 정상이다. 오류가 아니라
    #    다음 단계의 일거리이므로, 리포트에 누가 하는지 적혔는지 확인하라고만 알린다.
    metas = meta_types(lines)
    absent_names = []
    for name, ln, desc, desc_ln in metas:
        m = ABSENT.search(desc)
        if m:
            absent_names.append(name)
            add("DOC-09", "확인", "%d줄(%s)" % (ln, name),
                "대상 환경에 미생성된 데이터 구조. 반입 전 생성 필요",
                "설계 리포트 7.1절(신규 메타타입)에 사용 개념·생성 방법·조치 주체 기재 여부 확인. "
                "규격 검사는 GOS61014로 지적하나 조치 주체는 알려 주지 않음",
                ln, around(desc, m.start(), m.end()), desc_ln)

    # DOC-08 원천 문서를 받았으면 데이터 구조 이름이 거기 있는지 대조한다
    #    원천에 없는 이름 자체는 잘못이 아니다 — 문서 타입은 여기서 처음 정해진다.
    #    다만 아무 설명 없이 원천에 없는 이름이 있으면 짚어 준다.
    if source is not None:
        for name, ln, desc, desc_ln in metas:
            if name not in source and name not in absent_names:
                add("DOC-08", "경고", "%d줄(%s)" % (ln, name),
                    "원천 문서에 없는 이름이며 출처 기재 없음",
                    "문서 타입·전처리로 새로 생기는 구조이면 설명에 기재. "
                    "원천 이름을 잘못 옮긴 경우 원천 이름으로 정정",
                    ln, clip(lines[ln - 1]), ln)

    # DOC-11 변환되지 않는 표 — 변환 스크립트는 블록마다 첫 표만 읽고(Link Type 은 첫 절의 첫 표만)
    #      첫 표 앞에서 제목 줄(#)을 만나면 그 블록의 표를 하나도 읽지 않는다.
    #      둘째 표는 표마다 머리글 줄로, 소제목 뒤 표는 블록마다 표 읽기를 멈춘 제목 줄로 짚는다.
    #      소제목 뒤 표 때문에 개념·매핑 블록에서 나는 변환 오류(속성 표 없음)는 수집 스크립트가 이 행에 합친다.
    for ln, case, _ in unread:
        heading = case == "소제목 뒤 표"
        add("DOC-11", "오류", "%d줄" % ln,
            "블록 제목과 첫 표 사이의 소제목. 변환 스크립트가 여기서 표 읽기를 멈춰 블록의 표 전체가 누락됨"
            if heading else "블록 안 둘째 표. 변환 스크립트가 첫 표만 읽어 표 전체가 누락됨",
            "블록 제목과 첫 표 사이의 소제목 줄을 지움" if heading
            else "표 내용을 블록의 첫 표나 설명 줄로 옮기고 둘째 표를 지움",
            ln, clip(lines[ln - 1]), ln, case="소제목 뒤 표" if heading else "둘째 표")

    findings.sort(key=lambda f: (f["규칙"], f["줄"], f["발췌"], f["무엇"]))
    return findings


def unreadable(args, doc, path, problem, detail=""):
    """문서를 읽지 못해 멈춘다. --json 이면 수집 스크립트가 알아볼 꼴로 낸다."""
    if args.json:
        json.dump({"읽힘": False, "까닭": "%s를 읽지 못함: %s (%s)" % (doc, path, problem),
                   "문서": doc, "경로": path, "문제": problem},
                  sys.stdout, ensure_ascii=False)
        print()
    else:
        print("%s를 읽지 못했다: %s (%s)" % (doc, path, problem + (": " + detail if detail else "")),
              file=sys.stderr)
        if doc == "원천 구조 문서":
            print("대조하지 않고 멈췄다. UTF-8 텍스트로 바꿔 다시 주면 대조한다. 바꿀 수 없으면 --source 로 주지 않는다.",
                  file=sys.stderr)
    return 2


def main():
    ap = argparse.ArgumentParser(description="온톨로지 정의 문서에서 조용히 사라지는 것을 찾는다.")
    ap.add_argument("path")
    ap.add_argument("--warn-mark", default="⚠", help="가이드가 정한 경고 기호 (기본 ⚠)")
    ap.add_argument("--source", nargs="*", default=[],
                    help="원천 구조 문서. 주면 데이터 구조 이름이 거기 있는지 대조한다. "
                         "UTF-8 텍스트로 읽지 못하면 멈춘다")
    ap.add_argument("--stats", action="store_true",
                    help="통계를 Markdown 표로만 출력한다. 문서에 그대로 붙여 넣는다")
    ap.add_argument("--json", action="store_true",
                    help="검사 결과와 통계를 JSON 으로 낸다. 수집 스크립트가 읽는다")
    args = ap.parse_args()

    try:
        text = di.read_text(args.path)
    except di.ReadError as e:
        return unreadable(args, "정의 문서", e.path, e.problem, e.detail)
    lines = text.splitlines()
    blocks = read_blocks(lines)

    if not blocks:
        if args.json:
            json.dump({"읽힘": False, "까닭": "Object Type 절에서 개념을 찾지 못함",
                       "문서": "정의 문서", "경로": args.path, "문제": "개념 없음"},
                      sys.stdout, ensure_ascii=False)
            print()
        else:
            print("Object Type 절에서 개념을 찾지 못했다. 절 제목을 확인한다.")
        return 2

    st = collect_stats(lines, blocks)
    if args.stats:
        print_stats(st, as_markdown=True)
        return 0

    # 원천 구조 문서는 모두 읽은 뒤에 대조한다. 하나라도 못 읽으면 대조하지 않고 멈춘다.
    source = None
    if args.source:
        texts = []
        for p in args.source:
            try:
                texts.append(di.read_text(p))
            except di.ReadError as e:
                return unreadable(args, "원천 구조 문서", e.path, e.problem, e.detail)
        source = "\n".join(texts)

    findings = check(lines, blocks, di.DefinitionIndex(lines), args.warn_mark, source)

    # ---- 보고
    errors = [f for f in findings if f["등급"] == "오류"]
    warns = [f for f in findings if f["등급"] == "경고"]
    notes = [f for f in findings if f["등급"] == "확인"]

    if args.json:
        json.dump({"읽힘": True, "통계": st, "걸린 것": findings}, sys.stdout, ensure_ascii=False)
        print()
        return 1 if errors else 0

    print("검사 대상: %s   (경고 기호 %s)\n" % (args.path, args.warn_mark))
    print_stats(st, as_markdown=False)
    print()

    # 묶음 이름은 규칙 목록의 등급 이름이다. JSON 의 옛 '등급' 칸 값(오류·경고·확인)은 앞 판과 맞추려고 그대로 둔다.
    for kind, group in (("Error", errors), ("Warning", warns), ("Info", notes)):
        if not group:
            continue
        print("%s %d건" % (kind, len(group)))
        for f in group:
            print("  %s  %s  %s" % (f["규칙"], f["위치"], f["무엇"]))
            print("      → %s" % f["어떻게"])
        print()

    if not findings:
        print("조용히 사라지는 자리를 찾지 못했다.")
        print("내용이 맞는지는 사람이 본다 — 질문이 쓰지 않는 개념, 근거 없이 채운 값 같은 것이다.")
        return 0

    print("Error는 고치고 다시 돌린다. Warning은 확인하고 근거를 리포트에 적는다.")
    print("Info는 잘못이 아니라 다음 단계로 넘길 일이다 — 리포트에 올랐는지만 본다.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
