# 회사 skill-hub 레지스트리 규약

skill-hub 는 **평면 구조의 스킬 폴더 + 단일 `registry.json`** 으로 운영된다. 정본 스키마는 같은 폴더의 [`registry.schema.json`](registry.schema.json) 이며, 스크립트들은 이 파일을 단일 진실원천으로 읽는다. 아래는 그 스키마를 실무 규칙으로 풀어 쓴 것이다.

## 1. hub 레이아웃

```
company-skills/
├─ registry.json                # 모든 스킬 엔트리 (스키마 v1.0)
├─ registry.schema.json
└─ skills/
   ├─ <name>/                   # 평면 — 항상 skills/<name>
   │  ├─ SKILL.md               # 필수
   │  ├─ scripts/ references/ assets/   # 선택
   └─ ...
```

## 2. 엔트리 필드 규칙

| 필드 | 필수 | 규칙 | 예 |
|---|---|---|---|
| `name` | O | 전역 유일. lowercase-hyphen(`^[a-z0-9]+(-[a-z0-9]+)*$`), ≤64. **domain 을 prefix 로 시작.** | `graphio-app-test` |
| `description` | O | 30–1024자. 트리거 문구 — **언제 쓰는지 + 언제 안 쓰는지** 모두, 약간 pushy. **꺾쇠 `< >` 금지.** | (아래 예 참고) |
| `domain` | O | enum: `mobigen` / `graphio` / `agent` / `workflow` / `data`. 새 도메인은 스키마 enum 에 추가. | `graphio` |
| `group` | — | 선택. lowercase-hyphen. **가변적이라 name 엔 넣지 않고 여기에만.** | `app-framework` |
| `version` | O | semver `MAJOR.MINOR.PATCH`. | `0.1.0` |
| `path` | O | 항상 `skills/<name>`. | `skills/graphio-app-test` |

### name 의 domain prefix 규칙

`name` 은 승인 domain 중 하나로 시작해야 한다. 경계는 정확히 일치하거나 하이픈이다:

- `mobigen-skill-creator` → domain `mobigen` ✓
- `graphio-app-dev` → domain `graphio` ✓
- `agentic-helper` → `agent` 로 시작하는 것처럼 보이지만 다음 글자가 `i`(하이픈 아님) → **매칭 안 됨**. domain 미상으로 거부.

`scripts/_schema.py` 의 `infer_domain()` 이 이 규칙으로 domain 을 추론한다.

### description 작성 (스키마 + 트리거 품질)

하드 규칙(스키마): 30–1024자, 꺾쇠 금지. 품질 규칙(트리거): 과소트리거를 막기 위해 약간 pushy 하게, 그리고 **언제 안 쓰는지**(형제 스킬로 보내기)를 꼭 포함한다.

**예 (graphio-app-test):**

> 만든 graphio app 을 로컬에서 실행·테스트할 때 반드시 로드한다. 패키지에 번들된 Test UI 를 `graphio-app run --test-ui` 로 띄워 브라우저에서 확인하거나 /stream 을 curl 로 직접 친다. '앱 테스트', '돌려보기', 'test-ui' 같은 표현에서 사용. 단, 앱을 새로 만드는 작업은 graphio-app-dev 를 대신 쓴다.

`< >` 가 필요해 보이면 `skills/이름` 처럼 풀어 쓰거나 백틱/따옴표로 대체한다.

## 3. 만들기 → 등록 흐름

```
scaffold_skill.py <name>            # skills/<name>/SKILL.md (compliant frontmatter)
        ↓  (description·본문 작성)
lint_description.py skills/<name>    # 길이·꺾쇠(하드) + when-to/when-not/pushy(소프트)
        ↓
registry_entry.py skills/<name> --version 0.1.0 --registry registry.json --write
        ↓                           # SKILL.md → 엔트리 생성·병합(같은 name 교체)
validate_registry.py registry.json  # 전체 재검증 (jsonschema 있으면 권위 검증)
```

- `registry_entry.py` 는 `path`(=`skills/<name>`)와 `domain`(prefix 추론)을 **자동 계산**하므로 손으로 쓰지 않는다.
- 기존 스킬을 갱신하면 `version` 을 semver 규칙으로 올린다(버그픽스=patch, 기능추가=minor, 호환깨짐=major).
- `registry.json` 은 `name` 알파벳 순으로 정렬해 머지한다(스크립트가 처리).

## 4. version 가이드

초판은 `0.1.0` 으로 시작한다. 성숙·안정 후 `1.0.0`. 스킬 본문/스크립트가 바뀌면:

- 트리거 description 만 손봄 / 문구 정리 → patch
- 새 섹션·스크립트·기능 추가 → minor
- 사용법·인터페이스가 바뀌어 기존 사용자가 깨짐 → major
