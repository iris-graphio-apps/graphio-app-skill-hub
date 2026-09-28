#!/usr/bin/env python3
"""온톨로지 구조를 확정해도 되는지 판정한다.

검증 리포트는 무엇을 검사했는지 적는다. 이 스크립트는 그 결과에 등급을 매겨
「확정해도 되는가」 한 줄로 만든다. 치명이 0건이면 확정할 수 있다.

    python3 judge_structure.py <온톨로지-정의.md> <온톨로지-검증-리포트.md>

CQ 문서가 CQ에 등급을 매겼으면 어느 말을 필수로 볼지 알려 준다.
알려 주지 않으면 모든 CQ를 필수로 본다.

    python3 judge_structure.py <정의.md> <검증-리포트.md> --required-grade 필수

규격 검사는 자매 스킬이 수행하므로 그 결과를 숫자로 받는다. 주지 않으면
「미수행 검사」 로 남고 판정 범위가 좁아진다.

    ... --spec-errors 0 --spec-warnings 0 --spec-deferred 1

스크립트가 셀 수 없는 세 항목은 스킬이 짚어 옵션으로 넘긴다. 짚었으면
--manual-checked, 찾은 것이 있으면 한 건마다 --add-major 를 준다.
CQ 등급 미확정은 검증 리포트 2절 「필수 CQ 기준」 을 보고 스크립트가 올린다.

    ... --manual-checked --add-major "구분|지적 내용|조치 방안|조치 주체|근거[|주석]"

입력을 읽지 못하면 판정 문서를 쓰지 않고 멈춘다(종료 코드 2). 읽지 못한 채 판정하면
치명이 가려진 문서가 「확정 가능」 으로 나가기 때문이다.

문서의 꼴과 문체는 references/리포트-작성-규칙.md 를 따른다.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "check_design_doc.py")

# 판정값. 리포트-작성-규칙.md 4장이 정한 닫힌 목록이라 여기서 늘리지 않는다.
CQ_VERDICTS = ("응답 가능", "부분 응답", "응답 불가")
MAP_VERDICTS = ("일치", "대체 매핑", "의미 불일치 미매핑",
                "원천 부재 미매핑", "원천 확인 필요 미매핑")
LEFT_EMPTY = ("의미 불일치 미매핑", "원천 부재 미매핑", "원천 확인 필요 미매핑")

# 옛 서식의 판정값. 이전에 쓴 검증 리포트도 판정할 수 있게 새 말로 읽는다.
OLD_VERDICTS = {
    "예": "응답 가능", "일부": "부분 응답", "아니오": "응답 불가",
    "같다": "일치", "대신답함": "대체 매핑", "뜻이달라비움": "의미 불일치 미매핑",
    "원천에없어비움": "원천 부재 미매핑", "원천에있는지몰라비움": "원천 확인 필요 미매핑",
}

# 스킬이 짚어 --add-major 로 넘기는 중대 사항의 구분. 구조-판정-서식.md 중대 목록과 같다.
MANUAL_KINDS = ("미사용 개념·속성", "스타일 가이드 위반", "서식 가이드 위반",
                "CQ 등급 미확정", "입력 문서 간 불일치")

# 스킬이 짚는 세 항목. --manual-checked 가 없으면 미수행 검사로 남긴다.
BY_HAND = ("미사용 개념·속성", "가이드 위반", "입력 문서 간 불일치")

# 필수 CQ 기준을 스킬이 정했다는 표시. 이 말이 있으면 CQ 등급 미확정을 중대로 올린다.
SKILL_DECIDED = ("스킬 판단", "전체 CQ")
ALL_CQ = "전체 CQ(필수 등급 판별 불가)"

# 검증 리포트 문서 정보 표에서 판정 문서로 옮기는 행. 옛 서식의 행 이름도 받는다.
CARRY_OVER = (("설계 리포트", ("설계 리포트",)),
              ("CQ 문서", ("CQ 문서", "CQ (검증질문)", "CQ(검증질문)")),
              ("스타일 가이드", ("스타일 가이드",)),
              ("서식 가이드", ("서식 가이드",)))

WHERE_CQ = "검증 리포트 5절(CQ별 판정)"
WHERE_MAP = "검증 리포트 6절(매핑 컬럼 대조 결과)"
WHERE_SPEC = "검증 리포트 4절(서식 변환 검사)"


class InputError(Exception):
    """판정할 수 없는 입력. 판정 문서를 쓰지 않고 멈춘다."""


def norm(s):
    """표 칸의 값을 맞대 보기 좋게 다듬는다. 백틱과 공백은 뜻을 바꾸지 않는다."""
    return re.sub(r"\s+", "", (s or "").replace("`", "").replace("*", "")).lower()


def esc(s):
    """표 칸에 넣을 값. 세로줄이 칸을 쪼개지 않게 막는다."""
    return str(s).replace("\\|", "|").replace("|", "\\|")


def verdict_of(raw):
    """판정값을 새 말로 읽는다. 모르는 값이면 None."""
    n = norm(raw)
    for v in CQ_VERDICTS + MAP_VERDICTS:
        if n == norm(v):
            return v
    return OLD_VERDICTS.get(n)


def sections(lines):
    """## 절을 {제목: (시작줄, 끝줄)} 로 나눈다."""
    marks = [(i, m.group(1).strip())
             for i, ln in enumerate(lines)
             if (m := re.match(r"^##\s+(?!#)(.+?)\s*$", ln))]
    out = {}
    for n, (i, title) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        out[title] = (i + 1, end)
    return out


