# 트러블슈팅 & 함정 (Troubleshooting and Gotchas)

> **언제 읽는지**: 에러 증상이 떴을 때 / "왜 동작 안 하지?" / 베이스라인·데모 문서 내용이 소스와 안 맞아 보일 때 / `make clean`·DB reset 같은 파괴적 작업을 하기 전.
>
> 이 문서는 모든 영역의 증상 → 원인 → 해결을 한곳에 모은 cross-cutting 표다. 더 깊은 배경은 해당 영역 reference 로 링크한다.

---

## 원칙: 권위 순서 (충돌 시 무엇을 믿나)

사실이 충돌하면 **패키지 소스 > 테스트 > 레퍼런스 앱 > docs/baseline 스킬** 순으로 소스가 이긴다.

- 패키지 소스: `/Users/rhcpn/Github/graphio-app-framework/graphio_app_framework/`
- 테스트: `/Users/rhcpn/Github/graphio-app-framework/tests/`
- 레퍼런스 앱: `/Users/rhcpn/Github/graphio-app-framework/src/services/`
- docs: `/Users/rhcpn/Github/graphio-app-framework/docs/` 와 데모 `docs/graphio_app_dev_guide.md`, 베이스라인 SKILL.md

**모든 import/실행 검증은 반드시 이 venv python 으로** 한다(시스템/pyenv python 은 의존성 누락으로 실패):

```bash
/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python -c "import graphio_app_framework; print(graphio_app_framework.__version__)"
```

---

## A. 그래프 작성 (scaffolding-and-authoring.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| 제목 생성·파일 정리·file_use 같은 공통 기능이 전혀 동작하지 않음 | build 함수 안에서 `builder.compile()` 을 직접 호출해 그 결과를 `graphio_app()` 에 넘겼거나, `graphio_app()` 을 거치지 않고 compiled 그래프를 직접 export 했다. 자동 주입은 `graphio_app()` → `rebuild_graph` 경로에서만 일어난다. | build 함수는 **compile 하지 않은 `StateGraph`** 를 `return` 하고, `my_app = graphio_app(user_graph, state_type=AgentState)` 형태로 감싼다. `user_graph()` 를 직접 호출하지도 말 것. (`graph_base/graph.py:18,38-41`) |
| 노드 추가 시 이름 충돌 / 그래프가 이상하게 동작 / RAG·cleanup 이 두 번 도는 듯 | 앱이 예약 노드 이름을 직접 `add_node` 했다: `graph_base_file_use`, `graph_base_clean_user_upload_files`, `graph_base_title`, `graph_base_title_router`. | 이 4개는 프레임워크 예약어다. 절대 이 이름으로 노드를 추가하지 말 것. 자체 cleanup 이 필요하면 **다른 이름**을 쓴다(레퍼런스 앱은 `clean_user_upload_files` 라는 다른 이름의 자체 노드를 둠 — 주입 노드 `graph_base_clean_user_upload_files` 와 별개). (`injectors/file.py:10-11`, `injectors/title.py:10-11`) |
| 메인 그래프가 자동 감지 안 됨 / 엉뚱한 그래프가 메인으로 잡힘 | 한 `src/` 트리에 `graphio_app()` 반환값이 0개거나 여러 개. 여러 개면 모두 `__graphio_main__` 마커를 가져 스캔 순서상 먼저 만난 것이 채택됨. | 메인 그래프는 **한 모듈에서만** `graphio_app()` 을 호출하고 그 반환값을 모듈 최상위 변수에 할당한다(`my_app = graphio_app(...)`). 서브그래프는 일반 `compile()` 로 만들고 `graphio_app()` 으로 감싸지 않는다. (`graph_base/graph.py:40`, `service_utils/graph_module_loader.py:195-218`) |
| 그래프 entry 를 임의 파일에 두고 `graphio_app()` 없이 `builder.compile()` 결과만 노출 → `ImportError('메인 그래프를 찾을 수 없습니다')` | duck typing 폴백(invoke+ainvoke+astream+checkpointer)은 **모듈명이 `graph.py`/`agent.py` 일 때만** 후보가 된다. 파일명이 다르고 `__graphio_main__` 마커/`graphio_app_flow` 변수명도 없으면 절대 감지 안 됨. | `graphio_app()` 으로 감싸 `__graphio_main__` 마커를 자동 설정하거나, 변수명을 `graphio_app_flow` 로 하거나, 파일명을 `graph.py`/`agent.py` 로 둔다. (`service_utils/graph_module_loader.py:178-218`) |
| baseline/guide 가 "graph 파일은 `graphio.py`/`agent.py` 로 이름지어야 한다"고 읽힘 → **STALE** | `PRIORITY_MODULES = ['graph','agent']` 는 스캔 **순서**와 duck typing 폴백 자격에만 영향. 마커가 있으면 파일명은 자유. | 파일명은 자유롭고 `__graphio_main__` 마커가 핵심임을 기억. (`service_utils/graph_module_loader.py:10`) |
| `rebuild_graph` 이후 종단 노드가 cleanup/title 을 안 거치는 듯함 | 앱 그래프가 `set_entry_point`/`END` 규약을 따르지 않아 재배선 훅이 안 걸림. | 진입점은 `set_entry_point`/`add_edge(__start__, ...)` 로 명확히 두고, 종단은 `END` 로 향하는 엣지로 표현한다. `END` 를 타깃으로 하는 conditional edge 도 첫 post-graph 주입 노드로 재배선되므로, 규약만 지키면 자동으로 cleanup/title 을 거친다. (`graph_base/rebuild.py:46-123`) |

