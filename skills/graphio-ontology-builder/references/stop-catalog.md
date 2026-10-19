# 멈춤 목록

멈춤과 실패마다 코드, 사람용 문장, 종료 코드를 한 곳에 둔다. 판정·수집·검사·관문·증분·원천 대조·앞 글 유지 확인 스크립트는 `--json` 옵션이 켜지면 표준 출력에 JSON 하나를 내고, 그 JSON의 `code`와 실행 결과 파일 `stop_reason.code`가 이 표의 코드를 쓴다. 같은 종료 코드 1·2라도 어느 스크립트의 어느 자리인지는 `code`로 가른다.

---

## 1. 멈춤 코드 표

| 코드 | 스크립트(자리) | 종료 코드 | 모드 | 까닭 쪽 | 사람용 한 줄 | 행동 | 남는 산출물 | 다시 시작 자리 |
|---|---|---|---|---|---|---|---|---|
| DOC_ERRORS | `check_design_doc.py` | 1 | 1차·`--fix`·`--verify` | 입력 | 정의 문서 검사에서 Error가 나와 다음 단계로 가지 않음 | fix | 정의 문서·검사 결과 | ⑨ 걸음 3 |
| DOC_INPUT | `check_design_doc.py` | 2 | 모든 모드 | 입력 | 정의 문서를 읽지 못함(파일 없음·UTF-8 아님·개념을 찾지 못함) | add_input | 그때까지 | 그 검사 |
| JUDGE_UNDECIDED | `judge_structure.py` | 1 | 모든 모드 | 입력 | 구조 판정이 '확정 불가'로 끝남 | fix | 설계 리포트·정의 문서·검증 리포트·구조 판정 | `--fix` |
| JUDGE_CQ_HASH | `judge_structure.py --design-report`(관문 5) | 1 | 모든 모드 | 입력 | `설계 리포트 4절 CQ 해시·등급이 CQ 문서와 다름: <CQ들>`(고칠 곳: `CQ 문서를 바꿨으면 --fix 로 설계 수정 차수에서 반영`) | fix | 그때까지 | `--fix` |
| JUDGE_INPUT | `judge_structure.py` | 2 | 모든 모드 | 입력 | 판정 입력을 읽지 못하거나 맞지 않음(파일 없음·UTF-8 아님·리포트 판 행 없음). `설계 리포트 4절 CQ 행에 '해시/등급' 칸이 없음`(고칠 곳: `관문 1(check_design_report.py --stage 설계)을 거친 설계 리포트를 준다`). `CQ 문서를 읽지 못함: <…> (<…>)`(고칠 곳: `--cq 경로`). 설계 리포트 절·칸 없음 `설계 리포트에 <…>절이 없음: <…>`·`설계 리포트 <…>절에 표가 없음`·`설계 리포트 <…>절 표에 <…> 칸이 없음`·`설계 리포트 <…>절 No. 칸이 정수가 아님: '<…>'`(고칠 곳: `--design-report 경로`) | add_input | 그때까지 | ⑨ 걸음 5 |
| JUDGE_DESIGN_BASIS | `judge_structure.py --design-report`(설계 리포트 4.2·4.3절 맞대기) | 2 | 모든 모드 | 입력 | 설계 리포트 맞대기에서 어긋남이 나옴: 검증 리포트 5.1절 미응답 사유가 4.2절 판정과 맞지 않음(근거 칸 4.2절 No. 누락·설계 누락 숨김·사유와 판정 불일치), `설계 리포트 4.3절 No.<…>에서 꼴 요소를 뺀 CQ <…>가 검증 리포트 5.1절에서 응답 가능임`(고칠 곳: `검증 리포트 5.1절 판정. 꼴 요소를 뺀 CQ는 응답 가능이 될 수 없음`), `설계 누락: 설계 리포트 4.3절 No.<…> 뺀 꼴 요소가 가리키는 4.2절 No.<…> 판정이 있음`(고칠 곳: `설계 리포트 4.3절 뺀 꼴 요소. 원천에 있는 꼴 요소는 빼지 않고 설계에 넣음`). 종료 코드 2(입력 쪽. 어느 멈춤인지는 `code`로 가름). 설계 누락 숨김도 검증 리포트 5.1절을 고쳐 푼다 | fix | 그때까지 | ⑨ 걸음 5 |
| COLLECT_INPUT | `collect_findings.py` | 2 | 모든 모드 | 입력 | 수집 입력을 읽지 못함 | add_input | 그때까지 | ⑨ 걸음 4 |
| GATE_FAILED | `check_design_report.py --stage 설계·확인·검증뒤`(관문 1·2·4) | 1 | 모든 모드 | 스킬 | 관문에서 빠진 칸·어긋난 자리가 나와 다음 단계로 가지 않음(CQ 해시·등급 어긋남은 GATE_CQ_HASH) | retry | 그때까지 | 그 관문 앞 단계 |
| GATE_CQ_HASH | `check_design_report.py --stage 검증뒤`(관문 4) | 1 | 모든 모드 | 입력 | CQ 문서에서 다시 셈한 번호별 해시·등급이 설계 리포트 4절과 다름 | fix | 그때까지 | `--fix` |
| CARRY_MISSING | `check_design_report.py --fix-request` | 1 | `--fix` | 스킬 | N차 요청서 6절의 옮겨야 할 행(출처와 상관없이 상태가 적용·적용 안 됨이 아닌 행)이 N+1차 요청서에 옮겨지지 않음 | retry | 그때까지 | 수정 요청서 쓰기 |
| DESIGN_FIRST_ORDER | `check_design_report.py --stage 검증뒤` | 1 | 1차·`--fix` | 스킬 | 설계 리포트보다 정의 문서를 먼저 고친 자리가 있음(설계 리포트 먼저 차례 위반) | retry | 그때까지 | 설계 리포트 고치기 |
| GATE_INPUT | `check_design_report.py` | 2 | 모든 모드 | 입력 | 관문 입력이 맞지 않음(파일 없음·UTF-8 아님·입력 해시 다름·리포트 판 행 없음). 「확인 대기」 판 덮어쓰기 거절은 스킬이 실행 결과 파일에 이 코드로 적음(관문 1이 회차 사본 잔존으로 검사: 같은 차수 회차 사본이 있는데 설계 리포트가 어느 사본과도 다른 판이고 12절에 마지막 사본에 없던 ⑥ 답 행도 없으면 이 코드) | add_input | 그때까지 | ① |
| EXTERNAL_DESIGN_CHANGE | `check_design_report.py --stage 검증뒤` | 2 | `--fix`(정비만 하는 차수 차례 2)·`--verify` | 입력 | 사람이 고친 정의 문서에 설계를 바꾸는 차이가 있어 검사하지 않음. status '입력 필요' | fix | 수정 요청서 사람 요청 행 초안, 외부 수정본 | `--fix` |
| CARRY_OVER_FINDINGS | `compare_definitions.py` | 1 | `--fix` | 스킬 | 부분 수정한 정의 문서가 연쇄 대상을 빠뜨림 | retry | 그때까지 | ⑨ 걸음 2 앞 |
| CARRY_OVER_INPUT | `compare_definitions.py` | 2 | `--fix` | 입력 | 맞댈 정의 문서·설계 리포트를 읽지 못함 | add_input | 그때까지 | ⑨ 걸음 2 앞 |
| SOURCE_MISMATCH | `source_match.py` | 1 | 모든 모드 | 스킬 | 설계 리포트 4.2절 근거 위치가 원천 문서 글자와 맞지 않음 | retry | 그때까지 | ②-1 |
| SOURCE_INPUT | `source_match.py` | 2 | 모든 모드 | 입력 | 원천 문서·설계 리포트를 읽지 못함 | add_input | 그때까지 | ②-1 |
| DELTA_CONDITION | `input_delta.py` | 1 | 1차 | 입력 | CQ 문서 변경이 부합 조건에 걸려 증분 반영을 하지 않음 | regenerate | 그때까지 | ① |
| DELTA_INPUT | `input_delta.py` | 2 | 1차 | 입력 | 입력 사본을 읽지 못함(사본 없음·UTF-8 아님) | add_input | 그때까지 | ① |
| SKILL_UNEXPECTED | 모든 스크립트 | 3 | 모든 모드 | 스킬 | 스크립트가 예상하지 못한 오류로 멈춤 | handover | 그때까지 | 없음 |
| SKILL_VERSION_MISMATCH | `collect_findings.py`·`judge_structure.py`(`MISMATCH_HINT`·`MismatchError`) | 3 | 모든 모드 | 스킬 | 스킬 스크립트·규칙 목록 문서의 판본이 맞지 않음 | handover | 그때까지 | 없음 |
| OUTPUT_WRITE_FAILED | 출력을 쓰는 스크립트(출력 파일·표준 출력, `OSError`) | 4 | 모든 모드 | 실행 환경 | 출력 파일을 쓰지 못함 | retry | 그때까지 | 그 단계 |
| HUMAN_STOP | (스크립트 아님, 실행 결과 파일 `stop_reason.code`) | 1 | 모든 모드 | 사람 판단 | 사람이 실행을 중단함. status '중단' | stop | 그때까지 | 없음 |