def find_section(secs, *choices):
    """제목에 낱말이 든 절을 찾는다. 절 번호가 바뀌어도 찾아낸다.
    choices 는 낱말 묶음 여럿이다. 앞의 묶음부터 맞춰 본다."""
    for words in choices:
        for title, span in secs.items():
            if all(w in title for w in words):
                return span
    return None


def tables(lines, span):
    """절 안의 본문 표를 모두 [(머리글, 행들)] 로 읽는다. 인용문(>) 안의 표는 건너뛴다."""
    out, head, rows = [], None, []
    for ln in lines[span[0]:span[1]] + [""]:
        s = ln.strip()
        if s.startswith("|") and not s.startswith(">"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", s.strip("|"))]
            if all(re.fullmatch(r":?-+:?", c or "-") for c in cells):
                continue
            if head is None:
                head = [norm(c) for c in cells]
            elif any(cells):
                rows.append(cells)
        elif head is not None:
            out.append((head, rows))
            head, rows = None, []
    return out


def pick_table(lines, span, *want):
    """want 열이 있는 첫 표. 표가 없으면 (None, None), 표는 있는데 열이 없으면 (머리글, None)."""
    found = tables(lines, span)
    for head, rows in found:
        if column(head, *want) is not None:
            return head, rows
    return (found[0][0] if found else None), None


def info_table(lines):
    """제목 아래 첫 절 앞의 문서 정보 표를 {항목: 내용} 으로 읽는다."""
    out = {}
    for ln in lines:
        if re.match(r"^##\s", ln):
            break
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) >= 2 and not re.fullmatch(r":?-+:?", cells[0] or "-"):
            out[cells[0]] = cells[1]
    return out


def column(head, *names):
    """표 머리글에서 열 자리를 찾는다. 이름이 조금 달라도 찾아낸다."""
    if not head:
        return None
    for want in names:
        w = norm(want)
        for i, h in enumerate(head):
            if h == w:
                return i
    for want in names:
        w = norm(want)
        for i, h in enumerate(head):
            if w and w in h:
                return i
    return None


def cell(row, idx):
    return row[idx].strip() if idx is not None and idx < len(row) else ""


def run_checker(path, warn_mark):
    """정의 문서 검사기를 수행해 지적 사항과 통계를 받는다. 읽지 못하면 멈춘다."""
    cmd = [sys.executable, CHECKER, path, "--json"]
    if warn_mark:
        cmd += ["--warn-mark", warn_mark]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        raise InputError("정의 문서 검사기를 수행하지 못함: %s" % e)
    out = (p.stdout or "").strip()
    try:
        data = json.loads(out.splitlines()[-1]) if out else None
    except ValueError:
        data = None
    if data is None:
        raise InputError("정의 문서 검사기 결과를 읽지 못함(종료 코드 %d)" % p.returncode)
    if not data.get("읽힘"):
        raise InputError("정의 문서를 읽지 못함: %s" % data.get("까닭", "까닭 없음"))
    return data