---

## B. State (scaffolding-and-authoring.md / advanced-features.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| 일부 메모/브리프가 "BaseAgentState 는 `total=False`" 라고 함 → **부정확** | 실제 소스는 `class BaseAgentState(MessagesState, total=True)`. 6개 공통 필드가 모두 required. `total=False` 가 등장하는 곳은 앱 서브클래스(`AgentState`/`GraphioAgentState`)이며 거기서도 새로 추가한 키만 optional. | 정확히: **BaseAgentState = `total=True`(6필드 required), 앱 서브클래스 = `total=False`(자체 키만 optional, 상속 6필드는 여전히 required)**. 런타임 `__required_keys__` 로 검증됨. (`states/base_agent.py:5`) |
| 앱에서 `user_upload_files`/`ontology_resource`/`title_output` 를 직접 정의·덮어쓰니 주입 노드 동작과 충돌 | 이 6개 필드(`messages`, `title_output`, `user_upload_files`, `user_upload_files_exclude`, `files`, `ontology_resource`)는 `graphio_app()` 자동 주입 노드가 채우는 계약 필드. | 앱 State 는 `BaseAgentState` 를 상속만 하고 6개 필드는 **재선언 금지**. 새 키만 `total=False` 로 추가한다. (`states/base_agent.py:5-25`) |
| `build_studio_agent()` 서브그래프를 붙였는데 `route_after_studio` 분기가 항상 `model` 로 가거나 studio 동작이 누락 | `BaseAgentState` 만 상속함. studio 전용 4필드(`studio_input`, `studio_type`, `studio_result`, `app_report_list`)는 `BaseAgentState` 에 **없다**. | 앱 `AgentState(total=False)` 에 `studio_input: Optional[dict]`, `studio_type: Optional[str]`, `studio_result: Optional[str]`, `app_report_list: Optional[list]` 4개를 직접 선언한다(또는 `GraphioAgentState` 를 상속). (`graph_base/agent.py:6-10`) |
| baseline SKILL.md 가 "BaseAgentState 가 studio_* 필드를 제공"하는 것처럼 읽힘 → **STALE** | studio_* 는 `GraphioAgentState`(graph_base/agent.py)와 `StudioStateMixin`(states/studio_mixin.py)에만 있고 `BaseAgentState` 엔 없다. | BaseAgentState 가 제공하는 건 정확히 6개. studio 쓰면 직접 선언. (위 참조) |
| `StudioStateMixin` 과 `GraphioAgentState` 를 혼동 | 둘은 필드가 거의 겹치지만 별개다. `StudioStateMixin(MessagesState, total=False)` 은 `studio_input`/`studio_type`/`app_report_list` 만(=`studio_result` 없음, BaseAgentState 미상속). `GraphioAgentState(BaseAgentState, total=False)` 는 4필드 모두(+`studio_result`). | **폴백/기본 State = `GraphioAgentState`** (StudioStateMixin 아님). `from graphio_app_framework.graph_base.agent import GraphioAgentState`. (`states/studio_mixin.py:5-9`, `graph_base/agent.py:1-11`) |
| `AgentState` 를 정의 안 했는데 그래프가 동작 → 정상 | 앱 모듈에서 `AgentState` 심볼을 못 찾으면 framework 가 `GraphioAgentState` 로 자동 폴백(에러 아님). 로그: `[OK] AgentState 미정의 — framework 기본값(GraphioAgentState) 사용`. | State 확장이 필요 없으면 생략 가능. 자체 키가 필요하면 `AgentState(BaseAgentState, total=False)` 정의 후 `graphio_app(state_type=AgentState)` 로 명시 전달. (`service_utils/graph_module_loader.py:291-296`) |

