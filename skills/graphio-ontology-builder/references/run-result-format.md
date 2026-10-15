# 결과 보고 서식

1차 생성·수정 단계(`--fix`)·검증만 모드(`--verify`)가 끝날 때 내는 결과 보고와 실행 결과 파일의 꼴을 정한다. **성공해도 실패해도 실행 결과 파일을 쓴다.**

---

## 1. 결과 보고 차례

| 차례 | 내용 |
|---|---|
| 1 | 산출물 표. 이번 차수 산출물 경로를 쓴 차례대로(설계 리포트 → 정의 문서 → 검증 리포트 → 구조 판정), 있으면 수정 요청서 |
| 2 | 판정 요약 세 줄 |
| 3 | 사람이 정할 일 |
| 4 | 다음 할 일(2장 행동 코드) |
| 5 | 경고 한 줄 |

- 대화 출력 상한([`dialog-output.md`](dialog-output.md))을 따른다

## 2. 행동 코드

- 다음 할 일은 아래 닫힌 목록에서만 고른다

| 코드 | 뜻 |
|---|---|
| fix | 판정과 대기열을 보고 설계를 고쳐 결과를 다시 냄(`--fix`) |
| fix_warning | 수정 범위를 'Warning 포함'으로 고침 |
| verify | 사람이 고친 정의 문서를 검사·판정만 다시 함(`--verify`) |
| answer_request | 멈춤 질문에 답함 |
| queue_add | 사람 요청을 수정 요청서에 적어 두기만 함 |
| regenerate | 판정 전 1차 실행을 ①부터 다시 함. 판정 뒤에는 쓰지 않고 restart_new_folder를 씀 |
| convert | 정의 문서를 graphio JSON으로 옮김(graphio-ontology-converter) |
| export_report | 응답 불가 CQ 보고를 결과 보고 부록으로 뽑음 |
| explain | 설계 판단을 설명함 |
| add_input | 입력 문서를 더함 |
| retry | 실패한 단계를 다시 함 |
| handover | 사람에게 넘김 |
| restart_new_folder | 새 폴더에서 처음부터 다시 만듦 |
| stop | 끝냄 |

## 3. 실행 결과 파일

- 이름은 `<이름>-실행결과-N차.json`이다. 출력 폴더에 쓴다

| 칸 | 적을 것 |
|---|---|
| mode | 1차·`--fix`·`--verify` 가운데 하나 |
| reached | 마친 마지막 단계 |
| status | 완료·멈춤 대기·입력 필요·실패(스킬 쪽)·실패(환경)·중단 |
| stop_reason | code, message_ko(사람용 한 줄), detail(표준 오류 원문·예외 이름) |
| outputs | 설계 리포트·정의 문서·검증 리포트·구조 판정·수정 요청서 경로 |
| verdict | 구조 판정 결과 |
| counts | error, warning, no_human_check('사람 확인 없음' 건수) |
| next[] | action(행동 코드), label, condition, args |
| leftovers[] | 남은 산출물의 역할·경로·판·쓸 수 있는지 |
| resume_from | 다시 시작할 자리 |
| self_repairs[] | 스스로 고쳐 다시 한 기록 |
| elapsed | 걸린 시간 |

- 종료 코드는 [`stop-catalog.md`](stop-catalog.md) 표를 따른다
- 진행 상태 파일 `<이름>-진행.json`은 출력 폴더에 두고 단계가 바뀔 때마다 덮어쓴다. 칸은 stage, step, started_at, done[{stage, counts}], waiting_stop이다
- 스킬이 앱에 내는 것(멈춤 질문 파일·되짚기 블록·진행 상태 파일·실행 결과 파일)은 모두 출력 폴더 아래 파일로 두고, 사람용 글은 이 파일에서 만든다
