#!/usr/bin/env python3
"""검사 규칙 목록 문서(references/검사-규칙.md)를 읽고 확인한다.

수집 스크립트와 판정 스크립트가 함께 쓴다. 2절 규칙 목록 표와 3절 규칙 설명 표만 읽는다.
두 절에는 표가 하나씩 있고, 머리글은 LIST_HEAD·DESC_HEAD 와 같아야 하며 칸 안에 세로줄이 없다.
문서 첫머리가 정한 확인 다섯 가지 가운데 하나라도 어긋나면 RuleError 를 낸다.

    import rule_catalog as rc      # 스크립트 폴더가 sys.path[0] 이라 그대로 읽힌다
    rules = rc.load()              # 스크립트 폴더 기준 ../references/검사-규칙.md
    rules.get("DOC-04")["등급"]    # 두 표의 칸을 합친 dict
    rules.order("SPC-01")          # 2절 표 차례(0부터). '규칙 번호 차례'는 이 차례다
    rules.skill_rules()            # 스킬이 검증 리포트 4.2절에 적는 규칙
    rc.COLLECTED, rc.JUDGED        # 수집 스크립트가 내는 규칙, 판정 스크립트가 5·6절과 2절에서 정하는 규칙

스크립트 규칙을 가르는 기준은 이 파일의 COLLECTED·JUDGED 하나다. 두 스크립트는 접두어로 가르지 않는다.
"""
import os
import re

from definition_index import split_row

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.normpath(os.path.join(HERE, "..", "references", "검사-규칙.md"))

LIST_HEAD = ("규칙", "이름", "등급", "탐지 방식", "외부 코드", "상태")
DESC_HEAD = ("규칙", "설명", "발생 경로 표기", "조치 지침", "기본 조치 주체", "기본 참고 자료")
GRADES = ("Error", "Warning", "Info")
STATES = ("사용", "사용하지 않음")
# 스크립트가 스스로 내는 규칙(규칙 목록 문서 첫머리의 목록). 목록에 없거나 쓰지 않게 되면 멈춘다.
# 나머지 '사용' 규칙은 스킬이 검증 리포트 4.2절에 적는다(skill_rules).
# COLLECTED 는 수집 스크립트가 4.2절 스크립트 행으로 내는 규칙, JUDGED 는 판정 스크립트가 5·6절과
# 2절에서 정하는 규칙이다. 4.2절에 JUDGED 규칙이 있으면 판정 스크립트가 멈춘다.
COLLECTED = (tuple("DOC-%02d" % n for n in range(1, 12)) + ("CNV-01",)
             + tuple("SPC-%02d" % n for n in range(1, 4)))
JUDGED = ("CQS-01", "CQS-02", "CQS-03", "CQS-04", "CQS-06") + tuple("MAP-%02d" % n for n in range(1, 5))
SCRIPT_RULES = COLLECTED + JUDGED
RULE_RE = re.compile(r"[A-Z]{3}-\d{2}")


class RuleError(Exception):
    """규칙 목록 문서를 읽지 못했거나 확인에 걸렸다."""


class Catalog:
    """규칙 목록. rules 는 2절 표 차례의 규칙 번호다."""

    def __init__(self, path, rows):
        self.path = path
        self.rules = [r["규칙"] for r in rows]
        self._rows = {r["규칙"]: r for r in rows}

    def __contains__(self, rule):
        return rule in self._rows

    def get(self, rule):
        """두 표의 칸을 합친 dict. 목록에 없으면 KeyError."""
        return self._rows[rule]

    def order(self, rule):
        """2절 표 차례. 목록에 없으면 KeyError."""
        return self._rows[rule]["차례"]

    def skill_rules(self):
        """스킬이 검증 리포트 4.2절에 적는 규칙. '사용' 규칙에서 스크립트가 스스로 내는 규칙을 뺀 것이다.

        탐지 방식 칸의 글자로 가리지 않는다. 그 칸은 판정 문서와 검증 리포트에 옮겨지는 말이라 바뀔 수 있기 때문이다.
        """
        return [r for r in self.rules if self._rows[r]["상태"] == "사용" and r not in SCRIPT_RULES]