def finding(kind, what, fix, owner, where, note=""):
    return {"구분": kind, "지적 내용": what, "조치 방안": fix,
            "조치 주체": owner, "근거": where, "주석": note}


def parse_manual(raw):
    """--add-major 값 하나를 지적 사항으로 읽는다."""
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) not in (5, 6) or not all(parts[:5]):
        raise InputError("--add-major 는 '구분|지적 내용|조치 방안|조치 주체|근거[|주석]' "
                         "꼴이어야 함: %s" % raw)
    if parts[0] not in MANUAL_KINDS:
        raise InputError("--add-major 구분 값이 정해진 말이 아님: '%s'. 가능한 값: %s"
                         % (parts[0], ", ".join(MANUAL_KINDS)))
    return finding(*parts[:5], note=parts[5] if len(parts) == 6 else "")


def required_basis(lines, secs, grades, present):
    """필수 CQ 기준을 정하고 검증 리포트 2절과 맞대 본다. 어긋나면 멈춘다."""
    if grades:
        missing = [g for g in grades if norm(g) not in present]
        if missing:
            raise InputError("검증 리포트 5절 등급 칸에 없는 --required-grade 값: %s. "
                             "5절 등급 칸의 값: %s"
                             % ("·".join(missing),
                                "·".join(sorted(v for v in present if v)) or "없음"))
    span = find_section(secs, ("검증 결과 요약",))
    written = ""
    if span:
        for head, rows in tables(lines, span):
            for row in rows:
                if norm(cell(row, 0)) == norm("필수 CQ 기준"):
                    written = cell(row, 1)
    if not written:
        return ("CQ 문서 등급 %s" % "·".join("'%s'" % g for g in grades)
                if grades else ALL_CQ)
    quoted = {norm(q) for q in re.findall(r"'([^']+)'", written)}
    if {norm(g) for g in grades} != quoted:
        raise InputError("검증 리포트 2절 '필수 CQ 기준'(%s)과 --required-grade(%s)가 다름"
                         % (written, "·".join(grades) or "지정 없음"))
    return written


