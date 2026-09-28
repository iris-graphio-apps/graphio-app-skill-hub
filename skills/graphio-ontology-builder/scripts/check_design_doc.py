#!/usr/bin/env python3
"""온톨로지 정의 문서에서 '오류 없이 사라지는 것'을 찾는다.

변환 스크립트는 서식 오류를 잡는다. 이 스크립트는 서식은 맞는데
내용이 새어 나가는 자리를 잡는다 — 오류가 나지 않아 아무도 모르는 것들이다.

    python3 check_design_doc.py <온톨로지-정의.md>

경고 기호가 가이드마다 다르므로 필요하면 지정한다.

    python3 check_design_doc.py <문서.md> --warn-mark ※
"""
import argparse
import json
import re
import sys

# 설명 줄이 잘렸는지 알아보는 표지. 대괄호로 시작하는 줄은 대개
# [SQL]·[별칭]·[출처] 같은 구획 표지라 설명 줄에 붙어 있어야 한다.
STRANDED = re.compile(r"^(\[|FK\s*JOIN|SQL\s*:)")
# 표에서 "그렇다"로 읽는 값. 가이드마다 표기가 달라 흔한 것을 모아 둔다.
TRUE_VALS = ("O", "예", "Y", "YES", "TRUE", "V", "✓", "✔", "○", "●")
JOSA = re.compile(r"[가-힣]\s*(이\(가\)|은\(는\)|을\(를\)|과\(와\)|와\(과\))")
# 서식 네 절의 제목. 제목은 공백·하이픈·밑줄·가운뎃점·마침표를 지우고 소문자로 맞춰 읽는다.
FOUR_SECTIONS = {"objecttype", "오브젝트타입", "linktype", "링크타입",
                 "metatype", "메타타입", "objectmapping", "오브젝트매핑"}


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
    """Meta Type 절의 (이름, 줄번호, 설명) 을 모은다."""
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
            cur = [m.group(1).strip(), i + 1, ""]
            out.append(cur)
            continue
        if cur is not None:
            m = re.match(r"^[-*]\s*(설명|description|desc)\s*[:：]\s*(.*)$", line.strip(), re.I)
            if m:
                cur[2] = m.group(2).strip()
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


def title_count(block):
    """개념 블록에서 대표 표시 속성으로 표시된 행의 수. 표가 없으면 None."""
    if not block["rows"]:
        return None
    header = [c.strip().lower() for c in block["rows"][0][1].strip("|").split("|")]
    ti = next((i for i, h in enumerate(header)
               if h in ("title", "title key", "대표", "대표 표시")), None)
    if ti is None:
        return 0
    n = 0
    for _, row in block["rows"][1:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c or "-") for c in cells) or not any(cells):
            continue
        if ti < len(cells) and cells[ti].upper() in TRUE_VALS:
            n += 1
    return n


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


