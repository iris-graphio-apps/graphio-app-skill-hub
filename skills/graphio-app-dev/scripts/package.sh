#!/usr/bin/env bash
#
# package.sh — Graphio APP 포털 업로드용 ZIP 생성기 (검증 포함)
#
# 무엇을 만드는가:
#   Graphio Portal('앱 관리 > 앱 등록')에 업로드하는 단일 *.zip 을 만든다.
#   포털 ZIP 계약(authoritative): 압축을 풀면 *최상위*에
#     - src/              (앱 소스, 최소 1개의 *.py 포함)
#     - requirements.txt  (graphio_app_framework 한 줄 + 앱 고유 패키지만)
#     - wheels/           (선택; 폐쇄망용 *.whl 모음)
#   세 항목이 모두 같은 depth 로 바로 보여야 한다. 한 단계라도 더 깊은 폴더 아래로
#   들어가면 포털이 src/ 를 찾지 못한다.
#   따라서 반드시 프로젝트 루트로 cd 한 뒤 *상대경로*로 압축한다(절대경로 금지).
#   근거: graphio_app_framework 의 모듈 디스커버리는 PROJECT_ROOT/src 를 기준으로
#         앱 모듈을 스캔한다(service_utils/graph_module_loader.find_project_src_root).
#
# 무엇을 검증하는가 (어느 것도 약화하지 말 것):
#   1) PROJECT_DIR 직속에 src/ 디렉터리와 requirements.txt 파일이 같은 depth 에 존재
#   2) src/ 안에 *.py 파일이 최소 1개 존재
#   3) wheels/ 가 있으면 자동 포함, 없으면 생략
#   4) 생성된 ZIP 최상위에 src/ 와 requirements.txt 가 즉시 보이는지 unzip -l 로 재검증
#
# 이 ZIP 은 프레임워크 자체의 .whl 빌드(make build / uv build --wheel)와는 별개 경로다.
# 앱 개발자는 보통 이 ZIP 만 산출한다.
#
# 사용 예:
#   bash scripts/package.sh
#   bash scripts/package.sh -o my_graphio_app.zip -f
#   bash scripts/package.sh -d /path/to/project -o out.zip
#
# 의존: bash, zip, unzip, find, awk (macOS/Linux 공통)

set -euo pipefail

PROJECT_DIR="$(pwd)"
OUTPUT=""
FORCE=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [-d PROJECT_DIR] [-o OUTPUT_ZIP] [-f] [-h]

Options:
  -d PROJECT_DIR   src/ 와 requirements.txt 가 위치한 프로젝트 루트 (기본값: 현재 디렉터리)
  -o OUTPUT_ZIP    생성할 ZIP 경로 (기본값: <project_basename>_graphio_app.zip)
  -f               OUTPUT_ZIP 이 이미 존재해도 덮어쓰기
  -h               도움말 출력
EOF
}

while getopts ":d:o:fh" opt; do
  case "$opt" in
    d) PROJECT_DIR="$OPTARG" ;;
    o) OUTPUT="$OPTARG" ;;
    f) FORCE=1 ;;
    h) usage; exit 0 ;;
    \?) echo "[ERROR] Unknown option: -$OPTARG" >&2; usage; exit 2 ;;
    :)  echo "[ERROR] Option -$OPTARG requires an argument" >&2; usage; exit 2 ;;
  esac
done

# ---------------------------------------------------------------------------
# 프로젝트 루트 정규화
# ---------------------------------------------------------------------------
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "[ERROR] Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="${PROJECT_DIR}/${PROJECT_NAME}_graphio_app.zip"
fi

