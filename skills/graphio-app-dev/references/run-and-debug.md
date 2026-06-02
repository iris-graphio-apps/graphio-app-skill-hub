# 실행 & 디버그 (Scope 2)

graphio-app CLI 로 앱을 로컬에서 띄우고, 메인 그래프가 감지되도록 하고, `/stream` 을 curl 로 호출하고, "모듈 못 찾음 / 메인 그래프 안 잡힘" 을 진단하는 방법을 다룬다.

> 모든 import/실행 검증은 반드시 데모 venv python 으로 한다:
> `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python`
> (시스템/pyenv python 은 의존성 누락으로 실패)

---

## A. graphio-app CLI

콘솔 스크립트는 **`graphio-app`** 하나이며 `graphio_app_framework.cli:main` 에 매핑된다 (pyproject.toml `[project.scripts]`). argparse `prog="graphio-app"`.

| 명령 | 동작 | 플래그 |
|---|---|---|
| `graphio-app run` | 앱 HTTP 서버(uvicorn) 실행. import 단계에서 `load_graph_entry()` 로 메인 그래프 사전 로드 | `--test-ui` (유일한 플래그, store_true) |
| `graphio-app copy-env` | 패키지 내장 `env.template` 을 `.env` 로 복사 | `--dest <파일명>` (기본 `.env`) |
| (인자 없음) | help 출력 | — |

```bash
graphio-app copy-env            # env.template → .env (이미 있으면 [SKIP], 덮어쓰지 않음)
graphio-app run                 # http://localhost:8888
graphio-app run --test-ui       # + Test UI 정적 서버 :18423, 브라우저 자동 오픈
```

- **`run` 의 플래그는 `--test-ui` 하나뿐이다.** `--port` / `--host` 같은 플래그는 **없다** — 포트/호스트는 `.env`(`APP_PORT`/`APP_HOST`)로만 제어한다 (cli.py:176-177, 138-141).
- `copy-env` 는 `dest` 가 이미 존재하면 `[SKIP]` 만 출력하고 **덮어쓰지 않는다** (cli.py:84-86).
- `.env` 는 **CWD 기준** `find_dotenv(usecwd=True)` 로 로드된다 → `graphio-app run` 은 `.env` 가 있는 프로젝트 루트에서 실행해야 한다 (core/config.py:98).
- `run` 은 import 단계에서 `load_graph_entry()` 를 호출하고, 실패하면 `[FATAL]` 출력 후 `sys.exit(1)` 한다 (cli.py:99-105).

---

## B. 두 개의 포트 (8888 vs 18423) — 혼동 금지

| 서버 | 포트 | 주소 | 제어 |
|---|---|---|---|
| 앱 API (uvicorn/FastAPI) | **8888** | `http://localhost:8888` | `.env` 의 `APP_PORT`(기본 8888), `APP_HOST`(기본 0.0.0.0) |
| Test UI 정적 HTML 서버 | **18423** (고정) | `http://localhost:18423/stream_test.html` | 변경 불가 상수 `TEST_UI_STATIC_PORT` |

- 두 포트는 **별개**다. Test UI 페이지(18423)가 그 안에서 API(8888)의 `/graphio/graphio_app/v1` 을 호출한다 (cli.py:14, 127; core/config.py:102-103).
- Test UI 의 API base 는 기본적으로 `http://127.0.0.1:8888/graphio/graphio_app/v1` 이며 `GRAPHIO_TEST_UI_API_BASE` 로 오버라이드 가능 (cli.py:17-31).
- `--test-ui` 없이도 `.env` 에 `TEST_UI=true` 면 API 모듈 import 시 CORS 미들웨어가 붙는다(정적 UI 서버는 안 뜸) (api/graphio_app.py:106-110).

---

## C. 핵심 환경변수

`graphio-app copy-env` 가 만드는 `.env` 에서 채운다. 최소 필수는 **LLM 설정**이다.

