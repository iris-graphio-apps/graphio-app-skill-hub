#!/usr/bin/env python3
"""검사 항목 No.1(정의 문서 검사)·No.2(서식 변환 검사)를 스크립트 셋으로 수행하고 결과를 검증 리포트 행으로 바꾼다.

정의 문서 검사기(check_design_doc.py)와 converter 스킬의 변환 스크립트·규격 검사기를 수행해
지적마다 규칙 번호, 외부 코드, 위치, 문제 설명, 발생 경로, 조치 방안, 조치 주체, 참고 자료를 채운다.
위치는 definition_index.py 로 정의 문서의 줄에 되돌리고, 문제 설명과 조치 방안은 이 파일의 변환표로
정한다. 조치 주체와 참고 자료는 references/검사-규칙.md 3절의 기본값이다.

    python3 collect_findings.py <온톨로지-정의.md> --converter <converter 스킬 폴더>
    python3 collect_findings.py <온톨로지-정의.md> --spec-skipped     # converter 스킬이 없을 때
    ... [--source <원천 구조 문서> ...] [--warn-mark ※] [--json]

검증 리포트 4.1 표의 No.1·No.2 행, 4.1 표 아래 자동 채움 주석, 4.2 지적 목록 표와 그 아래
수집 조건 주석을 낸다. 붙일 꼴은 [ ] 머리말 아래에 있고 머리말 줄은 붙이지 않는다.
스크립트 지적이 없으면 4.2 표 대신 '해당 없음' 한 줄을 낸다.

--json 이면 판정 스크립트가 읽는 꼴로 낸다. 판정 스크립트는 collect() 를 모듈로 불러도 같은 dict 를 받는다.

    검사 결과      4.1 표의 No.1·No.2 행 [{No., 검사 항목, 검사 대상, 결과, 지적 내용}]
    자동 채움 주석  4.1 표 아래 '※ No.2 자동 채움:' 줄 목록. 변환이 실패하면 비어 있다
    지적 목록      4.2 행 [{No., 규칙, 외부 코드, 위치, 문제 설명, 발생 경로, 조치 방안, 조치 주체, 참고 자료, 줄}].
                   값은 세로줄을 막지 않은 원문이고, 줄은 위치에 적은 줄 번호다
    수집 조건      {줄, 정의 문서, 경고 기호, 규격 검사, converter, 원천 구조 문서, 빌더}. 줄은 parse_condition() 으로 되푼다.
                   원천 구조 문서 경로는 작업 폴더 아래면 상대 경로로 적는다(shown_path)
    원천 구조 문서 대조  '수행'·'미수행(원천 구조 문서 미제공)'·'미수행(텍스트로 읽을 수 없는 형식)'
    통계           정의 문서 검사기의 통계('확인 필요 표기' 등). 판정 스크립트가 4절 건수에 쓴다
    건수           정의 문서 검사 등급별 건수, 서식 변환 검사 결과와 나누기 뒤·겹침 처리 전 건수, 겹쳐서 DOC 행으로 적은 건수
멈추면 {"수집됨": false, "까닭": …, "스킬 판본 문제": …} 를 낸다.

지적은 규칙 번호 차례(검사-규칙.md 2절 표 차례), 줄 번호, 발생 경로 차례로 둔다. 같은 입력이면
늘 같은 출력이다. 같은 결함을 두 검사가 함께 잡으면 검사-규칙.md 4절대로 DOC 행만 남긴다.

아래 경우에는 표 행을 내지 않고 멈춘다(종료 코드 2). 규칙 목록 문서 확인에 걸림, 정의 문서를 읽지
못함, 하위 스크립트가 예외로 끝나거나 JSON 을 내지 못함, converter 폴더에 두 스크립트가 없음,
--converter 와 --spec-skipped 를 함께 주거나 둘 다 주지 않음, 원천 구조 문서가 없거나 읽지 못함,
변환표에 없는 코드·메시지 꼴, 색인과 변환 스크립트가 정의 문서를 다르게 읽음, 정의 문서 위치로
되돌릴 수 없는 경로. 원천 구조 문서가 UTF-8 텍스트가 아니면 멈추지 않고 '대조 불가(형식)'로 적는다.
하나라도 그러면 원천 구조 문서 대조(DOC-08)를 하지 않는다. 일부만 대조하면 읽지 못한 파일에만 있는
이름이 모두 경고로 올라가기 때문이다.

멈춤 가운데 스킬 스크립트·규칙 목록 문서·converter 쪽에서 생긴 것은 MismatchError 로 가른다. 변환표에
없는 코드·메시지 꼴, 색인과 변환 스크립트가 정의 문서를 다르게 읽음, 하위 스크립트 출력에 칸이 없음,
규격 검사기가 짚은 대상을 되돌리지 못함, 규칙 목록 문서 확인에 걸림, 하위 스크립트가 예외로 끝나거나
JSON 을 내지 못함이 그렇다. 입력이나 옵션으로 풀리지 않으므로 스크립트를 고치지 말고 사용자에게 알린다.

종료 코드: 0 수집함(지적이 있어도 0), 2 멈춤.
"""
import argparse
import ast
import collections
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

import definition_index as di
import rule_catalog as rc

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "check_design_doc.py")
# 빌더 판본 해시를 만드는 파일. 수집 결과를 바꾸는 파일만 둔다.
BUILDER_FILES = (os.path.abspath(__file__), CHECKER, os.path.join(HERE, "definition_index.py"),
                 os.path.join(HERE, "rule_catalog.py"), rc.DEFAULT_PATH)
CONVERTER_FILES = ("build_graphio_json.py", "validate_graphio_json.py")
TIMEOUT = 300       # 하위 스크립트 하나에 주는 시간(초)
MARK = "⚠"          # 정의 문서 검사기의 기본 경고 기호
NONE = "해당 없음"
NOT_TEXT = "대조 불가(형식)"
COLUMNS = ("No.", "규칙", "외부 코드", "위치", "문제 설명", "발생 경로", "조치 방안", "조치 주체", "참고 자료")
SPEC_RULE = {"error": "SPC-01", "warning": "SPC-02", "deferred": "SPC-03"}

# ── 변환표 ───────────────────────────────────────────────────────────────────
# 하위 스크립트의 지적을 리포트 문체의 문제 설명·조치 방안으로 바꾼다. 뜻은 검사-규칙.md 3절 조치 지침과
# 맞춘다. 메시지에 든 이름·건수는 위치와 발생 경로로 옮기고 문구에는 넣지 않는다. 같은 규칙·같은 조치인
# 지적이 판정 문서에서 한 묶음이 되도록 문제 설명에 요소 이름을 적지 않는다.
# 메시지 꼴은 converter 스크립트의 % 서식 문자열 그대로다. 짚은 내용은 발생 경로 끝 괄호에 붙는 말이고,
# {0}·{1} 은 서식의 값 자리 차례, {title} 은 변환 스크립트가 짚은 ### 제목이다.
# converter 가 코드나 메시지를 바꾸면 여기서 찾지 못해 수집이 멈춘다. 그때 이 표를 함께 고친다.

# 정의 파일을 변환 스크립트가 만드는 한 나오지 않는 지적의 조치
RECONVERT = "정의 문서를 다시 변환함. 같은 지적이 다시 나오면 변환 스크립트 문제로 알림"
SEVEN_TYPES = "7종(INTEGER·TEXT·DATETIME·FLOAT8·BOOLEAN·VECTOR·UNKNOWN) 가운데 하나로 고침"
THREE_DIRECTS = "방향 칸에 UNIDIRECTIONAL(→)·REVERSE_DIRECTIONAL(←)·BIDIRECTIONAL(↔) 가운데 하나를 적음"