---

## C. 실행 / CLI (run-and-debug.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| `graphio-app run --port 9000` / `--host` 가 인식 안 됨 | `run` 의 **유일한 플래그는 `--test-ui`**. 포트/호스트는 CLI 인자가 아니다. | 포트는 `.env` 의 `APP_PORT`, 호스트는 `APP_HOST` 로 설정. `graphio-app run` / `graphio-app run --test-ui` 두 형태뿐. (`cli.py:176-189`) |
| Test UI 가 8888 에서 열릴 줄 알았는데 18423 에서 열림 / 두 포트 혼동 | 앱 API 서버 포트(`APP_PORT`, 기본 **8888**)와 Test UI 정적 HTML 서버 포트(고정 **18423**)는 별개. | 브라우저 UI = `http://localhost:18423/stream_test.html`, API = `http://localhost:8888/graphio/graphio_app/v1`. (`core/config.py:102-103`, `cli.py:14`) |
| `ImportError('PROJECT_ROOT 또는 GRAPHIO_APP_DIR 환경변수를 지정하세요.')` / 앱 모듈을 못 찾음 | CWD 기준 상위 4단계 안에서 `src/` 를 못 찾았고 env 힌트도 없음. | 프로젝트 루트(`src/` 와 `.env` 가 있는 곳)에서 실행하거나, `PROJECT_ROOT` 를 지정(→ `{PROJECT_ROOT}/src` 탐색)하거나 `GRAPHIO_APP_DIR` 로 스캔 패키지를 좁힌다. `MODE=dev`(기본)는 src 미발견 시 framework 기본 그래프로 폴백, `MODE=prod` 면 ImportError raise. (`service_utils/graph_module_loader.py:48-85,263-272`) |
| src 경로/모듈 목록을 바꿨는데 반영 안 됨 | `_project_src_root`/`_services_modules_cache`/`_symbol_cache` 가 모듈 전역에 1회 캐시됨. | `reset_loader_state()` 호출로 캐시를 비우거나 새 프로세스로 실행. (`service_utils/graph_module_loader.py:16-21`) |
| baseline 이 "메인 그래프 파일에 `__graphio_main__ = True` 문장을 추가하라"고 함 → 오해 소지 | 감지 로직은 모듈 전역 변수가 아니라 **compiled graph 객체의 속성**을 본다. `graphio_app()` 이 이미 `compiled.__graphio_main__ = True` 를 설정해 반환하므로 `my_app = graphio_app(...)` 한 줄로 충분. | 모듈 레벨 `__graphio_main__ = True` 문장은 감지에 **무관(no-op)**. 있어도 무해하지만 동작에 기여하지 않는다. (`graph_base/graph.py:40`, `service_utils/graph_module_loader.py:201-203`) |
| 시스템/pyenv python 으로 import 검증 시 의존성 누락으로 실패 | 프레임워크 의존성이 demo venv 에만 설치됨. | 모든 import/run 검증은 `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python` 으로. |

### 모듈/그래프 진단 명령 (venv python)