| 변수 | 기본값 | 용도 |
|---|---|---|
| `LLM_MODEL` | (필수) | ModelManager 가 읽는 모델명. 미설정 시 `get_chat_model()` 에서 RuntimeError |
| `LLM_API_KEY` | — | API 키 방식(openai/anthropic/google/...) |
| `LLM_API_ADDRESS` | — | vllm/ollama base_url 방식. `LLM_API_KEY` 또는 `LLM_API_ADDRESS` **중 최소 하나 필수** |
| `APP_HOST` | `0.0.0.0` | 앱 API 바인드 호스트 |
| `APP_PORT` | `8888` | 앱 API 포트 |
| `MODE` | `dev` | dev 면 src 미발견 시 framework 기본 그래프로 폴백; prod 면 ImportError |
| `TEST_UI` | — | `true` 면 import 시 CORS 미들웨어 활성화 |
| `PROJECT_ROOT` | — | src 루트 탐색 힌트 → `{PROJECT_ROOT}/src` |
| `PROJECT_SRC_RESOLVED` | — | 이미 해결된 src 경로(최우선) |
| `GRAPHIO_APP_DIR` | (없으면 `services`) | 스캔할 패키지 디렉터리 한정 + 하위 디렉터리 자동 탐색 끔 |
| `ENABLE_FILE_USE` / `ENABLE_CLEAN_USER_UPLOAD_FILES` / `ENABLE_TITLE` | `true` | 자동 주입 노드 토글 (자세한 계약은 advanced-features.md) |
| `GRAPHIO_APP_STORAGE_PATH` / `GRAPHIO_APP_STORAGE` / `GRAPHIO_APP_DB` | `GRAPHIO_APP_STORAGE` / `graphio_app_storage` / `graphio_app.db` | sqlite 체크포인트 디렉터리/파일 |

> `GRAPHIO_APP_STORAGE` 주의: code default(미설정 시)는 `graphio_app_storage`(core/config.py:114)이지만 동봉 `env.template`은 `graphio_app_store`(env.template:13)를 ship한다. `.env`를 template에서 생성(`graphio-app copy-env`)했다면 실제 체크포인트/스토리지 디렉터리명은 `graphio_app_store`가 되어 표의 `graphio_app_storage`와 다르다.

근거: core/config.py:102-121, 111-115; graph_module_loader.py:48-85.

> LLM_MODEL/LLM_API_KEY/LLM_API_ADDRESS 의 자세한 의미·provider 선택 순서는 advanced-features.md(ModelManager 섹션) 참고.

---

## D. 모듈 디스커버리 (src 루트 + 모듈 목록)

### src 루트 탐색 우선순위 (`find_project_src_root`)
1. `PROJECT_SRC_RESOLVED` 환경변수 → 그 경로 그대로
2. `PROJECT_ROOT` 환경변수 → `{PROJECT_ROOT}/src` 탐색
3. CWD 부터 **상위로 최대 4단계** 탐색

모두 실패하면 `ImportError("앱 모듈 경로를 찾을 수 없습니다. PROJECT_ROOT 또는 GRAPHIO_APP_DIR 환경변수를 지정하세요.")`.
결과는 모듈 전역 `_project_src_root` 에 **1회 캐시**된다 (graph_module_loader.py:48-85).

src 후보 검증(`_find_src_with_app`): `root/src/<GRAPHIO_APP_DIR or 'services'>` 가 디렉터리면 `root/src` 채택 → 아니면 `src/` 최상위에 보이는 `.py` 있으면 채택 → 아니면 `src/*/` 하위 디렉터리에 보이는 `.py` 있으면 채택 (graph_module_loader.py:32-45).

### 모듈 목록 빌드 순서 (`_build_services_module_list`)
1. `src/<GRAPHIO_APP_DIR or 'services'>/*.py` — 패키지 디렉터리 (존재 시)
2. `src/*.py` — 최상위
3. **`GRAPHIO_APP_DIR` 미설정 시에만** `src/*/*.py` — 나머지 하위 디렉터리(이미 스캔한 패키지 제외)

각 디렉터리 내부 스캔 순서: **`graph.py` → `agent.py`** 먼저(`PRIORITY_MODULES = ["graph", "agent"]`), 그 다음 `sorted(glob("*.py"))` 알파벳순. **`__init__.py` 와 `_` 로 시작하는 파일은 항상 제외**. 결과는 `_services_modules_cache` 에 1회 캐시 (graph_module_loader.py:10, 92-155).

