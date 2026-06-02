---
name: graphio-subagent-dev
description: graphio-app-framework에 재사용 가능한 service node(sub-agent)를 저작·등록·패키징할 때 쓰는 스킬. graphio_app 그래프에 "노드 하나로 꽂히는" 인터페이스 계약(ServiceNode Protocol), dynamic_graph_symbol_import 로 AgentState 참조, 예약 키 보호, I/O 매니페스트, 설정·환경변수(core.config / env.template), 새 렌더 타입 SSE 등록, __init__.py 의 _lazy 등록, make build wheel 패키징을 다룬다. 'service_utils', '새 sub-agent', '서비스 노드', 'chart_agent 같은 노드', 'ServiceNode', 'Protocol 계약', '_lazy 등록', 'dynamic_graph_symbol_import', '노드 인터페이스', '프레임워크에 노드 추가', 'env.template 추가', 'make build' 표현이 나오면 로드한다. 단, 앱을 만들어 Graphio Portal에 올리는 작업은 graphio-app-dev 스킬을 쓴다. 모든 설명은 한국어로, 코드/식별자는 영어 그대로.
---

# Graphio Sub-agent(Service Node) 개발 스킬

graphio-app-framework 위에 **재사용 가능한 노드(=service node, 통칭 sub-agent)** 를 만들어 프레임워크에 싣고, wheel 로 패키징하는 작업을 다룬다. `chart_agent`, `file_refer_agent`, `studio_agent` 처럼 `service_utils/` 에 들어가 **여러 앱이 가져다 쓰는** 공통 노드가 대상이다.

이 스킬의 **심장은 "구현 가이드"가 아니라 인터페이스 계약**이다. 노드의 뒷쪽 기능은 자유롭게 만들어도 되지만, graphio_app 그래프에 노드로 꽂히려면 **ServiceNode 계약**을 지켜야 한다.

> **경계 (graphio-app-dev 와 구분)**
> - **graphio-app-dev** = *앱 저자*. `graphio_app()` 으로 앱을 만들어 Graphio Portal 에 업로드 (소비 측).
> - **graphio-subagent-dev** (이 스킬) = *프레임워크 기여자*. `service_utils/` 에 재사용 노드를 추가해 프레임워크 wheel 로 릴리스 (저작 측).
> - 두 스킬은 보통 다른 repo/워크스페이스에서 로드된다. 앱에 노드를 **쓰는** 법은 graphio-app-dev 를 참조.

이 스킬이 **정본(source of truth)** 이다. `docs/FRAMEWORK_DEVELOPMENT.md` 는 보조 문서이며, 두 곳이 충돌하면 이 스킬을 따른다.

---

## 0. 가장 자주 틀리는 6가지 (Quick Reference)

새 노드를 만들 때 항상 점검한다. 어기면 노드가 인식되지 않거나 앱을 깨뜨린다.

1. **`__init__.py` 의 `_lazy` 등록을 빠뜨린다.** `service_utils.<name>` 단축 import 가 동작하려면 필수다. (스캐폴더가 자동 처리 — §5)
2. **반환 dict 가 예약 키를 덮어쓴다.** `title_output` / `user_upload_files` / `user_upload_files_exclude` / `files` / `ontology_resource` 를 반환하면 프레임워크 자동 기능이 깨진다. `messages` 는 append 만 안전. (§3 ①)
3. **앱의 `AgentState` 를 직접 import 한다.** `service_utils/` 모듈은 앱 코드를 import 할 수 없다. `dynamic_graph_symbol_import('AgentState')` 로 동적 참조한다. (§1)
4. **동기 함수로 작성한다.** 노드는 `async def` 여야 한다.
5. **env 를 `os.getenv` 로 산발적으로 읽는다.** 설정은 `core.config.config` 싱글톤을 경유한다. (단 `APP_ID`/`MODE` 같은 런타임 ambient 는 예외 — §4)
6. **새 시각화 타입인데 SSE 등록을 안 한다.** `additional_kwargs={"type": "X"}` 로 새 타입을 내보내면 프론트가 못 그린다. (§3 ③)

---

## 1. ServiceNode 계약 (이 스킬의 심장)

프레임워크는 이미 `injectors/base.py` 에서 `GraphInjector(Protocol)` 로 인터페이스를 정의해 둔다. service node 도 같은 하우스 스타일의 **Protocol** 로 계약을 잡는다.