def main():
    ap = argparse.ArgumentParser(description="온톨로지 정의 문서에서 조용히 사라지는 것을 찾는다.")
    ap.add_argument("path")
    ap.add_argument("--warn-mark", default="⚠", help="가이드가 정한 경고 기호 (기본 ⚠)")
    ap.add_argument("--source", nargs="*", default=[],
                    help="원천 구조 문서. 주면 데이터 구조 이름이 거기 있는지 대조한다")
    ap.add_argument("--stats", action="store_true",
                    help="통계를 Markdown 표로만 출력한다. 문서에 그대로 붙여 넣는다")
    ap.add_argument("--json", action="store_true",
                    help="검사 결과와 통계를 JSON 으로 낸다. 판정 스크립트가 읽는다")
    args = ap.parse_args()

    text = open(args.path, encoding="utf-8").read()
    lines = text.splitlines()
    blocks = read_blocks(lines)

    findings = []

    def add(kind, where, what, how, tag=""):
        # tag 는 판정 스크립트가 따로 세는 종류다. 대표 표시 속성은 치명 구분이 달라 표시한다.
        findings.append((kind, where, what, how, tag))

    if not blocks:
        if args.json:
            json.dump({"읽힘": False,
                       "까닭": "Object Type 절에서 개념을 찾지 못함"},
                      sys.stdout, ensure_ascii=False)
            print()
        else:
            print("Object Type 절에서 개념을 찾지 못했다. 절 제목을 확인한다.")
        return 2

    st = collect_stats(lines, blocks)
    if args.stats:
        print_stats(st, as_markdown=True)
        return 0

    # 1) 설명 줄에서 떨어져 나간 줄 — 변환할 때 조용히 버려진다
    for b in blocks:
        for ln, s in b["after"]:
            if STRANDED.match(s):
                add("오류", "%d줄" % ln,
                    "설명 줄에서 분리된 줄: %s. 변환 시 누락됨" % s[:50],
                    "앞 `- 설명:` 줄 끝에 이어 붙임")

    # 2) 설명이 아예 없는 개념
    for b in blocks:
        if not b["desc"]:
            add("경고", "%d줄(%s)" % (b["line"], b["name"]),
                "설명 없음. 설명은 임베딩되어 검색에 사용됨", "가이드 형식에 따라 설명 작성")

    # 3) 템플릿의 조사 괄호가 그대로 남았다
    for i, line in enumerate(lines):
        if JOSA.search(line):
            add("오류", "%d줄" % (i + 1),
                "조사 괄호 잔존: %s" % JOSA.search(line).group(0),
                "앞말 받침 유무에 맞는 조사 하나만 남김(받침 있음: 이/은/을/과, 없음: 가/는/를/와)")

    # 4) 경고문이 한쪽에만 있다
    #    경고문의 핵심은 "A 가 아니라 B 를 써야 한다" 이므로 그 자리에서 상대를 뽑는다.
    #    본문에 스쳐 지나간 다른 개념 이름까지 상대로 보면 없는 짝을 만들어 낸다.
    mark = args.warn_mark
    names = sorted({b["name"] for b in blocks}, key=len, reverse=True)
    pair_re = re.compile(r"아니라\s*(\S+?)\s*(?:을|를)\s*(?:써야|사용)")
    points_to, unreadable = {}, []
    for b in blocks:
        d = b["desc"] or ""
        if mark not in d:
            continue
        seg = d[d.find(mark):]
        found = set()
        for cand in pair_re.findall(seg):
            for n in names:
                if n != b["name"] and (cand == n or cand.startswith(n) or n in cand):
                    found.add(n)
                    break
        if found:
            points_to[b["name"]] = found
        else:
            unreadable.append(b["name"])

    for src, targets in points_to.items():
        for tgt in targets:
            if src not in points_to.get(tgt, set()):
                add("경고", "개념 '%s'" % tgt,
                    "경고문 단방향: %s → %s 경고는 있으나 %s → %s 경고 없음. 반대 방향 질의에서 오답 발생"
                    % (src, tgt, tgt, src),
                    "%s 설명에 경고 추가 또는 미추가 근거를 설계 리포트에 기재" % tgt)

    for n in unreadable:
        add("경고", "개념 '%s'" % n,
            "경고 기호는 있으나 가리키는 개념 식별 불가. 가이드 경고문 형식과 다르게 작성된 경우일 수 있음",
            "경고문에 상대 개념 이름 포함 여부 확인")

    # 5) 대상 환경에 아직 없는 데이터 구조를 짚는다
    #    문서 타입과 전처리 산출물은 여기 나오는 것이 정상이다. 오류가 아니라
    #    다음 단계의 일거리이므로, 리포트에 누가 하는지 적혔는지 확인하라고만 알린다.
    ABSENT = re.compile(r"(아직\s*(없|등록되지)|존재하지\s*않|전처리가\s*(필요|선행)|만들어야|생성해야)")
    absent_names = []
    for name, ln, desc in meta_types(lines):
        if ABSENT.search(desc):
            absent_names.append(name)
            add("확인", "%d줄(%s)" % (ln, name),
                "대상 환경에 미생성된 데이터 구조. 반입 전 생성 필요",
                "설계 리포트 7.1절(신규 메타타입)에 사용 개념·생성 방법·조치 주체 기재 여부 확인. "
                "규격 검사는 GOS61014로 지적하나 조치 주체는 알려 주지 않음")

    # 6) 원천 문서를 받았으면 데이터 구조 이름이 거기 있는지 대조한다
    #    원천에 없는 이름 자체는 잘못이 아니다 — 문서 타입은 여기서 처음 정해진다.
    #    다만 아무 설명 없이 원천에 없는 이름이 있으면 짚어 준다.
    if args.source:
        src = ""
        for p in args.source:
            try:
                src += open(p, encoding="utf-8").read()
            except OSError as e:
                print("원천 문서를 읽지 못했다: %s (%s)" % (p, e), file=sys.stderr)
        for name, ln, desc in meta_types(lines):
            if name not in src and name not in absent_names:
                add("경고", "%d줄(%s)" % (ln, name),
                    "원천 문서에 없는 이름이며 출처 기재 없음",
                    "문서 타입·전처리로 새로 생기는 구조이면 설명에 기재. "
                    "원천 이름을 잘못 옮긴 경우 원천 이름으로 정정")

    # 7-1) 대표 표시 속성이 정확히 1개가 아니다
    #      통계로만 세면 아무도 보지 않는다. 0개면 무엇으로 보여 줄지 정해지지 않고,
    #      2개 이상이면 반입이 막힌다. 둘 다 문서가 만들어진 뒤에 드러난다.
    for b in blocks:
        n = title_count(b)
        if n is None or n == 1:
            continue
        add("오류", "%d줄(%s)" % (b["line"], b["name"]),
            "대표 표시 속성 %d건. 개념마다 1건이어야 하며 0건이면 표시값 미정, 2건 이상이면 반입 불가" % n,
            "서식 가이드의 대표 표시 속성 규칙에 따라 1건만 지정", tag="대표 표시 속성")

    # 7) 표 안에 세로줄이 새어 칸 수가 어긋났다
    for b in blocks:
        if not b["rows"]:
            continue
        ncol = len(b["rows"][0][1].strip("|").split("|"))
        for ln, row in b["rows"][1:]:
            if len(row.strip("|").split("|")) != ncol:
                add("오류", "%d줄" % ln,
                    "표의 칸 수가 머리글과 다름. 설명 안의 세로줄이 칸을 분할함",
                    "설명 안 세로줄을 쉼표나 가운뎃점으로 변경")

    # ---- 보고
    errors = [f for f in findings if f[0] == "오류"]
    warns = [f for f in findings if f[0] == "경고"]
    notes = [f for f in findings if f[0] == "확인"]

    if args.json:
        json.dump({"읽힘": True, "통계": st,
                   "걸린 것": [{"등급": k, "자리": w, "무엇": t, "어떻게": h, "종류": g}
                             for k, w, t, h, g in findings]},
                  sys.stdout, ensure_ascii=False)
        print()
        return 1 if errors else 0

    print("검사 대상: %s   (경고 기호 %s)\n" % (args.path, mark))
    print_stats(st, as_markdown=False)
    print()

    for kind, group in (("오류", errors), ("경고", warns), ("확인", notes)):
        if not group:
            continue
        print("%s %d건" % (kind, len(group)))
        for _, where, what, how, _ in group:
            print("  %s  %s" % (where, what))
            print("      → %s" % how)
        print()

    if not findings:
        print("조용히 사라지는 자리를 찾지 못했다.")
        print("내용이 맞는지는 사람이 본다 — 질문이 쓰지 않는 개념, 근거 없이 채운 값 같은 것이다.")
        return 0

    print("오류는 고치고 다시 돌린다. 경고는 확인하고 근거를 리포트에 적는다.")
    print("확인 항목은 잘못이 아니라 다음 단계로 넘길 일이다 — 리포트에 올랐는지만 본다.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
