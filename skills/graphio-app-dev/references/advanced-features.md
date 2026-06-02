# 고급 기능 — service_utils / utils 재사용 + 자동 주입 노드 계약

이 문서는 graphio-app-framework 가 제공하는 **재사용 가능한 노드/헬퍼**(`service_utils`, `utils`)와, `graphio_app()` 이 그래프에 **자동으로 끼워넣는 노드의 계약**을 다룬다. "studio_agent·chart·file_use·ontology·title 같은 framework 노드를 쓴다 / ModelManager·loader·LOG 를 재사용한다 / 자동 주입 노드를 이해한다 / 서브그래프를 합성한다" 일 때 이 파일을 읽는다.

모든 비자명 사실은 framework 소스(파일:라인)가 ground truth다. import/실행 검증은 항상 `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python` 으로 한다(시스템/pyenv python 은 의존성 누락으로 실패).

관련 문서:
- 그래프 작성/State 정의 기본 → [scaffolding-and-authoring.md](./scaffolding-and-authoring.md)
- CLI/실행/디버그/configurable 키 → [run-and-debug.md](./run-and-debug.md)
- 에러 증상→원인→해결 → [troubleshooting-and-gotchas.md](./troubleshooting-and-gotchas.md)

---

## A. service_utils import 규칙 — 항상 서브모듈 전체 경로

`graphio_app_framework/service_utils/__init__.py` 는 **0바이트(빈 파일)**다. 패키지 레벨 re-export 가 전혀 없으므로 **반드시 서브모듈 전체 경로**로 import 한다.

```python
# OK — 서브모듈 전체 경로
from graphio_app_framework.service_utils.studio_agent import build_studio_agent
from graphio_app_framework.service_utils.chart import chart_agent
from graphio_app_framework.service_utils.file_refer import file_refer_agent
from graphio_app_framework.service_utils.file_use import pending_file, clean_user_upload_files
from graphio_app_framework.service_utils.util_node import file_use, ontology_info, ontology_config_info
from graphio_app_framework.service_utils.title import TitleSummary, TitleOutput

# ImportError — 패키지 레벨 import 금지
from graphio_app_framework.service_utils import build_studio_agent   # ✗
```

> 근거: `graphio_app_framework/service_utils/__init__.py` (empty, 0 bytes).

> 참고: framework `__init__.py` 의 호환 shim 때문에 `from service_utils.chart import chart_agent` 같은 짧은 경로도 동작하지만, 앱 코드는 명확성을 위해 항상 `graphio_app_framework.service_utils...` 전체 경로를 쓴다.

---

## B. 자동 주입 노드 계약 (가장 중요) — 이름 4개 + 트리거 + 재배선

`graphio_app()` 은 `build_graph_fn()` 으로 만든 원본 builder 를 `rebuild_graph()` 로 복제하면서 **3개의 injector** 를 적용한다. 각 injector 는 `GraphConfig` 환경변수가 켜져 있을 때만(기본 모두 켜짐) 노드를 주입한다.

### 예약 노드 이름 4개 — 절대 직접 `add_node` 하지 말 것

| 상수 | 노드 이름 | 역할 | source |
|---|---|---|---|
| `FILE_USE_NODE` | `graph_base_file_use` | 파일 RAG(pgvector) 조회 | `injectors/file.py:10` |
| `CLEAN_USER_UPLOAD_FILES_NODE` | `graph_base_clean_user_upload_files` | 종단 직전 user_upload_files 정리 | `injectors/file.py:11` |
| `TITLE_NODE` | `graph_base_title` | 제목 생성 | `injectors/title.py:10` |
| `TITLE_ROUTER_NODE` | `graph_base_title_router` | 제목 라우터(통과 노드) | `injectors/title.py:11` |

앱이 이 4개 이름으로 `add_node` 하면 이름 충돌/중복 주입이 발생한다. 자체 cleanup 이 필요하면 **다른 이름**을 쓴다(레퍼런스 앱은 `clean_user_upload_files` 라는 *다른* 이름의 자체 노드를 두기도 한다 — 주입 노드 `graph_base_clean_user_upload_files` 와 별개라 충돌하지 않는다).

### 3개 injector와 ENABLE_* 트리거

