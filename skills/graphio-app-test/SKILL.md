---
name: graphio-app-test
description: 만든 graphio app 을 로컬에서 테스트·실행해볼 때 쓰는 스킬. 프레임워크 패키지 안에 번들된 Test UI(test_ui/stream_test.html)를 `graphio-app run --test-ui` 로 띄워 브라우저에서 대화·스트리밍을 확인하거나, /stream 엔드포인트를 curl 로 직접 쳐서 헤드리스로 테스트하는 법을 안내한다. 프레임워크가 라이브러리로 설치되면 Test UI 가 site-packages 안에 숨어 보이지 않으므로, 그걸 꺼내 쓰는 법이 핵심이다. '앱 테스트', '어떻게 테스트', '테스트 해보기', '앱 실행해보기', '돌려보기', 'test-ui', '--test-ui', 'stream_test.html', 'Test UI', 'graphio-app run', '/stream 호출', 'curl 로 테스트', 'SSE 확인', '브라우저에서 확인' 표현이 나오면 로드한다. 앱을 새로 만들거나 구조를 잡는 작업은 graphio-app-dev 스킬을 쓴다. 모든 설명은 한국어로, 코드/식별자는 영어 그대로.
---

# Graphio App 테스트 실행 스킬

만든 graphio app 을 **로컬에서 돌려보고 확인**하는 방법을 다룬다. 핵심 문제: 프레임워크를 라이브러리(`graphio_app_framework`)로 설치하면 테스트 UI(`test_ui/stream_test.html`)가 **site-packages 안에 숨어** 사람들이 그게 있는지조차 모른다. 답은 **CLI 가 그걸 꺼내 띄워준다**는 것이다.

> **경계 (graphio-app-dev 와 구분)**
> - **graphio-app-dev** = 앱을 새로 만들고 구조를 잡고 포털에 올리는 전체 라이프사이클.
> - **graphio-app-test** (이 스킬) = 이미 만든 앱을 **실행해서 테스트**하는 것에 집중. 테스트 방법을 모를 때 가장 먼저 로드.

---

## 0. TL;DR — 한 줄이면 된다

```bash
# 앱 프로젝트 루트(=src/ 가 있는 곳)에서
graphio-app run --test-ui
```

그러면 자동으로:

1. 앱 서버가 **`http://localhost:8888`** 에서 뜨고 (`/graphio/graphio_app/v1/stream`)
2. 번들된 Test UI 가 **`http://localhost:18423/stream_test.html`** 에서 서빙되고
3. **브라우저가 자동으로 열린다**.

브라우저 채팅창에 메시지를 넣으면 앱의 `/stream` 으로 SSE 요청이 가고 응답이 실시간으로 그려진다. 끝.

---

## 1. 전제조건

`graphio-app run --test-ui` 가 동작하려면:

| 항목 | 확인 |
|---|---|
| **앱 프로젝트 루트에서 실행** | `src/` 가 있는 디렉터리에서 실행한다. 프레임워크가 `cwd`(및 상위 4단계)를 훑어 `graphio_app()` 그래프를 찾는다. 특정 디렉터리만 보게 하려면 `GRAPHIO_APP_DIR=services`, 루트를 지정하려면 `PROJECT_ROOT`. |
| **`.env` 존재** | 없으면 `graphio-app copy-env` 로 템플릿을 복사한다. |
| **venv 에 framework 설치** | `graphio_app_framework` 가 설치된 가상환경을 활성화한다. |
| **LLM 도달 가능** | `.env` 의 `LLM_MODEL` / `LLM_API_KEY` / `LLM_API_ADDRESS` (또는 `OPENAI_API_KEY`) 가 채워져 있고 호출 가능해야 한다. |

> `graphio-app` 명령이 없다면(콘솔 스크립트 미설치 등) `python -m graphio_app_framework.cli run --test-ui` 로 동일하게 실행된다.

---

## 2. 브라우저 Test UI 로 테스트

`graphio-app run --test-ui` 로 연 `stream_test.html` 에서 할 수 있는 것:

- **메시지 전송** — 채팅창에 입력 → `/stream` 으로 SSE 요청, 토큰이 실시간으로 그려짐
- **멀티턴 대화** — `thread_id` 를 지정/유지하면 대화 히스토리가 이어진다. 첫 대화/`thread_id` 변경 시 자동으로 `create_title: true`, 이후 `false`.
- **thread 저장 모드** — `thread_history` 토글로 체크포인터 저장 여부 제어
- **특수 렌더 타입 확인** — 응답 메시지의 `additional_kwargs.type` 에 따라 차트(`chart`), 파일 다운로드 링크(`file`), Studio 보고서 iframe 패널(`studio_url`), 에디터(`editor`) 등이 렌더된다. 새로 만든 service node 의 시각화 출력을 눈으로 검증할 때 유용.

브라우저가 자동으로 안 열리면 직접 접속: **http://localhost:18423/stream_test.html**

> CORS: 브라우저(18423)에서 앱(8888)으로의 cross-origin 요청은 `start_test_ui()` 가 붙이는 CORS 미들웨어로 허용된다. `--test-ui` 플래그가 이를 자동 처리하며, `.env` 의 `TEST_UI=true` 로도 켜진다(env.template 기본값).

---

## 3. curl 로 헤드리스 테스트 (스크립트·CI)

브라우저 없이 `/stream` 을 직접 친다. 서버만 떠 있으면 되므로 `--test-ui` 없이 `graphio-app run` 으로 띄워도 된다(curl 은 CORS 무관).

