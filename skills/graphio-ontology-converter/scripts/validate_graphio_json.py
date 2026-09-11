#!/usr/bin/env python3
"""graphio JSON 온톨로지 정의 파일 검증기.

표준 라이브러리만 쓴다. 폐쇄망에서도 그대로 돈다.

    python3 validate_graphio_json.py ontology.json
    python3 validate_graphio_json.py ontology.json --json     # 기계가 읽는 형태
    python3 validate_graphio_json.py ontology.json --strict   # 보류도 실패로 본다

찾은 것을 세 등급으로 나눈다.

  오류(error)   graphio 규격 위반. 반입해도 적용이 막힌다. 반드시 고친다.
  경고(warning) 규격은 통과하지만 의도를 확인해야 한다.
  보류(deferred) 파일만으로 끝낼 수 없는 항목. 대상 환경에서 사람이 마무리한다.

종료 코드: 0 오류 없음, 1 오류 있음(--strict 면 보류도), 2 파일을 읽지 못함.
"""

import argparse
import json
import re
import sys
from collections import Counter

NAME_RE = re.compile(r"^[a-zA-Z가-힣][a-zA-Z0-9가-힣_]{0,49}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

DATA_TYPES = ("INTEGER", "TEXT", "DATETIME", "FLOAT8", "BOOLEAN", "VECTOR", "UNKNOWN")
DIRECTS = ("UNIDIRECTIONAL", "REVERSE_DIRECTIONAL", "BIDIRECTIONAL")
META_KINDS = ("CUSTOM", "PARSING", "DOC_TYPE")
TOP_KEYS = ("objectTypes", "linkTypes", "metaTypes", "objectMapping")

OT_SYSTEM_KEYS = ("id", "owner", "ownerId", "objectTypeGroupIds", "projectIds",
                  "status", "metaTypeIds", "metaTypeProperties")
LT_SYSTEM_KEYS = ("id", "ownerId", "sourceObjectTypeId", "targetObjectTypeId",
                  "projectIds", "status")

ERROR, WARNING, DEFERRED = "error", "warning", "deferred"
GRADE_LABEL = {ERROR: "오류", WARNING: "경고", DEFERRED: "보류"}


class Report:
    def __init__(self):
        self.findings = []

    def add(self, grade, code, path, message, fix=None, target=None):
        self.findings.append({
            "grade": grade, "code": code, "path": path,
            "target": target, "message": message, "fix": fix,
        })

    def count(self, grade):
        return sum(1 for f in self.findings if f["grade"] == grade)


def as_text(value):
    """문자열일 때만 문자열로 돌려준다. None·"null"·숫자를 구분해 다루기 위한 것."""
    return value if isinstance(value, str) else None


def as_flag(node, key, aliases=()):
    """boolean 필드를 읽는다. 반입이 받아 주는 별칭도 함께 읽되 쓴 별칭을 돌려준다."""
    if isinstance(node.get(key), bool):
        return node[key], None
    for alias in aliases:
        if isinstance(node.get(alias), bool):
            return node[alias], alias
    return False, None


def suggest_name(raw):
    """이름 형식을 어긴 문자열에서 쓸 수 있는 이름 후보를 만든다."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    cleaned = re.sub(r"[^a-zA-Z0-9가-힣_]", "_", raw.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")[:50]
    if not cleaned:
        return None
    return cleaned if NAME_RE.match(cleaned) else cleaned + " (앞에 영문·한글 한 자를 더 붙여야 한다)"


# ---------------------------------------------------------------- 최상위 구조

def check_top(doc, rep):
    if not isinstance(doc, dict):
        rep.add(ERROR, "GOS50001", "$", "최상위가 객체가 아니다.",
                "objectTypes·linkTypes·metaTypes·objectMapping 네 키를 가진 객체로 감싼다.")
        return False

    for key in doc:
        if key.startswith("__"):
            rep.add(WARNING, "GOS61337", key,
                    "내부 마커 키다. 반입 과정에서 제거된다.",
                    "새로 만드는 파일에서는 지운다.")
        elif key not in TOP_KEYS:
            rep.add(ERROR, "GOS50001", key,
                    "허용되지 않는 최상위 키다. 이 키가 있으면 반입 자체가 거부된다.",
                    "네 키(objectTypes·linkTypes·metaTypes·objectMapping)만 남긴다.")

    ok = True
    for key in ("objectTypes", "linkTypes"):
        if not isinstance(doc.get(key), list):
            rep.add(ERROR, "GOS50001", key, "필수 배열이 없거나 배열이 아니다.",
                    "값이 없어도 빈 배열([])로 둔다.")
            ok = False
    for key in ("metaTypes", "objectMapping"):
        if key in doc and not isinstance(doc[key], list):
            rep.add(ERROR, "GOS50001", key, "배열이 아니다.", "배열로 바꾸거나 키를 지운다.")
            ok = False

    if ok and not doc.get("objectTypes") and not doc.get("linkTypes"):
        rep.add(ERROR, "GOS61203", "$",
                "objectTypes 와 linkTypes 가 모두 0건이다. 반입은 되지만 적용이 거부된다.",
                "Object Type 을 최소 1건 담는다.")
    return ok


# --------------------------------------------------------------- Object Type

def check_object_types(object_types, rep):
    """이름 -> 속성 정보 표와 식별 속성 표를 만들어 돌려준다. 뒤 단계의 교차 검사가 쓴다."""
    catalog = {}
    pk_by_ot = {}
    seen = Counter()

    for i, ot in enumerate(object_types):
        path = "objectTypes[%d]" % i
        if not isinstance(ot, dict):
            rep.add(ERROR, "GOS50001", path, "Object Type 항목이 객체가 아니다.")
            continue

        name = as_text(ot.get("name"))
        label = name or "(이름 없음)"
        if not name:
            rep.add(ERROR, "GOS61002", path + ".name", "이름이 없다.",
                    "문서의 ### 제목에 개념 이름을 적는다.")
        elif not NAME_RE.match(name):
            hint = suggest_name(name)
            rep.add(ERROR, "GOS61002", path + ".name",
                    "이름 형식 위반: %r. 영문·한글로 시작하고 영문·숫자·한글·밑줄만, 50자까지." % name,
                    ("문서에서 %s 로 고친다." % hint) if hint else "문서에서 이름을 다시 정한다.", label)
        else:
            seen[name] += 1

        for key in OT_SYSTEM_KEYS:
            if key in ot:
                rep.add(WARNING, "-", "%s.%s" % (path, key),
                        "시스템 값이다. 파일에 넣어도 반입 과정에서 제거된다.",
                        "키를 지운다.", label)

        desc = as_text(ot.get("description"))
        if desc and len(desc) > 5000:
            rep.add(ERROR, "GOS61003", path + ".description",
                    "설명이 %d자다. 5000자를 넘을 수 없다." % len(desc), "문서에서 5000자 이내로 줄인다.", label)

        color = as_text(ot.get("colorCode"))
        if not color or not color.strip():
            rep.add(ERROR, "GOS61004", path + ".colorCode", "화면 색상이 없다.",
                    "문서의 - 색: 줄에 #RRGGBB 꼴로 적는다.", label)
        elif not COLOR_RE.match(color):
            rep.add(WARNING, "-", path + ".colorCode",
                    "색상이 #RRGGBB 꼴이 아니다: %r" % color, "#RRGGBB 로 맞춘다.", label)

        props = ot.get("properties")
        if not isinstance(props, list) or not props:
            rep.add(ERROR, "GOS61005", path + ".properties", "속성이 0건이다. 1건 이상 있어야 한다.",
                    "문서에 속성 표를 적는다.", label)
            catalog[name or label] = {}
            pk_by_ot[name or label] = set()
            continue

        prop_types, prop_names, order_nos = {}, Counter(), []
        titles, pks = [], []

        for j, prop in enumerate(props):
            ppath = "%s.properties[%d]" % (path, j)
            if not isinstance(prop, dict):
                rep.add(ERROR, "GOS50001", ppath, "속성 항목이 객체가 아니다.", None, label)
                continue

            pname = as_text(prop.get("name"))
            if not pname:
                rep.add(ERROR, "-", ppath + ".name", "속성 이름이 없다.", "속성 이름을 넣는다.", label)
            else:
                prop_names[pname] += 1
                prop_types[pname] = prop.get("dataType")

            dtype = prop.get("dataType")
            if dtype not in DATA_TYPES:
                rep.add(ERROR, "-", ppath + ".dataType",
                        "데이터 타입이 %r 이다. 7종 중 하나여야 한다." % (dtype,),
                        "INTEGER·TEXT·DATETIME·FLOAT8·BOOLEAN·VECTOR·UNKNOWN 중에서 고른다.", label)

            order = prop.get("orderNo")
            if not isinstance(order, int) or isinstance(order, bool) or order < 1:
                rep.add(ERROR, "-", ppath + ".orderNo",
                        "표시 순서가 %r 이다. 1 이상의 정수여야 한다." % (order,),
                        "1부터 차례로 붙인다.", label)
            else:
                order_nos.append(order)

            pdesc = as_text(prop.get("description"))
            if pdesc and len(pdesc) > 5000:
                rep.add(WARNING, "-", ppath + ".description",
                        "설명이 %d자다. 저장 한계인 5000자를 넘는다." % len(pdesc), "줄인다.", label)

            is_title, title_alias = as_flag(prop, "isTitleKey", ("title",))
            is_pk, pk_alias = as_flag(prop, "isPrimaryKey", ("pk", "isPkKey"))
            for alias, canonical in ((title_alias, "isTitleKey"), (pk_alias, "isPrimaryKey")):
                if alias:
                    rep.add(WARNING, "-", "%s.%s" % (ppath, alias),
                            "반입이 읽어 주는 별칭이지만 규격 키가 아니다.",
                            "%s 로 바꿔 쓴다." % canonical, label)
            if is_title:
                titles.append(pname or "(이름 없음)")
            if is_pk:
                pks.append(pname or "(이름 없음)")

        for pname, n in prop_names.items():
            if n > 1:
                rep.add(ERROR, "GOS61010", "%s.properties[name=%s]" % (path, pname),
                        "속성 이름이 %d번 나온다. 한 Object Type 안에서 유일해야 한다." % n,
                        "문서에서 속성 이름을 갈라 준다.", label)

        dup_orders = [o for o, n in Counter(order_nos).items() if n > 1]
        if dup_orders:
            rep.add(ERROR, "-", path + ".properties[].orderNo",
                    "표시 순서가 겹친다: %s. 저장 단계의 유일 제약을 어긴다." % sorted(dup_orders),
                    "문서의 표에서 행을 정리한다.", label)
        elif order_nos and sorted(order_nos) != list(range(1, len(order_nos) + 1)):
            rep.add(WARNING, "-", path + ".properties[].orderNo",
                    "표시 순서가 1부터 연속이 아니다: %s" % sorted(order_nos),
                    "1..%d 로 다시 붙인다." % len(order_nos), label)

        if len(titles) == 0:
            rep.add(ERROR, "GOS61006", path + ".properties",
                    "대표 표시 속성(isTitleKey)이 없다. 정확히 1개 있어야 한다.",
                    "문서의 Title 칸에 O 를 정확히 하나 적는다.", label)
        elif len(titles) > 1:
            rep.add(ERROR, "GOS61007", path + ".properties",
                    "대표 표시 속성이 %d개다(%s). 정확히 1개여야 한다." % (len(titles), ", ".join(titles)),
                    "문서에서 Title 칸의 O 를 하나만 남긴다.", label)

        if len(pks) > 1:
            rep.add(ERROR, "GOS61008", path + ".properties",
                    "식별 속성(isPrimaryKey)이 %d개다(%s). 1개까지만 쓸 수 있다." % (len(pks), ", ".join(pks)),
                    "문서에서 PK 칸의 O 를 하나만 남긴다. 복합키라면 비운다.", label)

        catalog[name or label] = prop_types
        pk_by_ot[name or label] = {p for p in pks if p}

    for name, n in seen.items():
        if n > 1:
            rep.add(ERROR, "GOS61011", "objectTypes[name=%s]" % name,
                    "Object Type 이름이 %d번 나온다. 파일 안에서 유일해야 한다." % n,
                    "문서에서 한쪽 이름을 바꾼다.", name)
    return catalog, pk_by_ot


# ----------------------------------------------------------------- Link Type

def check_link_types(link_types, catalog, pk_by_ot, rep):
    signatures = Counter()
    by_name = {}

    for i, lt in enumerate(link_types):
        path = "linkTypes[%d]" % i
        if not isinstance(lt, dict):
            rep.add(ERROR, "GOS50001", path, "Link Type 항목이 객체가 아니다.")
            continue

        name = as_text(lt.get("name"))
        label = name or "(이름 없음)"
        if not name:
            rep.add(ERROR, "GOS61102", path + ".name", "관계 이름이 없다.",
                    "문서의 관계 이름 칸을 채운다.")

        for key in LT_SYSTEM_KEYS:
            if key in lt:
                rep.add(WARNING, "-", "%s.%s" % (path, key),
                        "시스템 값이다. 파일에 넣어도 반입 과정에서 제거된다.", "키를 지운다.", label)

        desc = as_text(lt.get("description"))
        if desc and len(desc) > 5000:
            rep.add(WARNING, "-", path + ".description",
                    "설명이 %d자다. 저장 한계인 5000자를 넘는다." % len(desc), "줄인다.", label)

        direct = lt.get("direct")
        if direct is None:
            rep.add(ERROR, "GOS61103", path + ".direct", "관계 방향이 없다.",
                    "문서의 방향 칸에 UNIDIRECTIONAL·REVERSE_DIRECTIONAL·BIDIRECTIONAL 중 하나를 적는다.", label)
        elif direct not in DIRECTS:
            rep.add(ERROR, "GOS61103", path + ".direct", "관계 방향이 %r 이다." % (direct,),
                    "UNIDIRECTIONAL·REVERSE_DIRECTIONAL·BIDIRECTIONAL 중에서 고른다.", label)

        src = as_text(lt.get("sourceObjectTypeName"))
        tgt = as_text(lt.get("targetObjectTypeName"))
        for role, value in (("source", src), ("target", tgt)):
            if not value:
                rep.add(ERROR, "GOS61107", "%s.%sObjectTypeName" % (path, role),
                        "%s Object Type 이 비어 있다." % role,
                        "문서의 Object Type 절에 있는 이름을 적는다.", label)
            elif value not in catalog:
                rep.add(ERROR, "GOS61107", "%s.%sObjectTypeName" % (path, role),
                        "%r 은 이 파일의 objectTypes 에 없다. 관계는 파일 안의 Object Type 으로만 풀린다." % value,
                        "문서의 Object Type 절에 그 개념을 적거나 이름을 맞춘다.", label)

        if src and tgt and src == tgt:
            rep.add(ERROR, "GOS61106", path,
                    "자기 참조 관계다(%s → %s). 규격이 막는다." % (src, tgt),
                    "문서에서 그 관계를 지우고 상위 식별자를 속성으로만 적는다. 규격이 자기 참조를 막는다.", label)

        pairs = (("source", src, as_text(lt.get("sourcePropertyName")), "GOS61108", "GOS61109"),
                 ("target", tgt, as_text(lt.get("targetPropertyName")), "GOS61110", "GOS61111"))
        for role, ot_name, prop_name, missing_code, unknown_code in pairs:
            field = "%s.%sPropertyName" % (path, role)
            if not prop_name:
                rep.add(ERROR, missing_code, field,
                        "%s 쪽 조인 속성이 없다. 관계 이름만으로는 링크가 성립하지 않는다." % role,
                        "문서의 %s 속성 칸을 채운다. 양쪽 값이 같아야 연결된다." % role, label)
            elif ot_name in catalog and prop_name not in catalog[ot_name]:
                rep.add(ERROR, unknown_code, field,
                        "%r 은 %s 의 속성이 아니다." % (prop_name, ot_name),
                        "문서에서 %s 에 그 속성을 적거나 이름을 맞춘다." % ot_name, label)

        sp, tp = as_text(lt.get("sourcePropertyName")), as_text(lt.get("targetPropertyName"))
        if src in catalog and tgt in catalog and sp in catalog.get(src, {}) and tp in catalog.get(tgt, {}):
            s_type, t_type = catalog[src][sp], catalog[tgt][tp]
            if s_type != t_type:
                rep.add(WARNING, "-", path,
                        "조인 속성의 데이터 타입이 다르다(%s.%s=%s, %s.%s=%s). 값이 맞지 않아 관계가 비어 있을 수 있다."
                        % (src, sp, s_type, tgt, tp, t_type),
                        "문서에서 양쪽 타입을 맞추거나 조인 속성을 바꾼다.", label)

        # target 쪽 조인 속성 값이 반복되면 관계가 의도한 한 건을 넘어 퍼진다.
        # 규격은 이것을 막지 않고 반입도 통과하므로 문서를 보고 확인해야 한다.
        if tgt in catalog and tp in catalog.get(tgt, {}):
            target_pks = pk_by_ot.get(tgt) or set()
            if not target_pks:
                rep.add(WARNING, "-", path + ".targetPropertyName",
                        "%s 에 식별 속성이 없어 %r 값이 유일한지 알 수 없다. 값이 반복되면 관계가 의도한 한 건을 넘어 퍼진다."
                        % (tgt, tp),
                        "문서가 그 값이 유일하다고 말하는지 확인한다. 아니면 리포트 5절에 적는다.", label)
            elif tp not in target_pks:
                rep.add(WARNING, "-", path + ".targetPropertyName",
                        "%r 은 %s 의 식별 속성(%s)이 아니다. 값이 반복되면 관계가 의도한 한 건을 넘어 퍼진다."
                        % (tp, tgt, ", ".join(sorted(target_pks))),
                        "문서에 유일한 속성이 있으면 그것으로 조인한다. 없으면 리포트 5절에 적는다.", label)

        sig = (name, src, sp, tgt, tp, direct)
        signatures[sig] += 1
        if name:
            by_name.setdefault(name, set()).add((src, tgt))

    for sig, n in signatures.items():
        if n > 1:
            rep.add(ERROR, "GOS61105", "linkTypes[name=%s]" % (sig[0],),
                    "이름·양끝·조인 속성·방향이 모두 같은 Link Type 이 %d건이다." % n,
                    "중복을 지운다.", sig[0])

    for name, endpoints in by_name.items():
        if len(endpoints) > 1:
            rep.add(WARNING, "GOS61330", "linkTypes[name=%s]" % name,
                    "같은 이름으로 양끝이 다른 관계가 %d건이다. 허용되지만 화면에서 구분되지 않는다." % len(endpoints),
                    "문서에서 구분되는 이름으로 갈라 준다.", name)


# ----------------------------------------------------------------- Meta Type

def check_meta_types(meta_types, rep):
    catalog = {}
    seen = Counter()

    for i, mt in enumerate(meta_types):
        path = "metaTypes[%d]" % i
        if not isinstance(mt, dict):
            rep.add(ERROR, "GOS50001", path, "Meta Type 항목이 객체가 아니다.")
            continue

        name = as_text(mt.get("name"))
        label = name or "(이름 없음)"
        if not name:
            rep.add(ERROR, "-", path + ".name", "Meta Type 이름이 없다.",
                    "대상 환경에 게시된 Meta Type 이름을 그대로 적는다.")
        else:
            seen[name] += 1

        kind = mt.get("metaTypeKind")
        if kind is not None and kind not in META_KINDS:
            rep.add(ERROR, "-", path + ".metaTypeKind", "종류가 %r 이다." % (kind,),
                    "CUSTOM·PARSING·DOC_TYPE 중에서 고른다.", label)

        props = mt.get("properties")
        prop_types, prop_names = {}, Counter()
        if isinstance(props, list):
            for j, prop in enumerate(props):
                ppath = "%s.properties[%d]" % (path, j)
                if not isinstance(prop, dict):
                    rep.add(ERROR, "GOS50001", ppath, "컬럼 항목이 객체가 아니다.", None, label)
                    continue
                pname = as_text(prop.get("name"))
                if not pname:
                    rep.add(ERROR, "-", ppath + ".name", "컬럼 이름이 없다.",
                            "대상 환경 Meta Type 의 컬럼 이름을 그대로 적는다.", label)
                else:
                    prop_names[pname] += 1
                    prop_types[pname] = prop.get("dataType")
                if prop.get("dataType") not in DATA_TYPES:
                    rep.add(ERROR, "-", ppath + ".dataType",
                            "데이터 타입이 %r 이다." % (prop.get("dataType"),),
                            "7종 중에서 고른다.", label)
                pdesc = as_text(prop.get("description"))
                if pdesc and len(pdesc) > 1000:
                    rep.add(WARNING, "-", ppath + ".description",
                            "설명이 %d자다. Meta Type 컬럼 설명은 1000자까지다." % len(pdesc), "줄인다.", label)
            for pname, n in prop_names.items():
                if n > 1:
                    rep.add(ERROR, "-", "%s.properties[name=%s]" % (path, pname),
                            "컬럼 이름이 %d번 나온다." % n, "한 Meta Type 안에서 유일하게 만든다.", label)
        elif props is not None:
            rep.add(ERROR, "GOS50001", path + ".properties", "배열이 아니다.", "배열로 바꾼다.", label)

        catalog[name or label] = prop_types

    for name, n in seen.items():
        if n > 1:
            rep.add(ERROR, "GOS61018", "metaTypes[name=%s]" % name,
                    "Meta Type 이름이 %d번 나온다. 파일 안에서 유일해야 한다." % n, "중복을 지운다.", name)
    return catalog


# ------------------------------------------------------------- Object Mapping

def check_object_mapping(mappings, ot_catalog, mt_catalog, has_meta_block, rep):
    pairs = Counter()
    mapped_ots, used_mts = set(), set()

    for i, om in enumerate(mappings):
        path = "objectMapping[%d]" % i
        if not isinstance(om, dict):
            rep.add(ERROR, "GOS50001", path, "Object Mapping 항목이 객체가 아니다.")
            continue

        ot_name = as_text(om.get("objectTypeName"))
        mt_name = as_text(om.get("metaTypeName"))
        label = "%s ← %s" % (ot_name or "?", mt_name or "?")

        if not ot_name:
            rep.add(ERROR, "GOS61021", path + ".objectTypeName", "연결할 Object Type 이름이 없다.",
                    "이 파일의 objectTypes 에 있는 이름을 넣는다.")
        elif ot_name not in ot_catalog:
            rep.add(ERROR, "GOS61021", path + ".objectTypeName",
                    "%r 은 이 파일의 objectTypes 에 없다. 반입 시 이 항목은 조용히 버려진다." % ot_name,
                    "문서에서 이름을 맞추거나 그 절을 지운다.", label)
        else:
            mapped_ots.add(ot_name)

        if not mt_name:
            rep.add(ERROR, "-", path + ".metaTypeName", "연결할 Meta Type 이름이 없다.",
                    "대상 환경에 게시된 Meta Type 이름을 적는다.", label)
        else:
            used_mts.add(mt_name)
            if has_meta_block and mt_name not in mt_catalog:
                rep.add(ERROR, "-", path + ".metaTypeName",
                        "%r 이 metaTypes 블록에 없다. 파일 안에서 대조할 수 없다." % mt_name,
                        "문서의 Meta Type 절에 같은 이름으로 적는다.", label)

        if ot_name and mt_name:
            pairs[(ot_name, mt_name)] += 1

        pms = om.get("propertyMappings")
        if not isinstance(pms, list) or not pms:
            rep.add(ERROR, "GOS61016", path + ".propertyMappings",
                    "속성 매핑이 0건이다. 반입은 되지만 적용이 막힌다.",
                    "문서의 Object Mapping 절에 속성 매핑 표를 적는다.", label)
            continue

        ot_props = ot_catalog.get(ot_name, {})
        mt_props = mt_catalog.get(mt_name, {})
        seen_ot_props = Counter()

        for j, pm in enumerate(pms):
            ppath = "%s.propertyMappings[%d]" % (path, j)
            if not isinstance(pm, dict):
                rep.add(ERROR, "GOS50001", ppath, "속성 매핑 항목이 객체가 아니다.", None, label)
                continue

            otp = as_text(pm.get("objectTypePropertyName"))
            mtp = as_text(pm.get("metaTypePropertyName"))

            if not otp:
                rep.add(ERROR, "-", ppath + ".objectTypePropertyName", "Object Type 속성 이름이 없다.",
                        "연결할 속성 이름을 넣는다.", label)
            else:
                seen_ot_props[otp] += 1
                if ot_name in ot_catalog and otp not in ot_props:
                    rep.add(ERROR, "GOS61022", ppath + ".objectTypePropertyName",
                            "%r 은 %s 의 속성이 아니다." % (otp, ot_name),
                            "문서에서 속성 이름을 맞춘다.", label)

            if not mtp:
                rep.add(ERROR, "-", ppath + ".metaTypePropertyName", "Meta Type 컬럼 이름이 없다.",
                        "연결할 컬럼 이름을 넣는다.", label)
            elif mt_name in mt_catalog and mt_props and mtp not in mt_props:
                rep.add(ERROR, "GOS61015", ppath + ".metaTypePropertyName",
                        "%r 은 %s 의 컬럼이 아니다." % (mtp, mt_name),
                        "문서에서 컬럼 이름을 맞춘다.", label)

            if otp in ot_props and mtp in mt_props and ot_props[otp] != mt_props[mtp]:
                rep.add(WARNING, "-", ppath,
                        "타입이 다르다(%s.%s=%s, %s.%s=%s)."
                        % (ot_name, otp, ot_props[otp], mt_name, mtp, mt_props[mtp]),
                        "의도한 변환이면 그대로 두고, 아니면 한쪽 타입을 맞춘다.", label)

        for otp, n in seen_ot_props.items():
            if n > 1:
                rep.add(ERROR, "GOS61020", "%s.propertyMappings[%s]" % (path, otp),
                        "%r 이 %d번 연결됐다. 한 Object Mapping 안에서 유일해야 한다." % (otp, n),
                        "문서에서 하나만 남긴다.", label)

    for (ot_name, mt_name), n in pairs.items():
        if n > 1:
            rep.add(ERROR, "GOS61019", "objectMapping[%s, %s]" % (ot_name, mt_name),
                    "같은 (Object Type, Meta Type) 쌍이 %d건이다." % n,
                    "문서에서 한 건으로 합친다.", "%s ← %s" % (ot_name, mt_name))

    return mapped_ots, used_mts


# ---------------------------------------------------------------- 남은 숙제

def check_deferred(ot_catalog, mt_catalog, mapped_ots, used_mts, rep):
    unmapped = [name for name in ot_catalog if name not in mapped_ots]
    if unmapped:
        rep.add(DEFERRED, "GOS61017", "objectMapping",
                "데이터 연결이 없는 Object Type %d건: %s" % (len(unmapped), ", ".join(sorted(unmapped))),
                "적용하려면 대상 환경에서 Meta Type 을 연결해야 한다. 문서에 데이터 정보가 없었다면 정상이다.")

    for name in mt_catalog:
        if name not in used_mts:
            rep.add(WARNING, "GOS61337", "metaTypes[name=%s]" % name,
                    "objectMapping 에서 참조되지 않는다. 반입 과정에서 제거된다.",
                    "문서에서 그 Meta Type 절을 지우거나 Object Mapping 절을 적는다.", name)

    if mt_catalog:
        rep.add(DEFERRED, "GOS61014", "metaTypes",
                "Meta Type %d건은 반입으로 만들어지지 않는다. 같은 이름·같은 컬럼 이름으로 대상 환경에 먼저 있어야 한다."
                % len(mt_catalog),
                "이름이 없으면 GOS61014, 컬럼이 없으면 GOS61015, 같은 이름이 둘 이상이면 GOS61023 이 붙는다.")


# --------------------------------------------------------------------- 출력

def render(path, doc, rep):
    lines = ["graphio JSON 검증 — %s" % path, ""]
    if isinstance(doc, dict):
        lines.append("  Object Type %d개 · Link Type %d개 · Meta Type %d개 · Object Mapping %d개" % (
            len(doc.get("objectTypes") or []), len(doc.get("linkTypes") or []),
            len(doc.get("metaTypes") or []), len(doc.get("objectMapping") or [])))
        lines.append("")

    tails = {ERROR: "반드시 고친다", WARNING: "의도를 확인한다", DEFERRED: "대상 환경에서 마무리한다"}
    for grade in (ERROR, WARNING, DEFERRED):
        found = [f for f in rep.findings if f["grade"] == grade]
        if not found:
            continue
        lines.append("%s %d건 (%s)" % (GRADE_LABEL[grade], len(found), tails[grade]))
        for f in found:
            head = "  [%s] %s" % (f["code"], f["path"]) if f["code"] != "-" else "  %s" % f["path"]
            if f["target"]:
                head += "  · %s" % f["target"]
            lines.append(head)
            lines.append("      %s" % f["message"])
            if f["fix"]:
                lines.append("      → %s" % f["fix"])
        lines.append("")

    n_err, n_warn, n_def = rep.count(ERROR), rep.count(WARNING), rep.count(DEFERRED)
    if n_err:
        lines.append("결과: 오류 %d건. 고친 뒤 다시 돌린다." % n_err)
    else:
        lines.append("결과: 오류 없음 (경고 %d건, 보류 %d건). 보류 항목은 설계 리포트에 옮겨 적는다."
                     % (n_warn, n_def))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="graphio JSON 온톨로지 정의 파일을 검증한다.")
    ap.add_argument("file", help="검증할 .json 파일")
    ap.add_argument("--json", action="store_true", dest="as_json", help="결과를 JSON 으로 낸다")
    ap.add_argument("--strict", action="store_true", help="보류 항목도 실패로 본다")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8") as fp:
            doc = json.load(fp)
    except FileNotFoundError:
        print("파일을 찾을 수 없다: %s" % args.file, file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print("JSON 파싱 실패 (GOS20009): %s" % exc, file=sys.stderr)
        return 2

    rep = Report()
    if check_top(doc, rep):
        ot_catalog, pk_by_ot = check_object_types(doc.get("objectTypes") or [], rep)
        check_link_types(doc.get("linkTypes") or [], ot_catalog, pk_by_ot, rep)
        mt_catalog = check_meta_types(doc.get("metaTypes") or [], rep)
        mapped_ots, used_mts = check_object_mapping(
            doc.get("objectMapping") or [], ot_catalog, mt_catalog,
            bool(doc.get("metaTypes")), rep)
        check_deferred(ot_catalog, mt_catalog, mapped_ots, used_mts, rep)

    if args.as_json:
        print(json.dumps({
            "file": args.file,
            "counts": {
                "objectTypes": len(doc.get("objectTypes") or []) if isinstance(doc, dict) else 0,
                "linkTypes": len(doc.get("linkTypes") or []) if isinstance(doc, dict) else 0,
                "metaTypes": len(doc.get("metaTypes") or []) if isinstance(doc, dict) else 0,
                "objectMapping": len(doc.get("objectMapping") or []) if isinstance(doc, dict) else 0,
            },
            "summary": {g: rep.count(g) for g in (ERROR, WARNING, DEFERRED)},
            "findings": rep.findings,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(args.file, doc, rep))

    if rep.count(ERROR):
        return 1
    if args.strict and rep.count(DEFERRED):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