`GraphConfig` 는 **import 시점**에 환경변수를 읽고, `_env_bool(name, default) = os.getenv(name, default).lower() == "true"` 로 판정한다(대소문자 무시, `'true'` 만 켜짐). 세 변수 모두 기본 `'true'`.

| Injector | 트리거 env (기본 true) | 주입 위치 | source |
|---|---|---|---|
| `FileUseInjector` | `ENABLE_FILE_USE` | PRE-graph (`__start__` 앞) | `graph_base/graph.py:29-30`, `injectors/file.py:16-31` |
| `CleanUserUploadFilesInjector` | `ENABLE_CLEAN_USER_UPLOAD_FILES` | POST-graph (END 직전) | `graph_base/graph.py:32-33`, `injectors/file.py:34-47` |
| `TitleInjector` | `ENABLE_TITLE` | POST-graph (END 직전) | `graph_base/graph.py:35-36`, `injectors/title.py:14-60` |

> 근거: `graphio_app_framework/graph_base/config.py:4-13`.

### 런타임 게이트 — ENABLE_* 가 켜져도 매번 도는 건 아니다

ENABLE_* 는 "노드를 그래프에 끼울지" 결정한다. 실제 노드 본문 실행은 **요청별 `configurable`** 로 다시 게이트된다.

- **file_use**: `__start__` 에서 `pending_file` 라우터가 분기한다. `config["configurable"]["file_names"]` 와 `["this_file"]` 가 **둘 다 비어 있으면 무조건 `'done'`** 으로 원래 entry 직행. 하나라도 있으면 LLM 이 "추가 조사 필요 여부"를 판단해 `'file_use'`(노드 실행) 또는 `'done'` 반환. → 즉 ENABLE_FILE_USE=true 여도 파일이 없으면 `graph_base_file_use` 는 실행되지 않는다.
  > 근거: `service_utils/file_use.py:34-79` (`pending_file`).
- **title**: `graph_base_title_router` 의 `_check_title_route` 가 `GraphConfig.ENABLE_TITLE` 가 false 이거나 `config["configurable"]["create_title"]` 가 falsy 면 `END`, 둘 다 truthy 면 `graph_base_title` 로 라우팅. → 즉 `create_title=true` 요청에서만 제목 생성.
  > 근거: `injectors/title.py:35-45`.
- **clean_user_upload_files**: 런타임 게이트 없음. 켜져 있으면 **모든 종단 직전에 항상 실행**되며 `{"user_upload_files": None, "user_upload_files_exclude": None}` 를 반환해 state 를 비운다.
  > 근거: `service_utils/file_use.py:362-369`.

### rebuild_graph 의 END 재배선 규약 (advanced)

`rebuild_graph(original_builder, state_type, injectors)` 는 원본을 복제하면서:
1. `__start__ → entry` 엣지를 가로채 file_use pre-graph 게이트로 대체(`inject_file_use` 시).
2. `* → END` 로 가던 모든 종단 노드(`end_nodes`)와 **conditional edge 가 `END` 를 타깃으로 한 경우**를, 첫 post-graph 주입 노드(`hook`)로 재배선한다.

즉 **유저 그래프가 `END` 로 가도 cleanup/title 을 거쳐서 끝난다**. 따라서 앱 build 함수는 `set_entry_point(...)` / `add_edge(node, END)` / `add_conditional_edges(..., {..., END: END})` 처럼 **진입점과 종단을 표준 규약(START/END)으로 표현**해야 재배선이 올바르게 동작한다.

> 근거: `graphio_app_framework/graph_base/rebuild.py:46-123` (특히 `end == END` 수집 73-74행, conditional END → hook 재배선 116-121행).

---

## C. Studio — `build_studio_agent()` 진입점 (compiled 서브그래프)

보고서(IRIS Studio) 생성/조작 기능. 진입점은 **`build_studio_agent()` 하나**이며, 컴파일된 서브그래프를 통째로 `add_node` 한다.

```python
from langgraph.graph import END, StateGraph
from graphio_app_framework.service_utils.studio_agent import build_studio_agent

studio_agent = build_studio_agent()   # 인자 없음 → compiled StateGraph(name="studio_agent")

def user_graph():
    agent = StateGraph(AgentState)
    agent.add_node("studio_agent", studio_agent)   # 서브그래프 통째로 add_node
    agent.add_node("model", acall_model)
    agent.set_entry_point("studio_agent")
    # studio 후 분기: studio_result 가 있으면 보고서 처리 완료 → END, 없으면 일반 질문 → model
    agent.add_conditional_edges("studio_agent", route_after_studio, {"model": "model", END: END})
    agent.add_edge("model", END)
    return agent
```

