#!/usr/bin/env bash
#
# scaffold_app.sh — graphio-app-framework 위에서 동작하는 최소 실행가능 앱 스켈레톤 생성
#
# 생성물 (TARGET_DIR 기준):
#   src/services/agent.py   — AgentState(BaseAgentState, total=False)
#   src/services/graph.py   — 1-노드 그래프 + graphio_app() + __graphio_main__ + graph.png 블록
#   requirements.txt        — graphio-app-framework 의존성 한 줄 + 폐쇄망 헤더(주석) 템플릿
#   .env                    — LLM_MODEL / LLM_API_KEY / APP_PORT / APP_HOST stub
#
# 모든 import 경로/시그니처는 framework 소스(ground truth)와 일치:
#   from graphio_app_framework.graph_base.graph import graphio_app   (graph.py:10)
#   from graphio_app_framework.states import BaseAgentState          (states/__init__.py)
#   from graphio_app_framework.utils.models import ModelManager      (utils/models.py:199)
#   from graphio_app_framework.utils.loading import loader           (utils/loading.py:11)
#
set -euo pipefail

# ----------------------------------------------------------------------------
# usage
# ----------------------------------------------------------------------------
usage() {
  cat <<'EOF'
Usage: scaffold_app.sh [-d TARGET_DIR] [-n APP_NAME] [-f] [-h]

  -d TARGET_DIR   스켈레톤을 생성할 대상 디렉터리 (기본: 현재 디렉터리 .)
  -n APP_NAME     앱 이름(주석/.env 라벨용, 기본: TARGET_DIR 의 basename)
  -f              기존 파일을 덮어쓴다 (미지정 시 충돌하면 종료)
  -h              이 도움말을 출력한다

예시:
  scaffold_app.sh                         # 현재 디렉터리에 생성
  scaffold_app.sh -d ./my-app -n my-app   # ./my-app 에 생성
  scaffold_app.sh -d ./my-app -f          # 기존 파일을 덮어쓰며 재생성

생성 후 다음 단계:
  1) cd TARGET_DIR
  2) graphio-app copy-env        # 주의: .env 가 이미 있으면 [SKIP] 만 출력되고 아무것도 안 받는다.
                                 #       더 완전한 설정(C_MINIO_* 등)이 필요하면 .env 삭제 후 copy-env
                                 #       하거나 필요한 변수를 수동 추가한다.
  3) .env 에서 LLM_MODEL / LLM_API_KEY 설정
  4) graphio-app run             # http://localhost:8888 (POST /graphio/graphio_app/v1/stream)
  5) graphio-app run --test-ui   # + Test UI http://localhost:18423/stream_test.html
EOF
}

# ----------------------------------------------------------------------------
# 옵션 파싱
# ----------------------------------------------------------------------------
TARGET_DIR="."
APP_NAME=""
FORCE=0

while getopts ":d:n:fh" opt; do
  case "${opt}" in
    d) TARGET_DIR="${OPTARG}" ;;
    n) APP_NAME="${OPTARG}" ;;
    f) FORCE=1 ;;
    h) usage; exit 0 ;;
    :) echo "[ERROR] 옵션 -${OPTARG} 에는 인자가 필요합니다." >&2; usage >&2; exit 2 ;;
    \?) echo "[ERROR] 알 수 없는 옵션: -${OPTARG}" >&2; usage >&2; exit 2 ;;
  esac
done

# 절대경로 정규화 (디렉터리는 미리 만들어 둔다)
mkdir -p "${TARGET_DIR}"
TARGET_DIR="$(cd "${TARGET_DIR}" && pwd)"

if [[ -z "${APP_NAME}" ]]; then
  APP_NAME="$(basename "${TARGET_DIR}")"
fi

SERVICES_DIR="${TARGET_DIR}/src/services"

echo "[INFO] 대상 디렉터리 : ${TARGET_DIR}"
echo "[INFO] 앱 이름       : ${APP_NAME}"
echo "[INFO] services 경로 : ${SERVICES_DIR}"