```bash
PROJECT_ROOT=$(pwd) /Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python -c "
from graphio_app_framework.service_utils.graph_module_loader import find_project_src_root, _build_services_module_list
src = find_project_src_root(); print('SRC', src); print('MODS', _build_services_module_list(src))"
```

---

## D. /stream API (run-and-debug.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| `/graphio/{앱이름}/v1/stream` 처럼 앱 이름을 넣어 호출 → 404 | prefix 는 `common_router` 에 `/graphio/graphio_app/v1` 로 하드코딩됨. `graphio_app` 은 앱 이름이 아니라 프레임워크 **고정 세그먼트**. | 항상 `POST /graphio/graphio_app/v1/stream` (모든 앱 공통). 기본 서버 `http://localhost:8888`. (`api/graphio_app.py:104,134`) |
| 로컬 단독 테스트 중 app_platform/DB 연결 오류·thread history 저장 실패 로그 | `thread_history` 기본값이 `True` 라 종료 시 외부 app_platform 으로 `add_message` POST 를 시도. | 로컬 테스트에서는 본문에 `"thread_history": false` 를 넣어 DB/플랫폼 저장 경로를 우회. (`api/graphio_app.py` thread_history 분기) |
| `active_tool` 기본값을 빈 dict `{}` 로 가정했는데 어긋남 | `schema.py` 에서 `active_tool: dict` 의 `default=False`(불리언)로 선언된 **비일관 설계**(소스에 실재). 하지만 `parse_input` 에서 `(active_tool or {})` 로 정규화됨. | 노드 코드에서는 `config['configurable']['active_tool']` 가 **항상 dict({} 포함)** 라고 가정 가능. schema 의 `default=False` 는 무시한다. (`api/schema.py:27-40`, `api/generator.py:179-188`) |
| SSE 파싱 실패: `token` 외에 `message`/`editor`/`title_token`/`done`/`editor_start`/`editor_end`/`cancelled` 가 섞여 옴 | 상위 `type` 종류가 다양하고, `type=='message'` 일 때 `content` 는 ChatMessage dict 이며 그 안의 `content.type`(highlights/chart/file/loading/loading_end/studio_*/interrupt)으로 재구분해야 한다. | 클라이언트는 (1) `data: ` 접두 제거 후 JSON 파싱 → (2) 상위 `type` 분기 → (3) `type=='message'` 면 `content.type` 재분기 → 마지막 `type=='done'` 으로 종료. (`api/generator.py:345-357,388,433`) |
| curl 로 SSE 를 보면 한꺼번에 버퍼링되어 스트리밍처럼 안 보임 | curl 기본 출력 버퍼링. | `curl -N` (`--no-buffer`) 플래그 사용. 서버는 이미 `Cache-Control: no-cache`, `Connection: keep-alive` 를 설정함. |
| `thread_id` 를 본문에서 빼면 422 검증 오류 | `UserInput.thread_id` 는 `str \| None` 이지만 default 가 없어 **키 자체는 필수**. | `thread_id` 키는 항상 포함하되 값으로 UUID 문자열 또는 `null` 을 넣는다. (`api/schema.py:19-22`) |
| `MODE` 에 따라 토큰 스트리밍이 안 되고 message 단위로만 나옴 | `os.getenv('MODE')=='dev_message'` 이면 `stream_tokens` 값과 무관하게 message 단위 전송으로 전환. | 토큰 스트리밍을 보려면 `MODE` 를 `dev_message` 로 두지 말고(기본 `dev`), `"stream_tokens": true` 로 요청. (`api/generator.py:345-349`) |
| 데모 dev guide / baseline 이 `/stream` 만 언급, `invoke`/`status`/`download`/`debug` 누락 → **STALE/축약** | 문서가 핵심 엔드포인트만 요약. | 실제 라우트: `GET /`, `POST /debug/set-cookie`, `POST .../v1/invoke`, `POST .../v1/stream`, `GET .../v1/status`, `GET .../v1/download/{file_id}`(+ FastAPI `/docs` `/redoc` `/openapi.json`). (`api/graphio_app.py:118-255`) |
| `create_title` 가 예제마다 다른 config 키에서 읽힘(`configurable` vs `metadata`) | production(/stream)은 `config['configurable']['create_title']`, 일부 테스트/데모 경로는 `config['metadata']['create_title']` 로 읽는 이중 경로 존재. | `configurable.create_title` 을 **authoritative** 로 사용한다. TitleInjector/`parse_input` 모두 configurable 기준. `metadata.create_title` 은 앱-side 편의일 뿐. (`injectors/title.py:35-45`, `api/generator.py:179-188`) |