# 출력 경로를 절대경로로 정규화 (압축 시 cd 이후 상대경로가 깨지지 않도록).
case "$OUTPUT" in
  /*) ABS_OUTPUT="$OUTPUT" ;;
  *)  ABS_OUTPUT="$(pwd)/$OUTPUT" ;;
esac

echo "[INFO] Project directory : $PROJECT_DIR"
echo "[INFO] Output ZIP        : $ABS_OUTPUT"

# ---------------------------------------------------------------------------
# 검증 1: src/ 디렉터리 + requirements.txt 파일이 같은 depth 에 존재
# ---------------------------------------------------------------------------
SRC_DIR="$PROJECT_DIR/src"
REQ_FILE="$PROJECT_DIR/requirements.txt"
WHEELS_DIR="$PROJECT_DIR/wheels"

ERRORS=0

if [[ ! -d "$SRC_DIR" ]]; then
  echo "[ERROR] 'src/' 디렉터리가 없습니다: $SRC_DIR" >&2
  ERRORS=$((ERRORS + 1))
fi

if [[ ! -f "$REQ_FILE" ]]; then
  echo "[ERROR] 'requirements.txt' 가 없습니다: $REQ_FILE" >&2
  ERRORS=$((ERRORS + 1))
fi

if (( ERRORS > 0 )); then
  echo "[ERROR] 프로젝트 루트에 'src/' 와 'requirements.txt' 가 같은 depth 에 위치해야 합니다." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 검증 2: src/ 안에 *.py 파일이 최소 1개 존재
# ---------------------------------------------------------------------------
PY_COUNT=$(find "$SRC_DIR" -type f -name '*.py' | wc -l | tr -d '[:space:]')
if [[ "$PY_COUNT" -eq 0 ]]; then
  echo "[ERROR] 'src/' 안에 *.py 파일이 하나도 없습니다. 최소 1개의 Python 파일이 필요합니다." >&2
  exit 1
fi
echo "[INFO] src/*.py count    : $PY_COUNT"

# ---------------------------------------------------------------------------
# 검증 3: wheels/ 포함 여부 결정 (있으면 자동 포함, 없으면 생략)
# ---------------------------------------------------------------------------
INCLUDE_WHEELS=0
if [[ -d "$WHEELS_DIR" ]]; then
  WHL_COUNT=$(find "$WHEELS_DIR" -type f -name '*.whl' | wc -l | tr -d '[:space:]')
  echo "[INFO] wheels/*.whl     : $WHL_COUNT (자동 포함)"
  INCLUDE_WHEELS=1
else
  echo "[INFO] wheels/          : (없음, 생략)"
fi

# ---------------------------------------------------------------------------
# 출력 ZIP 충돌 처리 (-f 없이 기존 파일 있으면 종료)
# ---------------------------------------------------------------------------
if [[ -e "$ABS_OUTPUT" ]]; then
  if (( FORCE == 1 )); then
    echo "[WARN] 기존 파일을 덮어씁니다: $ABS_OUTPUT"
    rm -f "$ABS_OUTPUT"
  else
    echo "[ERROR] 출력 파일이 이미 존재합니다: $ABS_OUTPUT" >&2
    echo "        덮어쓰려면 -f 옵션을 사용하세요." >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# 압축: 반드시 프로젝트 루트로 cd 한 뒤 상대경로로 압축해서
#       ZIP 내부 최상위에 src/ 와 requirements.txt 가 즉시 보이도록 한다.
#       __pycache__ / *.pyc / .DS_Store 는 제외.
# ---------------------------------------------------------------------------
if ! command -v zip >/dev/null 2>&1; then
  echo "[ERROR] 'zip' 명령을 찾을 수 없습니다. macOS/Linux 의 zip 패키지가 필요합니다." >&2
  exit 1
fi

pushd "$PROJECT_DIR" >/dev/null

if (( INCLUDE_WHEELS == 1 )); then
  zip -r "$ABS_OUTPUT" src requirements.txt wheels \
    -x 'src/**/__pycache__/*' 'src/**/*.pyc' 'src/.DS_Store' \
       'wheels/.DS_Store' '.DS_Store'
else
  zip -r "$ABS_OUTPUT" src requirements.txt \
    -x 'src/**/__pycache__/*' 'src/**/*.pyc' 'src/.DS_Store' '.DS_Store'
fi

popd >/dev/null

# ---------------------------------------------------------------------------
# 검증 4: ZIP 최상위에 src/ 와 requirements.txt 가 직접 보이는가 (unzip -l 재검증)
#   unzip -l 출력은 헤더 3줄 + 엔트리들 + 구분선('----')과 합계 요약 2줄로 끝난다.
#   엔트리 행은 "  Length  Date Time  Name" 4컬럼 고정이므로 경로는 4번째 컬럼($4).
#   구분선 이후의 합계 요약 행(예: "  86   6 files")이 섞이지 않도록 '----'
#   구분선을 만나면 파싱을 멈춘다. 첫 경로 세그먼트만 유니크하게 모은다.
# ---------------------------------------------------------------------------
if ! command -v unzip >/dev/null 2>&1; then
  echo "[ERROR] 'unzip' 명령을 찾을 수 없습니다. ZIP 구조 재검증에 필요합니다." >&2
  exit 1
fi

TOP_ENTRIES="$(unzip -l "$ABS_OUTPUT" \
  | awk 'NR>3 { if ($0 ~ /^[[:space:]]*-----/) exit; print $4 }' \
  | awk -F/ '{print $1}' \
  | sort -u | grep -v '^$' || true)"

echo "[INFO] ZIP top-level entries:"
echo "$TOP_ENTRIES" | sed 's/^/         /'

if ! echo "$TOP_ENTRIES" | grep -qx 'src'; then
  echo "[ERROR] ZIP 최상위에 'src/' 가 없습니다. 압축 구조가 잘못되었습니다." >&2
  echo "        프로젝트 루트로 cd 한 뒤 상대경로로 압축했는지 확인하세요." >&2
  exit 1
fi
if ! echo "$TOP_ENTRIES" | grep -qx 'requirements.txt'; then
  echo "[ERROR] ZIP 최상위에 'requirements.txt' 가 없습니다. 압축 구조가 잘못되었습니다." >&2
  exit 1
fi

SIZE_BYTES=$(wc -c <"$ABS_OUTPUT" | tr -d '[:space:]')
echo "[OK] Graphio APP ZIP 생성 완료"
echo "     - 경로 : $ABS_OUTPUT"
echo "     - 크기 : ${SIZE_BYTES} bytes"