- 까닭 쪽은 입력·스킬·실행 환경·사람 판단 넷 가운데 하나다
- ①·②-2·⑥ 멈춤은 스크립트가 내는 종료 코드가 아니라 실행 결과 파일 status '멈춤 대기'로 알린다. 멈춤 질문 파일 꼴은 [`design-report-review.md`](design-report-review.md) 3.3을 따른다
- 멈춤 JSON은 사람용 문장(`message_ko`)과 모델용 지시(`model_hint`)를 나눠 담는다. `model_hint`는 대화 출력에 내지 않는다

## 2. 알림 꼴

- 멈춤·실패 알림은 넷째 줄까지로 고정한다
  1. 무엇이 안 됐는지
  2. 까닭
  3. 할 수 있는 일
  4. 남은 산출물

## 3. 종료 코드

| 종료 코드 | 뜻 | 실행 결과 파일 status |
|---|---|---|
| 0 | 완료 | 완료 |
| 1 | 검사·판정은 끝났고 결과가 다음 단계로 가지 못함. 오류가 아님(판정 '확정 불가', 관문 빠짐·어긋남, 검사기 Error 있음, 요청서 옮김 누락, 설계 리포트 먼저 차례 위반, 앞 글 유지 확인 지적 있음, 사람 중단) | 완료. 사람 중단이면 중단 |
| 2 | 입력 쪽 멈춤(파일 없음·UTF-8 아님·입력 해시 다름·리포트 판 행 없음, 외부 설계 변경 멈춤 포함) | 입력 필요 |
| 3 | 스킬 쪽 실패(예상 밖 예외, 스킬 판본 문제) | 실패(스킬 쪽) |
| 4 | 출력 쓰기 실패(파일·표준 출력, `OSError`). 스크립트는 이 경우에만 4를 냄 | 실패(환경) |
| 10 | 멈춤 대기. 스크립트는 내지 않고 실행 결과 파일 status로만 씀 | 멈춤 대기 |