---

## E. service_utils (advanced-features.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| `from graphio_app_framework.service_utils import build_studio_agent` / `chart_agent` 가 `ImportError` | `service_utils/__init__.py` 가 0바이트 빈 파일이라 패키지 레벨 re-export 가 전혀 없다. | 항상 **서브모듈 전체 경로**로 import: `from graphio_app_framework.service_utils.studio_agent import build_studio_agent`, `...service_utils.chart import chart_agent`, `...service_utils.file_refer import file_refer_agent`, `...service_utils.file_use import pending_file, clean_user_upload_files`. |
| `service_utils.chart`/`file_refer`/`studio` 등을 import 만 했는데 `RuntimeError('LLM이 초기화되지 않았습니다...')` 또는 MinIO `ValueError('path in endpoint is not allowed')` | 이 모듈들은 **import 시점**(모듈 최상위)에 `ModelManager.get_chat_model()` / `create_client()`(MinIO)를 즉시 호출. | `.env`/env.template 로 `LLM_MODEL` + (`LLM_API_KEY` 또는 `LLM_API_ADDRESS`), 그리고 `C_MINIO_CLIENT_HOST`(스킴 없는 host, 예 `localhost`)를 세팅한 뒤 import. 정상 `graphio-app run` 환경에서는 자동 충족. 오프라인 검증 시 `utils.models._probe`/`_create_llm` 를 monkeypatch. (`service_utils/chart.py:14`) |
| 데모 dev guide 의 `pending_studio_agent → studio_url_start → studio_url_agent → studio_url_end` / `studio_param_*` 흐름도대로 노드를 직접 와이어링했더니 안 맞음 → **STALE** | 그 흐름도는 레거시 `studio_node.py`/`studio.py` 경로. 현재 권장 진입점은 `studio_agent.py` 의 `build_studio_agent()` 서브그래프. | `agent.add_node('studio_agent', build_studio_agent())` 로 통째 등록. `studio_url_start`/`pending_studio_agent` 같은 레거시 개별 노드는 신규 앱에서 사용 안 함. (`service_utils/studio_agent.py:553-578`) |
| 파일 RAG 노드(`file_use`)를 직접 `add_node` 했더니 주입 노드 `graph_base_file_use` 와 중복되거나 RAG 가 두 번 도는 듯 | `FileUseInjector`/`CleanUserUploadFilesInjector` 가 자동 주입(`ENABLE_FILE_USE`/`ENABLE_CLEAN_USER_UPLOAD_FILES` 기본 true). 앱이 같은 기능을 또 추가하면 혼동. | 기본 경로에서는 `pending_file`/`file_use` 를 직접 add_node 하지 말고 인젝터에 맡긴다. RAG 게이트를 직접 제어하려면 `ENABLE_FILE_USE=false` 로 자동 주입을 끈 뒤 수동 와이어링. (`injectors/file.py:10-31`) |
| `chart_agent`/`file_refer_agent` 를 `add_node` 할 때 config 인자를 기대하고 잘못 래핑 | 두 함수는 `async def fn(state)` — **config 파라미터가 없다**. `file_use`/`title_model`/`ontology_*`/`clean_user_upload_files` 는 `(state, config)`. | `chart_agent`, `file_refer_agent` 는 함수 자체를 그대로 add_node. config 가 필요한 노드와 시그니처가 다름에 주의. (`service_utils/chart.py:96-123`, `file_refer.py:59-69`) |
| 보고서 '조작'(operation) 경로가 절대 안 타고 항상 done/generation 으로만 분기 | operation 경로는 `config['configurable']['active_tool']` 가 `{'type':'studio','value':<보고서 URL>}` 형태여야 활성화. type 불일치/미전달 시 `studio_result='error'`. | 클라이언트/포털이 보낸 `configurable.active_tool` 을 그대로 전달하고, `active_tool.value` URL 이 `app_report_list` 의 `report['url']` 과(query 제거 후) 일치하는지 확인. (`service_utils/studio_agent.py:360-377`) |

