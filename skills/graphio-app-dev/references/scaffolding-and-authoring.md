# Scaffolding & Authoring — 새 앱 만들기

graphio-app-framework 위에 LangGraph 앱을 처음부터 만든다. 이 문서는 **스캐폴딩(디렉터리/requirements/.env)** 과 **그래프 작성(graphio_app·State·노드·라우터·툴·서브그래프)** 을 다룬다.

> 권위 순서: 패키지 소스 > 테스트 > 레퍼런스 앱 > docs/baseline. 충돌 시 소스가 이긴다. 모든 import/실행 검증은 `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python` 으로 한다.
> 정본 레퍼런스 앱: `/Users/rhcpn/Github/graphio-app-framework/src/services/` (agent.py, my_graph.py, graph_main.py, nodes.py, routers.py, tools.py, prompt.py).

빠른 시작: `scripts/scaffold_app.sh -d <대상> -n <앱이름>` 로 최소 실행가능 스켈레톤을 만든 뒤 아래 규칙대로 살을 붙인다.

---

## A. 표준 src/ 디렉터리 레이아웃과 파일 역할

앱은 `src/<패키지>/` (기본 패키지명 `services`) 아래에 모듈을 둔다. 프레임워크는 `src/` 를 자동 탐색하며, `services/` 는 레거시 기본값이다(`GRAPHIO_APP_DIR` 로 다른 디렉터리 지정 가능 — run-and-debug.md 참고).

```
<프로젝트 루트>/
├── src/
│   └── services/
│       ├── agent.py        # AgentState 정의 (BaseAgentState 상속)
│       ├── graph_main.py   # user_graph() 빌더 함수 (compile 안 함)
│       ├── my_graph.py     # graphio_app() 등록 → 메인 그래프 (__graphio_main__)
│       ├── nodes.py        # async 노드 함수 + ModelManager/loader
│       ├── routers.py      # conditional edge 함수 (Literal 반환)
│       ├── tools.py        # @tool 정의
│       ├── prompt.py       # 프롬프트 상수
│       └── editor.py       # (옵션) 서브그래프
├── requirements.txt        # 프레임워크 한 줄 + 앱 고유만
└── .env                    # graphio-app copy-env 로 생성
```

| 파일 | 역할 | 정본 |
|---|---|---|
| `agent.py` | `class AgentState(BaseAgentState, total=False)` 정의 | `src/services/agent.py:8` |
| `graph_main.py` | `def user_graph() -> StateGraph` (compile 안 한 빌더) | `src/services/graph_main.py:20` |
| `my_graph.py` | `my_app = graphio_app(user_graph, state_type=AgentState)` | `src/services/my_graph.py:7` |
| `nodes.py` | `async def node(state, config)` 노드들 | `src/services/nodes.py:47` |
| `routers.py` | conditional edge 함수 (`-> Literal[...]`) | `src/services/routers.py:42` |
| `tools.py` | `@tool` 데코레이트 함수 | `src/services/tools.py:15` |
| `prompt.py` | 시스템 프롬프트/지시문 상수 | `src/services/prompt.py` |

> 정본 레퍼런스 앱은 빌더(`graph_main.py:user_graph`)와 등록(`my_graph.py:graphio_app`)을 **다른 파일**로 분리한다. 데모 앱(`graphio-app-demo-html-generator/src/services/new_app.py`)은 같은 파일에 인라인으로 둔다. 둘 다 유효하나, **한 파일에 인라인으로 두는 패턴을 권장**한다(메인 그래프 식별이 단순).
>
> **파일명은 자유다.** `graph.py`/`agent.py` 는 모듈 스캔에서 우선순위(PRIORITY_MODULES)일 뿐, 메인 그래프 식별은 `__graphio_main__` 마커로 한다(run-and-debug.md 참고). 위 레이아웃은 관용일 뿐 강제 아님.

---

## B. graphio_app() 시그니처와 의미 — 빌더 함수를 넘긴다, compile 금지

```python
from graphio_app_framework.graph_base.graph import graphio_app
# 또는: from graphio_app_framework.graph_base import graphio_app  (재노출)
```

**정확한 시그니처** (`graphio_app_framework/graph_base/graph.py:10`):

```python
def graphio_app(build_graph_fn, state_type=None, *, checkpointer=None):
```