# 정의 문서 검사기. (규칙, 경우) → (문제 설명, 조치 방안)
DOC_TEXT = {
    ("DOC-01", ""): ("개념 설명에서 떨어진 줄이 있음. 변환할 때 이 줄이 버려져 설명 내용이 누락됨",
                     "떨어진 줄을 앞 `- 설명:` 줄 끝에 이어 붙임"),
    ("DOC-02", ""): ("조사 괄호가 남아 있음. 읽히지 않는 문장이 설명으로 반입되어 검색에 쓰임",
                     "앞말 받침에 맞는 조사 하나만 남김(받침 있음: 이·은·을·과, 받침 없음: 가·는·를·와)"),
    ("DOC-03", ""): ("표 행의 칸 수가 머리글과 다름. 설명 안의 세로줄이 칸을 나눠 값이 다른 칸으로 밀림",
                     "설명 안의 세로줄을 쉼표나 가운뎃점으로 바꿈"),
    ("DOC-04", "0건"): ("대표 표시 속성이 없음. 개체를 화면에 보일 값이 정해지지 않아 반입할 수 없음",
                        "사람이 개체를 알아보는 속성 하나를 대표 표시 속성으로 지정함"),
    ("DOC-04", "2건 이상"): ("대표 표시 속성이 2건 이상임. 개념마다 1건만 허용되어 반입할 수 없음",
                           "대표 표시 속성을 하나만 남김"),
    ("DOC-05", ""): ("개념 설명 줄이 없음. 설명이 검색에 쓰이므로 질의가 이 개념을 찾지 못할 수 있음",
                     "스타일 가이드의 개념 설명 형식대로 설명을 씀. 확인되지 않은 값은 '확인 필요'로 적음"),
    ("DOC-05", "읽히지 않는 설명"): (
        "개념 설명 줄이 변환할 때 읽히지 않음(첫 표나 소제목 뒤에 있거나 '- desc:' 꼴임). 변환된 개념에 설명이 "
        "없어 질의가 이 개념을 찾지 못할 수 있음", "설명 줄을 '- 설명:' 꼴로 개념 제목 바로 아래에 둠"),
    ("DOC-06", ""): ("헷갈리지 말라는 경고문이 상대 개념에만 있음. 반대 방향 질의에서 개념을 잘못 고를 수 있음",
                     "이 개념 설명에도 반대 방향 경고문을 넣음. 넣지 않을 까닭이 있으면 설계 리포트에 적음"),
    ("DOC-07", ""): ("경고 기호는 있으나 가리키는 상대 개념을 알 수 없음. 헷갈리는 상대가 검색에 전달되지 않을 수 있음",
                     "스타일 가이드의 경고문 형식대로 상대 개념 이름을 넣어 고침"),
    ("DOC-08", ""): ("원천 구조 문서에 없는 이름이고 대상 환경에 아직 없다는 표기도 없음. "
                     "원천 이름을 잘못 옮겼으면 데이터가 연결되지 않음",
                     "새로 만드는 구조이면 설명에 대상 환경에 아직 없다는 표기를 넣음. "
                     "원천 이름을 잘못 옮겼으면 원천 이름으로 고침"),
    ("DOC-09", ""): ("대상 환경에 아직 없는 데이터 구조임. 반입 전에 대상 환경에서 만들어야 함", NONE),
    ("DOC-11", "둘째 표"): (
        "블록 안의 둘째 표임. 변환 스크립트가 블록마다 첫 표만 읽어(Link Type은 첫 절의 첫 표만) 이 표의 내용이 "
        "오류 없이 버려짐", "표 내용을 블록의 첫 표나 설명 줄로 옮기고 둘째 표를 지움"),
    ("DOC-11", "소제목 뒤 표"): (
        "블록 제목과 첫 표 사이에 소제목이 있음. 변환 스크립트가 소제목에서 표 읽기를 멈춰 이 블록의 표 내용이 "
        "모두 누락됨", "블록 제목과 첫 표 사이의 소제목 줄을 지움"),
}

# 변환 스크립트 오류. 메시지 꼴 → (문제 설명, 조치 방안, 짚은 내용). 문제 설명이 None 이면 멈춘다.
CONVERT_TEXT = {
    "%s 칸의 값 %r 을 참·거짓으로 읽을 수 없다.": (
        "참·거짓 칸의 값을 읽을 수 없어 변환이 실패함", "표시하려면 O, 비우려면 빈칸으로 고침", "{0} 칸 값 {1}"),
    "%s 칸의 값 %r 이 영문 O 인지 숫자 0 인지 가릴 수 없다.": (
        "참·거짓 칸의 값이 영문 O인지 숫자 0인지 가릴 수 없어 변환이 실패함",
        "표시하려면 O, 비우려면 빈칸으로 고침", "{0} 칸 값 {1}"),
    # '문서 전체' 를 짚는다. 개념이 없는 문서라 정의 문서 검사기가 먼저 멈추므로 나오면 멈춘다
    "'## Object Type' 절이 없다. 서식이 아닌 문서로 보인다.": (None, None, None),
    "Object Type 이름 %r 이 규격 형식을 어긴다.": (
        "개념 이름이 규격 형식을 어겨 변환이 실패함. 영문·한글로 시작하고 영문·숫자·한글·밑줄만 50자까지 쓸 수 있음",
        "규격 형식에 맞게 개념 이름을 고침", "이름 {0}"),
    "색 %r 이 #RRGGBB 꼴이 아니다.": (
        "화면 색이 #RRGGBB 꼴이 아니어서 변환이 실패함", "색을 #RRGGBB 꼴로 고침", "색 {0}"),
    "속성 표가 없다. 규격이 속성을 1건 이상 요구한다.": (
        "속성 표가 없어 변환이 실패함. 규격이 속성을 1건 이상 요구함",
        "제목 아래에 서식대로 속성 표를 적음", "속성 표 없음"),
    "속성 표에 '속성' 또는 '데이터 타입' 머리글이 없다.": (
        "속성 표에 '속성' 또는 '데이터 타입' 머리글이 없어 변환이 실패함", "서식의 표 머리글을 그대로 씀", "머리글 없음"),
    "속성 이름이 비어 있다.": ("속성 이름 칸이 비어 있어 변환이 실패함", "속성 이름을 채움", "속성 이름 빈칸"),
    "%s 의 데이터 타입 %r 이 7종에 없다.": (
        "데이터 타입이 7종에 없어 변환이 실패함", SEVEN_TYPES, "데이터 타입 {1}"),
    "%s 칸이 비어 있어 이 관계를 만들 수 없다.": (
        "관계 행에 빈 칸이 있어 변환이 실패함. 규격이 관계 이름, 양끝 개념과 조인 속성, 방향을 요구함",
        "빈 칸을 채움", "빈 칸 {0}"),
    "방향 %r 을 3종 중 하나로 읽을 수 없다.": (
        "관계 방향을 3종 가운데 하나로 읽을 수 없어 변환이 실패함", THREE_DIRECTS, "방향 {0}"),
    "종류 %r 이 3종에 없다.": (
        "데이터 구조 종류가 3종(CUSTOM·PARSING·DOC_TYPE)에 없어 변환이 실패함",
        "종류를 3종 가운데 하나로 고침", "종류 {0}"),
    "컬럼 이름이 비어 있다.": ("컬럼 이름 칸이 비어 있어 변환이 실패함", "컬럼 이름을 채움", "컬럼 이름 빈칸"),
    "제목이 'Object Type 이름 ← Meta Type 이름' 꼴이 아니다.": (
        "매핑 제목이 '개념 이름 ← 데이터 구조 이름' 꼴이 아니어서 변환이 실패함",
        "화살표(←)로 두 이름을 잇는 제목으로 고침", "제목 {title}"),
    "속성 매핑 표가 없어 이 연결을 만들 수 없다.": (
        "속성 매핑 표가 없어 변환이 실패함. 규격이 속성 매핑을 1건 이상 요구함",
        "제목 아래에 서식대로 속성 매핑 표를 적음", "속성 매핑 표 없음"),
    "속성 매핑의 한쪽이 비어 있다.": ("속성 매핑 행의 한쪽 칸이 비어 있어 변환이 실패함", "빈 칸을 채움", "한쪽 칸 빈칸"),
}

# 소제목 뒤 표(DOC-11) 때문에 개념·매핑 블록에서 나는 변환 오류. 같은 블록의 DOC-11 행에 합친다(검사-규칙.md 4절)
NO_TABLE = ("속성 표가 없다. 규격이 속성을 1건 이상 요구한다.", "속성 매핑 표가 없어 이 연결을 만들 수 없다.")

# 변환 스크립트 자동 채움. 메시지 꼴 → (설명, 짚은 내용). 4.1 표 아래 '※ No.2 자동 채움' 주석이 된다.
FILLED_TEXT = {
    "문서에 색이 없어 규격 필수값을 채웠다 (%s). 뜻은 없고 다른 색과 겹치지 않는다.": (
        "문서에 색이 없어 규격 필수값인 화면 색을 채움. 색에는 뜻이 없고 다른 색과 겹치지 않음", "`{0}`"),
}