---

## F. utils (advanced-features.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| `loader("...")` 를 호출했는데 로딩 메시지가 전혀 안 뜸 | (1) `config` 인자를 안 넘겼거나 `None` 이 전달됨 — loader 는 `config is None` 이면 조용히 `return`. (2) `await` 누락(loader 는 async). (3) 그래프가 `astream_events(v2)`(=`/stream`) 경로로 실행돼야 `on_custom_event` 가 잡힘. | 노드 시그니처를 `async def node(state, config: RunnableConfig)` 로 두고 그 config 를 `await loader("...", config)` 로 그대로 전달. (`utils/loading.py:11-24`) |
| `ModelManager.get_chat_model()` 호출 시 `RuntimeError('LLM이 초기화되지 않았습니다...')` 또는 `'LLM_API_KEY 미설정...'` | `LLM_MODEL` 이 비었거나, `LLM_API_KEY`/`LLM_API_ADDRESS` 둘 다 미설정. | `.env`(또는 컨테이너 env)에 `LLM_MODEL` 과 (`LLM_API_KEY` 또는 `LLM_API_ADDRESS`)를 설정. 모델명/키를 코드에 **하드코딩 금지**. (`utils/models.py:177-183,210-212`) |
| LLM 옵션을 매번 바꿔 호출하니 느림/메모리 누수처럼 보임 | `disable_streaming=True` 또는 `temperature` 지정 시 `get_chat_model` 은 캐시를 안 쓰고 매 호출마다 새 인스턴스를 생성. | 옵션 지정 LLM 은 노드 **밖(모듈 레벨)**에서 1회 생성해 재사용. (`utils/models.py:214-248`) |
| 로그가 콘솔에 안 보임 | `LOG_CONSOLE_ENABLED` 기본값이 `false` 라 콘솔 핸들러 미추가. 로그는 파일에만 쌓임. | 개발 중 콘솔 확인이 필요하면 `LOG_CONSOLE_ENABLED=true`. 파일 로그: `{STORAGE_PATH}/{LOG_DIRECTORY}/{APP_ID}/app_container.log`. (`utils/logger.py:41,52-67`) |
| 앱에서 `logging.getLogger(__name__)` 로 별도 로거를 만들었더니 파일/Phoenix 에 안 잡힘 | 프레임워크는 `graphio-app-container` 로거에만 파일/Phoenix 핸들러를 붙인다. 별도 로거는 핸들러가 없다. | `from graphio_app_framework.utils.logger import LOG` 후 `LOG` 를 그대로 사용. (`utils/logger.py:33,100`) |
| baseline/문서가 minio·rabbitmq·VectorStore·AsyncPostgresDB 를 앱 필수 유틸처럼 소개 → 과대 표현 | 이들은 인프라/내부용으로 레퍼런스·데모 앱 services 에서 직접 import 되지 않음. 일반 앱이 늘 쓰는 건 `ModelManager`/`loader`/`LOG`/`find_latest_human_message`/`get_chat_file_path` 뿐. | 핵심 util 과 '필요 시 고급' 인프라 클라이언트를 분리해 이해. 인프라 클라이언트는 모두 config(env) 기본값 자동주입이므로 호스트/크리덴셜 **하드코딩 금지**. |
| 소스에서 `from utils.logger import LOG`(전체 경로 아님)를 보고 혼란 | `__init__.py` 의 `_register_compat()` 가 `sys.modules` 에 `utils.logger` 같은 짧은 별칭을 등록해 동작(폴백 import). | 앱 코드는 항상 정식 경로 `graphio_app_framework.utils.logger` 사용. 짧은 별칭은 호환용. (`__init__.py:40-171`) |

---

## G. 패키징 (packaging-and-deploy.md 참조)

