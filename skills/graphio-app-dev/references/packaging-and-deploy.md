# 패키징 & 배포 (Scope 4)

graphio 앱을 만든 뒤 **어떻게 배포하느냐**를 다룬다. 가장 흔한 산출물은 **포털 업로드용 ZIP**(`src/` + `requirements.txt`)이고, 폐쇄망에서는 여기에 **wheel 모음**을 더한다. 프레임워크 자체의 `.whl` 빌드(`make build`)는 **앱 배포와 별개 경로**다 — 둘을 절대 혼동하지 말 것.

> 모든 import/실행 검증은 `/Users/rhcpn/Github/graphio-app-demo-html-generator/.venv/bin/python` 으로 한다(시스템/pyenv python 은 의존성 누락으로 실패). 버전은 항상 `pyproject.toml` 기준(현재 **0.1.0**) — 문서 곳곳의 `0.2.0` 예시는 stale.

관련: 실행/`.env`는 [run-and-debug.md](run-and-debug.md), 스캐폴딩은 [scaffolding-and-authoring.md](scaffolding-and-authoring.md), 에러 증상은 [troubleshooting-and-gotchas.md](troubleshooting-and-gotchas.md). 패키저 스크립트는 [../scripts/package.sh](../scripts/package.sh).

---

## A. 두 가지 배포 모델 (혼동 금지)

| | (A) 포털 ZIP — 앱 개발자 산출물 | (B) 프레임워크 라이브러리 설치 |
|---|---|---|
| **무엇을** | `src/` + `requirements.txt` (+선택 `wheels/`) 를 묶은 `*.zip` | `graphio_app_framework` 패키지(`.whl` 또는 pyproject 의존성) |
| **만드는 법** | `zip -r app.zip src requirements.txt` (또는 `package.sh`) | `make build`(`uv build --wheel`) |
| **어디에** | Graphio Portal "앱 관리 > 앱 등록" 업로드 | 내부 wheel 서버 / `pip install` / editable |
| **누가** | **앱 개발자(거의 항상 이쪽)** | 프레임워크 관리자 / 폐쇄망 wheel 준비자 |

앱 개발자는 보통 **(A)만** 만든다. `make build`는 *프레임워크 자체*를 빌드하는 것이지 **앱 ZIP을 만들지 않는다**. 앱 레포 Makefile에는 `build` 타겟이 아예 없다(H 참조).

핵심: 포털은 ZIP을 받아 그 안의 `requirements.txt`로 `graphio_app_framework`(+앱 고유 패키지)를 설치하고, `src/`를 앱 코드로 마운트한다. 따라서 ZIP **최상위 구조**와 `requirements.txt` **내용**이 배포의 전부다.

---

## B. 포털 ZIP 계약 (가장 자주 틀리는 부분)

ZIP을 **압축 해제했을 때 최상위에 `src/` 디렉터리와 `requirements.txt` 파일이 같은 depth로 바로 보여야** 한다. (`wheels/`는 폐쇄망용 선택.)

```
my_graphio_app.zip
├── src/
│   └── services/
│       ├── agent.py
│       ├── graph.py
│       └── ...
├── requirements.txt
└── wheels/            # (선택, 폐쇄망)
    └── *.whl
```

**반드시 프로젝트 루트로 `cd` 한 뒤 상대경로로 압축한다.**

```bash
cd /path/to/project-root            # src/ 와 requirements.txt 가 있는 곳
# wheels/ 가 있을 때
zip -r my_graphio_app.zip src requirements.txt wheels \
  -x 'src/**/__pycache__/*' 'src/**/*.pyc' 'src/.DS_Store' 'wheels/.DS_Store' '.DS_Store'
# wheels/ 가 없을 때
zip -r my_graphio_app.zip src requirements.txt \
  -x 'src/**/__pycache__/*' 'src/**/*.pyc' 'src/.DS_Store' '.DS_Store'
# 검증: 최상위에 src/ 와 requirements.txt 가 보여야 함
unzip -l my_graphio_app.zip | head
```

**절대경로로 압축 금지.** `zip app.zip /abs/path/src` 처럼 절대경로를 넘기면 ZIP 안에 `abs/path/src/...` 같은 불필요한 계층이 생겨 포털이 최상위 `src/`를 못 찾는다.