- `GRAPHIO_APP_DIR` 를 설정하면 3단계(하위 디렉터리 자동 스캔)를 건너뛴다 → 스캔 범위를 좁혀 의도치 않은 그래프 감지를 막을 수 있다.
- 캐시 때문에 경로/모듈을 바꿔도 같은 프로세스에서는 반영되지 않는다. `reset_loader_state()` 로 비우거나 새 프로세스로 실행 (graph_module_loader.py:16-21).

---

## E. 메인 그래프 감지 (`_find_graph_entry_candidate`)

compiled 그래프 객체를 다음 우선순위로 찾는다:
1. **`obj.__graphio_main__ == True` 마커** (권장) — `graphio_app()` 이 자동 설정
2. 변수명이 정확히 **`graphio_app_flow`** 인 compiled 그래프
3. **duck typing 폴백**: `invoke`+`ainvoke`+`astream` 호출 가능 + `checkpointer` 속성 보유 객체 — **단 그 모듈명이 `graph` 또는 `agent`(PRIORITY_MODULES)일 때만** 후보. 이때 `[WARN]` 로그가 남는다.

근거: graph_module_loader.py:178-218.

- `graphio_app()` 은 compile 후 `compiled.__graphio_main__ = True` 를 객체에 설정해 반환한다 (graph_base/graph.py:40). 따라서 **`my_app = graphio_app(...)` 한 줄이면 파일명/변수명과 무관하게** 메인 그래프로 감지된다.
- **모듈 레벨의 `__graphio_main__ = True` 문장은 감지에 사용되지 않는다(no-op).** 감지는 모듈 변수가 아니라 *compiled 객체*의 속성을 본다. 있어도 무해하지만 동작에 기여하지 않으며, 변수명을 `graphio_app_flow` 로 둘 필요도 없다.
- 메인 그래프는 src 트리에 **정확히 1개**만. `graphio_app()` 결과 변수가 여러 개면 모두 마커를 가져, D의 스캔 순서상 먼저 만나는 것이 채택된다.

라이브 확인(데모 앱): 로더가 `services.new_app.my_app 에서 graphio_app() 메인 그래프 감지` 로그를 찍고, 데모는 `graph.py`/`agent.py` 가 없어 모듈이 알파벳순(`services.editor, services.new_app, services.new_state, services.prompt, services.tools`)으로 나열된다.

---

## F. 서버 부팅 흐름과 checkpointer 주입

1. `api/generator.py` 모듈 **import 시점**에 `graph_entry = load_graph_entry()` 가 1회 실행되어 메인 그래프를 해석한다 (api/generator.py:35).
2. `graphio-app run` 도 import 단계에서 `load_graph_entry()` 를 호출, 실패 시 `[FATAL]` 후 `sys.exit(1)` (cli.py:99-105).
3. FastAPI `lifespan` 이 `AsyncSqliteSaver.from_conn_string(<storage_path>/<storage>/<db>)` 로 saver 를 만들어 **런타임에** `graph_entry.checkpointer = saver` 로 주입한다 (api/graphio_app.py:84-90).
4. 스트림/invoke 는 `graph_entry.astream_events(version="v2")` / `.ainvoke` 를 호출한다 (api/generator.py:266).

→ **앱 그래프는 `checkpointer` 없이 compile 해도 된다.** `graphio_app()` 은 `checkpointer=None` 이면 `compile(checkpointer=None)` 하고, 실제 체크포인터는 HTTP lifespan 이 붙인다. (베이스라인의 "생략 시 프레임워크 기본값 사용" 표현은 부정확 — 컴파일 시점엔 None, lifespan 에서 주입.)

dev 폴백: `MODE=dev`(기본)에서 src 루트를 못 찾으면 framework 내장 기본 그래프(dev 심볼명 `graphio_app_flow`)/`GraphioAgentState` 로 폴백한다. `MODE` 가 dev 가 아니면 ImportError 를 그대로 raise (graph_module_loader.py:263-272, 317-324).