```python
from typing import Protocol, runtime_checkable
from langchain_core.runnables import RunnableConfig
# AgentState = dynamic_graph_symbol_import('AgentState')


@runtime_checkable
class ServiceNode(Protocol):
    """graphio_app 그래프에 노드로 추가되는 재사용 노드 계약.

    내부 구현(뒷쪽 기능)은 자유다. 아래 시그니처와 §3 의 계약만 지키면
    어떤 graphio_app 그래프든 `builder.add_node("name", node)` 로 꽂을 수 있다.
    """

    async def __call__(self, state: "AgentState", config: RunnableConfig) -> dict: ...
```

- **함수든 클래스든 OK.** 별도로 상속할 필요 없다. 위 시그니처에 **구조적으로 맞기만** 하면 LangGraph 가 노드로 받아들인다. 함수형이 기본, 초기화 인자가 필요하면 `__call__` 을 가진 클래스형을 쓴다.
- **단위는 "노드"** 다. state-update dict 를 반환한다. 조건부 엣지(라우터, `Literal` 반환)나 서브그래프 빌더(`build_*() -> StateGraph`)는 이 계약의 범위 밖이다. (그런 패턴이 필요하면 `studio_agent.py` 를 참고하되, 본 스킬의 표준 계약과는 별개다.)

---

## 2. 노드 작성 패턴

함수형 표준 예시. **매니페스트 docstring**(Reads/Writes/Config/Env)과 **에러 폴백**이 계약 필수 항목이다.

```python
"""keyword_agent — 최근 사용자 메시지에서 키워드를 뽑는 service node 예시.

Reads:   messages
Writes:  messages
Config:  configurable.max_keywords (int, 기본 5)
Env:     (없음 — core.config / 새 env var 의존 없음)
"""
from langchain_core.messages import ChatMessage as LangchainChatMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from graphio_app_framework.utils.logger import LOG
from graphio_app_framework.utils.models import ModelManager
from graphio_app_framework.service_utils.graph_module_loader import dynamic_graph_symbol_import

# service_utils 는 앱의 AgentState 를 직접 import 할 수 없으므로 동적 참조한다.
AgentState = dynamic_graph_symbol_import("AgentState")

_model = ModelManager.get_chat_model(disable_streaming=True)


async def keyword_agent(state: AgentState, config: RunnableConfig) -> dict:
    try:
        max_keywords = (config.get("configurable") or {}).get("max_keywords", 5)
        question = _latest_human_text(state.get("messages", []))
        if not question:
            return {"messages": []}                      # 입력 없음 — 조용히 통과

        resp = await _model.ainvoke(
            [HumanMessage(content=f"다음에서 핵심 키워드 {max_keywords}개만 콤마로: {question}")]
        )
        return {"messages": [LangchainChatMessage(content=resp.content, role="assistant")]}
    except Exception as e:
        LOG.error(f"keyword_agent 실패: {e}")             # 에러 폴백 — 그래프를 깨뜨리지 않음
        return {"messages": []}


def _latest_human_text(messages) -> str | None:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return None
```

앱 그래프에서 소비하는 쪽(참고):

```python
from graphio_app_framework.service_utils.keyword_agent import keyword_agent
builder.add_node("keyword", keyword_agent)
```

**재사용 유틸은 새로 만들지 말고 가져다 쓴다.**

```python
from graphio_app_framework.utils.models import ModelManager      # LLM (env 자동 감지)
from graphio_app_framework.utils.loading import loader           # await loader("처리 중...", config)
from graphio_app_framework.utils.logger import LOG               # LOG.info / LOG.error
from graphio_app_framework.core.config import config             # 설정/외부서비스 (§4)
```

---

## 3. 계약 조항

| 조항 | 내용 |
|---|---|
| **시그니처** (기본) | `async def (state, config) -> dict`. 부분 state dict 반환(`total=False` 갱신). |
| **AgentState** (기본) | `AgentState = dynamic_graph_symbol_import('AgentState')`. 앱 없이 import 해도 framework 기본값으로 안전하게 fallback 된다. |
| **네이밍** (기본) | `*_agent` (LLM 판단/생성 포함) / `*_node` (단순 변환). `graph_base_*` 접두는 금지(자동주입 예약). |
| **① 예약 키 침범 금지** | 반환 dict 가 덮으면 안 되는 키: `title_output`, `user_upload_files`, `user_upload_files_exclude`, `files`, `ontology_resource`. `messages` 는 리듀서가 append 하므로 추가만 안전. 노드 이름도 `graph_base_file_use` / `graph_base_clean_user_upload_files` / `graph_base_title` / `graph_base_title_router` 와 충돌 금지. |
| **② I/O 매니페스트** | 모듈 docstring 에 `Reads:` / `Writes:` / `Config:` / `Env:` 섹션 **필수**. 공유되는 노드가 "내가 무엇에 의존하는지" 스스로 밝혀 재사용·배포를 쉽게 한다. 정적 점검이 필요하면 클래스에 `ClassVar` 속성(`reads`, `writes`, `config_keys`)을 추가로 선언해도 된다(선택). |
| **③ 새 렌더 타입 SSE 등록** | 새 시각화 타입을 `additional_kwargs={"type": "X"}` 로 내보낼 때만 해당. 아래 3곳을 등록해야 프론트가 렌더한다. |
| **④ 에러 폴백** | 예외 시 안전한 부분 state(예: `{"messages": []}`)를 반환해 그래프를 깨뜨리지 않는다. (`file_use` 가 이 패턴) |
| **등록** (기본) | `__init__.py` 의 `_lazy` 블록에 한 줄 추가 (§5). |