| 인자 | 의미 |
|---|---|
| `build_graph_fn` | **호출하면 UNcompiled `StateGraph` 빌더를 반환하는 zero-arg 함수.** `graphio_app` 이 내부에서 `build_graph_fn()` 을 호출한다(graph.py:18). 절대 빌더의 `.compile()` 결과나 이미 호출한 결과를 넘기지 말 것. |
| `state_type` | State 클래스(TypedDict). 생략 시 빌더의 `state_schema`/`schema` → `dict` 순 폴백(graph.py:20-25). **명시 전달 권장.** |
| `checkpointer` | 키워드 전용(`*`). `None`(기본)이면 `compile(checkpointer=None)`. HTTP 앱은 lifespan 이 런타임에 `AsyncSqliteSaver` 를 주입하므로 **보통 생략**한다(graph.py:11 docstring; api/graphio_app.py:88-90). |

**graphio_app() 내부 동작** (graph.py:18-41):
1. `build_graph_fn()` 호출 → 원본 UNcompiled `StateGraph` 획득
2. `GraphConfig.ENABLE_*` 가 켜진 injector 수집 → `rebuild_graph()` 로 자동 주입 노드(제목/파일/cleanup)를 끼운 새 builder 생성
3. `builder.compile(checkpointer=checkpointer)` 호출
4. `compiled.__graphio_main__ = True` 설정 → 메인 그래프 자동 감지 마커
5. compiled 그래프 반환

**표준 패턴:**

```python
from langgraph.graph import END, StateGraph
from graphio_app_framework.graph_base.graph import graphio_app
from services.agent import AgentState  # class AgentState(BaseAgentState, total=False)

def user_graph():
    agent = StateGraph(AgentState)
    agent.add_node("model", acall_model)
    agent.set_entry_point("model")
    agent.add_edge("model", END)
    return agent  # ← compile() 하지 않은 StateGraph 를 반환

my_app = graphio_app(user_graph, state_type=AgentState)  # 모듈 최상위 변수에 할당
```

> **가장 흔한 치명적 실수:** `graphio_app(user_graph(), ...)` (호출해서 넘김) 또는 `graphio_app(builder.compile, ...)` (compile 결과). 이러면 `rebuild_graph` 의 자동 주입(제목/파일조회/cleanup)이 사라진다. 반드시 **호출 안 한 함수 객체** `user_graph` 자체를 넘긴다.

---

## C. State 정의 — BaseAgentState 상속(total=False)

```python
from graphio_app_framework.states import BaseAgentState
```

**BaseAgentState 의 정확한 6개 공통 필드** (`graphio_app_framework/states/base_agent.py:6-24`, `class BaseAgentState(MessagesState, total=True)`):

| 필드 | 타입 | 채우는 주체 |
|---|---|---|
| `messages` | (MessagesState 제공) | 노드/LLM |
| `title_output` | `TitleOutput` | TitleInjector (graph_base_title) |
| `user_upload_files` | `Optional[list]` | FileUseInjector (graph_base_file_use) |
| `user_upload_files_exclude` | `Optional[list]` | FileUseInjector |
| `files` | `Optional[list]` | file_refer_agent (출처 정보, 삭제예정) |
| `ontology_resource` | `Optional[list]` | ontology_config_info 노드 |

> `TitleOutput` 은 `class TitleOutput(BaseModel): title: list[str]` (`service_utils/title.py:8`). base_agent.py 가 이를 import 해 `title_output` 타입으로 쓴다.

**이 6개 필드는 절대 앱에서 재정의/덮어쓰기 금지** — 자동 주입 노드가 이름/타입에 의존한다. 앱은 **새 키만 추가**한다.

**표준 앱 State 패턴** (`src/services/agent.py:8`):

```python
from typing import Optional
from langgraph.managed.is_last_step import IsLastStep  # 앱이 직접 선언 (BaseAgentState 미제공)
from graphio_app_framework.states import BaseAgentState

class AgentState(BaseAgentState, total=False):
    is_last_step: IsLastStep
    studio_result: Optional[str]
    intent: Optional[str]
```

**`total` 의 정확한 의미** (소스 검증: `BaseAgentState.__total__ == True`):
- `BaseAgentState` 는 `total=True` → 상속받은 6개 필드는 모두 **required**(`__required_keys__`).
- 앱 서브클래스 `AgentState(BaseAgentState, total=False)` 의 `total=False` 는 **"이 서브클래스에서 새로 추가한 키만"** optional 로 만든다. 상속받은 6개 필드는 여전히 required.
- LangGraph state 는 노드를 거치며 키가 점진 추가되므로 새 키는 `total=False` 가 적절(아직 값이 없어도 KeyError 안 남).

> 일부 메모/문서의 "BaseAgentState = total=False" 는 **부정확**하다. 소스는 `total=True`.