| 증상 | 원인 | 해결 |
|---|---|---|
| 포털 업로드 후 앱을 인식 못 하거나 `src/` 를 못 찾음 | zip 에 절대경로를 넘기거나 상위 폴더째 압축해, ZIP 내부 최상위에 `src/` 와 `requirements.txt` 가 직접 보이지 않고 한 단계 더 깊이 들어감. | 반드시 프로젝트 루트로 `cd` 한 뒤 `zip -r app.zip src requirements.txt [wheels]` 상대경로 압축. `scripts/package.sh` 로 만들면 `unzip -l` 재검증까지 자동. |
| 폐쇄망 wheel 서버에서 `Could not find a version that satisfies the requirement ...` | (a) 의존성 wheel 이 서버에 없음, 또는 (b) wheel 을 버전별 **하위 폴더**에 두어 `--find-links` 가 재귀 탐색 못함. | 모든 `.whl` 을 서버 **단일 폴더(flat)**에 둔다. 누락 패키지는 `pip download <pkg>==<ver> --only-binary=:all: --python-version 3.11 --platform <p> --implementation cp -d ./whls/` 로 추가. |
| `no matching distribution found`(플랫폼 불일치) | `download_wheels.sh` 의 `--platform` 이 설치 서버 아키텍처와 다름(예: Mac arm64 휠을 Linux x86_64 에 설치). | 설치 서버에서 `uname -m` 확인 후 `x86_64→manylinux2014_x86_64`, `aarch64→manylinux2014_aarch64`, Mac arm64→`macosx_13_0_arm64` 로 `--platform` 지정. |
| `requirements.txt` 에 fastapi/langchain 등을 직접 적었더니 pip 버전 충돌/설치 실패 | `graphio_app_framework` 가 이미 핀한 전이 의존성을 중복 기재해 해석 충돌. | `requirements.txt` 에는 `graphio_app_framework` 한 줄과 **앱 고유 패키지만**. 프레임워크 전이 의존성은 자동 해결됨. |
| 버전을 올렸는데 빌드 산출물이 옛 코드 그대로 | 같은 파일명의 기존 `dist/*.whl` 이 남아 덮어쓰지 않음. | **`make clean` 후 `make build`** (`Makefile:35-40`). ⚠️ make clean 은 파괴적 — 아래 I 항목 참조. |
| `download_wheels.sh` 실행 중 'build 모듈 없음' 에러 | `python -m build` 를 쓰는데 `build` 패키지 미설치. | `pip install build` 후 재실행. |
| INSTALL.md/OFFLINE_INSTALL.md 의 `graphio_app_framework==0.2.0` 을 그대로 설치 시도 → 없는 버전 → **STALE** | 문서 예시 버전(0.2.0)이 실제 패키지 version(**0.1.0**)과 불일치. | 실제 버전은 `pyproject.toml` version 기준(현재 0.1.0). 데모 `requirements.txt` 도 `==0.1.0`. 버전을 하드코딩하지 말고 pyproject 에서 확인. |
| INSTALL.md 끝의 '참고'가 `docs/PACKAGING_GUIDE.md` 를 링크하지만 파일 없음 → **STALE 링크** | 존재하지 않는 문서 참조가 남음. | 패키징 설계 원칙은 `docs/BUILD.md` 의 '패키징 설계 원칙' 섹션 참조. |
| OFFLINE_INSTALL.md 에 Step 1·2·4 만 있고 Step 3 가 비어 있음 → **문서 편집 흔적** | 섹션 번호 누락. | 실제 흐름은 ① `download_wheels.sh` ② wheel 서버 flat 업로드 ③ `requirements.txt` 작성 + `pip install --no-index --find-links` 설치 3단계. |

---

## H. 비스트리밍 LLM 미사용 시 JSON 토큰 SSE 누출

| 증상 | 원인 | 해결 |
|---|---|---|
| 내부/구조화-출력 LLM 호출의 raw JSON 토큰이 SSE 스트림으로 새어 사용자에게 보임 | `astream_events(v2)` 가 모든 `on_chat_model_stream` 토큰을 전달. 스트리밍이 켜진 모델을 분류/구조화 출력에 쓰면 JSON 이 노출됨. | **비사용자대면 LLM 은 `ModelManager.get_chat_model(disable_streaming=True)`** 로 만든다(분류·구조화 출력·라우팅 등). 프레임워크 `file_use._get_llm`, `chart.no_stream_model` 도 이 패턴. (`utils/models.py:199-248`) |

