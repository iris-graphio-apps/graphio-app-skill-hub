#!/usr/bin/env python3
"""graphio-subagent-dev 스캐폴더 — 새 service node(sub-agent) 뼈대 생성.

생성물:
  - graphio_app_framework/service_utils/<name>.py   (ServiceNode 계약 스텁)
  - tests/service_utils/test_<name>.py              (pytest 스텁)
  - graphio_app_framework/__init__.py 의 _lazy 블록에 등록 줄 자동 삽입

사용:
  python .claude/skills/graphio-subagent-dev/scripts/new_subagent.py keyword_agent
  python .../new_subagent.py keyword_agent --repo /path/to/graphio-app-framework

옵션:
  --repo, -d   프레임워크 repo 루트 (생략 시 자동 탐색)
  --force, -f  이미 있는 파일을 덮어쓴다
"""
import argparse
import keyword
import re
import sys
from pathlib import Path

TOKEN = "NODENAME"

MODULE_TEMPLATE = '''"""NODENAME — graphio_app_framework service node (sub-agent).

ServiceNode 계약을 따르는 재사용 노드. 내부 구현(뒷쪽 기능)은 자유롭게 채운다.
graphio_app 그래프에 `builder.add_node("NODENAME", NODENAME)` 로 꽂을 수 있다.

Reads:   messages                 # TODO: 이 노드가 읽는 state 키
Writes:  messages                 # TODO: 반환(갱신)하는 state 키 — 예약 키 금지
Config:  (없음)                    # TODO: config["configurable"] 에서 읽는 키
Env:     (없음)                    # TODO: config.<field> 또는 새 env var 의존 시 명시
"""
from langchain_core.messages import ChatMessage as LangchainChatMessage  # noqa: F401
from langchain_core.runnables import RunnableConfig

from graphio_app_framework.utils.logger import LOG

# LLM 이 필요하면:
# from graphio_app_framework.utils.models import ModelManager
# _model = ModelManager.get_chat_model(disable_streaming=True)
#
# 설정/외부 서비스가 필요하면:
# from graphio_app_framework.core.config import config

from graphio_app_framework.service_utils.graph_module_loader import dynamic_graph_symbol_import

# service_utils 는 앱의 AgentState 를 직접 import 할 수 없으므로 동적 참조한다.
AgentState = dynamic_graph_symbol_import("AgentState")


async def NODENAME(state: AgentState, config: RunnableConfig) -> dict:
    """TODO: 한 줄 설명. graphio_app 그래프에 노드로 추가되어 실행된다."""
    try:
        # TODO: 핵심 로직. state.get("messages", []) 등에서 입력을 읽고
        #       부분 state dict 를 반환한다.
        #       예약 키(title_output / user_upload_files / user_upload_files_exclude /
        #       files / ontology_resource)는 절대 반환하지 않는다. messages 는 append 만.
        #       새 시각화 타입을 내보내면 additional_kwargs={"type": "<x>"} +
        #       SSE 등록(api/generator.py custom_type / api/schema.py / test_ui/stream_test.html).
        return {"messages": []}
    except Exception as e:
        # 에러 폴백: 그래프를 깨뜨리지 않도록 안전한 state 를 반환한다.
        LOG.error(f"NODENAME 실패: {e}")
        return {"messages": []}
'''

TEST_TEMPLATE = '''import pytest
from unittest.mock import AsyncMock, patch  # noqa: F401

from graphio_app_framework.service_utils.NODENAME import NODENAME


@pytest.mark.asyncio
async def test_NODENAME_returns_dict():
    result = await NODENAME({"messages": []}, {"configurable": {}})
    assert isinstance(result, dict)


# LLM/외부 의존을 추가하면 모듈 레벨 객체를 mock 한다. 예:
# @pytest.mark.asyncio
# @patch("graphio_app_framework.service_utils.NODENAME._model")
# async def test_NODENAME_fallback(mock_model):
#     mock_model.ainvoke = AsyncMock(side_effect=Exception("boom"))
#     result = await NODENAME({"messages": []}, {"configurable": {}})
#     assert result == {"messages": []}   # 에러 폴백 계약 검증
'''


def fail(msg: str) -> "None":
    print(f"[ERROR] {msg}")
    sys.exit(1)