```bash
# 단일 메시지 — SSE 프레임을 그대로 출력 (-N: curl 버퍼링 끔)
curl -N -X POST http://127.0.0.1:8888/graphio/graphio_app/v1/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message":"안녕, 너는 누구야?","thread_id":"test-001","create_title":true,"stream_tokens":true}'

# 같은 thread_id 로 이어가기 (멀티턴) — create_title 은 false
curl -N -X POST http://127.0.0.1:8888/graphio/graphio_app/v1/stream \
  -H "Content-Type: application/json" -H "Accept: text/event-stream" \
  -d '{"message":"방금 뭐라고 했지?","thread_id":"test-001","create_title":false}'

# 업로드 파일 사용 흐름 테스트
curl -N -X POST http://127.0.0.1:8888/graphio/graphio_app/v1/stream \
  -H "Content-Type: application/json" -H "Accept: text/event-stream" \
  -d '{"message":"이 파일 요약해줘","thread_id":"t2","file_names":["report.pdf"],"this_file":["report.pdf"]}'
```

응답은 `data: {"type":"token","content":"..."}\n\n` 형태의 SSE 프레임이 연속으로 온다(`token`, `message`, `chart`, `file`, `studio_url` …).

### `/stream` 요청 바디 필드 (`StreamInput`)

| 필드 | 기본값 | 설명 |
|---|---|---|
| `message` | (필수) | 사용자 입력 |
| `model` | `gpt-4o` | 사용할 LLM 모델명 |
| `thread_id` | — | 멀티턴 유지용 스레드 ID |
| `thread_history` | `true` | 대화 히스토리 저장 여부 |
| `create_title` | `false` | 스레드 제목 자동 생성 트리거 |
| `active_tool` | `{}` | `{"type":"studio"\|"editor","value":...}` |
| `file_names` | `[]` | 누적 업로드 파일명 |
| `this_file` | `[]` | 이번에 업로드 중인 파일명 |
| `stream_tokens` | `true` | LLM 토큰 스트리밍 여부 |
| `request_type` | `run` | `run`(신규) / `resume`(HITL 인터럽트 재개) |

---

## 4. 설정·포트

| 항목 | 기본 | 비고 |
|---|---|---|
| 앱 서버 | `0.0.0.0:8888` | `.env` 의 `APP_HOST` / `APP_PORT`. 브라우저는 `127.0.0.1:8888` 로 접근. |
| Test UI 정적 서버 | `18423` | `--test-ui` 시에만 뜸 (`TEST_UI_STATIC_PORT`). |
| CORS 허용 | `TEST_UI=true` 또는 `--test-ui` | 브라우저 테스트에 필요. |
| API base 오버라이드 | `GRAPHIO_TEST_UI_API_BASE` | CLI 가 HTML 에 주입 시도 (아래 제약 참고). |

> ⚠️ **포트는 8888 로 유지하라(번들 UI 제약).** 현재 번들된 `stream_test.html` 은 API URL 을 `http://127.0.0.1:8888/...` 로 **하드코딩**하고 있고, CLI 가 주입하는 `window.__GRAPHIO_TEST_UI_API_BASE__` 를 소비하지 않는다. 따라서 `APP_PORT` 를 8888 에서 바꾸면 **브라우저 Test UI 가 응답을 못 받는다**(`GRAPHIO_TEST_UI_API_BASE` 오버라이드도 무시됨). 다른 포트로 테스트해야 하면 **curl 경로(§3)** 를 쓴다.

---

## 5. 자주 마주치는 문제

| 증상 | 원인 / 해결 |
|---|---|
| `[FATAL] ... 그래프 진입점` 못 찾음 | 앱 프로젝트 루트가 아닌 곳에서 실행. `src/` 가 있는 디렉터리에서 실행하거나 `GRAPHIO_APP_DIR` / `PROJECT_ROOT` 설정. 메인 그래프 옆에 `__graphio_main__ = True` 마커 권장. |
| 브라우저에서 CORS / 네트워크 에러 | `--test-ui` 없이 띄웠거나 `TEST_UI` 가 `true` 가 아님. `graphio-app run --test-ui` 사용(또는 `.env` 에 `TEST_UI=true`). |
| 브라우저가 자동으로 안 열림 | 수동 접속: http://localhost:18423/stream_test.html |
| 포트 바꿨더니 UI 가 무응답 | 번들 UI 는 8888 하드코딩. 앱을 8888 로 유지하거나 다른 포트는 curl 로 테스트(§4 제약). |
| `Address already in use` (8888/18423) | 기존 프로세스 종료 후 재실행. |
| LLM 호출 에러 | `.env` 의 `LLM_MODEL` / `LLM_API_KEY` / `LLM_API_ADDRESS`(또는 `OPENAI_API_KEY`) 확인, 도달 가능성 점검. |
| `.env` 가 없음 | `graphio-app copy-env` 로 템플릿 복사. |
| thread 히스토리 관련 오류(구조 변경 후) | `GRAPHIO_APP_STORAGE/*.db` 삭제로 체크포인터 초기화. **데이터 삭제이므로 실행 전 확인.** |

---

## 6. 참고

- 앱 서버 엔드포인트: `POST /graphio/graphio_app/v1/stream` (SSE), 기본 `http://localhost:8888`
- CLI: `graphio-app run [--test-ui]`, `graphio-app copy-env [--dest .env]`
- 앱 개발(만들기/구조/패키징): `graphio-app-dev` 스킬
- 재사용 노드 저작: `graphio-subagent-dev` 스킬