- `build_studio_agent() -> StateGraph` — **인자 없음**, `g.compile(name="studio_agent")` 반환.
  > 근거: `service_utils/studio_agent.py:553-578`.
- top-level 내부 노드: `__start__`, `studio_router`, `studio_url_pipeline`, `studio_param_pipeline`, `__end__`. `studio_url_pipeline`/`studio_param_pipeline` 은 각각 `start → agent → end → response` 서브그래프다. **앱은 이 내부 노드를 직접 와이어링하지 않는다.**
  > 근거: `service_utils/studio_agent.py:553-573`.

### Studio 가 요구하는 State 필드 — AgentState 에 직접 선언

서브그래프 내부는 `GraphioAgentState` 로 만들어졌고, **`studio_input` / `studio_type` / `studio_result` / `app_report_list` 4필드를 읽고 쓴다**. `BaseAgentState` 에는 이 필드가 **없으므로**, 앱 `AgentState(total=False)` 에 직접 선언해야 메인 그래프에서 분기가 동작한다.

```python
from typing import Optional
from graphio_app_framework.states import BaseAgentState

class AgentState(BaseAgentState, total=False):
    studio_input: Optional[dict]
    studio_type: Optional[str]     # studio_router 가 'generation'|'operation'|'done' 설정
    studio_result: Optional[str]   # 파이프라인이 'url'|'param'|'error'|None 설정
    app_report_list: Optional[list]
```

> 근거: `graphio_app_framework/graph_base/agent.py:6-10` (GraphioAgentState 의 4필드), `service_utils/studio_agent.py:291-299` (`_studio_router` 가 `studio_type` 반환), `:430` (`_response` 가 `studio_result="url"`), `:494` (`studio_result="param"`).

### 분기 로직(`route_after_studio`)과 의존성

메인 그래프는 studio 이후 `state.get("studio_result")` 유무로 분기한다(레퍼런스 앱 `routers.route_after_studio`).

```python
from typing import Literal
from langgraph.graph import END

def route_after_studio(state) -> Literal["model", "__end__"]:
    if state.get("studio_result"):   # url/param/error 가 채워짐 → 보고서 처리 완료
        return END
    return "model"                   # 일반 질문 → 다음 노드로
```

- 내부 동작: `studio_router` 가 `studio_type` 을 `generation`/`operation`/`done` 으로 분류 → `route_by_studio_type` 이 `studio_url_pipeline`/`studio_param_pipeline`/`END` 로 라우팅.
  > 근거: `service_utils/studio_agent.py:291-299`.
- **operation(조작) 경로**는 `config["configurable"]["active_tool"]` 에 의존한다. `active_tool` 이 `{"type": "studio", "value": <보고서 URL>}` 형태여야 활성화되고, `value` URL(query 제거)이 `app_report_list` 의 `report["url"]` 과 매칭돼야 한다. 매칭 실패 시 `studio_result="error"`.
  > 근거: `service_utils/studio_agent.py:360-377` (`_get_active_report_operation`).
- 보고서 목록은 `os.getenv("APP_ID")` + app_platform reports/versions API 로 조회(`StudioUtil.get_app_reports()`). `state["app_report_list"]` 캐시 우선.

### 레거시 studio 경로는 사용 금지

`studio_node.py`(`pending_studio_agent`/`studio_url_start`/`studio_url_end`/`studio_param_*` 등)와 `studio.py`(`StudioURLGenerator`/`StudioOperation`/`StudioUtil`)는 여전히 import 가능하지만 **구버전**이다. 신규 앱은 개별 레거시 노드를 손으로 와이어링하지 말고 `build_studio_agent()` 서브그래프만 통째로 add_node 한다. (데모 dev guide 의 `pending_studio_agent → studio_url_start → ...` 흐름도는 stale.)

---

## D. chart_agent / file_refer_agent — **무-config** async 노드 (그대로 add_node)

두 노드는 `config` 인자가 **없는** `async def fn(state)` 형태다. 함수 자체를 그대로 add_node 한다(래핑 불필요).