**AgentState 미정의 시 폴백:** 앱이 `AgentState` 심볼을 정의하지 않으면 프레임워크가 `GraphioAgentState`(`from graphio_app_framework.graph_base.agent import GraphioAgentState`)를 기본값으로 쓴다. 이는 `class GraphioAgentState(BaseAgentState, total=False)` 로 `studio_input`/`studio_result`/`studio_type`/`app_report_list` 4필드를 추가한 것이다(`graph_base/agent.py:6-10`). State 확장이 필요 없으면 정의 생략 가능. **Studio(build_studio_agent)를 쓰면 이 4필드를 직접 선언해야 한다 — advanced-features.md 참고.**

**graphio_app 에 State 전달:** `graphio_app(user_graph, state_type=AgentState)` 처럼 빌더 안 `StateGraph(AgentState)` 와 동일한 State 를 명시 전달하는 것이 표준이다.

---

## D. 메인 그래프 작성 표준 패턴

규약 (rebuild_graph 가 올바르게 재배선하려면 지켜야 함, `graph_base/rebuild.py:46-123`):
- **진입점**: `agent.set_entry_point("...")` 또는 `agent.add_edge("__start__", "...")` 로 명확히.
- **종단**: `END` 로 향하는 엣지로 표현(`from langgraph.graph import END`). conditional edge 가 END 를 타깃으로 해도 rebuild 가 첫 post-graph 주입 노드(cleanup/title)로 재배선하므로, END 로 가는 유저 그래프도 cleanup/title 을 거친다.
- **메인 그래프는 src/ 트리에 정확히 1개.** `graphio_app()` 반환값을 모듈 최상위 변수에 할당하면 `__graphio_main__` 마커가 자동 설정되어 파일/변수명과 무관하게 감지된다. 여러 모듈에서 `graphio_app()` 을 호출하면 모두 마커를 가져 충돌하므로 메인은 한 모듈에서만 호출한다.

정본 메인 그래프 구조(`src/services/graph_main.py:20-51`) — 자체 노드 + 프레임워크 service_utils 노드를 함께 와이어링:

```python
from langgraph.graph import END, StateGraph
from graphio_app_framework.service_utils.chart import chart_agent
from graphio_app_framework.service_utils.file_refer import file_refer_agent
from services.agent import AgentState
from services.nodes import acall_model, tool_node
from services.routers import pending_tool_calls

def user_graph():
    agent = StateGraph(AgentState)
    agent.add_node("model", acall_model)
    agent.add_node("tools", tool_node)
    agent.add_node("file_agent", file_refer_agent)  # 프레임워크 노드 재사용
    agent.add_node("chart", chart_agent)
    agent.set_entry_point("model")
    agent.add_conditional_edges("model", pending_tool_calls, {"tools": "tools", "done": "file_agent"})
    agent.add_edge("tools", "model")
    agent.add_edge("file_agent", "chart")
    agent.add_edge("chart", END)
    return agent
```

> **예약 노드 이름 4개 금지** (직접 `add_node` 하면 안 됨): `graph_base_file_use`, `graph_base_clean_user_upload_files`, `graph_base_title`, `graph_base_title_router`. 자체 cleanup 이 필요하면 다른 이름을 쓴다(레퍼런스 앱은 `clean_user_upload_files` 라는 별개 이름의 service_utils 노드를 명시 등록 — 주입 노드와 충돌 안 함). 자동 주입 노드 계약은 advanced-features.md 참고.

선택: 메인 그래프 모듈에서 그래프 PNG 를 그릴 수 있다(`my_graph.py:13`):

```python
if __name__ == "__main__":
    my_app.get_graph().draw_mermaid_png(output_file_path="graph.png")
```

---

## E. 노드 작성 패턴

노드는 `async def node(state, config: RunnableConfig)` 시그니처로 작성하고, **전체 state 가 아니라 변경된 키만 담은 dict(부분 업데이트)** 를 반환한다.

```python
from langchain_core.runnables import RunnableConfig
from graphio_app_framework.utils.loading import loader
from graphio_app_framework.utils.logger import LOG
from graphio_app_framework.utils.models import ModelManager
from services.agent import AgentState

chat_model = ModelManager.get_chat_model()  # 모듈 최상위에서 1회 획득 후 재사용

async def acall_model(state: AgentState, config: RunnableConfig):
    await loader("model 노드 실행중입니다.", config)  # config 필수 (None이면 무동작), await 필수
    try:
        response = await wrap_model(chat_model).ainvoke(state, config)
        return {"messages": [response]}      # 부분 업데이트 dict 반환
    except Exception as e:
        LOG.error("acall_model %s" % str(e))
        raise
```

