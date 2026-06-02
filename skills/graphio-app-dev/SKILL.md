---
name: graphio-app-dev
description: graphio-app-framework 위에서 LangGraph 기반 AI 앱을 만들 때 사용한다. graphio_app() 으로 그래프를 감싸고, BaseAgentState 를 상속해 State 를 정의하고, 노드/라우터/툴/서브그래프를 작성하고, graphio-app run 으로 로컬 실행/디버깅하고, /stream 엔드포인트를 호출하고, service_utils(studio_agent, chart, file_use 등)와 utils(ModelManager, loader, LOG)를 재사용하고, 포털 업로드용 앱 zip(src/ + requirements.txt) 을 패키징하거나 폐쇄망 wheel 을 만들 때 적용한다. 다음 표현이 나오면 로드: 'graphio app', 'graphio_app()', 'graphio app framework', 'BaseAgentState', 'AgentState', 'graphio-app run', 'copy-env', 'graphio-app CLI', '메인 그래프', '자동 주입 노드', 'studio_agent', 'service_utils', 'ModelManager', '/stream', '포털 업로드', '앱 zip', 'package.sh', 'wheels', '폐쇄망 설치', 'GRAPHIO_APP_DIR', 'PROJECT_ROOT'. 모든 답변은 한국어로, 코드/식별자는 영어 그대로.
---

# graphio-app-dev

graphio-app-framework 위에 **LangGraph 앱**을 만드는 4개 라이프사이클을 다룬다:
**스캐폴딩 → 실행/디버그 → 고급기능 → 패키징/배포.**

이 스킬은 **라우터**다. 깊은 디테일은 `references/*.md` 에 있으니, 아래 결정 맵으로 필요한 파일만 골라 읽는다.

> **0) 원칙 — 소스가 ground truth**
> 모든 비자명한 주장은 프레임워크 소스(`/Users/rhcpn/Github/graphio-app-framework/graphio_app_framework/`)가 권위다.
> 사실이 충돌하면 **패키지 소스 > 테스트 > 레퍼런스 앱 > docs/baseline** 순으로 소스가 이긴다.
> import/실행 검증은 **반드시** `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python` 로 한다(시스템/pyenv python 은 의존성 누락으로 실패).
> 잘못된 import 경로나 시그니처를 적은 스킬은 스킬이 없는 것보다 나쁘다. 확신이 없으면 소스를 열어 확인한다.

---

## 1) 가장 자주 틀리는 7가지 (Quick-Reference — 위반 시 앱이 깨짐)

1. **`graphio_app()` 에는 compile 안 한 builder '함수'를 넘긴다.**
   `my_app = graphio_app(user_graph, state_type=AgentState)` — `user_graph` 는 **호출하면 UNcompiled `StateGraph` 를 반환하는 zero-arg 함수**다. `user_graph()` 를 직접 호출하거나 `builder.compile()` 결과를 넘기면 자동 주입(제목/파일/cleanup)이 사라진다.
   (`graph_base/graph.py:10,18,38-41` — 시그니처 `graphio_app(build_graph_fn, state_type=None, *, checkpointer=None)`)

2. **State 는 `class AgentState(BaseAgentState, total=False)`.**
   import 는 `from graphio_app_framework.states import BaseAgentState`. studio 를 쓰면 `studio_input/studio_type/studio_result/app_report_list` 를 **직접 선언**한다(BaseAgentState 엔 없음). `is_last_step` 도 앱이 `from langgraph.managed.is_last_step import IsLastStep` 로 직접 선언.
   (`states/base_agent.py:6`, `graph_base/agent.py:6-10`)

3. **예약 노드 이름 4개를 직접 `add_node` 하지 말 것:**
   `graph_base_file_use`, `graph_base_clean_user_upload_files`, `graph_base_title`, `graph_base_title_router`.
   (`injectors/file.py:10-11`, `injectors/title.py:10-11`)

4. **BaseAgentState 6개 공통 필드 재정의 금지:**
   `messages`, `title_output`, `user_upload_files`, `user_upload_files_exclude`, `files`, `ontology_resource` — 주입 노드가 채운다. 앱은 상속만 하고 **자체 키만** total=False 로 추가한다.
   (`states/base_agent.py:6-24`)

5. **`/stream` 경로는 고정:** `POST /graphio/graphio_app/v1/stream`.
   `'graphio_app'` 은 앱 이름이 아니라 **프레임워크 고정 prefix 세그먼트**다(앱 이름과 무관, 변경 불가). 기본 서버 `http://localhost:8888`, Test UI 는 **별개 포트 18423**. 포트/호스트는 CLI 플래그가 아니라 `.env`(`APP_PORT`/`APP_HOST`)로만 제어.
   (`api/graphio_app.py:104,134`, `core/config.py:102-103`, `cli.py:14`)

6. **메인 그래프는 정확히 1개.**
   `graphio_app()` 반환값을 모듈 최상위 변수에 할당하면 `compiled.__graphio_main__ = True` 마커가 **자동 설정**되어 파일명/변수명과 무관하게 감지된다. 모듈 레벨 `__graphio_main__ = True` 문장은 감지에 무관(no-op, 있어도 무해). `graphio_app()` 호출이 여러 개면 모두 마커를 가져 충돌하므로 메인은 **한 모듈에서만** 호출한다.
   (`graph_base/graph.py:40`, `service_utils/graph_module_loader.py:195-218`)

7. **포털 zip 최상위 = `src/` + `requirements.txt` (+선택 `wheels/`).**
   반드시 프로젝트 루트로 `cd` 후 **상대경로**로 압축(절대경로 금지). 비스트리밍 LLM 은 `ModelManager.get_chat_model(disable_streaming=True)` 로 JSON 토큰의 SSE 누출을 막는다.
   (`scripts/package.sh`, `utils/models.py:199-248`)