# ----------------------------------------------------------------------------
# 충돌 검사 헬퍼: -f 없으면 기존 파일이 있을 때 종료
# ----------------------------------------------------------------------------
GENERATED_FILES=(
  "${SERVICES_DIR}/agent.py"
  "${SERVICES_DIR}/graph.py"
  "${TARGET_DIR}/requirements.txt"
  "${TARGET_DIR}/.env"
)

if [[ "${FORCE}" -ne 1 ]]; then
  conflict=0
  for f in "${GENERATED_FILES[@]}"; do
    if [[ -e "${f}" ]]; then
      echo "[ERROR] 이미 존재: ${f}" >&2
      conflict=1
    fi
  done
  if [[ "${conflict}" -eq 1 ]]; then
    echo "[ERROR] 기존 파일을 덮어쓰려면 -f 옵션을 사용하세요." >&2
    exit 1
  fi
fi

# ----------------------------------------------------------------------------
# 디렉터리 생성
# ----------------------------------------------------------------------------
mkdir -p "${SERVICES_DIR}"
echo "[INFO] 디렉터리 생성 완료: ${SERVICES_DIR}"

# ----------------------------------------------------------------------------
# src/services/agent.py
#   - BaseAgentState 상속 (total=False) — 자체 키만 optional, 상속 6필드는 그대로 유지
#   - import 경로: from graphio_app_framework.states import BaseAgentState
#   - 공통 6필드(messages, title_output, user_upload_files, user_upload_files_exclude,
#     files, ontology_resource)는 절대 재정의하지 않는다(주입 노드가 채움).
# ----------------------------------------------------------------------------
cat > "${SERVICES_DIR}/agent.py" <<'PYEOF'
"""앱 State 정의.

BaseAgentState 를 상속하고 total=False 로 선언한다.
- total=False: 이 클래스에서 새로 추가한 키만 optional 이 된다.
  (상속받은 공통 6필드는 여전히 required 이며, framework 주입 노드가 채운다.)
- 공통 6필드(messages, title_output, user_upload_files,
  user_upload_files_exclude, files, ontology_resource)는 재정의 금지.
"""

from typing import Optional

from langgraph.managed.is_last_step import IsLastStep
from graphio_app_framework.states import BaseAgentState


class AgentState(BaseAgentState, total=False):
    # is_last_step 은 BaseAgentState 가 제공하지 않으므로 앱이 직접 선언한다.
    is_last_step: IsLastStep

    # 앱 고유 키 예시 (필요에 맞게 추가/삭제)
    intent: Optional[str]

    # ── Studio(build_studio_agent)를 쓸 때만 아래 4필드를 선언한다 ──
    # (BaseAgentState 에는 없음. Studio 서브그래프가 읽고/쓴다.)
    # studio_input: Optional[dict]
    # studio_type: Optional[str]
    # studio_result: Optional[str]
    # app_report_list: Optional[list]
PYEOF
echo "[INFO] 생성: ${SERVICES_DIR}/agent.py"

# ----------------------------------------------------------------------------
# src/services/graph.py
#   - user_graph(): compile 하지 않은 StateGraph 반환 (set_entry_point + END)
#   - graphio_app(user_graph, state_type=AgentState) — compiled.__graphio_main__ 자동 설정
#   - ModelManager.get_chat_model() / loader 예시 노드
#   - if __name__ == "__main__": graph.png 출력 블록
#   - 동일 패키지 내 import 는 `from services.agent import AgentState`
#     (framework 가 src/ 를 sys.path 에 올리므로 동작)
# ----------------------------------------------------------------------------
cat > "${SERVICES_DIR}/graph.py" <<'PYEOF'
"""메인 그래프 정의.

핵심 규칙:
- user_graph() 는 compile 하지 않은 StateGraph 를 반환한다.
  (graphio_app() 이 내부에서 rebuild_graph + compile 을 수행하며,
   여기서 제목/파일/cleanup 자동 주입이 일어난다. 직접 compile 하면 사라진다.)
- graphio_app() 반환값을 모듈 최상위 변수에 할당하면
  compiled.__graphio_main__ = True 가 자동 설정되어 메인 그래프로 감지된다.
- 예약 노드 이름 4개(graph_base_file_use, graph_base_clean_user_upload_files,
  graph_base_title, graph_base_title_router)는 직접 add_node 하지 않는다.
"""

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from graphio_app_framework.graph_base.graph import graphio_app
from graphio_app_framework.utils.loading import loader
from graphio_app_framework.utils.logger import LOG
from graphio_app_framework.utils.models import ModelManager

