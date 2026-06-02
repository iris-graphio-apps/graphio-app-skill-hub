---
name: mobigen-skill-creator
description: Mobigen company skill-hub 에 올릴 새 스킬을 만들·개선·등록할 때 반드시 로드한다. Claude 공식 skill-creator 방법론(progressive disclosure, pushy 한 description, 가벼운 테스트·반복)을 토대로, 회사 registry 스키마 규약(domain-prefix 네이밍, semver, path skills/이름, description 30–1024자·꺾쇠 금지·when-to와 when-not 포함)을 강제하고, 스캐폴드→작성→description 린트→registry.json 엔트리 생성·검증까지 한 흐름으로 안내한다. '스킬 만들어', 'skill 만들기', '스킬 등록', 'skill-hub', 'registry 엔트리', 'mobigen-skill-creator', '새 스킬 스캐폴드', 'description 최적화', '스킬 검증' 같은 표현에서 사용. 단, 기존 graphio 앱/노드 자체를 만드는 작업은 graphio-app-dev 나 graphio-subagent-dev 를 대신 쓴다. 모든 설명은 한국어로, 코드/식별자는 영어 그대로.
---

# Mobigen Skill Creator

회사 **skill-hub** 에 올릴 스킬을 만들고 등록하는 메타 스킬이다. Claude 공식 `skill-creator` 의 방법론(스킬을 잘 쓰는 법)에 **회사 레지스트리 컴플라이언스**(hub 규약대로 등록)를 더한 것이 핵심이다.

- **방법론** → [`references/skill-authoring.md`](references/skill-authoring.md) (공식 skill-creator 압축, Apache-2.0 기반)
- **레지스트리 규약** → [`references/registry-conventions.md`](references/registry-conventions.md)
- **정본 스키마** → [`references/registry.schema.json`](references/registry.schema.json) (스크립트의 단일 진실원천)

> **경계**: 이 스킬은 *스킬을 만들고 hub 에 등록*한다. *graphio 앱*을 만들면 `graphio-app-dev`, *재사용 노드(sub-agent)* 저작은 `graphio-subagent-dev`, *앱 테스트*는 `graphio-app-test` 를 쓴다.

---

## 0. 가장 자주 틀리는 것 (Quick Reference)

1. **name 이 domain prefix 로 시작 안 함** — 반드시 `mobigen-` / `graphio-` / `agent-` / `workflow-` / `data-` 중 하나로 시작. lowercase-hyphen, ≤64.
2. **description 에 꺾쇠 `< >`** — 금지. `skills/이름` 처럼 풀어 쓰거나 백틱으로.
3. **description 이 너무 짧거나(<30) 트리거가 약함** — 30–1024자, when-to + **when-not(형제 스킬로 보내기)** + 약간 pushy.
4. **`path`·`domain` 을 손으로 씀** — `registry_entry.py` 가 자동 계산(`skills/<name>`, prefix 추론)한다.
5. **등록을 빠뜨림** — SKILL.md 만 쓰고 끝내지 않는다. registry.json 엔트리 생성·검증까지가 "done".

---

## 1. 워크플로

공식 skill-creator 의 루프(intent → 작성 → 테스트 → 개선)를 따르되, 회사 hub 는 **가벼운 정성 테스트 + 레지스트리 등록**에 초점을 둔다.

1. **Intent 포착** — 무엇을 가능하게? 언제 트리거? 출력 형식? (자세히 → `references/skill-authoring.md` §1)
2. **스캐폴드** — `scaffold_skill.py <name>` 으로 compliant 한 SKILL.md 뼈대 생성.
3. **작성** — progressive disclosure 로 SKILL.md 본문 + (필요 시) `scripts/`·`references/`. description 은 트리거의 전부 — 공들여 쓴다.
4. **가벼운 테스트** — 실제 사용자가 말할 법한 프롬프트 2–3개로 스킬을 적용해 보고 사용자에게 결과를 확인. (무거운 벤치마크가 필요하면 §4 의 공식 skill-creator.)
5. **등록** — `lint_description.py` → `registry_entry.py --write` → `validate_registry.py`.

---

## 2. 번들 스크립트

모두 `scripts/` 에 있고, `references/registry.schema.json` 을 단일 진실원천으로 읽는다. (의존성 없음. `jsonschema` 가 설치돼 있으면 권위 검증도 함께 수행.)

