# graphio-app-skill-hub

langgraph 기반 **graphio-app-framework** 개발에 필요한 Claude 스킬을 모아 배포·관리하는 **사내 스킬 레지스트리(skill-hub)**.

스킬을 한 곳(`registry.json`)에 등록해 두고, 개발자는 필요할 때 자기 도구의 스킬 디렉터리로 **골라 설치**한다. 새 역량이 생기면 스킬로 만들어 여기에 올린다. 목표는 "사내 graphio 개발 노하우를 스킬 단위로 재사용·공유"하는 것.

## 무엇이 들어있나

| 구성 | 설명 |
|---|---|
| `registry.json` | 전체 스킬 카탈로그 (schema v1.0) — 설치기·검증기가 읽는 단일 진실원천 |
| `registry.schema.json` | 레지스트리 정본 스키마 |
| `skills/<name>/` | 각 스킬 (평면 구조): 필수 `SKILL.md` + 선택 `scripts/`·`references/` |

## 등록된 스킬

| name | domain | group | 설명 |
|---|---|---|---|
| **mobigen-skill-installer** | mobigen | core | **hub 진입점** — 레지스트리에서 스킬을 찾아 로컬에 설치/갱신 |
| mobigen-skill-creator | mobigen | skill-tooling | hub 용 스킬을 저작·등록하는 메타 스킬 |
| graphio-app-dev | graphio | app-framework | graphio app 개발·구조·포털 업로드 패키징 |
| graphio-subagent-dev | graphio | app-framework | 재사용 service node(ServiceNode 계약) 저작·등록 |
| graphio-app-test | graphio | app-framework | graphio app 로컬 테스트 (Test UI / curl) |

## 스킬 사용하기 (설치)

**① 한 번만 — 진입점 부트스트랩**: `skills/mobigen-skill-installer/` 폴더를 본인 도구의 스킬 디렉터리(`.claude/skills/`)에 복사한다. 이후엔 이 진입점이 나머지 스킬 설치를 맡는다.

**② 그다음부터** — 진입점이 자동/직접으로 설치:

- **자동**: graphio 작업 중 필요한 스킬이 로컬에 없으면 Claude 가 알아서 제안·설치
- **직접**: `/mobigen-skill-installer <스킬이름>` (또는 `/mobigen-skill-installer list`)
- **스크립트 직접**:

```bash
SK=skills/mobigen-skill-installer/scripts/skillhub.py

python3 $SK list                       # 레지스트리 목록
python3 $SK list --query 테스트          # 검색 (name+description)
python3 $SK install graphio-app-test   # 설치 (기본: 현재 프로젝트 .claude/skills/)
python3 $SK install graphio-app-test --user   # 전역 ~/.claude/skills/
python3 $SK update --all               # 설치된 스킬 일괄 갱신
```

설치기는 이 repo 의 **기본 브랜치(main)** 에서 스킬 폴더를 shallow+sparse git clone 으로 가져온다(필요 시 `--ref`/`GRAPHIO_SKILLHUB_REF` 로 변경). git 만 있으면 동작한다.

## 스킬 기여하기 (등록)

새 스킬은 `mobigen-skill-creator` 가 저작→등록을 안내한다.

```bash
S=skills/mobigen-skill-creator/scripts

python3 $S/scaffold_skill.py <domain>-<name>                 # 규약에 맞는 뼈대 생성
# … SKILL.md 본문/description 작성 …
python3 $S/lint_description.py skills/<domain>-<name>        # description 점검
python3 $S/registry_entry.py  skills/<domain>-<name> \
        --version 0.1.0 --registry registry.json --write     # 레지스트리 등록(+자동 검증)
python3 $S/validate_registry.py registry.json               # 전체 재검증
```

그다음 **PR 을 `dev` 로** 올린다(아래 워크플로).

## 레지스트리 규약 (요약)

- `name`: 전역 유일, lowercase-hyphen, ≤64, **domain prefix 로 시작** (`mobigen` / `graphio` / `agent` / `workflow` / `data`)
- `description`: 30–1024자, 꺾쇠(`<` `>`) 금지, "언제 쓰는지 + 언제 안 쓰는지" 포함, 약간 pushy
- `version`: semver · `path`: 항상 `skills/<name>` · `group`: 선택(이름엔 넣지 않음)

자세한 규약·작성 가이드: `skills/mobigen-skill-creator/references/`.

## 브랜치 워크플로

- 스킬/기능 PR 은 **`dev` 를 대상**으로 한다.
- 검증·리뷰 후 **`dev` → `main`** 으로 릴리스한다(배포 기준은 `main`).
- `dev` 와 `main` 이 갈라지지 않게 유지한다(직접 `main` 푸시 지양). 설치기는 기본적으로 `main` 을 읽는다.

## 레지스트리 검증

```bash
python3 skills/mobigen-skill-creator/scripts/validate_registry.py registry.json
```
