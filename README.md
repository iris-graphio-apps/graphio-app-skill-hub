# graphio-app-skill-hub

langgraph 기반 framework 개발에 필요한 skill 을 관리하는 사내 스킬 레지스트리.

## 구조

- `registry.json` — 전체 스킬 목록 (schema v1.0). 정본 스키마는 `registry.schema.json`.
- `skills/<name>/` — 각 스킬 (평면 구조). 필수 `SKILL.md` + 선택 `scripts/`·`references/`.

## 등록 규약

- `name`: 전역 유일, lowercase-hyphen, ≤64, **domain prefix 로 시작** (`mobigen` / `graphio` / `agent` / `workflow` / `data`)
- `description`: 30–1024자, 꺾쇠(`<` `>`) 금지, "언제 쓰는지 + 언제 안 쓰는지" 포함, 약간 pushy
- `version`: semver · `path`: 항상 `skills/<name>` · `group`: 선택(이름엔 넣지 않음)

작성·등록 가이드와 도구(스캐폴더·린터·엔트리 생성기·검증기)는 `skills/mobigen-skill-creator/` 참고.

## 현재 스킬

| name | domain | group | 설명 |
|---|---|---|---|
| graphio-app-dev | graphio | app-framework | graphio app 개발·구조·포털 업로드 패키징 |
| graphio-subagent-dev | graphio | app-framework | 재사용 service node(ServiceNode 계약) 저작·등록 |
| graphio-app-test | graphio | app-framework | graphio app 로컬 테스트 (Test UI / curl) |
| mobigen-skill-creator | mobigen | skill-tooling | hub 용 스킬 저작·등록 메타 스킬 |

## 검증

```bash
python3 skills/mobigen-skill-creator/scripts/validate_registry.py registry.json
```