# 규격 검사기. (등급, 코드, 메시지 꼴) → (문제 설명, 조치 방안, 짚은 내용). 코드가 '-' 면 코드 없는 지적이다.
SPEC_TEXT = {
    # 정의 파일의 꼴. 변환 스크립트가 만든 파일에서는 나오지 않는다
    ("error", "GOS50001", "최상위가 객체가 아니다."): (
        "정의 파일의 최상위가 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "허용되지 않는 최상위 키다. 이 키가 있으면 반입 자체가 거부된다."): (
        "정의 파일에 허용되지 않는 최상위 키가 있음. 반입 자체가 거부됨", RECONVERT, None),
    ("error", "GOS50001", "필수 배열이 없거나 배열이 아니다."): (
        "정의 파일에 필수 배열이 없거나 배열이 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "배열이 아니다."): ("배열이어야 하는 값이 배열이 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "Object Type 항목이 객체가 아니다."): ("개념 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "속성 항목이 객체가 아니다."): ("속성 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "Link Type 항목이 객체가 아니다."): ("관계 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "Meta Type 항목이 객체가 아니다."): (
        "데이터 구조 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "컬럼 항목이 객체가 아니다."): ("컬럼 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "Object Mapping 항목이 객체가 아니다."): ("매핑 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("error", "GOS50001", "속성 매핑 항목이 객체가 아니다."): (
        "속성 매핑 항목이 객체가 아님. 반입할 수 없음", RECONVERT, None),
    ("warning", "GOS61337", "내부 마커 키다. 반입 과정에서 제거된다."): (
        "정의 파일에 내부 표시용 키가 있음. 반입 과정에서 제거됨", RECONVERT, None),
    ("error", "GOS61203", "objectTypes 와 linkTypes 가 모두 0건이다. 반입은 되지만 적용이 거부된다."): (
        "개념과 관계가 모두 0건임. 반입은 되나 적용이 거부됨", "Object Type 절에 개념을 1건 이상 적음", None),
    ("warning", "-", "시스템 값이다. 파일에 넣어도 반입 과정에서 제거된다."): (
        "시스템이 정하는 키가 들어 있음. 반입 과정에서 제거됨", RECONVERT, None),
    ("warning", "-", "반입이 읽어 주는 별칭이지만 규격 키가 아니다."): (
        "규격 키가 아닌 별칭 키를 씀. 반입은 읽어 주나 규격과 다름", RECONVERT, None),
    # 개념과 속성
    ("error", "GOS61002", "이름이 없다."): (
        "개념 이름이 없음. 반입할 수 없음", "Object Type 절의 ### 제목에 개념 이름을 적음", None),
    ("error", "GOS61002", "이름 형식 위반: %r. 영문·한글로 시작하고 영문·숫자·한글·밑줄만, 50자까지."): (
        "개념 이름이 규격 형식을 어김. 영문·한글로 시작하고 영문·숫자·한글·밑줄만 50자까지 쓸 수 있음",
        "규격 형식에 맞게 개념 이름을 고침", None),
    ("error", "GOS61003", "설명이 %d자다. 5000자를 넘을 수 없다."): (
        "개념 설명이 5000자를 넘음. 반입할 수 없음", "개념 설명을 5000자 이내로 줄임", "설명 {0}자"),
    ("error", "GOS61004", "화면 색상이 없다."): ("화면 색이 없음. 반입할 수 없음", RECONVERT, None),
    ("warning", "-", "색상이 #RRGGBB 꼴이 아니다: %r"): ("화면 색이 #RRGGBB 꼴이 아님", RECONVERT, "색 {0}"),
    ("error", "GOS61005", "속성이 0건이다. 1건 이상 있어야 한다."): (
        "속성이 0건임. 개념마다 속성이 1건 이상 있어야 함", "제목 아래에 서식대로 속성 표를 적음", None),
    ("error", "-", "속성 이름이 없다."): ("속성 이름이 없음. 반입할 수 없음", RECONVERT, None),
    ("error", "-", "데이터 타입이 %r 이다. 7종 중 하나여야 한다."): (
        "속성의 데이터 타입이 7종에 없음. 반입할 수 없음", SEVEN_TYPES, "데이터 타입 {0}"),
    ("error", "-", "표시 순서가 %r 이다. 1 이상의 정수여야 한다."): (
        "속성의 표시 순서가 1 이상의 정수가 아님. 반입할 수 없음", RECONVERT, "표시 순서 {0}"),
    ("warning", "-", "설명이 %d자다. 저장 한계인 5000자를 넘는다."): (
        "설명이 저장 한계인 5000자를 넘음. 넘는 부분이 저장되지 않을 수 있음", "설명을 5000자 이내로 줄임", "설명 {0}자"),
    ("error", "GOS61010", "속성 이름이 %d번 나온다. 한 Object Type 안에서 유일해야 한다."): (
        "같은 이름의 속성이 둘 이상 있음. 속성 이름은 개념 안에서 유일해야 함",
        "속성 이름이 겹치지 않게 고치거나 겹친 행을 하나로 합침", "같은 이름 {0}건"),
    ("error", "-", "표시 순서가 겹친다: %s. 저장 단계의 유일 제약을 어긴다."): (
        "속성의 표시 순서가 겹침. 저장 단계에서 거부됨", RECONVERT, "표시 순서 {0}"),
    ("warning", "-", "표시 순서가 1부터 연속이 아니다: %s"): (
        "속성의 표시 순서가 1부터 연속이 아님", RECONVERT, "표시 순서 {0}"),
    ("error", "GOS61006", "대표 표시 속성(isTitleKey)이 없다. 정확히 1개 있어야 한다."): (
        "대표 표시 속성이 없음. 개념마다 1건이 있어야 함",
        "사람이 개체를 알아보는 속성 하나를 대표 표시 속성으로 지정함", None),
    ("error", "GOS61007", "대표 표시 속성이 %d개다(%s). 정확히 1개여야 한다."): (
        "대표 표시 속성이 2건 이상임. 개념마다 1건만 허용됨", "대표 표시 속성을 하나만 남김",
        "대표 표시 속성 {0}건: {1}"),
    ("error", "GOS61008", "식별 속성(isPrimaryKey)이 %d개다(%s). 1개까지만 쓸 수 있다."): (
        "식별 속성이 2건 이상임. 개념마다 1건까지만 쓸 수 있음", "식별 속성을 하나만 남김. 복합키이면 모두 비움",
        "식별 속성 {0}건: {1}"),
    ("error", "GOS61011", "Object Type 이름이 %d번 나온다. 파일 안에서 유일해야 한다."): (
        "같은 이름의 개념이 둘 이상 있음. 개념 이름은 정의 문서 안에서 유일해야 함",
        "한쪽 개념 이름을 바꾸거나 두 개념을 하나로 합침", "같은 이름 {0}건"),
    # 관계
    ("error", "GOS61102", "관계 이름이 없다."): (
        "관계 이름이 없음. 반입할 수 없음", "Link Type 표의 관계 이름 칸을 채움", None),
    ("warning", "-", "조인 속성의 데이터 타입이 다르다(%s.%s=%s, %s.%s=%s). 값이 맞지 않아 관계가 비어 있을 수 있다."): (
        "양쪽 조인 속성의 데이터 타입이 다름. 값이 맞지 않아 관계가 비어 있을 수 있음",
        "의도가 아니면 양쪽 조인 속성의 데이터 타입을 맞추거나 조인 속성을 바꿈", "{0}.{1} {2}, {3}.{4} {5}"),
    ("error", "GOS61103", "관계 방향이 없다."): ("관계 방향이 없음. 반입할 수 없음", THREE_DIRECTS, None),
    ("error", "GOS61103", "관계 방향이 %r 이다."): (
        "관계 방향이 규격의 3종에 없음. 반입할 수 없음", THREE_DIRECTS, "방향 {0}"),
    ("error", "GOS61107", "%s Object Type 이 비어 있다."): (
        "관계의 양끝 개념 가운데 한쪽이 비어 있음. 관계를 풀 수 없음",
        "Link Type 표의 source·target 칸에 Object Type 절의 개념 이름을 적음", "{0} 쪽"),
    ("error", "GOS61107", "%r 은 이 파일의 objectTypes 에 없다. 관계는 파일 안의 Object Type 으로만 풀린다."): (
        "관계의 양끝 개념 가운데 정의 문서에 없는 개념이 있음. 관계를 풀 수 없음",
        "개념 이름을 Object Type 절의 이름과 맞추거나 그 개념을 적음", "개념 {0}"),
    ("error", "GOS61106", "자기 참조 관계다(%s → %s). 규격이 막는다."): (
        "출발과 도착이 같은 개념인 자기 참조 관계임. 규격이 막음", "관계를 지우고 상위 식별자를 속성으로만 적음", None),
    ("error", "GOS61108", "%s 쪽 조인 속성이 없다. 관계 이름만으로는 링크가 성립하지 않는다."): (
        "관계의 조인 속성이 없음. 관계 이름만으로는 링크가 성립하지 않음",
        "Link Type 표의 source 속성·target 속성 칸을 채움", "{0} 쪽"),
    ("error", "GOS61110", "%s 쪽 조인 속성이 없다. 관계 이름만으로는 링크가 성립하지 않는다."): (
        "관계의 조인 속성이 없음. 관계 이름만으로는 링크가 성립하지 않음",
        "Link Type 표의 source 속성·target 속성 칸을 채움", "{0} 쪽"),
    ("error", "GOS61109", "%r 은 %s 의 속성이 아니다."): (
        "조인 속성이 양끝 개념의 속성에 없음. 관계가 이어지지 않음",
        "조인 속성 이름을 개념의 속성 이름과 맞추거나 개념에 그 속성을 적음", "조인 속성 {0}"),
    ("error", "GOS61111", "%r 은 %s 의 속성이 아니다."): (
        "조인 속성이 양끝 개념의 속성에 없음. 관계가 이어지지 않음",
        "조인 속성 이름을 개념의 속성 이름과 맞추거나 개념에 그 속성을 적음", "조인 속성 {0}"),
    ("warning", "-", "%s 에 식별 속성이 없어 %r 값이 유일한지 알 수 없다. 값이 반복되면 관계가 의도한 한 건을 넘어 퍼진다."): (
        "도착 개념에 식별 속성이 없어 조인 값이 유일한지 알 수 없음. 값이 반복되면 관계가 의도보다 넓게 이어짐",
        "조인 값이 유일한지 확인함. 유일하지 않으면 확인 결과를 검증 리포트에 적음", "조인 속성 {1}"),
    ("warning", "-", "%r 은 %s 의 식별 속성(%s)이 아니다. 값이 반복되면 관계가 의도한 한 건을 넘어 퍼진다."): (
        "도착 쪽 조인 속성이 식별 속성이 아님. 값이 반복되면 관계가 의도보다 넓게 이어짐",
        "유일한 속성이 있으면 그 속성으로 조인함. 없으면 확인 결과를 검증 리포트에 적음",
        "조인 속성 {0}, 식별 속성 '{2}'"),
    ("error", "GOS61105", "이름·양끝·조인 속성·방향이 모두 같은 Link Type 이 %d건이다."): (
        "이름·양끝·조인 속성·방향이 모두 같은 관계가 둘 이상 있음", "겹친 관계를 하나만 남김", "같은 관계 {0}건"),
    ("warning", "GOS61330", "같은 이름으로 양끝이 다른 관계가 %d건이다. 허용되지만 화면에서 구분되지 않는다."): (
        "같은 이름으로 양끝이 다른 관계가 있음. 허용되나 화면에서 구분되지 않음",
        "의도가 아니면 구분되는 이름으로 관계 이름을 바꿈", None),     # 건수는 양끝 조합 수라 행 수와 달라 적지 않는다
    # 데이터 구조와 컬럼
    ("error", "-", "Meta Type 이름이 없다."): (
        "데이터 구조 이름이 없음. 반입할 수 없음", "Meta Type 절의 ### 제목에 대상 환경의 데이터 구조 이름을 적음", None),
    ("error", "-", "종류가 %r 이다."): (
        "데이터 구조 종류가 3종(CUSTOM·PARSING·DOC_TYPE)에 없음. 반입할 수 없음",
        "종류를 3종 가운데 하나로 고침", "종류 {0}"),
    ("error", "-", "컬럼 이름이 없다."): ("컬럼 이름이 없음. 반입할 수 없음", RECONVERT, None),
    ("error", "-", "데이터 타입이 %r 이다."): (
        "컬럼의 데이터 타입이 7종에 없음. 반입할 수 없음", SEVEN_TYPES, "데이터 타입 {0}"),
    ("warning", "-", "설명이 %d자다. Meta Type 컬럼 설명은 1000자까지다."): (
        "컬럼 설명이 1000자를 넘음. 넘는 부분이 저장되지 않을 수 있음", "컬럼 설명을 1000자 이내로 줄임", "설명 {0}자"),
    ("error", "-", "컬럼 이름이 %d번 나온다."): (
        "같은 이름의 컬럼이 둘 이상 있음. 컬럼 이름은 데이터 구조 안에서 유일해야 함",
        "겹친 컬럼 행을 하나만 남김", "같은 이름 {0}건"),
    ("error", "GOS61018", "Meta Type 이름이 %d번 나온다. 파일 안에서 유일해야 한다."): (
        "같은 이름의 데이터 구조가 둘 이상 있음. 데이터 구조 이름은 정의 문서 안에서 유일해야 함",
        "겹친 데이터 구조를 하나만 남김", "같은 이름 {0}건"),
    # 매핑
    ("error", "GOS61021", "연결할 Object Type 이름이 없다."): (
        "매핑할 개념 이름이 없음. 반입할 수 없음", "매핑 제목의 화살표 앞에 개념 이름을 적음", None),
    ("error", "GOS61021", "%r 은 이 파일의 objectTypes 에 없다. 반입 시 이 항목은 조용히 버려진다."): (
        "매핑한 개념이 정의 문서에 없음. 반입할 때 이 매핑이 버려짐",
        "매핑 제목의 개념 이름을 Object Type 절의 이름과 맞추거나 이 매핑을 지움", None),
    ("error", "-", "연결할 Meta Type 이름이 없다."): (
        "매핑할 데이터 구조 이름이 없음. 반입할 수 없음", "매핑 제목의 화살표 뒤에 데이터 구조 이름을 적음", None),
    ("error", "-", "%r 이 metaTypes 블록에 없다. 파일 안에서 대조할 수 없다."): (
        "매핑한 데이터 구조가 Meta Type 절에 없음. 컬럼을 대조할 수 없음",
        "Meta Type 절에 같은 이름으로 데이터 구조를 적거나 매핑 제목의 이름을 맞춤", None),
    ("error", "GOS61016", "속성 매핑이 0건이다. 반입은 되지만 적용이 막힌다."): (
        "속성 매핑이 0건임. 반입은 되나 적용이 막힘", "제목 아래에 서식대로 속성 매핑 표를 적음", None),
    ("error", "-", "Object Type 속성 이름이 없다."): (
        "속성 매핑 행의 개념 속성 이름이 없음. 반입할 수 없음", "속성 매핑 표의 개념 속성 칸을 채움", None),
    ("error", "GOS61022", "%r 은 %s 의 속성이 아니다."): (
        "매핑한 속성이 개념의 속성에 없음. 반입할 수 없음", "속성 이름을 개념의 속성 이름과 맞춤", None),
    ("error", "-", "Meta Type 컬럼 이름이 없다."): (
        "속성 매핑 행의 컬럼 이름이 없음. 반입할 수 없음", "속성 매핑 표의 컬럼 칸을 채움", None),
    ("error", "GOS61015", "%r 은 %s 의 컬럼이 아니다."): (
        "매핑한 컬럼이 데이터 구조의 컬럼에 없음. 반입할 수 없음", "컬럼 이름을 데이터 구조의 컬럼 이름과 맞춤", "컬럼 {0}"),
    ("warning", "-", "타입이 다르다(%s.%s=%s, %s.%s=%s)."): (
        "속성과 매핑한 컬럼의 데이터 타입이 다름", "의도한 변환이면 확인 결과를 검증 리포트에 적고, 아니면 한쪽 타입을 맞춤",
        "{0}.{1} {2}, {3}.{4} {5}"),
    ("error", "GOS61020", "%r 이 %d번 연결됐다. 한 Object Mapping 안에서 유일해야 한다."): (
        "한 매핑 안에서 같은 속성을 둘 이상 매핑함. 속성은 매핑마다 한 번만 쓸 수 있음",
        "겹친 속성 매핑 행을 하나만 남김", "같은 속성 {1}건"),
    ("error", "GOS61019", "같은 (Object Type, Meta Type) 쌍이 %d건이다."): (
        "같은 개념과 데이터 구조를 잇는 매핑이 둘 이상 있음", "겹친 매핑을 하나로 합침", "같은 매핑 {0}건"),
    ("warning", "GOS61337", "objectMapping 에서 참조되지 않는다. 반입 과정에서 제거된다."): (
        "어느 매핑도 쓰지 않는 데이터 구조임. 반입 과정에서 제거됨",
        "쓰지 않는 데이터 구조이면 지우고, 쓰는 것이면 매핑을 적음", None),
    # 대상 환경에서 마무리할 것. 조치 대상 외 항목이라 조치 방안을 적지 않는다
    ("deferred", "GOS61017", "데이터 연결이 없는 Object Type %d건: %s"): (
        "데이터가 연결되지 않은 개념임. 적용하려면 대상 환경에서 데이터 구조를 연결해야 함", NONE, None),
    ("deferred", "GOS61014", "Meta Type %d건은 반입으로 만들어지지 않는다. 같은 이름·같은 컬럼 이름으로 대상 환경에 먼저 있어야 한다."): (
        "반입으로 만들어지지 않는 데이터 구조임. 같은 이름·같은 컬럼 이름으로 대상 환경에 먼저 있어야 함", NONE, None),
}