from services.agent import AgentState


# 모듈 로드 시 1회 획득해 재사용 (싱글톤 캐시).
# 모델명/키는 .env 의 LLM_MODEL / LLM_API_KEY 등으로 받는다 (하드코딩 금지).
chat_model = ModelManager.get_chat_model()


async def call_model(state: AgentState, config: RunnableConfig):
    """단일 LLM 노드. 노드는 변경된 키만 담은 dict(partial update)를 반환한다."""
    # loader 는 async 이며 config 가 None 이면 무동작 → 노드 config 를 그대로 넘긴다.
    await loader("model 노드 실행중입니다.", config)
    try:
        response = await chat_model.ainvoke(state["messages"], config)
    except Exception as e:
        LOG.error("call_model 실패: %s", e)
        raise
    return {"messages": [response]}


def user_graph():
    """compile 하지 않은 StateGraph 를 반환한다 (graphio_app 이 compile 한다)."""
    builder = StateGraph(AgentState)
    builder.add_node("model", call_model)
    builder.set_entry_point("model")
    builder.add_edge("model", END)
    return builder


# graphio_app() 한 줄로 __graphio_main__ 마커가 자동 설정된다 (변수명/파일명 무관).
# checkpointer 는 생략한다 — HTTP 실행 시 lifespan 이 AsyncSqliteSaver 를 런타임 주입한다.
my_app = graphio_app(user_graph, state_type=AgentState)


if __name__ == "__main__":
    # 그래프 시각화: services 패키지가 src/ 아래라 src 를 sys.path 에 올려야 한다.
    #   cd src && PROJECT_ROOT=$(pwd)/.. python -m services.graph
    #   (또는 저장소 루트에서) PYTHONPATH=src python src/services/graph.py
    # 주의: 위 모듈은 최상위에서 ModelManager.get_chat_model() 을 호출하므로
    #       도달 가능한 LLM(LLM_MODEL + LLM_API_KEY/LLM_API_ADDRESS)과
    #       스킴 없는 C_MINIO_CLIENT_HOST 가 설정돼야 PNG 가 생성된다.
    #       (오프라인이면 utils.models._probe 를 monkeypatch 후 실행)
    my_app.get_graph().draw_mermaid_png(output_file_path="graph.png")
PYEOF
echo "[INFO] 생성: ${SERVICES_DIR}/graph.py"

# ----------------------------------------------------------------------------
# requirements.txt
#   - framework 한 줄 + 앱 고유 패키지만 (전이 의존성 fastapi/langchain 등 중복 금지)
#   - 폐쇄망 헤더(--no-index / --trusted-host / --find-links)는 그 순서로 주석 템플릿 제공
#   - 패키지명은 graphio_app_framework (현재 버전 0.1.0, pyproject.toml 기준)
# ----------------------------------------------------------------------------
cat > "${TARGET_DIR}/requirements.txt" <<'REQEOF'
# ─────────────────────────────────────────────────────────────────────────
# 폐쇄망(오프라인) 설치 시: 아래 3줄을 이 순서대로 파일 최상단에 둔다.
#   --no-index 는 완전 격리망일 때만 주석 해제 (PyPI 완전 차단)
# --no-index
# --trusted-host 192.168.109.254
# --find-links http://192.168.109.254:31333/graphio/app_platform/control/api/wheel/
# ─────────────────────────────────────────────────────────────────────────

# framework — 전이 의존성(fastapi/langchain/langgraph/pydantic 등)은 자동 해결되므로
# 여기에 중복 기재하지 않는다 (버전 충돌 방지).
graphio_app_framework==0.1.0