---

## G. /stream API — 경로·라우트·요청 스키마

스트리밍 엔드포인트는 **고정 경로**다:

```
POST /graphio/graphio_app/v1/stream      (media_type: text/event-stream)
```

`/graphio/graphio_app/v1` 은 `common_router.prefix` 에 하드코딩된 **프레임워크 고정 prefix** 다. `graphio_app` 은 앱 이름이 아니라 prefix 세그먼트이며 **모든 앱 공통, 변경 불가**. 앱 이름을 넣은 경로는 404 (api/graphio_app.py:104, 134).

전체 라우트(+ FastAPI 기본 `/docs` `/redoc` `/openapi.json`):

| 메서드 | 경로 |
|---|---|
| GET | `/` |
| POST | `/debug/set-cookie` |
| POST | `/graphio/graphio_app/v1/invoke` |
| POST | `/graphio/graphio_app/v1/stream` |
| GET | `/graphio/graphio_app/v1/status` |
| GET | `/graphio/graphio_app/v1/download/{file_id}` |

근거: api/graphio_app.py:118-123, 134, 230-249.

### StreamInput 요청 본문 (api/schema.py:9-59)

| 필드 | 타입 | 기본 | 비고 |
|---|---|---|---|
| `message` | str | (필수) | 사용자 입력 |
| `model` | str | `"gpt-4o"` | configurable.model 로 전달 |
| `thread_id` | str \| None | (키 필수, 값 None 허용) | 키 자체는 빠지면 422 |
| `thread_history` | bool | `True` | false 면 외부 DB/플랫폼 저장 우회(로컬 테스트용) |
| `create_title` | bool | `False` | title 주입 게이트 |
| `active_tool` | dict | `False`(선언) | parse_input 에서 `(active_tool or {})` 로 정규화 → 노드는 항상 dict 가정 가능 |
| `file_names` | list | `[]` | 누적 업로드 파일명 |
| `this_file` | list | `[]` | 이번 업로드 파일명 |
| `stream_tokens` | bool | `True` | false 또는 `MODE=dev_message` 면 message 단위 전송 |
| `request_type` | `'run'`\|`'resume'` | `'run'` | resume 면 HITL 재개 |

> `active_tool` 의 pydantic default 가 `False`(불리언)로 선언된 것은 소스에 실재하는 비일관성이지만, `parse_input` 이 `(active_tool or {})` 로 정규화하므로 **노드는 항상 dict(`{}` 포함)로 가정**하면 된다. schema 의 default=False 는 무시.

---

## H. configurable 매핑 — 노드가 읽는 키

`parse_input()` 이 요청을 `RunnableConfig(configurable={...})` 로 변환한다. 노드는 `config["configurable"][...]` 로 읽는다.

```python
run_config = {
    "access_token": access_token,                 # 쿠키에서 전달, 없으면 None
    "project_resource": project_resource,          # access_token 으로 governance API 조회
    "thread_id": thread_id,
    "model": user_input.model,
    "create_title": user_input.create_title,
    "active_tool": user_input.active_tool or {},   # None → {} 정규화
    "file_names": user_input.file_names,
    "this_file": user_input.this_file,
}
```

근거: api/generator.py:179-188.

```python
from langchain_core.runnables import RunnableConfig

async def my_node(state, config: RunnableConfig):
    cfg = config["configurable"]
    model        = cfg["model"]          # "gpt-4o"
    file_names   = cfg["file_names"]     # list
    this_file    = cfg["this_file"]      # list
    active_tool  = cfg["active_tool"]    # dict (비활성 시 {})
    access_token = cfg["access_token"]   # str | None
    thread_id    = cfg["thread_id"]
    create_title = cfg["create_title"]   # bool
    return state
```

`request_type == "resume"` 면 graph 입력이 `Command(resume=message)` 로, 아니면 `{"messages": [HumanMessage(content=message)]}` 로 들어간다 (api/generator.py:190-194).

---

## I. SSE 응답 형태