핵심(상세는 advanced-features.md):
- **State 접근**: `state["messages"]` 또는 `state.get("messages", [])` (dict 처럼).
- **LLM**: `ModelManager.get_chat_model()` 로만 획득. 모델명/키 하드코딩 금지(env: `LLM_MODEL` + `LLM_API_KEY` 또는 `LLM_API_ADDRESS`). 분류/구조화 출력 등 비사용자대면 호출은 `ModelManager.get_chat_model(disable_streaming=True)` 로 JSON 토큰의 SSE 누출 방지.
- **loader**: `async`, `config` 가 `None` 이면 조용히 무동작. 노드가 받은 `config` 를 그대로 `await loader("...", config)` 로 넘겨야 화면에 뜬다.
- **로그**: `from graphio_app_framework.utils.logger import LOG` 사용(별도 `logging.getLogger` 금지).

정본: `src/services/nodes.py:18,47-67`.

---

## F. 라우터(conditional edge 함수)와 툴

**라우터**는 `state`(필요 시 `config`)를 받아 다음 노드 키를 `Literal` 로 반환한다. `add_conditional_edges(소스, 라우터함수, {반환값: 노드명})` 으로 연결.

```python
from typing import Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

def pending_tool_calls(state, config: RunnableConfig) -> Literal["tools", "done"]:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            return "tools" if msg.tool_calls else "done"
    return "done"
```

`END` 를 타깃으로 쓰려면 매핑에 `from langgraph.graph import END` 의 `END` 키를 직접 둔다: `{"model": "model", END: END}` (`graph_main.py:41`, `routers.py:51`).

정본: `src/services/routers.py:42-67`.

**툴**은 `@tool` 데코레이트 함수로 정의하고 `ToolNode` 로 묶어 노드로 등록한다.

```python
# tools.py
from langchain_core.tools import tool

@tool
def basic_question_tool(expression: str) -> str:
    """You take user questions and process them.

    Args:
        expression (str): user question
    Returns:
        str: response
    """
    ...
```

```python
# nodes.py
from langgraph.prebuilt import ToolNode
from services.tools import basic_question_tool

tools = [basic_question_tool]
tool_node = ToolNode(tools)        # user_graph()에서 agent.add_node("tools", tool_node)
```

`bind_tools`: LLM 에 툴을 붙이려면 `model.bind_tools(tools)` (`nodes.py:26`).

정본: `src/services/tools.py:15-35`, `nodes.py:20-26`.

> `tools.py` 의 `ChatOpenAI(...)` 직접 생성 예시는 레퍼런스 앱의 단순 데모일 뿐, **앱 노드 LLM 은 `ModelManager.get_chat_model()` 사용을 권장**한다(모델/키를 env 로 받음).

---

## G. 서브그래프 합성 (2가지 관용)

**(A) compile 후 노드로 추가** — 서브그래프를 `g.compile(name=...)` 한 뒤 부모에 통째로 `add_node`:

```python
# 서브그래프 빌더
def build_editor_subgraph():
    g = StateGraph(AgentState)
    g.add_node("text", editor_text)
    g.set_entry_point("text")
    g.add_edge("text", END)
    return g.compile(name="editor_subgraph")

# user_graph() 안에서
agent.add_node("editor", build_editor_subgraph())
```

프레임워크 `build_studio_agent()` 도 동일하게 compiled 서브그래프를 반환하므로 그대로 `agent.add_node("studio_agent", build_studio_agent())` 로 추가한다(advanced-features.md).

**(B) mutation 빌더** — 부모 `StateGraph` 를 인자로 받아 노드/엣지를 제자리에서 추가(진입/종단 와이어링은 호출자가):

```python
def build_viz_subgraph(agent, *, llm):
    agent.add_node("viz_data", data_node)
    agent.add_node("viz", viz_node)
    agent.add_edge("viz_data", "viz")
# 호출자: build_viz_subgraph(agent, llm=...); agent.add_edge("file_agent", "viz_data"); agent.add_edge("viz", END)
```

> studio_* state 를 건드리는 서브그래프는 `GraphioAgentState`(또는 그 4필드를 선언한 AgentState)를 사용한다. 정본: `src/services/editor.py`(빌더 패턴), demo `viz_adapter/graph.py`(mutation 패턴).

---

## H. scaffold_app.sh 로 최소 실행가능 스켈레톤 생성