### ③ 새 렌더 타입 등록 (해당 시)

기본 텍스트 응답은 `token` 으로 스트리밍되므로 등록이 필요 없다. **새 시각화 타입**(차트·파일·커스텀 UI 등)을 내보낼 때만 3곳을 손본다.

```python
# 노드에서 내보내기
LangchainChatMessage(content=payload, role="assistant", additional_kwargs={"type": "mytype"})
```

1. `graphio_app_framework/api/generator.py` 의 `custom_type` 리스트에 `"mytype"` 추가
2. `graphio_app_framework/api/schema.py` 의 ChatMessage `type` Literal 에 추가
3. `graphio_app_framework/test_ui/stream_test.html` 에 프론트 렌더 처리 추가

기존 타입: `highlights`, `chart`, `file`, `loading`, `loading_end`, `studio_param`, `studio_url`, `studio_url_start`, `studio_url_end`, `studio_param_start`, `studio_param_end` …

---

## 4. 설정·환경변수

프레임워크는 env 를 한 곳에 모은다. **노드에서 `os.getenv` 를 흩뿌리지 말고 `config` 싱글톤을 경유한다.**

```python
from graphio_app_framework.core.config import config

bucket = config.minio_bucket_name      # 타입·기본값이 보장된 설정값
```

- 모델 env(`LLM_MODEL`, `LLM_API_KEY`, `OPENAI_API_KEY` …)는 `ModelManager` 가 이미 처리한다. 노드에서 모델 env 를 다시 읽지 말고 `ModelManager.get_chat_model()` 을 쓴다.

### 새 env var 가 필요할 때 (3곳 갱신)

새 외부 서비스/키를 도입하면 다음 3곳을 모두 갱신한다. 그래야 `graphio-app copy-env` 로 배포 환경까지 전파된다.

1. `graphio_app_framework/core/config.py` 의 `Config` 클래스에 필드 추가 (시크릿은 `SecretStr`)
2. 같은 파일 `Config.get_env()` 에 `os.getenv("MY_KEY", default)` 줄 추가
3. `graphio_app_framework/env.template` 에 `MY_KEY=default` 추가 (주석 섹션과 함께)

> **컨테이너/플랫폼이 주입하는 변수는 `C_` 접두**를 쓴다 (`C_MINIO_*`, `C_DATABASE_*`, `C_APP_PLATFORM_*` …).

### Config 관리형 vs 런타임 ambient (함정)

| 종류 | 예 | 접근 방식 |
|---|---|---|
| **Config 관리형** (typed, env.template 에 존재) | minio, db, llm, ontology | `config.<field>` |
| **런타임 ambient** (컨테이너가 주입, Config 에 없음) | `APP_ID`, `MODE` | `os.getenv()` 직접 |

ambient 변수는 `Config` 에 넣지 않는다. 매니페스트의 `Env:` 에는 **두 종류 모두** 적어 둔다.

---

## 5. `__init__.py` `_lazy` 등록

`service_utils.<name>` 단축 import 가 동작하려면 레지스트리에 한 줄을 추가해야 한다. (docs 의 옛 체크리스트는 이 단계를 빠뜨렸다. **스캐폴더가 자동으로 처리한다 — §8.**)

```python
# graphio_app_framework/__init__.py 의 service_utils._lazy 블록 (알파벳 순 유지)
_lazy("service_utils.keyword_agent", "graphio_app_framework.service_utils.keyword_agent")
```

확인: `python -c "import graphio_app_framework; import service_utils.keyword_agent"` 가 통과해야 한다.

---

## 6. 테스트

`tests/service_utils/test_<name>.py` 에 작성한다. pytest-asyncio + 모듈 레벨 객체 mock 패턴을 따른다.