각 이벤트는 한 줄 `data: {json}\n\n` 형식. media_type `text/event-stream`.

- 토큰 프레임: `{"type": "token", "content": "<글자>"}` — 글자 단위 스트리밍. title 노드 토큰은 `type: "title_token"`, editor 노드는 `type: "editor"`.
- 메시지 프레임: `{"type": "message", "content": {<ChatMessage dump>}}` — 이때 `content.type` 으로 highlights/chart/file/loading/loading_end/studio_*/interrupt 등 custom type 을 다시 구분.
- 상위 `type` 종류: `token`, `title_token`, `editor`, `message`, `done`, `cancelled`, `editor_start`, `editor_end`.
- 종료는 항상 `data: {"type": "done", "thread_id": "<uuid>"}\n\n`.
- `stream_tokens=false` 또는 환경변수 `MODE=dev_message` 면 토큰 대신 **message 단위**로 전송. custom type 메시지는 `stream_tokens` 와 무관하게 항상 message 단위.

근거: api/generator.py:357, 388, 433; api/schema.py:78-117.

**클라이언트 파싱 권장 순서**: (1) `data: ` 접두 제거 후 JSON 파싱 → (2) 상위 `type` 분기 → (3) `type=="message"` 면 `content.type` 재분기 → (4) `type=="done"` 으로 종료.

---

## J. HITL resume / access_token 쿠키

- **resume**: interrupt 후 재개는 **같은 `thread_id`** 로 `request_type: "resume"` 를 보내며, `message` 가 `Command(resume=message)` 로 그래프에 전달된다. interrupt 발생 시 스트림은 interrupt 값을 token 으로 흘린 뒤 `{"type":"message","content":{"type":"interrupt","content":"true"}}` 와 `done` 을 보내고 종료한다 (api/generator.py:190-194, 425-427).
- **access_token 은 본문이 아니라 `access_token` 쿠키**로 전달된다(`Cookie(alias="access_token")`). 로컬 테스트는 `POST /debug/set-cookie?x_access_token=...` 가 httponly 쿠키를 설정해준다. `access_token=None` 이면 경고만 찍고 진행하므로 로컬 단독 테스트 가능 (api/graphio_app.py:125, 249-255).

---

## K. 로컬 curl 테스트 & graph.png

### /stream 을 curl 로 (외부 DB/플랫폼 없이)

`thread_history:false` 로 두면 app_platform/DB 저장 경로를 우회한다. `-N`(no-buffer)로 SSE 라인이 실시간 출력된다.

```bash
curl -N -X POST http://localhost:8888/graphio/graphio_app/v1/stream \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d '{
    "message": "안녕하세요",
    "model": "gpt-4o",
    "thread_id": "00000000-0000-0000-0000-000000000001",
    "thread_history": false,
    "create_title": false,
    "stream_tokens": true,
    "file_names": [],
    "this_file": [],
    "active_tool": {}
  }'
# 출력 예)
#  data: {"type": "token", "content": "안"}
#  data: {"type": "done", "thread_id": "00000000-0000-0000-0000-000000000001"}
```

HITL 재개 (같은 thread_id, request_type=resume):

```bash
curl -N -X POST http://localhost:8888/graphio/graphio_app/v1/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"사용자 응답","thread_id":"00000000-0000-0000-0000-000000000001","request_type":"resume","thread_history":false}'
```

인증이 필요한 노드 테스트 (쿠키):

```bash
curl -c cookies.txt -X POST 'http://localhost:8888/debug/set-cookie?x_access_token=TEST_TOKEN'
curl -N -b cookies.txt -X POST http://localhost:8888/graphio/graphio_app/v1/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"hi","thread_id":"00000000-0000-0000-0000-000000000001","thread_history":false}'
```

### graph.png 그리기

compiled 그래프는 LangGraph 표준 `get_graph().draw_mermaid_png()` 로 시각화한다. 그래프 모듈에 다음을 두면 직접 실행해 PNG 를 얻는다:

```python
if __name__ == "__main__":
    my_app.get_graph().draw_mermaid_png(output_file_path="graph.png")
```