def _table(lines, word, head):
    """제목에 word 가 든 ## 절의 표 하나를 읽는다. [(줄, {머리글: 칸})]"""
    marks = [i for i, ln in enumerate(lines) if re.match(r"^##\s+(?!#)", ln)]
    found = [i for i in marks if word in lines[i]]
    if len(found) != 1:
        raise RuleError("제목에 '%s'가 든 절이 %d개임. 하나여야 함" % (word, len(found)))
    start = found[0] + 1
    end = next((i for i in marks if i > found[0]), len(lines))
    tables, cur = [], None
    for i in range(start, end):
        if lines[i].strip().startswith("|"):
            if cur is None:
                cur = []
                tables.append(cur)
            cur.append(i)
        else:
            cur = None
    if len(tables) != 1:
        raise RuleError("'%s' 절에 표가 %d개임. 하나여야 함" % (word, len(tables)))
    rows = tables[0]
    if tuple(split_row(lines[rows[0]])) != head:
        raise RuleError("'%s' 표 머리글이 정해진 꼴과 다름(%d줄). 머리글: %s"
                        % (word, rows[0] + 1, " | ".join(head)))
    if len(rows) < 2 or not all(re.fullmatch(r":?-+:?", c) for c in split_row(lines[rows[1]])):
        raise RuleError("'%s' 표 머리글 아래 구분 줄이 없음(%d줄)" % (word, rows[0] + 2))
    out = []
    for i in rows[2:]:
        cells = split_row(lines[i])
        if len(cells) != len(head):
            raise RuleError("'%s' 표 %d줄의 칸 수가 머리글과 다름(칸 %d개, 머리글 %d개)"
                            % (word, i + 1, len(cells), len(head)))
        out.append((i + 1, dict(zip(head, cells))))
    return out


def load(path=DEFAULT_PATH):
    """규칙 목록 문서를 읽고 확인한다. 어긋나면 RuleError."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        raise RuleError("규칙 목록 문서가 없음: %s" % path)
    except (OSError, UnicodeDecodeError) as e:
        raise RuleError("규칙 목록 문서를 읽지 못함: %s (%s)" % (path, e))

    listed = _table(lines, "규칙 목록", LIST_HEAD)
    described = _table(lines, "규칙 설명", DESC_HEAD)

    seen = set()
    for ln, row in listed:
        rule = row["규칙"]
        if not RULE_RE.fullmatch(rule):
            raise RuleError("규칙 번호가 'ABC-01' 꼴이 아님: '%s'(%d줄)" % (rule, ln))
        if rule in seen:
            raise RuleError("규칙 번호가 겹침: %s(%d줄)" % (rule, ln))
        seen.add(rule)
        if row["등급"] not in GRADES:
            raise RuleError("%s 등급 값이 %s 가운데 하나가 아님: '%s'(%d줄)"
                            % (rule, "·".join(GRADES), row["등급"], ln))
        if row["상태"] not in STATES:
            raise RuleError("%s 상태 값이 %s 가운데 하나가 아님: '%s'(%d줄)"
                            % (rule, "·".join(STATES), row["상태"], ln))
    state = {row["규칙"]: row["상태"] for _, row in listed}
    missing = [r for r in SCRIPT_RULES if state.get(r) != "사용"]
    if missing:
        raise RuleError("스크립트가 내는 규칙이 없거나 상태가 '사용'이 아님: %s" % ", ".join(missing))
    if [row["규칙"] for _, row in listed] != [row["규칙"] for _, row in described]:
        raise RuleError("2절과 3절의 규칙 번호가 같은 차례로 같지 않음")

    rows = []
    for k, ((_, a), (_, b)) in enumerate(zip(listed, described)):
        row = dict(a)
        row.update(b)
        row["차례"] = k
        rows.append(row)
    return Catalog(path, rows)