```python
from graphio_app_framework.service_utils.chart import chart_agent
from graphio_app_framework.service_utils.file_refer import file_refer_agent

agent.add_node("chart", chart_agent)          # async def chart_agent(state)
agent.add_node("file_agent", file_refer_agent) # async def file_refer_agent(state)
```

- `chart_agent(state)`: 마지막 메시지를 LLM 으로 분석해 차트 무관이면 `{"messages": []}`, 차트면 Highcharts JSON 을 `additional_kwargs={"type": "chart"}` 메시지로 반환.
  > 근거: `service_utils/chart.py:96-123`.
- `file_refer_agent(state)`: `state.get("files", [])` 의 파일에 대해 MinIO presigned URL(최대 7일)을 만들어 `additional_kwargs={"type": "file"}` 메시지 반환 후 `{"files": []}` 로 리셋. files 가 비면 `{"messages": []}`.
  > 근거: `service_utils/file_refer.py:59-69`.

> 시그니처 주의: `chart_agent`/`file_refer_agent` 는 `(state)` 만 받는다. 반면 `file_use`/`title_model`/`ontology_*`/`clean_user_upload_files` 는 `(state, config)` 다. 혼동하면 add_node 시 잘못 래핑한다.

### 차트 헬퍼 직접 호출

```python
from graphio_app_framework.service_utils.chart import create_chart_rule_tool
# async; 숫자 데이터 설명 → Highcharts JSON 문자열 (지원 타입: area/line/column/pie)
chart_json = await create_chart_rule_tool("월별 매출: 1월 100, 2월 120, ...")
```
> 근거: `service_utils/chart.py:60-73`.

---

## E. 파일 RAG — 자동 주입 vs 수동 import

**기본은 인젝터 자동 주입이다.** `ENABLE_FILE_USE`/`ENABLE_CLEAN_USER_UPLOAD_FILES`(기본 true)면 `graph_base_file_use` 게이트와 `graph_base_clean_user_upload_files` 가 자동으로 들어가므로 **앱은 보통 이들을 직접 add_node 하지 않는다**(B절 참조).

직접 제어가 필요할 때만 수동 import:

```python
from graphio_app_framework.service_utils.file_use import pending_file, clean_user_upload_files
from graphio_app_framework.service_utils.util_node import file_use
# pending_file(state, config) -> Literal["file_use", "done"]   # __start__ 조건 라우터
# file_use(state, config)                                       # DB pgvector RAG 노드
# clean_user_upload_files(state, config)                        # 동기, state 정리
```

- `pending_file`/`get_top_similar_chunks` 는 `config["configurable"]` 의 **`file_names`(list), `this_file`(list), `thread_id`(str)** 를 읽는다. `file_names`+`this_file` 가 모두 비면 RAG 를 건너뛴다.
  > 근거: `service_utils/file_use.py:34-79`(`pending_file`), `:298-353`(`get_top_similar_chunks`), `util_node.py:73-77`(`file_use` 가 `thread_id` 읽고 `get_top_similar_chunks` 호출).
- `file_use` 노드는 PostgreSQL `app_platform.app_chat_file_info` / `app_chat_chunk_embeddings` 를 pgvector 코사인 유사도로 조회(top_k=3)하므로 **DB(`AsyncPostgresDB`) + OpenAIEmbeddings(`embedding_model`, `llm_api_key`)** 가 필요하다.
- `get_top_similar_chunks` 는 `{"user_upload_files": [...], "user_upload_files_exclude": [...]}` 를 반환하고, `clean_user_upload_files` 가 두 필드를 `None` 으로 리셋한다. 두 필드는 **`BaseAgentState` 에 이미 정의**되어 있으므로(`user_upload_files`, `user_upload_files_exclude`) 앱이 따로 선언할 필요 없다.

> 수동으로 `file_use` 를 add_node 하면서 ENABLE_FILE_USE 를 끄지 않으면 자동 주입 노드와 중복된다. 직접 제어하려면 `ENABLE_FILE_USE=false` 로 인젝터를 끈 뒤 수동 와이어링한다.

---

## F. ontology / title / loader_end 두 종류

### ontology 노드