자동 주입 노드까지 포함된 최종 그래프가 그려지므로 `graph_base_file_use` / `graph_base_clean_user_upload_files` / `graph_base_title` / `graph_base_title_router` 가 보인다(주입 계약은 advanced-features.md).

---

## L. 디버깅 — module-not-found / graph-not-detected

증상별 진단. 검증 명령은 **데모 venv python** 으로 실행한다.

### src 루트 / 모듈 목록 확인

```bash
PROJECT_ROOT=$(pwd) /Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python -c "
from graphio_app_framework.service_utils.graph_module_loader import find_project_src_root, _build_services_module_list
src = find_project_src_root(); print('SRC', src)
print('MODS', _build_services_module_list(src))"
```

### 메인 그래프가 감지되는지 확인

```bash
PROJECT_ROOT=$(pwd) /Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python -c "
from graphio_app_framework.service_utils.graph_module_loader import load_graph_entry
g = load_graph_entry()
print('OK main graph:', type(g).__name__, 'nodes=', list(g.get_graph().nodes))"
```

`[OK] ... 에서 graphio_app() 메인 그래프 감지` 로그가 나오면 정상.

| 증상 | 원인 | 해결 |
|---|---|---|
| `ImportError: 앱 모듈 경로를 찾을 수 없습니다. PROJECT_ROOT 또는 GRAPHIO_APP_DIR ...` | CWD 상위 4단계에서 src 못 찾음, env 힌트 없음 | `.env` 가 있는 프로젝트 루트에서 `graphio-app run`, 또는 `PROJECT_ROOT` 설정 |
| `ImportError: 메인 그래프를 찾을 수 없습니다` | `graphio_app()` 미사용(마커 없음) + 변수명 `graphio_app_flow` 아님 + 파일명 `graph.py`/`agent.py` 아님 | `my_app = graphio_app(build_fn, state_type=AgentState)` 로 감싸 마커 자동 설정 |
| 엉뚱한 그래프가 메인으로 잡힘 | `graphio_app()` 결과 변수가 여러 개 → 스캔 순서상 먼저 만난 것 채택 | 메인은 한 모듈에서만 호출. `GRAPHIO_APP_DIR` 로 스캔 범위 축소 |
| `[WARN] ... duck typing 폴백` | 마커/`graphio_app_flow` 없이 `graph.py`/`agent.py` 의 compiled 그래프로 폴백됨 | `graphio_app()` 로 감싸 마커를 갖게 함 |
| 경로/모듈 바꿨는데 반영 안 됨 | `_project_src_root`/`_services_modules_cache`/`_symbol_cache` 1회 캐시 | `reset_loader_state()` 호출 또는 새 프로세스 |
| `/stream` 호출 시 404 | 앱 이름 넣은 경로 사용 | 항상 `POST /graphio/graphio_app/v1/stream` |
| `/stream` 시 app_platform/DB 연결 오류 | `thread_history` 기본 True 라 외부 add_message 시도 | 본문에 `"thread_history": false` |
| curl 응답이 한꺼번에 버퍼링 | curl 출력 버퍼링 | `curl -N` (--no-buffer) |
| 토큰 스트리밍 안 되고 message 단위만 | `MODE=dev_message` | `MODE` 를 dev_message 로 두지 말고 `stream_tokens:true` |
| import 단계 `RuntimeError: LLM이 초기화되지 않았습니다` | `LLM_MODEL` 미설정 또는 API key/address 둘 다 없음 | `.env` 에 `LLM_MODEL` + (`LLM_API_KEY` 또는 `LLM_API_ADDRESS`) |

> 더 자세한 에러표·파괴적 작업(체크포인트 reset 등) 경고는 troubleshooting-and-gotchas.md 참고.

---

## 관련 reference

- 그래프/State 작성, `graphio_app()` 시그니처: scaffolding-and-authoring.md
- 자동 주입 노드 계약, ModelManager/loader/LOG, service_utils: advanced-features.md
- 포털 zip/폐쇄망 wheel: packaging-and-deploy.md
- 에러 증상 → 원인 → 해결 종합, stale 문서 정정: troubleshooting-and-gotchas.md