```python
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage

from graphio_app_framework.service_utils.keyword_agent import keyword_agent


@pytest.mark.asyncio
@patch("graphio_app_framework.service_utils.keyword_agent._model")
async def test_keyword_agent_basic(mock_model):
    mock_model.ainvoke = AsyncMock(return_value=type("R", (), {"content": "a, b, c"})())
    result = await keyword_agent(
        {"messages": [HumanMessage(content="문장")]},
        {"configurable": {"max_keywords": 3}},
    )
    assert result["messages"]


@pytest.mark.asyncio
@patch("graphio_app_framework.service_utils.keyword_agent._model")
async def test_keyword_agent_fallback(mock_model):
    mock_model.ainvoke = AsyncMock(side_effect=Exception("boom"))
    result = await keyword_agent({"messages": [HumanMessage(content="x")]}, {"configurable": {}})
    assert result == {"messages": []}      # ④ 에러 폴백 계약 검증
```

```bash
make test        # pytest
make fmt         # black + isort
```

---

## 7. 패키징 / 배포

스킬의 책임 범위는 **wheel 빌드까지**다.

```bash
make build       # uv build --wheel → dist/graphio_app_framework-<ver>-py3-none-any.whl
make reinstall   # 빌드 후 로컬 강제 재설치 (즉시 검증용)
```

- 버전은 `pyproject.toml` 의 `version = "X.Y.Z"` 를 올린다.
- 내부 wheel 서버 업로드(`download_wheels.sh` 등)는 **프레임워크 관리자**의 몫이다 (`docs/OFFLINE_INSTALL.md`). 빌드한 wheel 과 변경 사항을 관리자에게 인계한다.

> **자동주입 노드는 범위 밖(포인터만).** 모든 앱에 강제 적용되는 노드는 ServiceNode 가 아니라 `injectors/` 경로다: `BaseInjector` 상속 + `graph_base/config.py` 플래그 + `graph_base/graph.py` 등록 + `states/base_agent.py` 필드. 자세한 절차는 `docs/FRAMEWORK_DEVELOPMENT.md` "자동 주입 노드" 체크리스트.

---

## 8. 스캐폴더

새 노드 뼈대는 직접 만들지 말고 스캐폴더로 생성한다. (`_lazy` 등록 누락 같은 반복 실수를 막는다.)

```bash
# 프레임워크 repo 루트에서
python .claude/skills/graphio-subagent-dev/scripts/new_subagent.py keyword_agent

# 다른 위치/repo 지정
python .claude/skills/graphio-subagent-dev/scripts/new_subagent.py keyword_agent --repo /path/to/graphio-app-framework
```

생성물:

- `graphio_app_framework/service_utils/<name>.py` — ServiceNode 계약 스텁 (매니페스트 docstring + dynamic AgentState + 에러 폴백)
- `tests/service_utils/test_<name>.py` — pytest 스텁
- `graphio_app_framework/__init__.py` 의 `_lazy` 블록에 등록 줄 **자동 삽입** (알파벳 순, 실패 시 삽입할 줄을 출력)

그리고 "다음 단계"(매니페스트 채우기 / 새 env 가 필요하면 §4 / `make test` / `make build`)를 출력한다.

---

## 9. 체크리스트

새 service node 를 만들 때:

- [ ] `service_utils/<name>.py` — `async def (state, config) -> dict` 시그니처
- [ ] `AgentState = dynamic_graph_symbol_import('AgentState')`
- [ ] 매니페스트 docstring (`Reads:` / `Writes:` / `Config:` / `Env:`)
- [ ] ① 예약 키 안 건드림 (`title_output` / `user_upload_files*` / `files` / `ontology_resource`; `messages` 는 append 만; `graph_base_*` 노드명 금지)
- [ ] ④ 에러 폴백 (`except` → 안전 state)
- [ ] (새 env면) `Config` + `get_env()` + `env.template` 3곳 (§4)
- [ ] (새 렌더 타입이면) `generator.custom_type` + `schema` + `stream_test.html` (§3 ③)
- [ ] `__init__.py` `_lazy` 등록 (§5, 스캐폴더 자동)
- [ ] `tests/service_utils/test_<name>.py` + `make test`
- [ ] `make fmt`
- [ ] `make build` (배포는 관리자에게 인계)

---

## 10. 참고

- 프레임워크 개발 가이드: `docs/FRAMEWORK_DEVELOPMENT.md` (보조 — 이 스킬이 정본)
- 폐쇄망 배포: `docs/OFFLINE_INSTALL.md`
- 인터페이스 선례: `graphio_app_framework/injectors/base.py` (`GraphInjector(Protocol)`)
- 노드 예시: `service_utils/chart.py`, `service_utils/file_refer.py`
- 서브그래프 빌더 예시(범위 밖, 참고용): `service_utils/studio_agent.py` (`build_studio_agent`)
- 앱 개발(소비 측): `graphio-app-dev` 스킬