```python
from graphio_app_framework.service_utils.util_node import ontology_info, ontology_config_info
# 둘 다 async def fn(state, config)
```
- `ontology_info(state, config)`: `os.getenv("APP_ID")` 미설정 시 `{"hasOntology": False}`. 설정되면 `config["configurable"]["project_resource"]` 의 `objectTypeIdList`+`linkTypeIdList` 개수가 0보다 크면 `{"hasOntology": True}`.
  > 근거: `service_utils/util_node.py:31-57`.
- `ontology_config_info(state, config)`: `project_resource` 를 knowledge-graph db-schema-mapping API 로 보내 `{"ontology_resource": result}` 반환. (`ontology_resource` 는 `BaseAgentState` 에 이미 정의됨.)
  > 근거: `service_utils/util_node.py:60-70`.

### title — 보통 TitleInjector 가 자동 처리

```python
from graphio_app_framework.service_utils.title import TitleSummary, TitleOutput
# 노드 밖에서 직접 제목을 만들고 싶을 때만:
out: TitleOutput = await TitleSummary().ainvoke("User", state["messages"])  # out.title: list[str]
title_text = " ".join(out.title)
```
- `TitleOutput(BaseModel): title: list[str]`. `TitleSummary().ainvoke(role: str, messages) -> TitleOutput`.
  > 근거: `service_utils/title.py:8-11, 41-64`.
- 보통은 `TitleInjector` 가 `create_title=true & ENABLE_TITLE` 일 때만 자동으로 `graph_base_title` 을 실행하므로 앱이 직접 호출할 필요는 거의 없다. `BaseAgentState.title_output: TitleOutput` 필드에 결과가 담긴다.

### loader_end 가 두 개라는 점

1. `graphio_app_framework.utils.loading.loader_end(config)` — **노드 본문에서 `await` 호출**해 즉시 `type="loading_end"` 이벤트 전송(H절).
2. 레퍼런스 앱의 노드 함수형 `loader_end(state)` (`src/services/nodes.py`) — 그래프 **노드로 등록**되어 `loading_end` 메시지를 `messages` 로 반환.

둘은 다른 메커니즘이다. 앱은 보통 (1) `loader`/`loader_end` 를 노드 본문에서 쓰면 충분하다.

---

## G. ModelManager — LLM 획득의 유일한 경로

LLM 을 직접 생성하지 말고 `ModelManager.get_chat_model()` 로 얻는다.

```python
from graphio_app_framework.utils.models import ModelManager

chat_model = ModelManager.get_chat_model()                          # 기본: 스트리밍 ON, 싱글톤 캐시
no_stream_model = ModelManager.get_chat_model(disable_streaming=True) # 비사용자대면(분류/구조화 출력)용
```

- 시그니처(classmethod): **`get_chat_model(disable_streaming: bool = False, temperature: float | None = None) -> BaseChatModel`**.
  > 근거: `graphio_app_framework/utils/models.py:199-248` (venv inspect 로 교차 검증).
- **싱글톤 캐시**: `disable_streaming=False` & `temperature=None`(기본)이면 캐시된 단일 인스턴스 반환. `disable_streaming=True` 또는 `temperature` 지정 시 **매 호출 새 인스턴스** 생성 → 옵션 지정 LLM 은 모듈 레벨에서 1회만 만들어 재사용한다.
- **`disable_streaming=True` 용도**: `/stream` 은 `astream_events(v2)` 로 모든 토큰을 SSE 로 흘린다. 분류/구조화 출력 같은 **비사용자대면 LLM 호출**에 스트리밍 모델을 쓰면 JSON 토큰이 클라이언트로 누출된다. 이런 호출은 `disable_streaming=True` 를 쓴다(framework 의 `chart.no_stream_model`, `file_use._get_llm` 도 동일 패턴).
  > 근거: `service_utils/chart.py:15` (`no_stream_model = ModelManager.get_chat_model(disable_streaming=True)`).

### 환경변수 3종 (하드코딩 금지)

| env | 의미 |
|---|---|
| `LLM_MODEL` | 모델명 (필수). 미설정 시 `get_chat_model()` 에서 `RuntimeError`. |
| `LLM_API_KEY` | API 키 (`LLM_API_ADDRESS` 와 최소 하나 필수) |
| `LLM_API_ADDRESS` | base_url (있으면 vllm/ollama, 없으면 openai→anthropic→google→mistral→cohere) |