def judge(args, lines):
    """치명과 중대를 모은다. 판정은 치명 건수가 정한다."""
    secs = sections(lines)
    critical, major, unchecked, counted = [], [], [], {}

    # ── 필수 CQ에 응답하는가 (검증 리포트 5절)
    span = find_section(secs, ("CQ별", "판정"), ("질문별", "판정"))
    if span is None:
        raise InputError("검증 리포트 5절(CQ별 판정)을 찾지 못함")
    head, rows = pick_table(lines, span, "판정", "답할 수 있나")
    if head is None:
        raise InputError("검증 리포트 5절(CQ별 판정)에 표가 없음")
    if rows is None:
        raise InputError("검증 리포트 5절 표에 '판정' 열이 없음")
    if not rows:
        raise InputError("검증 리포트 5절 표에 행이 없음")
    gi = column(head, "등급")
    vi = column(head, "판정", "답할 수 있나")
    qi = column(head, "CQ", "질문")
    ni = column(head, "No.")
    mi = column(head, "누락 항목", "무엇이 빠졌나")
    if args.required_grade and gi is None:
        raise InputError("--required-grade 를 받았으나 검증 리포트 5절 표에 '등급' 열이 없음")
    bad = ["%s: '%s'" % (cell(row, qi) or "(CQ 이름 없음)", cell(row, vi))
           for row in rows if verdict_of(cell(row, vi)) not in CQ_VERDICTS]
    if bad:
        raise InputError("검증 리포트 5절 판정값이 정해진 값(%s)이 아님: %s"
                         % ("·".join(CQ_VERDICTS), ", ".join(bad)))
    present = {norm(cell(row, gi)) for row in rows} if gi is not None else set()
    counted["필수 CQ 기준"] = required_basis(lines, secs, args.required_grade, present)

    required = {norm(g) for g in args.required_grade}
    tally = {}
    for row in rows:
        name = cell(row, qi) or "(CQ 이름 없음)"
        is_req = (not required) or (norm(cell(row, gi)) in required)
        verdict = verdict_of(cell(row, vi))
        key = ("필수" if is_req else "그 밖", verdict)
        tally[key] = tally.get(key, 0) + 1
        if verdict == "응답 가능":
            continue
        gap = cell(row, mi)
        gap = "(누락 항목: %s)" % gap if gap and norm(gap) != norm("해당 없음") else ""
        where = WHERE_CQ + (" No.%s" % cell(row, ni) if cell(row, ni) else "")
        if is_req:
            critical.append(finding(
                "필수 CQ %s" % verdict, "%s %s%s" % (name, verdict, gap),
                "응답 경로 추가 또는 필수 CQ에서 제외" if verdict == "응답 불가"
                else "누락 항목 보완 또는 필수 CQ에서 제외",
                "지정 필요", where))
        else:
            major.append(finding(
                "CQ %s" % verdict,
                "%s %s%s. 필수 CQ가 아니므로 확정을 막지 않음" % (name, verdict, gap),
                "응답 경로 추가" if verdict == "응답 불가" else "누락 항목 보완",
                "설계 담당", where))
    counted["CQ"] = {"전체": len(rows), "집계": tally}

    # ── 뜻이 다른 컬럼으로 대신 답하지 않았는가 (검증 리포트 6절)
    span = find_section(secs, ("매핑", "대조"), ("맞대 본 결과",))
    if span is None:
        raise InputError("검증 리포트 6절(매핑 컬럼 대조 결과)을 찾지 못함")
    head, rows = pick_table(lines, span, "판정")
    if head is not None and rows is None:
        raise InputError("검증 리포트 6절 표에 '판정' 열이 없음")
    if not rows:
        why = next((re.sub(r"^[-*]\s*", "", ln.strip()) for ln in lines[span[0]:span[1]]
                    if "미수행" in ln), "")
        unchecked.append(("매핑 의미 검사", why or "검증 리포트 6절 표에 행 없음"))
    else:
        vi = column(head, "판정")
        ni = column(head, "No.")
        ki = column(head, "값")
        pi = column(head, "대상 속성", "담은 속성")
        ci = column(head, "매핑 컬럼", "매핑한 컬럼")
        bad = ["%s: '%s'" % (cell(row, ki) or "(값 이름 없음)", cell(row, vi))
               for row in rows if verdict_of(cell(row, vi)) not in MAP_VERDICTS]
        if bad:
            raise InputError("검증 리포트 6절 판정값이 정해진 값(%s)이 아님: %s"
                             % ("·".join(MAP_VERDICTS), ", ".join(bad)))
        tally = {}
        for row in rows:
            verdict = verdict_of(cell(row, vi))
            tally[verdict] = tally.get(verdict, 0) + 1
            if verdict == "대체 매핑":
                critical.append(finding(
                    "대체 매핑",
                    "값 '%s', 대상 속성 '%s', 매핑 컬럼 '%s'. 뜻이 다른 컬럼에 매핑되어 "
                    "질의 결과가 틀림" % (cell(row, ki), cell(row, pi), cell(row, ci)),
                    "해당 매핑 제거 후 설계 리포트 7.2절(기존 메타타입 추가 컬럼)에 "
                    "필요 컬럼으로 등재",
                    "설계 담당",
                    WHERE_MAP + (" No.%s" % cell(row, ni) if cell(row, ni) else "")))
        counted["매핑"] = {"전체": len(rows), "집계": tally}

    # ── 정의 문서에서 내용이 사라지는가 (이 스킬의 검사기)
    data = run_checker(args.definition, args.warn_mark)
    stats = data["통계"]
    kinds = {}
    for f in data["걸린 것"]:
        kinds.setdefault(f["등급"], []).append(f)
    for f in kinds.get("오류", []):
        # 대표 표시 속성은 구분을 따로 둔다. 통계로 한 번 더 세지 않는다.
        kind = "대표 표시 속성 오류" if f.get("종류") == "대표 표시 속성" else "정의 문서 오류"
        critical.append(finding(kind, f["무엇"], f["어떻게"],
                                "설계 담당", "정의 문서 %s" % f["자리"]))
    for f in kinds.get("경고", []):
        major.append(finding("정의 문서 경고", f["무엇"], f["어떻게"],
                             "설계 담당", "정의 문서 %s" % f["자리"]))
    counted["정의 문서 검사"] = {k: len(v) for k, v in kinds.items()}

    # ── 반입되는가 (자매 스킬의 규격 검사, 결과를 인자로 받는다)
    if args.convert_failed:
        critical.append(finding(
            "변환 실패", "정의 문서가 Graphio 정의 파일로 변환되지 않음. 반입 불가",
            "변환 스크립트가 지적한 줄 수정 후 재수행", "설계 담당", WHERE_SPEC))
    if args.spec_skipped or args.spec_errors is None:
        unchecked.append(("서식 변환 검사",
                          "규격 검사 결과 미제공(검증 리포트 4절 No.2 참조). 반입 가능 여부 미확인"))
    else:
        if args.spec_errors:
            critical.append(finding(
                "규격 오류", "Graphio 규격 오류 %d건. 반입 불가" % args.spec_errors,
                "규격 검사가 지적한 항목을 정의 문서에서 수정 후 재수행",
                "설계 담당", WHERE_SPEC))
        if args.spec_warnings:
            major.append(finding(
                "규격 경고", "Graphio 규격 경고 %d건. 규격은 통과함" % args.spec_warnings,
                "의도 여부 확인 후 검증 리포트 4절에 기재", "설계 담당", WHERE_SPEC))

    # ── 필수 CQ 기준을 스킬이 정했으면 CQ 등급 미확정 (스킬이 이미 넘겼으면 겹쳐 올리지 않는다)
    basis = counted["필수 CQ 기준"]
    if (any(w in basis for w in SKILL_DECIDED)
            and not any(f["구분"] == "CQ 등급 미확정" for f in args.manual_findings)):
        major.append(finding(
            "CQ 등급 미확정",
            "CQ 문서가 필수 등급을 밝히지 않아 필수 CQ 기준을 스킬이 정함(2절 필수 CQ 기준 참조). "
            "필수 CQ 범위가 바뀌면 판정이 달라질 수 있음",
            "CQ 문서 작성자의 필수 등급 확인 후 판정 재수행", "CQ 문서 작성자",
            "검증 리포트 2절(검증 결과 요약) 필수 CQ 기준"))

    # ── 스킬이 짚은 세 항목
    major.extend(args.manual_findings)
    if not args.manual_checked:
        for kind in BY_HAND:
            unchecked.append(("스킬 확인 항목(%s)" % kind, "확인 결과 미반영"))

    return critical, major, unchecked, counted, stats