def validate_name(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        fail(f"이름은 snake_case 여야 함 (소문자로 시작, 소문자/숫자/_): {name!r}")
    if keyword.iskeyword(name):
        fail(f"파이썬 예약어는 쓸 수 없음: {name!r}")
    if name.startswith("graph_base_"):
        fail("graph_base_ 접두는 자동주입 예약어라 쓸 수 없음")
    if not (name.endswith("_agent") or name.endswith("_node")):
        print(f"[WARN] 관례상 *_agent / *_node 를 권장한다 (현재: {name})")


def find_repo_root(explicit: "str | None") -> Path:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / "graphio_app_framework" / "__init__.py").is_file():
            return p
        fail(f"--repo 경로에 graphio_app_framework/__init__.py 가 없음: {p}")
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        cur = start
        for _ in range(10):
            if (cur / "graphio_app_framework" / "__init__.py").is_file():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
    fail("graphio_app_framework repo 루트를 찾지 못함. --repo 로 지정하세요.")
    return Path()  # unreachable


def render(template: str, name: str) -> str:
    return template.replace(TOKEN, name)


def write_file(path: Path, content: str, force: bool) -> str:
    if path.exists() and not force:
        return "skip"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "write"


def register_lazy(init_path: Path, name: str) -> str:
    """__init__.py 의 service_utils._lazy 블록에 등록 줄을 알파벳 순으로 삽입."""
    text = init_path.read_text(encoding="utf-8")
    if f'"service_utils.{name}"' in text:
        return "exists"

    lines = text.splitlines(keepends=True)
    block = [i for i, ln in enumerate(lines) if re.search(r'_lazy\(\s*"service_utils\.', ln)]
    if not block:
        return "no-block"

    def name_of(line: str) -> str:
        m = re.search(r'_lazy\(\s*"service_utils\.([A-Za-z0-9_]+)"', line)
        return m.group(1) if m else ""

    indent = re.match(r"\s*", lines[block[0]]).group(0)
    new_line = (
        f'{indent}_lazy("service_utils.{name}", '
        f'"graphio_app_framework.service_utils.{name}")\n'
    )

    insert_at = block[-1] + 1
    for i in block:
        if name_of(lines[i]) > name:
            insert_at = i
            break

    lines.insert(insert_at, new_line)
    init_path.write_text("".join(lines), encoding="utf-8")
    return "inserted"


def main() -> None:
    ap = argparse.ArgumentParser(description="새 graphio service node(sub-agent) 스캐폴더")
    ap.add_argument("name", help="노드 이름 (snake_case, 예: keyword_agent / glossary_node)")
    ap.add_argument("--repo", "-d", default=None, help="프레임워크 repo 루트 (생략 시 자동 탐색)")
    ap.add_argument("--force", "-f", action="store_true", help="기존 파일 덮어쓰기")
    args = ap.parse_args()

    name = args.name
    validate_name(name)
    repo = find_repo_root(args.repo)

    module_path = repo / "graphio_app_framework" / "service_utils" / f"{name}.py"
    test_path = repo / "tests" / "service_utils" / f"test_{name}.py"
    init_path = repo / "graphio_app_framework" / "__init__.py"

    m_status = write_file(module_path, render(MODULE_TEMPLATE, name), args.force)
    t_status = write_file(test_path, render(TEST_TEMPLATE, name), args.force)
    r_status = register_lazy(init_path, name)

    label = {
        "write": "생성",
        "skip": "이미 있음 (건너뜀, 덮어쓰려면 --force)",
        "exists": "이미 등록됨",
        "inserted": "등록 줄 삽입",
        "no-block": "service_utils _lazy 블록을 못 찾음",
    }
    rel = lambda p: p.relative_to(repo)  # noqa: E731
    print(f"\nrepo: {repo}")
    print(f"  module : {label[m_status]:30} {rel(module_path)}")
    print(f"  test   : {label[t_status]:30} {rel(test_path)}")
    print(f"  _lazy  : {label[r_status]:30} {rel(init_path)}")

    if r_status == "no-block":
        print("\n[수동 추가 필요] __init__.py 의 service_utils._lazy 블록에 아래 줄을 넣으세요:")
        print(
            f'    _lazy("service_utils.{name}", '
            f'"graphio_app_framework.service_utils.{name}")'
        )

    print("\n다음 단계:")
    print(f"  1) {rel(module_path)} 의 매니페스트(Reads/Writes/Config/Env)와 로직을 채운다")
    print("  2) 새 env 가 필요하면: core/config.py(Config + get_env) + env.template 3곳 갱신")
    print("  3) 새 렌더 타입이면: api/generator.py custom_type + api/schema.py + test_ui/stream_test.html")
    print("  4) make test && make fmt")
    print("  5) make build   # wheel — 배포는 프레임워크 관리자에게 인계")


if __name__ == "__main__":
    main()