# %r 로 적힌 값: 따옴표로 싼 문자열, 또는 None·숫자 같은 한 낱말
REPR = r"('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|[^\s'\"]+)"
PARTS = {"%r": REPR, "%s": r"(.+?)", "%d": r"(-?\d+)"}


class CollectError(Exception):
    """수집하지 않고 멈출 까닭. 입력이나 옵션을 고치면 풀린다."""


class MismatchError(CollectError):
    """스킬 스크립트·규칙 목록 문서·converter 쪽 문제로 멈출 까닭. 입력이나 옵션으로 풀리지 않는다."""


# MismatchError 로 멈췄을 때 할 일. 수집·판정 스크립트가 함께 쓴다.
MISMATCH_HINT = "스킬 스크립트·규칙 목록 문서·converter 쪽 문제라 입력이나 옵션으로 풀리지 않음. 스크립트를 고치지 말고 사용자에게 알림"


def _compile(fmt):
    """% 서식 문자열을 메시지 전체와 맞대는 정규식과 값 자리의 종류로 바꾼다."""
    out, kinds, i = [], [], 0
    for m in re.finditer(r"%[rsd]", fmt):
        out.append(re.escape(fmt[i:m.start()]))
        out.append(PARTS[m.group(0)])
        kinds.append(m.group(0)[1])
        i = m.end()
    out.append(re.escape(fmt[i:]))
    return re.compile("".join(out)), kinds