---

## I. ⚠️ 파괴적 작업 — 실행 전 반드시 사용자 확인

아래 작업들은 **데이터/체크포인트를 영구 삭제**한다. 에이전트는 실행 전에 반드시 사용자에게 확인을 받아야 한다. 절대 자동으로 돌리지 말 것.

| 작업 | 무엇이 삭제되나 | 주의 |
|---|---|---|
| `make clean` | `dist/`, `build/`, `*.egg-info`, **`graphio_app_framework/GRAPHIO_APP_STORAGE` 와 `GRAPHIO_APP_STORAGE`(스토리지 디렉터리 전체)**, 모든 `__pycache__`, `*.pyc` | 스토리지 디렉터리에는 sqlite 체크포인트 DB 와 업로드/생성 파일이 들어 있을 수 있다. 빌드 정리 목적이라도 스토리지가 함께 날아간다는 사실을 사용자에게 고지 후 진행. (`Makefile:36-39`) |
| 체크포인터 DB(.db) 삭제 / "db reset" | HTTP lifespan 이 만든 sqlite 체크포인트 파일 `{GRAPHIO_APP_STORAGE_PATH}/{GRAPHIO_APP_STORAGE}/{GRAPHIO_APP_DB}` | 이 파일을 지우면 모든 thread 의 대화 이력/HITL 재개 상태가 사라진다(`AsyncSqliteSaver`). 삭제 전 사용자 확인 필수. (`api/graphio_app.py:84-90`) |
| 스토리지 디렉터리 `rm -rf` | 위 sqlite DB + 로그 파일(`app_container.log`) + 업로드/다운로드 파일 | 복구 불가. 반드시 경로를 사용자에게 보여주고 확인 후 진행. |

체크포인터 동작 참고: `graphio_app()` 은 `checkpointer=None` 이면 `compile(checkpointer=None)` 으로 컴파일 시점엔 체크포인터가 없다. HTTP 앱 실행 시 lifespan 이 `AsyncSqliteSaver.from_conn_string(...)` 로 saver 를 만들어 `graph_entry.checkpointer = saver` 로 런타임 할당한다. 따라서 앱은 보통 checkpointer 를 생략한다. (baseline 의 "생략 시 프레임워크 기본값 사용" 표현은 부정확 — 컴파일 시점엔 `None`, HTTP lifespan 에서 주입.) (`api/graphio_app.py:84-90`, `graph_base/graph.py:38-41`)

---

## J. 문서 권위 순서 요약 (stale 대응 빠른 참조)

충돌·의심 시 이 순서로 신뢰한다. 위 표의 **STALE** 표시 항목들은 모두 docs/baseline 이 소스와 어긋난 사례다.

1. **패키지 소스** — `graphio_app_framework/` (최우선)
2. **테스트** — `tests/`
3. **레퍼런스 앱** — `src/services/` (현행 권장: 인라인 `graphio_app()` + `__graphio_main__` 마커)
4. **docs/baseline 스킬** — 최후순위. 특히 버전(0.2.0), studio 흐름도, BaseAgentState 필드표, 엔드포인트 목록이 stale.

검증은 항상 `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python`.

---

## 관련 reference 링크

- [scaffolding-and-authoring.md](./scaffolding-and-authoring.md) — A·B 항목 배경(그래프 작성, State 계약)
- [run-and-debug.md](./run-and-debug.md) — C·D 항목 배경(CLI, 모듈 디스커버리, /stream)
- [advanced-features.md](./advanced-features.md) — E·F·H 항목 배경(service_utils, utils, 비스트리밍 LLM)
- [packaging-and-deploy.md](./packaging-and-deploy.md) — G·I 항목 배경(포털 zip, 폐쇄망 wheel, make clean)
- [../SKILL.md](../SKILL.md) — 라우터 / 결정 맵