---

## 2) 결정 맵 (Decision / Scope Map — 어떤 reference 로 갈지)

| 하려는 일 | 읽을 파일 |
|---|---|
| 새 앱을 처음부터 만든다 · State/노드/라우터/툴/서브그래프 작성 · `.env` 생성 | [`references/scaffolding-and-authoring.md`](references/scaffolding-and-authoring.md) , [`scripts/scaffold_app.sh`](scripts/scaffold_app.sh) |
| `graphio-app run` 으로 실행 · 모듈을 못 찾거나 메인 그래프가 안 잡힘 · `--test-ui` · `graph.png` · `/stream` 을 curl 로 호출 · configurable 키 | [`references/run-and-debug.md`](references/run-and-debug.md) |
| `studio_agent`/`chart`/`file_use`/`ontology`/`title` 같은 framework 노드 사용 · `ModelManager`/`loader`/`LOG` · 자동 주입 노드 계약 · 서브그래프 | [`references/advanced-features.md`](references/advanced-features.md) |
| 포털 업로드 zip 생성 · `requirements.txt` · 폐쇄망 wheel · `.whl` 빌드 · Makefile | [`references/packaging-and-deploy.md`](references/packaging-and-deploy.md) , [`scripts/package.sh`](scripts/package.sh) |
| 에러 증상 → 원인 → 해결 · `make clean`/db reset 같은 파괴적 작업 | [`references/troubleshooting-and-gotchas.md`](references/troubleshooting-and-gotchas.md) |

---

## 3) 핵심 import 치트시트 (자세한 사실표는 references/ 에)

```python
# 그래프 등록
from graphio_app_framework.graph_base.graph import graphio_app
#   시그니처: graphio_app(build_graph_fn, state_type=None, *, checkpointer=None)
#   (또는: from graphio_app_framework.graph_base import graphio_app — __init__.py 재노출)

# State
from graphio_app_framework.states import BaseAgentState
#   앱: class AgentState(BaseAgentState, total=False)
#   폴백/스튜디오 기본: from graphio_app_framework.graph_base.agent import GraphioAgentState

# LLM (직접 생성 금지 — 항상 이 경로)
from graphio_app_framework.utils.models import ModelManager
#   ModelManager.get_chat_model(disable_streaming=False, temperature=None) -> BaseChatModel

# 로딩 UI / 로그
from graphio_app_framework.utils.loading import loader   # await loader("...", config)  (config None이면 무동작)
from graphio_app_framework.utils.logger import LOG        # logging.getLogger('graphio-app-container')
```

> **service_utils 는 항상 서브모듈 전체 경로로 import 한다.** `service_utils/__init__.py` 가 빈 파일이라 패키지 레벨 import 는 `ImportError`. 예:
> `from graphio_app_framework.service_utils.studio_agent import build_studio_agent`
> `from graphio_app_framework.service_utils.chart import chart_agent`
> 자세한 목록은 [`references/advanced-features.md`](references/advanced-features.md).

---

## 4) 표준 앱 파일 구성 (한 눈에)

```
project-root/
├─ src/services/            # GRAPHIO_APP_DIR 미설정 시 기본 스캔 대상
│  ├─ agent.py              # class AgentState(BaseAgentState, total=False)
│  ├─ graph.py (또는 graph_main.py)   # user_graph()->StateGraph(compile 안함) + my_app = graphio_app(...)
│  ├─ nodes.py              # async def node(state, config: RunnableConfig) → 부분 업데이트 dict 반환 + ToolNode
│  ├─ routers.py            # conditional edge 함수 (Literal 반환)
│  ├─ tools.py              # @tool 정의
│  ├─ prompt.py
│  └─ (옵션) editor.py / 서브그래프 모듈
├─ requirements.txt         # graphio_app_framework 한 줄 + 앱 고유만
└─ .env                     # graphio-app copy-env 로 생성 (LLM_MODEL, LLM_API_KEY 등)
```

- 메인 그래프 등록은 한 줄: `my_app = graphio_app(user_graph, state_type=AgentState)` (변수명 자유 — 마커 자동 설정).
- 표준 패턴/스켈레톤 생성: [`references/scaffolding-and-authoring.md`](references/scaffolding-and-authoring.md) , [`scripts/scaffold_app.sh`](scripts/scaffold_app.sh).

---

## 5) references 및 scripts 링크 (상대경로)

- [`references/scaffolding-and-authoring.md`](references/scaffolding-and-authoring.md) — 새 앱 레이아웃, `graphio_app()` 의미, State 계약, 노드/라우터/툴/서브그래프 작성, requirements/.env
- [`references/run-and-debug.md`](references/run-and-debug.md) — `graphio-app` CLI, env vars, 모듈 디스커버리, 메인 그래프 감지, `/stream` API·SSE·configurable, 로컬 curl, 디버깅
- [`references/advanced-features.md`](references/advanced-features.md) — `service_utils`(studio/chart/file_use/ontology/title), `ModelManager`/`loader`/`LOG`, 자동 주입 노드 계약, 인프라 클라이언트
- [`references/packaging-and-deploy.md`](references/packaging-and-deploy.md) — 포털 zip, requirements 규칙, 폐쇄망 wheel, `.whl` 빌드, Makefile
- [`references/troubleshooting-and-gotchas.md`](references/troubleshooting-and-gotchas.md) — 에러 증상→원인→해결, stale 문서 정정, 파괴적 작업 경고
- [`scripts/package.sh`](scripts/package.sh) — 포털 zip 패키저(구조 검증 + `unzip -l` 재검증)
- [`scripts/scaffold_app.sh`](scripts/scaffold_app.sh) — 최소 실행가능 앱 스켈레톤 생성