> 참고: 다운로드 URL 형식 `/graphio/{APP_ID}/graphio/graphio_app/v1/download/{file_id}` 처럼 `APP_ID`가 들어가는 게이트웨이 경로는 *런타임 라우팅*용이지 ZIP 구조와 무관하다.

---

## C. `package.sh` — 검증 포함 패키저 (권장)

손으로 `zip` 하다 구조를 틀리는 사고를 막으려면 [../scripts/package.sh](../scripts/package.sh)를 쓴다. 4가지를 자동 검증한다.

| # | 검증 | 실패 시 |
|---|---|---|
| 1 | `PROJECT_DIR` 직속에 `src/` 디렉터리 **와** `requirements.txt` 파일이 **같은 depth**에 존재 | 종료(exit 1) |
| 2 | `src/` 안 `*.py` ≥ 1개 (`find -name '*.py'`) | 종료(exit 1) |
| 3 | `wheels/` 있으면 자동 포함, 없으면 생략 | (정상) |
| 4 | 생성 후 `unzip -l` 로 **ZIP 최상위**에 `src` 와 `requirements.txt` 가 직접 보이는지 재검증 | 종료(exit 1) |

`__pycache__/`, `*.pyc`, `.DS_Store` 는 압축에서 제외된다. `zip`/`unzip` 미설치 또는 출력 충돌(`-f` 없이 기존 파일 존재) 시 종료한다.

**옵션**

| 옵션 | 의미 | 기본값 |
|---|---|---|
| `-d PROJECT_DIR` | `src/`+`requirements.txt` 가 있는 루트 | 현재 디렉터리(`pwd`) |
| `-o OUTPUT_ZIP` | 생성할 ZIP 경로 | `<project_basename>_graphio_app.zip` |
| `-f` | 출력 파일이 이미 있어도 덮어쓰기 | (없으면 종료) |
| `-h` | 도움말 | |

```bash
# 가장 단순: 현재 디렉터리 기준
bash .claude/skills/graphio-app-dev/scripts/package.sh
# 파일명 지정 + 덮어쓰기
bash .claude/skills/graphio-app-dev/scripts/package.sh -o my_graphio_app.zip -f
# 다른 프로젝트 루트 지정
bash .claude/skills/graphio-app-dev/scripts/package.sh -d /path/to/project -o out.zip
```

출력 예:
```
[INFO] src/*.py count    : 6
[INFO] wheels/          : (없음, 생략)
[INFO] ZIP top-level entries:
         requirements.txt
         src
[OK] Graphio APP ZIP 생성 완료
```

---

## D. `requirements.txt` 작성 규칙

**프레임워크 한 줄 + 앱 고유 패키지만.** `fastapi`/`langchain`/`langgraph`/`pydantic`/`arize-phoenix-otel` 등 `graphio_app_framework`가 이미 핀한 **전이 의존성은 중복 기재 금지**(pip 버전 충돌 유발).

### 인터넷 환경 + 사내 wheel 서버 (현재 데모 앱의 실제 형태)

```txt
# 아래 3줄을 파일 최상단에 이 순서대로
--trusted-host graphio.mobigen.com
--find-links https://graphio.mobigen.com/graphio/app_platform/control/api/wheel/
graphio_app_framework==0.1.0

# 앱 고유 패키지만 추가
pandas==2.3.3
openpyxl==3.1.5

# Dev
pytest>=8.4
pytest-asyncio>=1.0
```

`--find-links`에 URL이 있으면 인터넷 환경에서도 그 서버를 **먼저** 보고, 없는 패키지만 PyPI에서 가져온다(`--no-index`가 없을 때).

### 완전 폐쇄망 (격리망)

최상단 헤더 순서: **`--no-index` → `--trusted-host` → `--find-links` → 프레임워크 핀**.

```txt
--no-index                                                                          # 완전 격리망에서만
--trusted-host 192.168.109.254
--find-links http://192.168.109.254:31333/graphio/app_platform/control/api/wheel/
graphio_app_framework==0.1.0

pandas==2.3.3
```

| 설정 | 동작 |
|---|---|
| `--find-links URL` 만 | 서버 + PyPI 둘 다 탐색(더 높은 버전 우선) |
| `--find-links URL` + `--no-index` | 서버만 탐색, PyPI 완전 차단 |

> wheel 서버 경로 `/graphio/app_platform/control/api/wheel/` 는 **고정**이다(IP/포트만 환경마다 다름).