```bash
bash scripts/scaffold_app.sh -d <대상_디렉터리> -n <앱이름>   # -f 로 덮어쓰기
```

생성물: `src/services/agent.py`(AgentState), `src/services/graph.py`(user_graph + graphio_app + 모델 노드 + loader 예시), `requirements.txt` stub(프레임워크 한 줄 + 폐쇄망 헤더 주석), `.env` 안내. 생성 후 다음 단계(copy-env → graphio-app run → package.sh)를 출력한다.

생성 직후 권장 검증:

```bash
# 모듈/메인 그래프가 잡히는지
PROJECT_ROOT=<대상> /Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python -c "
from graphio_app_framework.service_utils.graph_module_loader import load_graph_entry
g = load_graph_entry(); print('OK', getattr(g, '__graphio_main__', None))"
```

---

## I. requirements.txt 작성 규칙

앱 `requirements.txt` = **프레임워크 한 줄 + 앱 고유 패키지만**. `fastapi`/`langchain`/`langgraph`/`pydantic` 등 프레임워크 전이 의존성은 **중복 기재 금지**(버전 충돌 유발).

```
# 폐쇄망: 아래 3줄을 파일 "최상단"에 이 순서로 (완전 격리망이면 --no-index 주석 해제)
# --no-index
--trusted-host graphio.mobigen.com
--find-links https://graphio.mobigen.com/graphio/app_platform/control/api/wheel/

graphio_app_framework==0.1.0        # 버전은 pyproject.toml(현재 0.1.0) 기준

# 앱 고유 패키지만 추가
pandas==2.3.3
openpyxl==3.1.5

# Dev (선택)
pytest>=8.4
pytest-asyncio>=1.0
```

- **버전**은 항상 pyproject.toml(현재 `0.1.0`) 기준. 문서의 `0.2.0` 예시는 stale.
- 폐쇄망 헤더 순서: `--no-index`(격리 시) → `--trusted-host` → `--find-links`. `--find-links` 경로는 `http://<host>:<port>/graphio/app_platform/control/api/wheel/` 고정.
- 패키징/폐쇄망 wheel 상세는 packaging-and-deploy.md 참고.

정본: `graphio_app_framework/env.template`(설명 헤더는 데모 `requirements.txt:1-30`), demo `requirements.txt`.

---

## J. .env 생성(copy-env)과 최소 변수

`.env` 는 직접 만들지 말고 `graphio-app copy-env` 로 패키지 내장 `env.template` 을 복사한다(`cli.py:77-88`).

```bash
graphio-app copy-env            # .env 생성 (이미 있으면 [SKIP], 덮어쓰지 않음)
graphio-app copy-env --dest .env.local   # 대상 파일명 변경
```

생성 후 **최소 설정값**(env.template 기준):

| 변수 | 의미 | 비고 |
|---|---|---|
| `LLM_MODEL` | LLM 모델명 (예 `gpt-4o-mini`) | **필수** — 미설정 시 `get_chat_model()` RuntimeError |
| `LLM_API_KEY` | API 키 | `LLM_API_KEY` 또는 `LLM_API_ADDRESS` 중 **최소 하나 필수** |
| `LLM_API_ADDRESS` | vllm/ollama base_url | 있으면 vllm→ollama, 없으면 openai→anthropic→… |
| `APP_PORT` | 앱 서버 포트 | 기본 `8888` |
| `APP_HOST` | 바인드 호스트 | 기본 `0.0.0.0` |
| `LOG_LEVEL` | 로그 레벨 | 기본 `DEBUG`(template) |

- 모델명/키/호스트/크리덴셜을 **코드에 하드코딩하지 말 것** — 전부 env 로 받는다.
- `.env` 는 cwd 기준 `find_dotenv(usecwd=True)` 로 탐색되므로 `graphio-app run` 은 `.env` 가 있는 프로젝트 루트에서 실행한다.
- 실행/포트/env 상세는 run-and-debug.md 참고.

정본: `graphio_app_framework/cli.py:77-88`, `env.template:1-21`, `core/config.py:102-103,118-121`.

---

## 다음 단계

- 실행/디버그(`graphio-app run`, `/stream`, configurable, 모듈 디스커버리): **run-and-debug.md**
- 프레임워크 노드 재사용(studio/chart/file_use), ModelManager/loader/LOG, 자동 주입 노드 계약: **advanced-features.md**
- 포털 zip 패키징, 폐쇄망 wheel: **packaging-and-deploy.md**
- 에러 증상→원인→해결: **troubleshooting-and-gotchas.md**