def leave_alone(counted, stats, args):
    """조치 대상 외 항목. 규칙을 지켜 비운 항목이라 판정을 막지 않는다."""
    out = []
    tally = counted.get("매핑", {}).get("집계", {})
    for name in LEFT_EMPTY:
        if tally.get(name):
            out.append((name, "%d건" % tally[name],
                        "검증 리포트 6절(매핑 컬럼 대조 결과) · "
                        "설계 리포트 7.2절(기존 메타타입 추가 컬럼)"))
    n = next((stats[k] for k in ("확인 필요 표기", "확인 필요 항목", "확인 필요가 남은 자리")
              if k in stats), 0)
    if n:
        out.append(("'확인 필요' 표기", "%s건" % n,
                    "검증 리포트 3절(산출 규모) · 설계 리포트 8절(확인 필요 사항)"))
    n = counted.get("정의 문서 검사", {}).get("확인", 0)
    if n:
        out.append(("정의 문서 검사 확인 사항", "%d건" % n, "검증 리포트 4절(정의 문서 검사)"))
    if args.spec_deferred and not (args.spec_skipped or args.spec_errors is None):
        out.append(("규격 검사 보류", "%d건" % args.spec_deferred,
                    "검증 리포트 4절(서식 변환 검사) · 검증 리포트 7.1절(대상 환경 조치)"))
    return out


def table(head, rows):
    """번호를 붙인 표. 줄이 없으면 '해당 없음' 한 줄."""
    if not rows:
        return ["해당 없음"]
    out = ["| No. | %s |" % " | ".join(head),
           "|%s|" % "|".join(["---"] * (len(head) + 1))]
    out += ["| %d | %s |" % (i, " | ".join(esc(c) for c in r)) for i, r in enumerate(rows, 1)]
    return out


def findings_table(items):
    out = table(["구분", "지적 내용", "조치 방안", "조치 주체", "근거"],
                [[f[k] for k in ("구분", "지적 내용", "조치 방안", "조치 주체", "근거")]
                 for f in items])
    notes = ["※ No.%d %s" % (i, f["주석"]) for i, f in enumerate(items, 1) if f["주석"]]
    if notes:
        out += [""] + notes
    return out