- `LLM_API_ADDRESS` 가 있으면 ChatOpenAI(base_url)→ChatOllama 순으로 시도. 둘 다 없으면 openai→anthropic→google→mistral→cohere.
  > 근거: `graphio_app_framework/utils/models.py:57-79, 163-216`.
- `ChatModelFactory` 는 **deprecated** (호환용). 신규 코드는 `ModelManager.get_chat_model()` 만 쓴다.
  > 근거: `graphio_app_framework/utils/models.py:256-280`.

---

## H. loader / LOG

### loader — 노드 본문에서 로딩 메시지 전송

```python
from langchain_core.runnables import RunnableConfig
from graphio_app_framework.utils.loading import loader, loader_end

async def my_node(state, config: RunnableConfig):
    await loader("처리 중입니다...", config)   # config 필수, await 필수
    ...
    await loader_end(config)                   # 로딩 종료 (선택)
    return {"messages": [...]}
```

- `async def loader(content: str, config: Optional[RunnableConfig] = None)`. **`config` 가 `None` 이면 조용히 return(무동작)**. async 이므로 반드시 `await`.
  > 근거: `graphio_app_framework/utils/loading.py:11-24`.
- 내부적으로 `LangchainChatMessage(content, role="assistant", additional_kwargs={"type": "loading"})` 를 `adispatch_custom_event("loading_message", msg, config=config)` 로 전송. `loader_end` 는 `type="loading_end"`.
  > 근거: `graphio_app_framework/utils/loading.py:26-35, 41-56`.
- 화면에 뜨려면 **노드 시그니처를 `async def node(state, config: RunnableConfig)` 로 두고 그 config 를 그대로 넘겨야** 한다. 그리고 `/stream`(`astream_events(v2)`) 경로로 실행되어야 `on_custom_event` 가 잡힌다.

### LOG — 공유 로거

```python
from graphio_app_framework.utils.logger import LOG
LOG.info("...")
LOG.error("my_node 실패: %s", e)
```

- `LOG` 는 이미 구성된 `logging.getLogger("graphio-app-container")` 인스턴스다. 앱에서 `logging.getLogger(...)` 로 **별도 로거를 만들지 말 것**(파일/Phoenix 핸들러가 안 붙는다).
  > 근거: `graphio_app_framework/utils/logger.py:33, 100` (`LOG = set_logger()`, `getLogger("graphio-app-container")`).
- 콘솔 출력은 **`LOG_CONSOLE_ENABLED=true` 일 때만**(기본 false).
  > 근거: `graphio_app_framework/utils/logger.py:41`.
- 파일 로그: `{STORAGE_PATH}/{LOG_DIRECTORY}/{APP_ID}/app_container.log` (RotatingFileHandler 10MB×10). `C_PHOENIX_USE=true` 면 ERROR 이상이 OpenTelemetry span 으로 기록.

---

## I. utils 헬퍼

```python
from graphio_app_framework.utils.utils import (
    find_latest_human_message,   # messages 역순 최근 HumanMessage, 없으면 None
    get_chat_file_path,          # async; configurable[file_key] 파일명 + 접근 prefix 결합 경로 리스트
    clean_json_response,         # LLM JSON 출력의 ```/잡문자 제거 후 dict 반환
)
from graphio_app_framework.utils.text_stream import PlainTextStream  # 텍스트 토큰 스트리밍 가짜 LLM (HITL/테스트용)
```

```python
question = find_latest_human_message(state["messages"])
paths = await get_chat_file_path(config, file_key="file_names")  # 또는 "this_file"
data = clean_json_response(response.content)                     # dict
```

- `get_chat_file_path(app_config: RunnableConfig, file_key: str = "file_names")` (async): `config.chat_file_access_path` + 각 파일명 결합 경로 리스트. `file_key` 는 `"file_names"`(기존 업로드) 또는 `"this_file"`(이번 업로드).
  > 근거: `graphio_app_framework/utils/utils.py:71-75, 112-160`.
- `PlainTextStream` 은 입력 텍스트를 글자 단위로 스트리밍하는 가짜 `BaseChatModel`(studio 의 응답 노드/HITL 테스트용).
  > 근거: `graphio_app_framework/utils/text_stream.py:9-52`.

> 주의: `find_latest_human_message` 는 `utils.utils` 와 `service_utils.chart` 양쪽에 중복 정의되어 있다. 앱은 `graphio_app_framework.utils.utils` 버전을 import 한다.

---

## J. 인프라 클라이언트 (필요 시 고급) — 모두 config(env) 기본값 자동 주입

일반 앱 노드에서는 거의 쓰지 않는다(레퍼런스/데모 앱 `services` 코드에 직접 사용처 없음). 필요하면 **인자 생략 → config(env) 기본값 자동 주입**. 호스트/크리덴셜을 **하드코딩하지 말 것**.

```python
# PostgreSQL — C_DATABASE_* env, pool min5/max10
from graphio_app_framework.db.connect_rdb import AsyncPostgresDB
db = AsyncPostgresDB()                 # 인자 생략 시 config.db_host/db_port/db_user/db_password/db_name
await db.connect()
rows = await db.fetch("SELECT * FROM t WHERE id = $1", some_id)  # fetch / fetchrow
await db.close()