def _index(table, key_of):
    out = {}
    for key, texts in table.items():
        fmt = key[-1] if isinstance(key, tuple) else key
        pat, kinds = _compile(fmt)
        out.setdefault(key_of(key), []).append((pat, kinds, texts))
    return out


_CONVERT = _index(CONVERT_TEXT, lambda k: None)
_FILLED = _index(FILLED_TEXT, lambda k: None)
_SPEC = _index(SPEC_TEXT, lambda k: k[:2])


def _show(value, kind):
    """메시지 속 값을 리포트에 적을 꼴로. %r 로 적힌 문자열은 작은따옴표로 감싼다."""
    if kind == "r" and value[:1] in ("'", '"'):
        try:
            return "'%s'" % ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return value
    return value


def lookup(table, key, message):
    """변환표에서 메시지 꼴이 맞는 항목. (문구, 값 목록). 없으면 (None, None)."""
    for pat, kinds, texts in table.get(key, ()):
        m = pat.fullmatch(message or "")
        if m:
            return texts, [_show(v, k) for v, k in zip(m.groups(), kinds)]
    return None, None


# ── 표기 ─────────────────────────────────────────────────────────────────────

# 검증 리포트와 판정 문서의 표는 이 세 함수로 쓰고 읽는다. 판정 스크립트도 이것을 쓴다.

def esc(value):
    """표 칸에 넣을 값. 역슬래시와 세로줄을 막는다. split_row() 가 그대로 되돌린다.

    세로줄만 막으면 원문의 '\\|' 와 막은 세로줄이 같아져 되돌릴 수 없으므로 역슬래시부터 막는다.
    """
    return str(value).replace("\\", "\\\\").replace("|", "\\|")


def split_row(line):
    """리포트 표 한 줄을 칸으로 나눈다. 막은 역슬래시·세로줄은 풀어서 칸 안에 둔다. esc() 의 반대다."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    cells, cur, i, closed = [], "", 0, False
    while i < len(body):
        ch = body[i]
        if ch == "\\" and body[i + 1:i + 2] in ("\\", "|"):
            cur, i, closed = cur + body[i + 1], i + 2, False
            continue
        if ch == "|":
            cells.append(cur)
            cur, closed = "", True
        else:
            cur, closed = cur + ch, False
        i += 1
    if not closed:
        cells.append(cur)
    return [c.strip() for c in cells]


def numbered(prefix, numbers):
    """[1, 2, 3, 7] → 'prefix No.1~3, No.7'. 비었으면 None."""
    groups = []
    for n in sorted(set(numbers)):
        if groups and n == groups[-1][1] + 1:
            groups[-1][1] = n
        else:
            groups.append([n, n])
    if not groups:
        return None
    return prefix + ", ".join("No.%d" % a if a == b else "No.%d~%d" % (a, b) for a, b in groups)


def row_numbers(numbers):
    """[1, 2, 3, 7] → '4.2절 No.1~3, No.7'. 비었으면 None."""
    return numbered("4.2절 ", numbers)


def shown_path(path):
    """리포트에 적을 경로. 작업 폴더 아래면 작업 폴더 기준 상대 경로로 적어 사용자 폴더 이름이 남지 않게 한다."""
    try:
        rel = os.path.relpath(os.path.abspath(path), os.getcwd())
    except ValueError:          # 다른 드라이브
        return path
    return path if rel == os.pardir or rel.startswith(os.pardir + os.sep) else rel


def file_hash(path):
    """파일 내용의 해시 앞 12자. 경로는 넣지 않는다."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def version_hash(paths):
    """여러 파일의 내용을 차례대로 묶은 판본 해시 앞 12자."""
    h = hashlib.sha256()
    for p in paths:
        with open(p, "rb") as f:
            h.update(hashlib.sha256(f.read()).hexdigest().encode("ascii"))
    return h.hexdigest()[:12]


def condition_line(cond):
    """수집 조건 한 줄. 4.2 표 아래 첫 ※ 주석이 된다. parse_condition() 이 되푼다."""
    spec = "수행(converter %s)" % cond["converter"] if cond["규격 검사"] == "수행" else "미수행"
    sources = "; ".join("%s %s" % (s["경로"], s["해시"] or NOT_TEXT) for s in cond["원천 구조 문서"])
    return ("※ 수집 조건: 정의 문서 %s, 경고 기호 %s, 규격 검사 %s, 원천 구조 문서 %s, 빌더 %s"
            % (cond["정의 문서"], cond["경고 기호"], spec, sources or "없음", cond["빌더"]))


# 수집 조건 줄의 원천 구조 문서 한 건. 경로에 '; ' 가 들어도 끝의 해시로 가른다.
SOURCE_RE = re.compile(r"(.+?) ([0-9a-f]{12}|%s)(?=; |$)" % re.escape(NOT_TEXT))
CONDITION_RE = re.compile(
    r"※ 수집 조건: 정의 문서 (?P<doc>[0-9a-f]{12}), 경고 기호 (?P<mark>.+?), "
    r"규격 검사 (?:수행\(converter (?P<conv>[0-9a-f]{12})\)|(?P<skip>미수행)), "
    r"원천 구조 문서 (?P<src>.+?), 빌더 (?P<builder>[0-9a-f]{12})")


def parse_condition(line):
    """수집 조건 줄을 칸별 값으로 푼다. condition_line() 의 반대. 꼴이 다르면 None."""
    m = CONDITION_RE.fullmatch((line or "").strip())
    if not m:
        return None
    sources, text, pos = [], m.group("src"), 0
    while text != "없음" and pos < len(text):
        part = SOURCE_RE.match(text, pos)
        if not part:
            return None
        sources.append({"경로": part.group(1), "해시": None if part.group(2) == NOT_TEXT else part.group(2)})
        pos = part.end() + (2 if text.startswith("; ", part.end()) else 0)
    return {"정의 문서": m.group("doc"), "경고 기호": m.group("mark"),
            "규격 검사": "미수행" if m.group("skip") else "수행", "converter": m.group("conv"),
            "원천 구조 문서": sources, "빌더": m.group("builder")}


# ── 하위 스크립트 ─────────────────────────────────────────────────────────────