def follow_ups(critical, major, unchecked):
    out = []
    if critical:
        out.append("3.1 치명 사항 조치 후 판정 재수행 필요")
    if unchecked:
        out.append("5절 미수행 검사 수행 후 판정 재수행 필요")
    if not critical and not unchecked:
        out.append("구조 확정 가능. 검증 리포트 7절(후속 조치) 사항 이행 필요")
    if major:
        out.append("3.2 중대 사항은 확정과 별개로 조치 필요. 처리 시점은 인수 측이 결정함")
    if any(f["구분"] in ("CQ 응답 불가", "CQ 부분 응답") for f in major):
        out.append("3.2의 CQ 가운데 필수 CQ로 격상되는 CQ가 있으면 판정 재수행 필요")
    out.append("CQ 등급이 바뀌어 필수 CQ가 달라지면 판정 재수행 필요")
    return out


def report(args, lines, critical, major, unchecked, counted, stats):
    name = args.name or os.path.basename(args.definition).split("-온톨로지")[0]
    verdict = "확정 불가" if critical else "확정 가능"
    info = info_table(lines)
    q = counted["CQ"]
    tally = q["집계"]
    req_total = sum(v for (kind, _), v in tally.items() if kind == "필수")
    req_yes = tally.get(("필수", "응답 가능"), 0)

    p = ["# %s 온톨로지 구조 판정" % name, "",
         "| 항목 | 내용 |", "|---|---|",
         "| 판정일 | %s |" % datetime.date.today().isoformat(),
         "| 대상 문서 | `%s` |" % esc(args.definition),
         "| 검증 리포트 | `%s` |" % esc(args.report)]
    for key, aliases in CARRY_OVER:
        value = next((info[a] for a in aliases if info.get(a)), "")
        if not value:
            print("경고: 검증 리포트 문서 정보 표에 '%s' 행이 없다" % key, file=sys.stderr)
            value = "확인 필요(검증 리포트 문서 정보 표에 없음)"
        p.append("| %s | %s |" % (key, value))

    p += ["", "## 1. 개요", "",
          "### 1.1 목적", "",
          "- 검증 리포트의 검사 결과에 등급을 부여하여 온톨로지 구조의 확정 가능 여부를 판정함",
          "- 조치가 필요한 항목과 조치 대상 외 항목을 구분함", "",
          "### 1.2 판정 기준", "",
          "- 치명 사항 0건이면 확정 가능, 1건 이상이면 확정 불가로 판정함",
          "- 중대 사항은 확정을 막지 않음. 처리 시점은 인수 측이 결정함", "",
          "| 등급 | 정의 | 판정 영향 |", "|---|---|---|",
          "| 치명 | 필수 CQ에 응답하지 못하거나 틀린 답을 내는 항목, 또는 Graphio 반입을"
          " 막는 항목 | 1건 이상이면 확정 불가 |",
          "| 중대 | 구조와 필수 CQ 응답에는 문제가 없으나 인수 측이 인지해야 하는 항목"
          " | 영향 없음 |", "",
          "- 규칙에 따라 비워 둔 항목은 등급을 부여하지 않고 4절에 건수만 기재함",
          "- 검증 리포트 7절(후속 조치)의 사항은 판정에 영향 없음",
          "- 5절에 미수행 검사가 있으면 판정은 수행한 검사 범위 내에서만 유효함"]

    p += ["", "## 2. 판정 결과", "",
          "| 항목 | 결과 |", "|---|---|",
          "| 판정 | **%s** |" % verdict,
          "| 치명 사항 | %d건 |" % len(critical),
          "| 중대 사항 | %d건 |" % len(major),
          "| 미수행 검사 | %s |" % ("%d건" % len(unchecked) if unchecked else "해당 없음"),
          "| 필수 CQ 응답 | %d건 중 %d건 응답 가능(전체 CQ %d건) |"
          % (req_total, req_yes, q["전체"]),
          "| 필수 CQ 기준 | %s |" % counted["필수 CQ 기준"]]
    if unchecked:
        p += ["", "- 미수행 검사 %d건이 있어 판정은 수행한 검사 범위 내에서만 유효함(5절 참조)"
              % len(unchecked)]

    p += ["", "## 3. 지적 사항", "", "### 3.1 치명 사항", ""]
    p += findings_table(critical)
    p += ["", "### 3.2 중대 사항", ""]
    p += findings_table(major)

    p += ["", "## 4. 조치 대상 외 항목", ""]
    rows = [list(r) for r in leave_alone(counted, stats, args)]
    if rows:
        p += ["- 규칙에 따라 비워 두었거나 다음 단계로 넘긴 항목임",
              "- 건수를 줄이기 위해 값을 임의로 채우지 않음",
              "- 조치 일정과 방법은 검증 리포트 7절(후속 조치)에 있음", ""]
    p += table(["항목", "건수", "참조 위치"], rows)

    p += ["", "## 5. 미수행 검사", ""]
    if unchecked:
        p += ["- 미수행 검사 항목은 판정에 반영되지 않았으므로 해당 범위의 지적 사항이 있을 수 있음", ""]
    p += table(["검사 항목", "미수행 사유"], [list(u) for u in unchecked])

    p += ["", "## 6. 후속 조치", ""]
    p += ["- %s" % s for s in follow_ups(critical, major, unchecked)]
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser(
        description="온톨로지 구조를 확정해도 되는지 판정한다. 치명이 0건이면 확정한다.")
    ap.add_argument("definition", help="온톨로지 정의 문서")
    ap.add_argument("report", help="온톨로지 검증 리포트")
    ap.add_argument("--required-grade", action="append", default=[], metavar="말",
                    help="등급 칸에서 필수로 볼 말. 여러 번 줄 수 있다. "
                         "주지 않으면 모든 CQ를 필수로 본다")
    ap.add_argument("--spec-errors", type=int, default=None, metavar="N",
                    help="Graphio 규격 검사 오류 건수")
    ap.add_argument("--spec-warnings", type=int, default=0, metavar="N",
                    help="Graphio 규격 검사 경고 건수")
    ap.add_argument("--spec-deferred", type=int, default=0, metavar="N",
                    help="Graphio 규격 검사 보류 건수")
    ap.add_argument("--spec-skipped", action="store_true",
                    help="규격 검사를 수행하지 못했다 (자매 스킬이 없을 때)")
    ap.add_argument("--convert-failed", action="store_true",
                    help="정의 문서가 Graphio 정의 파일로 옮겨지지 않았다")
    ap.add_argument("--manual-checked", action="store_true",
                    help="스킬이 짚는 세 항목(미사용 개념·속성, 가이드 위반, "
                         "입력 문서 간 불일치)을 모두 짚었다")
    ap.add_argument("--add-major", action="append", default=[], metavar="칸들",
                    help="스킬이 찾은 중대 사항 한 건. "
                         "'구분|지적 내용|조치 방안|조치 주체|근거[|주석]'. 여러 번 줄 수 있다. "
                         "구분은 %s 가운데 하나" % "·".join(MANUAL_KINDS))
    ap.add_argument("--warn-mark", default=None, metavar="기호",
                    help="가이드가 정한 경고 기호. 정의 문서 검사기에 그대로 넘긴다")
    ap.add_argument("--name", default=None, help="문서 제목에 쓸 이름")
    ap.add_argument("-o", "--out", default=None, metavar="파일",
                    help="판정 문서를 쓸 곳. 주지 않으면 화면에 낸다")
    args = ap.parse_args()

    for path in (args.definition, args.report):
        if not os.path.exists(path):
            print("파일이 없다: %s" % path, file=sys.stderr)
            return 2

    try:
        args.manual_findings = [parse_manual(raw) for raw in args.add_major]
        lines = open(args.report, encoding="utf-8").read().splitlines()
        critical, major, unchecked, counted, stats = judge(args, lines)
    except InputError as e:
        print("판정하지 않음: %s" % e, file=sys.stderr)
        print("검증 리포트나 옵션을 고친 뒤 다시 수행한다. 판정 문서는 쓰지 않았다.",
              file=sys.stderr)
        return 2

    text = report(args, lines, critical, major, unchecked, counted, stats)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("판정: %s   치명 %d건 · 중대 %d건 · 미수행 검사 %d건"
              % ("확정 불가" if critical else "확정 가능",
                 len(critical), len(major), len(unchecked)))
        print("썼다: %s" % args.out)
    else:
        print(text)
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