# HTTP — app_platform_host:port
from graphio_app_framework.clients.client import AsyncHTTPClient
http = AsyncHTTPClient()               # base_url 생략 시 config.app_platform_host:port

# MinIO — config.minio_client_* (secure=False)
from graphio_app_framework.utils.minio_utils import create_client, MinioObject
minio = create_client()

# RabbitMQ — headers exchange
from graphio_app_framework.utils.rabbitmq import publish_message
await publish_message(headers={...}, body=b"...")
```

> 근거: `db/connect_rdb.py:7-43`(`AsyncPostgresDB.__init__` config 기본값, min/max), `clients/client.py:8-13`(`AsyncHTTPClient` base_url 기본값), `utils/minio_utils.py:14-25`(`create_client` config.minio_*, secure=False), `utils/rabbitmq.py:30-45`(`publish_message(headers, body)` HEADERS exchange).

---

## K. 모듈 import 부작용 — 검증 시 주의

`chart.py`, `file_use.py`, `file_refer.py`, `studio*.py`, `util_node.py` 일부는 **import 시점(모듈 최상위)** 에 `ModelManager.get_chat_model()` 또는 MinIO `create_client()` 를 호출한다.

- `chart.py:14-15` 가 모듈 레벨에서 `ModelManager.get_chat_model()` 호출 → import 하려면 `LLM_MODEL` + (`LLM_API_KEY` 또는 `LLM_API_ADDRESS`) 필요.
- `file_refer.py:15` 가 모듈 레벨에서 `create_client()` 호출 → `C_MINIO_CLIENT_HOST`(스킴 없는 host, 예 `localhost`) 필요.

미설정 시 import 단계에서 `RuntimeError("LLM이 초기화되지 않았습니다...")` 또는 MinIO `ValueError`(`path in endpoint is not allowed` — 호스트에 스킴이 들어가면 발생)가 난다.

정상 `graphio-app run` 환경(`.env`/env.template)에서는 자동 충족되므로 문제 없다. 오프라인 검증 시에는 `LLM_MODEL`/`LLM_API_KEY`/`C_MINIO_CLIENT_HOST=localhost` 를 세팅하거나 `utils.models` 의 LLM probe 를 monkeypatch 한 뒤 import 한다. 모든 검증은 `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python` 으로 수행한다.

---

## 빠른 요약 (이 문서의 핵심)

1. `service_utils` 는 **항상 서브모듈 전체 경로**로 import(패키지 `__init__` 은 빈 파일).
2. 자동 주입 노드 이름 4개(`graph_base_file_use`, `graph_base_clean_user_upload_files`, `graph_base_title`, `graph_base_title_router`)는 **예약어** — 직접 add_node 금지. ENABLE_* 로 켜지고 `file_names`/`this_file`/`create_title` 로 런타임 게이트된다.
3. Studio 는 `build_studio_agent()` 서브그래프를 통째로 add_node 하고, `AgentState` 에 `studio_input/studio_type/studio_result/app_report_list` 4필드를 직접 선언한다.
4. `chart_agent`/`file_refer_agent` 는 **무-config** `(state)` 노드. `file_use`/`ontology_*` 는 `(state, config)`.
5. LLM 은 `ModelManager.get_chat_model()`(비사용자대면은 `disable_streaming=True`), 로딩은 `await loader(msg, config)`(config None 이면 무동작), 로그는 공유 `LOG`.
6. 인프라 클라이언트는 config(env) 기본값 자동 주입 — 호스트/크리덴셜 하드코딩 금지.