def run_json(args, who, codes=(0, 1)):
    """하위 스크립트를 수행해 표준 출력의 JSON 을 읽는다. 출력은 UTF-8 로 읽는다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        p = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                           encoding="utf-8", timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        raise MismatchError("%s가 %d초 안에 끝나지 않음" % (who, TIMEOUT))
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as e:
        raise MismatchError("%s를 수행하지 못함: %s" % (who, e))
    err = (p.stderr or "").strip().splitlines()
    if p.returncode not in codes:
        raise MismatchError("%s가 종료 코드 %d로 끝남%s"
                           % (who, p.returncode, ": " + err[-1] if err else ""))
    try:
        data = json.loads(p.stdout)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise MismatchError("%s가 JSON 을 내지 못함(종료 코드 %d)%s"
                           % (who, p.returncode, ": " + err[-1] if err else ""))
    return data, p.returncode


def read_sources(paths):
    """원천 구조 문서마다 {경로, 해시}. UTF-8 텍스트가 아니면 해시 대신 None. 없거나 못 읽으면 멈춘다.

    경로는 리포트에 적을 꼴(shown_path)이다. 작업 폴더 기준이라 그대로 파일을 열 수 있다.
    """
    out = []
    for p in paths:
        try:
            di.read_text(p)
        except di.ReadError as e:
            if e.problem != di.NOT_UTF8:
                raise CollectError("원천 구조 문서를 읽지 못함: %s (%s)" % (p, e.problem))
            out.append({"경로": shown_path(p), "해시": None})
            continue
        out.append({"경로": shown_path(p), "해시": file_hash(p)})
    return out


def converter_scripts(folder):
    """converter 스킬 폴더의 두 스크립트. 없으면 멈춘다. 경로를 잘못 준 것이 미수행으로 넘어가지 않게 한다."""
    paths = [os.path.join(folder, "scripts", n) for n in CONVERTER_FILES]
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        raise CollectError("--converter 폴더에 스크립트가 없음: %s" % ", ".join(missing))
    return paths


# ── 행 만들기 ─────────────────────────────────────────────────────────────────

def make_row(rules, rule, code, where, line, problem, route, fix):
    r = rules.get(rule)
    return {"규칙": rule, "외부 코드": code, "위치": where, "문제 설명": problem, "발생 경로": route,
            "조치 방안": fix, "조치 주체": r["기본 조치 주체"], "참고 자료": r["기본 참고 자료"], "줄": line}


def doc_rows(rules, checked):
    """정의 문서 검사기 지적을 DOC 행으로 바꾼다. 건수는 규칙 목록의 등급으로 센다.

    검사기 JSON 의 옛 '등급' 칸(오류·경고·확인)은 읽지 않는다. 등급을 두는 곳은 규칙 목록 한 곳이다.
    """
    rows, counts = [], {g: 0 for g in rc.GRADES}
    found = checked.get("걸린 것")
    if not isinstance(found, list):
        raise MismatchError("정의 문서 검사기 출력에 '걸린 것' 칸이 없음")
    for f in found:
        try:
            rule, case = f["규칙"], f["경우"]
            where, line, excerpt, at = f["위치"], f["줄"], f["발췌"], f["발췌 줄"]
        except (KeyError, TypeError):
            raise MismatchError("정의 문서 검사기 출력에 규칙·위치·발췌 칸이 없음. 검사기 판본을 확인함")
        texts = DOC_TEXT.get((rule, case))
        if texts is None:
            raise MismatchError("변환표에 없는 정의 문서 검사 지적: %s %s" % (rule, case or "(경우 없음)"))
        if rule not in rules or rule not in rc.COLLECTED:
            raise MismatchError("정의 문서 검사기가 낸 규칙이 규칙 목록에 없음: %s" % rule)
        counts[rules.get(rule)["등급"]] += 1
        rows.append(dict(make_row(rules, rule, NONE, where, line, texts[0],
                                  "정의 문서 %d줄: %s" % (at, excerpt), texts[1]), 경우=case))
    return rows, counts


def converter_where(idx, where):
    """변환 스크립트가 짚은 'n줄 (### 이름)'·'n줄' 을 (위치, 줄, 제목) 으로. 색인과 다르면 멈춘다."""
    m = re.fullmatch(r"(\d+)줄 \(### (.*)\)", where or "")
    if m:
        n, title = int(m.group(1)), m.group(2)
        el = idx.element_at(n) if 1 <= n <= len(idx.lines) else None
        if (el is None or el.line != n or el.kind not in ("개념", "데이터 구조", "매핑")
                or not re.fullmatch(r"###\s+%s\s*" % re.escape(title), idx.lines[n - 1])):
            raise MismatchError("변환 스크립트가 짚은 제목 줄을 색인이 찾지 못함: %s" % where)
        return idx.locate_line(n), n, "'%s'" % title
    m = re.fullmatch(r"(\d+)줄", where or "")
    if m:
        n = int(m.group(1))
        el = idx.element_at(n) if 1 <= n <= len(idx.lines) else None
        if el is None or el.line != n or el.kind not in ("속성", "관계", "컬럼", "매핑 속성"):
            raise MismatchError("변환 스크립트가 짚은 표 행을 색인이 찾지 못함: %s" % where)
        return idx.locate_line(n), n, ""
    if where == "문서 전체":
        raise CollectError("변환 스크립트가 문서 전체를 짚음. 서식 네 절을 갖춘 정의 문서인지 확인함")
    raise MismatchError("변환 스크립트의 위치 꼴을 읽지 못함: %s" % where)


def convert_rows(rules, idx, built):
    """변환 스크립트의 오류를 CNV 행으로, 자동 채움을 주석 재료로 바꾼다."""
    rows, filled = [], {}
    for f in built.get("findings", []):
        level, message = f.get("level"), f.get("message")
        if level not in ("error", "filled"):
            raise MismatchError("변환 스크립트 지적의 단계가 정해진 값이 아님: %r" % (level,))
        table = _CONVERT if level == "error" else _FILLED
        texts, values = lookup(table, None, message)
        if texts is None:
            raise MismatchError("변환표에 없는 변환 스크립트 메시지: %s" % message)
        if texts[0] is None:
            raise CollectError("변환 스크립트가 서식이 아닌 문서로 봄: %s" % message)
        where, line, title = converter_where(idx, f.get("where"))
        if level == "error":
            rows.append(dict(make_row(rules, "CNV-01", NONE, where, line, texts[0],
                                      "정의 문서 %d줄 → 변환 실패(%s)" % (line, texts[2].format(*values, title=title)),
                                      texts[1]), 메시지=message))
        else:
            filled.setdefault(texts[0], []).append((line, where, texts[1].format(*values, title=title)))
    return rows, filled


def duplicated_links(elements, document):
    """이름이 같은 관계 가운데 이름·양끝·조인 속성·방향이 모두 겹치는 것만 남긴다(GOS61105)."""
    links = (document or {}).get("linkTypes") or []
    keys = ("name", "sourceObjectTypeName", "sourcePropertyName",
            "targetObjectTypeName", "targetPropertyName", "direct")
    sig = {e.line: tuple(links[e.json].get(k) for k in keys) for e in elements
           if e.json is not None and e.json < len(links) and isinstance(links[e.json], dict)}
    counts = collections.Counter(sig.values())
    return [e for e in elements if counts.get(sig.get(e.line), 0) > 1]


# 규격 검사기가 하위 행을 늘 이름으로 적는 코드. 숫자만으로 된 이름을 첨자로 읽지 않게 한다.
NAME_PATH_CODES = ("GOS61020",)


def split_check(code, values, names):
    """배열 전체를 짚은 GOS61014·61017 을 나눌 대상이 규격 검사기가 센 대상과 같은지 본다. 다르면 멈춘다.

    values 는 메시지의 값(건수, 이름 목록), names 는 색인이 고른 요소의 이름이다. 규격 검사기는 같은 이름을
    한 번만 센다. 다르면 converter 가 대상을 고르는 규칙이 바뀐 것이라 행을 나누지 않는다.
    """
    unique = sorted(set(names))
    same = int(values[0]) == len(unique)
    if same and code == "GOS61017":
        same = values[1] == ", ".join(unique)
    if not same:
        raise MismatchError("규격 검사기가 짚은 대상이 색인과 다름: %s(규격 검사기 %s건, 색인 %d건%s)"
                            % (code, values[0], len(unique), ": " + ", ".join(unique) if unique else ""))


def spec_elements(idx, document, code, path, values=()):
    """규격 검사기 경로를 정의 문서 요소로 되돌린다. [(요소, JSON 경로)]. 되돌릴 수 없으면 멈춘다.

    배열 전체를 짚는 GOS61014 는 데이터 구조마다, GOS61017 은 데이터가 붙지 않은 개념마다 나누고
    나눈 행의 JSON 경로는 요소 자신의 첨자 경로로 적는다. 나누기 전에 규격 검사기가 센 대상과 맞대 본다.
    이름 경로는 같은 이름의 요소마다 나누고 규격 검사기 경로를 그대로 적는다.
    GOS61105 는 이름만 같은 관계를 빼고 모든 값이 겹치는 관계만 남긴다.
    """
    if code == "GOS61014" and path == "metaTypes":
        found = idx.converted("metaTypes")
        split_check(code, values, [e.name for e in found])
        els = [(e, "metaTypes[%d]" % e.json) for e in found]
    elif code == "GOS61017" and path == "objectMapping":
        found = idx.unmapped_concepts()
        split_check(code, values, [e.name for e in found])
        els = [(e, "objectTypes[%d]" % e.json) for e in found]
    elif path in di.TOP_KEYS:
        raise MismatchError("배열 전체를 짚은 규격 검사기 지적이라 요소로 나눌 수 없음: %s %s" % (code, path))
    else:
        try:
            found = idx.resolve(path, row_names=code in NAME_PATH_CODES)
        except di.PathError as e:
            raise MismatchError("규격 검사기 경로를 정의 문서 위치로 되돌리지 못함: %s" % e)
        if code == "GOS61105":
            found = duplicated_links(found, document)
        els = [(e, path) for e in found]
    if not els:
        raise MismatchError("규격 검사기가 짚은 요소를 정의 문서에서 찾지 못함: %s %s" % (code, path))
    return els


def spec_rows(rules, idx, document, checked):
    """규격 검사기 지적을 SPC 행으로 바꾼다. 여러 요소를 짚은 지적은 요소마다 한 행이다."""
    rows = []
    for f in checked.get("findings", []):
        grade, code, path, message = f.get("grade"), f.get("code"), f.get("path"), f.get("message")
        rule = SPEC_RULE.get(grade)
        texts, values = lookup(_SPEC, (grade, code), message)
        if rule is None or texts is None:
            raise MismatchError("변환표에 없는 규격 검사기 지적: %s %s %s" % (grade, code, message))
        detail = texts[2].format(*values, title="") if texts[2] else ""
        for el, jpath in spec_elements(idx, document, code, path, values):
            route = "정의 문서 %d줄 → 변환 → `%s` → %s" % (el.line, jpath, code if code != "-" else "코드 없음")
            if detail:
                route += "(%s)" % detail
            rows.append(make_row(rules, rule, code if code != "-" else NONE, el.location(), el.line,
                                 texts[0], route, texts[1]))
    return rows


def overlap(idx, doc, cnv, spc):
    """검사-규칙.md 4절. 같은 결함을 두 검사가 잡으면 DOC 행만 남긴다.

    남는 CNV·SPC 행, 뺀 건수, 뺀 것을 받은 DOC 행을 돌려준다. 받은 GOS 코드는 DOC 행의 외부 코드가 된다.
    DOC-03 은 같은 줄의 CNV-01 을, DOC-11 소제목 뒤 표는 같은 블록의 표 없음 CNV-01(NO_TABLE)을 받는다.
    CNV-01 행의 줄은 표 행 줄이거나 블록 제목 줄이다.
    """
    by_where = {}
    for r in doc:
        by_where.setdefault((r["규칙"], r["위치"]), []).append(r)
    kept, dropped, taken, codes = [], {"DOC-03": 0, "DOC-04": 0, "DOC-09": 0, "DOC-11": 0}, [], {}
    for r in spc:
        keeper = {"GOS61006": "DOC-04", "GOS61007": "DOC-04", "GOS61014": "DOC-09"}.get(r["외부 코드"])
        hosts = by_where.get((keeper, r["위치"]), []) if keeper else []
        if not hosts:
            kept.append(r)
            continue
        dropped[keeper] += 1
        for h in hosts:
            codes.setdefault(id(h), set()).add(r["외부 코드"])
            taken.append(h)
    lines, heads = {}, {}
    for r in doc:
        if r["규칙"] == "DOC-03":
            lines.setdefault(r["줄"], []).append(r)
        elif r["규칙"] == "DOC-11" and r["경우"] == "소제목 뒤 표":
            block = idx.element_at(r["줄"])
            if block is not None:       # Link Type 절은 블록이 없고 표 없음 오류도 나지 않는다
                heads.setdefault(block.line, []).append(r)
    for r in cnv:
        keeper, hosts = "DOC-03", lines.get(r["줄"], [])
        if not hosts and r["메시지"] in NO_TABLE:
            keeper, hosts = "DOC-11", heads.get(r["줄"], [])
        if not hosts:
            kept.append(r)
            continue
        dropped[keeper] += 1
        taken.extend(hosts)
    for r in doc:
        if id(r) in codes:
            r["외부 코드"] = "·".join(sorted(codes[id(r)]))
    return kept, dropped, taken


# ── 수집 ─────────────────────────────────────────────────────────────────────

def condition(definition, converter=None, spec_skipped=False, warn_mark=None, sources=()):
    """하위 스크립트를 수행하지 않고 수집 조건을 만든다. 옵션이 맞지 않거나 파일을 읽지 못하면 CollectError.

    판정 스크립트가 다시 수집하기 전에 검증 리포트의 수집 조건 줄과 맞대 본다. 수집 뒤 정의 문서가 바뀌어
    다시 수집이 실패해도 '정의 문서가 바뀜' 으로 알리기 위해서다.
    """
    if converter and spec_skipped:
        raise CollectError("--converter 와 --spec-skipped 를 함께 줌. 둘 가운데 하나만 줌")
    if not converter and not spec_skipped:
        raise CollectError("--converter 와 --spec-skipped 가운데 하나를 주지 않음")
    mark = MARK if warn_mark is None else warn_mark
    if not mark:
        raise CollectError("--warn-mark 가 비었음")
    scripts = converter_scripts(converter) if converter else None
    try:
        di.read_text(definition)
    except di.ReadError as e:
        raise CollectError("정의 문서를 읽지 못함: %s (%s)" % (e.path, e.problem))
    cond = {"정의 문서": file_hash(definition), "경고 기호": mark,
            "규격 검사": "수행" if scripts else "미수행",
            "converter": version_hash(scripts) if scripts else None,
            "원천 구조 문서": read_sources(sources), "빌더": version_hash(BUILDER_FILES)}
    return dict(cond, 줄=condition_line(cond))


def collect(definition, converter=None, spec_skipped=False, warn_mark=None, sources=()):
    """스크립트 검사를 수행해 수집 결과를 만든다. 멈출 까닭이 있으면 CollectError(또는 MismatchError).

    판정 스크립트가 모듈로 불러 다시 수행할 때도 쓴다. 결과는 main() 의 --json 출력과 같은 dict 다.
    """
    cond = condition(definition, converter, spec_skipped, warn_mark, sources)
    try:
        rules = rc.load()
    except rc.RuleError as e:
        raise MismatchError("규칙 목록 문서 확인에 걸림: %s" % e)
    scripts = converter_scripts(converter) if converter else None
    mark, src = cond["경고 기호"], cond["원천 구조 문서"]
    text = di.read_text(definition)
    compare = bool(src) and all(s["해시"] for s in src)

    # 하위 스크립트에는 절대 경로를 주고 '--' 뒤에 둔다. '-' 로 시작하는 파일 이름을 옵션으로 읽지 않게 한다.
    args = [CHECKER, "--json", "--warn-mark=" + mark]
    if compare:
        args += ["--source"] + [os.path.abspath(s["경로"]) for s in src]
    checked, _ = run_json(args + ["--", os.path.abspath(definition)], "정의 문서 검사기", codes=(0, 1, 2))
    if not checked.get("읽힘"):
        raise CollectError("정의 문서 검사기가 정의 문서를 읽지 못함: %s" % checked.get("까닭", "까닭 없음"))
    idx = di.DefinitionIndex(text.splitlines())
    doc, no1 = doc_rows(rules, checked)

    cnv, spc, filled, no2 = [], [], {}, {"결과": "미수행", "변환 Error": 0, "규격 Error": 0, "Warning": 0, "Info": 0}
    if scripts:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "definition.json")
            built, _ = run_json([scripts[0], "-o", out, "--json", "--", os.path.abspath(definition)], "변환 스크립트")
            if not isinstance(built.get("findings"), list) or not isinstance(built.get("document"), dict):
                raise MismatchError("변환 스크립트 출력에 findings·document 가 없음")
            gaps = idx.mismatches(built["document"])
            if gaps:
                raise MismatchError("색인과 변환 스크립트가 정의 문서를 다르게 읽음: %s" % "; ".join(gaps[:3]))
            cnv, filled = convert_rows(rules, idx, built)
            if cnv:
                no2.update({"결과": "실패", "변환 Error": len(cnv)})
                filled = {}     # 정의 파일이 만들어지지 않았으므로 채운 값도 남지 않는다
            else:
                if not os.path.isfile(out):
                    raise MismatchError("변환 스크립트가 오류 없이 끝났으나 정의 파일을 쓰지 않음")
                checked_spec, _ = run_json([scripts[1], "--json", "--", out], "규격 검사기")
                if not isinstance(checked_spec.get("findings"), list):
                    raise MismatchError("규격 검사기 출력에 findings 가 없음")
                spc = spec_rows(rules, idx, built["document"], checked_spec)
                no2.update({"결과": "성공",
                            "규격 Error": sum(r["규칙"] == "SPC-01" for r in spc),
                            "Warning": sum(r["규칙"] == "SPC-02" for r in spc),
                            "Info": sum(r["규칙"] == "SPC-03" for r in spc)})

    kept, dropped, taken = overlap(idx, doc, cnv, spc)
    ordered = sorted(doc + kept, key=lambda r: (rules.order(r["규칙"]), r["줄"], r["발생 경로"],
                                                r["문제 설명"], r["조치 방안"], r["위치"]))
    for n, r in enumerate(ordered, 1):
        r["No."] = n
    rows = [dict([(k, r[k]) for k in COLUMNS] + [("줄", r["줄"])]) for r in ordered]

    if not src:
        compared = "미수행(원천 구조 문서 미제공)"
    elif not compare:
        compared = "미수행(텍스트로 읽을 수 없는 형식)"
    else:
        compared = "수행"
    note = None if compare else "원천 구조 문서 대조(DOC-08) %s" % compared
    first = row_numbers([r["No."] for r in doc])
    no1_text = ". ".join(x for x in (first, note) if x) or NONE

    if no2["결과"] == "미수행":
        no2_value, no2_text = "미수행", "converter 스킬 없음"
    else:
        if no2["결과"] == "실패":
            moved = ", ".join("%d건은 %s 행으로" % (dropped[k], k) for k in ("DOC-03", "DOC-11") if dropped[k])
            no2_value = "변환 실패(Error %d건%s), 규격 검사 미수행" % (
                no2["변환 Error"], ", %s 적음" % moved if moved else "")
        else:
            no2_value = "변환 성공, 규격 Error %d건%s, Warning %d건, Info %d건%s" % (
                no2["규격 Error"], "(%d건은 DOC-04 행으로 적음)" % dropped["DOC-04"] if dropped["DOC-04"] else "",
                no2["Warning"], no2["Info"], "(%d건은 DOC-09 행으로 적음)" % dropped["DOC-09"] if dropped["DOC-09"] else "")
        no2_text = row_numbers({r["No."] for r in kept + taken}) or NONE

    notes = []
    for desc, items in filled.items():
        items.sort()
        notes.append("※ No.2 자동 채움: %s. 대상 %d건: %s"
                     % (desc, len(items), ", ".join("%s %s" % (w, d) for _, w, d in items)))

    return {
        "수집됨": True,
        "정의 문서": definition,
        "검사 결과": [
            {"No.": 1, "검사 항목": "정의 문서 검사", "검사 대상": "정의 문서",
             "결과": ", ".join("%s %d건" % (g, no1[g]) for g in rc.GRADES),
             "지적 내용": no1_text},
            {"No.": 2, "검사 항목": "서식 변환 검사", "검사 대상": "정의 문서",
             "결과": no2_value, "지적 내용": no2_text}],
        "자동 채움 주석": notes,
        "지적 목록": rows,
        "수집 조건": cond,
        "원천 구조 문서 대조": compared,
        "통계": checked.get("통계", {}),
        "건수": {"정의 문서 검사": no1,
                 "서식 변환 검사": dict(no2, **{"DOC 행으로 적음": dropped}),
                 "지적 목록": len(rows)},
    }


# ── 출력 ─────────────────────────────────────────────────────────────────────

def result_lines(result):
    """4.1 표의 No.1·No.2 행."""
    keys = ("No.", "검사 항목", "검사 대상", "결과", "지적 내용")
    return ["| %s |" % " | ".join(esc(r[k]) for k in keys) for r in result["검사 결과"]]


def table_lines(result):
    """4.2 지적 목록 표. 행이 없으면 '해당 없음' 한 줄."""
    rows = result["지적 목록"]
    if not rows:
        return [NONE]
    out = ["| %s |" % " | ".join(COLUMNS), "|%s|" % "|".join(["---"] * len(COLUMNS))]
    out += ["| %s |" % " | ".join(esc(r[k]) for k in COLUMNS) for r in rows]
    return out


def render(result):
    cond = result["수집 조건"]
    sources = cond["원천 구조 문서"]
    p = ["수집 대상: %s   (경고 기호 %s, 규격 검사 %s, 원천 구조 문서 대조 %s)"
         % (result["정의 문서"], cond["경고 기호"], cond["규격 검사"], result["원천 구조 문서 대조"])]
    if sources:
        p.append("  원천 구조 문서: %s" % ", ".join(
            "%s(%s)" % (s["경로"], "대조" if s["해시"] else NOT_TEXT) for s in sources))
    if any(not s["해시"] for s in sources):
        p.append("  UTF-8 텍스트가 아닌 원천 구조 문서가 있어 원천 구조 문서 대조(DOC-08)를 하지 않음. "
                 "UTF-8 텍스트로 바꿔 다시 수행하면 대조함")
    p += ["", "[4.1 검사 항목별 결과] 표의 No.1·No.2 행을 아래 두 줄로 바꿈"]
    p += result_lines(result)
    if result["자동 채움 주석"]:
        p += ["", "[4.1 표 아래 주석] 표 아래에 붙임"] + result["자동 채움 주석"]
    if result["지적 목록"]:
        p += ["", "[4.2 지적 목록] 표와 수집 조건 주석을 그대로 붙임. 스킬 행은 표 끝에 이어 붙이고 번호를 이어 매김"]
    else:
        p += ["", "[4.2 지적 목록] 스크립트 지적 없음. 스킬 행도 없으면 아래를 그대로 붙임. "
                  "스킬 행이 있으면 '해당 없음' 대신 지적 목록 표를 만들어 No.1부터 적음"]
    p += table_lines(result) + ["", cond["줄"]]
    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser(
        description="검사 항목 No.1(정의 문서 검사)·No.2(서식 변환 검사)를 스크립트 셋으로 수행하고 "
                    "결과를 검증 리포트 4.1·4.2절에 붙일 행으로 바꾼다.")
    ap.add_argument("definition", help="온톨로지 정의 문서")
    ap.add_argument("--converter", metavar="폴더",
                    help="converter 스킬 폴더. scripts/ 에 변환 스크립트와 규격 검사기가 있어야 한다")
    ap.add_argument("--spec-skipped", action="store_true",
                    help="converter 스킬이 없어 서식 변환 검사를 수행하지 못함. --converter 와 함께 주지 않는다")
    ap.add_argument("--warn-mark", default=None, metavar="기호",
                    help="가이드가 정한 경고 기호 (기본 %s). 정의 문서 검사기에 넘긴다" % MARK)
    ap.add_argument("--source", nargs="+", default=[], metavar="파일",
                    help="원천 구조 문서. 주면 데이터 구조 이름을 대조한다(DOC-08)")
    ap.add_argument("--json", action="store_true", help="판정 스크립트가 읽는 JSON 으로 낸다")
    args = ap.parse_args()

    try:
        result = collect(args.definition, converter=args.converter, spec_skipped=args.spec_skipped,
                         warn_mark=args.warn_mark, sources=args.source)
    except Exception as e:      # 예상하지 못한 오류도 종료 코드 2 로 멈춘다. 1 은 쓰지 않는 값이다
        mismatch = isinstance(e, MismatchError) or not isinstance(e, CollectError)
        why = str(e) if isinstance(e, CollectError) else "수집 스크립트가 예상하지 못한 오류로 멈춤(%s: %s)" % (
            type(e).__name__, e)
        if args.json:
            json.dump({"수집됨": False, "까닭": why, "스킬 판본 문제": mismatch}, sys.stdout, ensure_ascii=False)
            print()
        else:
            print("수집하지 않음: %s" % why, file=sys.stderr)
            if mismatch:
                print("스킬 스크립트·규칙 목록 문서·converter 쪽 문제라 입력이나 옵션으로 풀리지 않는다. "
                      "스크립트를 고치지 말고 사용자에게 알린다. 지적 목록 행은 내지 않았다.", file=sys.stderr)
            else:
                print("입력이나 옵션을 고친 뒤 다시 수행한다. 지적 목록 행은 내지 않았다.", file=sys.stderr)
        return 2
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