# ── 앱 고유 패키지만 아래에 추가 ──
# pandas==2.3.3
# openpyxl==3.1.5

# ── (선택) Dev ──
# pytest>=8.4
# pytest-asyncio>=1.0
REQEOF
echo "[INFO] 생성: ${TARGET_DIR}/requirements.txt"

# ----------------------------------------------------------------------------
# .env stub
#   - graphio-app copy-env 로 framework env.template 을 받는 것이 더 완전하지만,
#     단독 실행이 가능하도록 최소 변수를 채운 stub 을 둔다.
#   - config 는 cwd 기준 find_dotenv(usecwd=True) 로 .env 를 로드 → 프로젝트 루트에 둔다.
# ----------------------------------------------------------------------------
cat > "${TARGET_DIR}/.env" <<ENVEOF
# ${APP_NAME} — graphio-app 실행 환경 변수 (최소 stub)
# 더 완전한 템플릿은 framework 내장본을 복사해 보강하세요:
#   graphio-app copy-env

# ── LLM (필수) ──
# LLM_MODEL 은 필수. LLM_API_KEY 또는 LLM_API_ADDRESS 중 최소 하나가 필요하다.
#   - LLM_API_KEY 사용 시(openai/anthropic/...): 아래처럼 모델명 + 키
#   - LLM_API_ADDRESS 사용 시(vllm/ollama): 키 대신 주소
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=
# LLM_API_ADDRESS=

# ── MinIO (필수: 스킴 없는 host 여야 함) ──
# auto-inject 되는 graph_base_file_use 경로가 import 시점에 MinIO 클라이언트를
# 생성한다(service_utils/file_refer.py:15). 이 값이 비면 config 기본값
# http://192.168.109.254 (스킴 포함)가 쓰여 그래프 로드 시
# ValueError('path in endpoint is not allowed')가 난다. 반드시 스킴 없는 host 로 둔다.
C_MINIO_CLIENT_HOST=localhost

# ── 앱 서버 ──
APP_HOST=0.0.0.0
APP_PORT=8888

# ── 실행 모드 / 로깅 ──
MODE=dev
# 콘솔 로그는 기본 비활성(false). 개발 중 콘솔 확인이 필요하면 true.
LOG_CONSOLE_ENABLED=false

# ── (선택) 자동 주입 노드 토글 (기본 모두 true) ──
# ENABLE_FILE_USE=true
# ENABLE_CLEAN_USER_UPLOAD_FILES=true
# ENABLE_TITLE=true

# ── (선택) 모듈 스캔 범위 제한 ──
# GRAPHIO_APP_DIR=services
ENVEOF
echo "[INFO] 생성: ${TARGET_DIR}/.env"

# ----------------------------------------------------------------------------
# 다음 단계 안내
# ----------------------------------------------------------------------------
cat <<EOF

[INFO] 스켈레톤 생성 완료.

생성된 파일:
  ${SERVICES_DIR}/agent.py
  ${SERVICES_DIR}/graph.py
  ${TARGET_DIR}/requirements.txt
  ${TARGET_DIR}/.env

다음 단계:
  1) cd "${TARGET_DIR}"
  2) graphio-app copy-env          # 주의: .env 가 이미 있으면 [SKIP] 만 출력된다(cli.py:85).
                                   #       이미 stub .env 가 생성됐으므로 그냥 실행하면 아무것도 안 받는다.
                                   #       전체 template(C_MINIO_* 등)이 필요하면 .env 를 삭제 후 copy-env
                                   #       하거나 필요한 변수를 수동 추가한다.
  3) .env 에서 LLM_MODEL / LLM_API_KEY 설정
  4) graphio-app run               # http://localhost:8888
                                   # 스트림: POST /graphio/graphio_app/v1/stream
  5) graphio-app run --test-ui     # + Test UI http://localhost:18423/stream_test.html

포털 업로드 zip 을 만들려면 같은 스킬의 scripts/package.sh 를 사용하세요.
EOF