| 스크립트 | 역할 |
|---|---|
| `scaffold_skill.py <name> [--hub-root DIR] [--desc T]` | hub 규약대로 `skills/<name>/SKILL.md` 뼈대 생성. name 규약·domain prefix 자동 검증 |
| `lint_description.py <skill-dir>` | description 하드 규칙(30–1024, 꺾쇠 금지) + 트리거 품질(when-to/when-not/pushy/구체 토큰) 점검 |
| `registry_entry.py <skill-dir> --version X.Y.Z [--group G] [--registry R --write]` | SKILL.md → 엔트리 생성(`domain`·`path` 자동) → registry.json 병합·검증 |
| `validate_registry.py [registry.json]` | registry 전체를 스키마에 대조 검증 |

### 만들기 → 등록 (한 흐름)

```bash
S=.claude/skills/mobigen-skill-creator/scripts      # 이 스킬의 scripts 경로
HUB=/path/to/company-skills                         # skills/ 와 registry.json 이 있는 hub 루트

python $S/scaffold_skill.py mobigen-foo --hub-root $HUB
#  → $HUB/skills/mobigen-foo/SKILL.md 생성. description·본문을 채운다.

python $S/lint_description.py $HUB/skills/mobigen-foo
#  → 길이·꺾쇠(하드) + when-to/when-not/pushy(소프트) 점검

python $S/registry_entry.py $HUB/skills/mobigen-foo --version 0.1.0 \
       --registry $HUB/registry.json --write
#  → 엔트리 생성·병합(같은 name 교체)·검증·기록

python $S/validate_registry.py $HUB/registry.json
#  → 전체 재검증 (VALID ✓)
```

---

## 3. 레지스트리 규약 (요약)

자세한 규칙·예시는 [`references/registry-conventions.md`](references/registry-conventions.md). 핵심만:

| 필드 | 규칙 |
|---|---|
| `name` | 전역 유일, lowercase-hyphen, ≤64, **domain prefix 로 시작** |
| `description` | 30–1024자, **꺾쇠 금지**, when-to + when-not, 약간 pushy |
| `domain` | `mobigen` / `graphio` / `agent` / `workflow` / `data` (enum) |
| `group` | 선택. name 에 넣지 말고 여기에만 |
| `version` | semver. 초판 0.1.0 |
| `path` | 항상 `skills/<name>` |

hub 는 평면 구조 — 스킬 폴더는 `skills/<name>/`, 엔트리는 모두 `registry.json` 한 곳.

---

## 4. 언제 공식 skill-creator 를 쓰나

이 스킬은 자립적으로 동작하며 **가벼운 정성 테스트 + 등록**에 초점을 둔다. 다음이 필요하면 설치된 공식 `skill-creator`(Anthropic, Apache-2.0)를 직접 쓴다:

- subagent 기반 **정량 벤치마크**(with-skill vs baseline, eval-viewer)
- **description 트리거 최적화 loop**(`run_loop.py` — 20개 트리거 eval 로 자동 반복)
- `.skill` 파일 **패키징**(`package_skill.py`) — 단, hub 배포는 `.skill` 이 아니라 `skills/<name>/` 폴더 + registry 엔트리다.

본 스킬의 방법론 요약(`references/skill-authoring.md`)은 그 공식 스킬을 토대로 재구성했다.

---

## 5. 기존 스킬 갱신

기존 스킬을 고칠 때:

- **name 보존** — 디렉터리명과 `name` frontmatter 를 그대로 둔다.
- `version` 을 semver 로 올린다(patch/minor/major — `references/registry-conventions.md` §4).
- 다시 `lint_description.py` → `registry_entry.py --write`(같은 name 이면 자동 교체) → `validate_registry.py`.

---

## 6. 참고

- 방법론: [`references/skill-authoring.md`](references/skill-authoring.md)
- 레지스트리 규약: [`references/registry-conventions.md`](references/registry-conventions.md)
- 정본 스키마: [`references/registry.schema.json`](references/registry.schema.json)
- 형제 스킬: `graphio-app-dev`(앱 개발) / `graphio-subagent-dev`(노드 저작) / `graphio-app-test`(앱 테스트)
- 토대: Anthropic 공식 `skill-creator` (Apache-2.0)