---

## E. 폐쇄망 wheel — `download_wheels.sh`

폐쇄망에 배포하려면 **인터넷 환경에서** `*.whl`을 모아 내부 wheel 서버에 올린다. 프레임워크 레포의 [scripts/download_wheels.sh](../../../../scripts/download_wheels.sh)가 프레임워크 `.whl` + **전체 의존성 wheel**을 한 폴더에 수집한다.

```bash
# [인터넷 환경] python -m build 를 쓰므로 build 모듈 필요
pip install build
# 프레임워크 .whl + 의존성 전부 수집 (Linux x86_64 타깃, Mac에서 크로스 다운로드)
./scripts/download_wheels.sh --platform manylinux2014_x86_64 --python 3.11 --dev
#  → whls/0.1.0_py3.11_manylinux2014_x86_64/*.whl
```

**옵션** (소스 verified)

| 옵션 | 의미 | 기본값 |
|---|---|---|
| `-p, --python VERSION` | 대상 Python 버전 | `3.11` |
| `-P, --platform PLATFORM` | 대상 플랫폼 태그 | `manylinux2014_x86_64` |
| `-d, --dev` | dev 의존성(pytest 등) 포함 | off |
| `-o, --output DIR` | 출력 디렉터리 | `./whls/<version>_py<py>_<platform>/` |
| `-h, --help` | 도움말 | |

내부 동작: `python -m build --wheel`(없으면 `pip install build` 안내 후 기존 `dist/*.whl` 복사 폴백) + `pip download --only-binary=:all: --python-version <ver> -d <out>` (플랫폼 지정 시 `--platform <p> --implementation cp` 추가).

### wheel 서버는 반드시 flat (단일 폴더)

`pip --find-links`는 **하위 디렉터리를 재귀 탐색하지 않는다.** 모든 `.whl`을 한 폴더에 평평하게 둔다(파일명에 버전이 들어가 공존 가능).

```bash
# wheel 서버에 flat 하게 복사 (하위 폴더 금지)
scp ./whls/0.1.0_py3.11_manylinux2014_x86_64/*.whl user@HOST:/path/to/wheel-server/
```

### 폐쇄망 설치

```bash
python -m pip install --no-index \
  --find-links http://192.168.109.254:31333/graphio/app_platform/control/api/wheel/ \
  -r requirements.txt
# 또는 로컬 wheel 폴더 직접 지정
python -m pip install --no-index --find-links=./whls -r requirements.txt
```

**플랫폼 매칭 주의:** `--platform`은 *설치 서버* 아키텍처와 같아야 한다(Mac arm64에서 받은 휠을 Linux x86_64에 설치하면 실패). 설치 서버에서 `uname -m`(또는 `python3 -c "import platform; print(platform.machine())"`) 확인 후: `x86_64 → manylinux2014_x86_64`, `aarch64 → manylinux2014_aarch64`, Mac `arm64 → macosx_*_arm64`.

> 앱 고유 패키지(프레임워크에 없는 것)도 같은 방식으로 받아 서버에 올려야 한다. 누락 시 `pip download <pkg>==<ver> --only-binary=:all: --python-version 3.11 --platform <p> --implementation cp -d ./whls/` 로 추가.

---

## F. `.whl` 빌드 (모델 B — 프레임워크 라이브러리)

앱 ZIP 배포에는 불필요하지만, 프레임워크를 라이브러리로 빌드/설치할 때:

```bash
pip install uv          # uv 미설치 시
make clean              # 버전 바꿨으면 stale wheel 제거 (필수)
make build              # uv build --wheel → dist/graphio_app_framework-0.1.0-py3-none-any.whl
uv pip install /path/to/graphio_app_framework-0.1.0-py3-none-any.whl
```

- wheel 파일명 규약: `graphio_app_framework-<version>-py3-none-any.whl` — **순수 py3 휠(플랫폼 태그 없음)**.
- **버전 변경 시 `make clean` 선행 필수:** 같은 버전이면 기존 `.whl`을 덮어쓰지 않아 stale wheel이 남는다.

---

## G. Makefile 타겟 — 프레임워크 레포 vs 앱 레포

두 Makefile은 타겟이 **다르다.** 앱 레포에는 `build`가 없다(앱은 ZIP 배포).

### 프레임워크 레포 ([Makefile](../../../../Makefile))

| 타겟 | 동작 |
|---|---|
| `make init` | uv 확인 + `make install` + `graphio-app copy-env`(`.env` 생성) |
| `make install` | `uv pip install -e ".[dev]"` (editable + dev extras) |
| `make build` | `uv build --wheel` → `dist/...whl` |
| `make reinstall` | `build` 후 `uv pip install --force-reinstall <DIST>` |
| `make fmt` | `uv run black .` + `uv run isort .` |
| `make test` | `uv run pytest` |
| `make clean` | `dist/` `build/` `*.egg-info`, **`GRAPHIO_APP_STORAGE`**, `__pycache__`, `*.pyc` 삭제 |

dev extras: `black>=25.1`, `isort>=6.0`, `pre-commit>=4.2`, `pytest>=8.4`, `pytest-asyncio>=1.0`.

> ⚠️ **`make clean`은 `GRAPHIO_APP_STORAGE`(체크포인트/스토리지 데이터 디렉터리)를 삭제한다.** 데이터 손실 가능 — 실행 전 반드시 사용자 확인을 받을 것.

### 앱 레포

앱 프로젝트 Makefile은 `init`(환경 자동감지 venv → `uv pip install -r requirements.txt` → `copy-env`), `install`(`uv pip install -r requirements.txt`), `reinstall`(requirements.txt의 `graphio_app_framework` 줄 + `--trusted-host`/`--find-links` 반영해 `--force-reinstall`), `test`, `clean` 정도다. **`build` 없음** — `.whl`을 만들지 않는다.

---

## H. 실행 준비 (배포 직전 로컬 확인)

```bash
graphio-app copy-env                 # 패키지 내장 env.template → .env (이미 있으면 [SKIP], 덮어쓰지 않음)
# .env 에서 최소 LLM_MODEL, LLM_API_KEY 설정 (APP_PORT 기본 8888, APP_HOST 0.0.0.0)
graphio-app run                      # http://localhost:8888
graphio-app run --test-ui            # + Test UI http://localhost:18423/stream_test.html
```

`copy-env --dest <파일명>` 으로 대상 파일명 변경 가능. 자세한 CLI/포트/`.env` 변수는 [run-and-debug.md](run-and-debug.md).

---

## I. 데이터 파일 번들 (MANIFEST.in / package-data)

프레임워크 [MANIFEST.in](../../../../MANIFEST.in):
```
include graphio_app_framework/env.template
recursive-include graphio_app_framework/test_ui *.html
```
이렇게 `env.template`과 `test_ui/*.html` 같은 **비-py 데이터 파일**을 `.whl`에 포함한다.

앱이 `*.md`/`*.html` 등 데이터 파일을 **`.whl`로 라이브러리화**하려면 앱 `pyproject.toml`의 `[tool.setuptools.package-data]` + `MANIFEST.in`의 `recursive-include`를 **함께** 선언해야 설치본에서 `importlib.resources`로 접근된다.

> 단 **포털 ZIP 배포**는 `src/`를 통째로 마운트하므로 이 작업이 필요 없다. `src/` 하위는 `.py` 위주로 두는 것을 권고하되, 앱이 직접 읽는 데이터 파일은 `src/` 안에 함께 넣어도 ZIP에 포함된다.

---

## J. 자주 틀리는 포인트 (요약)

- **버전 하드코딩 금지** — 항상 `pyproject.toml` version(현재 **0.1.0**) 기준. 문서의 `0.2.0`은 stale.
- **ZIP은 상대경로로** — 프로젝트 루트로 `cd` 후 `src requirements.txt [wheels]`. 절대경로/상위 폴더째 압축하면 포털이 `src/`를 못 찾음.
- **전이 의존성 중복 기재 금지** — `requirements.txt`엔 `graphio_app_framework` 한 줄 + 앱 고유만.
- **wheel 서버는 flat** — 하위 폴더에 두면 `--find-links`가 못 찾음.
- **`make clean` / 체크포인트 reset은 파괴적** — `GRAPHIO_APP_STORAGE`를 지운다. 사용자 확인 후 실행.
- 문서 stale: `INSTALL.md`의 `PACKAGING_GUIDE.md` 링크는 존재하지 않음 → 패키징 설계 원칙은 [BUILD.md](../../../../docs/BUILD.md) "패키징 설계 원칙" 섹션 참조.
