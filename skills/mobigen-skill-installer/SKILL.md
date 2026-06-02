---
name: mobigen-skill-installer
description: graphio app 개발 중 로컬에 없는 사내 스킬·역량이 필요할 때 반드시 로드한다. graphio-app-skill-hub 레지스트리(registry.json)를 읽어 사용자의 need 를 각 스킬 description 과 매칭하고, shallow+sparse git clone 으로 해당 skills/이름 폴더를 현재 도구의 스킬 디렉터리(.claude/skills, --user 시 ~/.claude/skills)에 설치·갱신한다. 목록/검색·install·update 를 지원. '스킬 설치', '스킬 찾아줘', '스킬 받아', 'skillhub', '레지스트리에서', '사내 스킬 없네', 'graphio 스킬 깔아', 'skill install', 'skill update', '필요한 스킬 가져와' 같은 표현에서 사용. 단, 새 스킬을 만들어 hub 에 올리는 작업은 mobigen-skill-creator 를 쓰고, 이미 설치된 스킬의 기능 자체는 그 스킬을 쓴다. 모든 설명은 한국어로, 코드/식별자는 영어 그대로.
---

# Mobigen Skill Installer

사내 스킬 레지스트리 **graphio-app-skill-hub** 의 진입점. 사용자가 graphio app 개발 중 **로컬에 없는 역량**이 필요할 때, 레지스트리에서 맞는 스킬을 찾아 **현재 도구의 스킬 디렉터리에 설치**한다.

> **경계**: 이 스킬은 *기존 스킬을 찾아 설치/갱신*한다. *새 스킬을 만들어 hub 에 올리는* 작업은 `mobigen-skill-creator`. *이미 설치된 스킬의 기능*(예: 앱 개발)은 그 스킬(`graphio-app-dev` 등)이 한다.

---

## 0. 핵심 동작 (Claude 가 따르는 흐름)

사용자가 "X 하는 스킬 없어?" / "graphio 스킬 깔아줘" 류로 요청하거나, 작업 중 **필요한 역량이 로컬에 없다고 판단**되면:

1. **레지스트리를 읽는다** — `skillhub.py list --json` (또는 `--query`) 로 `registry.json` 을 가져온다.
2. **need 를 매칭한다** — 사용자의 작업/요청을 각 엔트리의 `description` 과 대조해 가장 맞는 스킬(들)을 고른다. 단순 키워드가 아니라 "무엇을 하려는가"로 판단한다.
3. **확인받는다** — 후보가 1개면 "이거 설치할까요?", 여러 개면 짧게 비교해 고르게 한다. (이미 설치돼 있으면 `update` 안내.)
4. **설치한다** — `skillhub.py install <name>` 으로 설치하고, 설치 위치를 알려준다. 새 스킬은 다음 요청부터 로드된다.

명시적으로 이름을 주면("graphio-app-test 설치") 2번을 건너뛰고 바로 설치한다.

---

## 1. 엔진: `scripts/skillhub.py`

레지스트리 읽기·설치·갱신을 담당하는 결정적 엔진. **git 만 있으면 동작**(외부 파이썬 의존성 없음). fetch 는 shallow + sparse git clone.

```bash
# 목록 / 검색
python3 scripts/skillhub.py list                  # 전체
python3 scripts/skillhub.py list --query 테스트     # name+description 부분일치
python3 scripts/skillhub.py list --domain graphio  # 도메인 필터
python3 scripts/skillhub.py list --json            # 매칭 로직용 기계 판독 출력

# 설치 (기본: 현재 프로젝트 .claude/skills/<name>/)
python3 scripts/skillhub.py install graphio-app-test
python3 scripts/skillhub.py install graphio-app-test --user    # 전역 ~/.claude/skills/<name>/
python3 scripts/skillhub.py install graphio-app-test --force   # 기존 덮어쓰기

# 갱신 (설치 시 남긴 .skillhub.json 마커의 version 과 레지스트리 version 비교)
python3 scripts/skillhub.py update graphio-app-test
python3 scripts/skillhub.py update --all                       # 설치된(마커 있는) 전체
```

설치하면 대상 폴더에 `.skillhub.json` 마커(`name`/`version`/`ref`/`repo`)를 남긴다. `update` 는 이 마커로 최신 여부를 판단한다.

---

## 2. 설치 경로

| 모드 | 위치 | 용도 |
|---|---|---|
| 기본 | `<cwd>/.claude/skills/<name>/` | 현재 프로젝트에만. 권장(작업 중인 곳에 스코프) |
| `--user` | `~/.claude/skills/<name>/` | 모든 프로젝트에서 전역 사용 |
| `--dir DIR` | `DIR/<name>/` | 명시적 위치(테스트·특수 환경) |

설치 후 새 스킬은 **다음 사용자 요청부터** 로드 목록에 잡힌다(현재 턴에서 즉시 활성화되지는 않음).

---

## 3. 소스 레포 / 브랜치(ref)

| 항목 | 기본값 | 오버라이드 |
|---|---|---|
| repo | `https://github.com/iris-graphio-apps/graphio-app-skill-hub` | `--repo` 또는 env `GRAPHIO_SKILLHUB_REPO` |
| ref | 원격 **기본 브랜치** 자동 감지 | `--ref` 또는 env `GRAPHIO_SKILLHUB_REF` |

> 스킬은 **ref 에 머지된 것만** 설치할 수 있다. 레지스트리에 엔트리가 있어도 해당 `path` 가 그 ref 에 없으면(머지 전) 설치가 실패한다 — 그땐 머지된 브랜치를 `--ref` 로 지정한다.

---

## 4. 매칭 가이드 (description → need)

`list --json` 결과의 각 `description` 은 "언제 쓰는지 + 언제 안 쓰는지"를 담고 있다. 매칭할 때:

- 사용자가 하려는 **작업의 동사/목표**에 집중한다(예: "앱을 테스트" → `graphio-app-test`, "재사용 노드 만들기" → `graphio-subagent-dev`).
- description 의 "단, … 대신 …" 문구로 **인접 스킬과의 경계**를 존중한다(잘못된 후보 배제).
- 애매하면 후보 2개를 짧게 제시하고 사용자가 고르게 한다. 임의로 여러 개를 한꺼번에 설치하지 않는다.

---

## 5. 자주 마주치는 문제

| 증상 | 원인 / 해결 |
|---|---|
| `registry.json 없음` / `SKILL.md 가 ref 에 없음` | 콘텐츠가 해당 ref 에 머지되기 전. `--ref <머지된 브랜치>` 지정 |
| `이미 존재` | 같은 스킬이 이미 설치됨. `update` 로 갱신하거나 `install --force` |
| `git 필요` | git 미설치. git 설치 후 재시도 |
| private repo 접근 실패 | 현재 hub 는 public. 향후 private 전환 시 git 인증(gh auth/credential) 필요 |
| 설치했는데 안 잡힘 | 새 스킬은 다음 요청부터 로드. 경로가 `.claude/skills/<name>/SKILL.md` 인지 확인 |

---

## 6. 참고

- 엔진: `scripts/skillhub.py` (`list` / `install` / `update`)
- 레지스트리 규약: hub 의 `registry.schema.json`, `skills/mobigen-skill-creator/references/registry-conventions.md`
- 새 스킬 저작·등록: `mobigen-skill-creator`
- 형제 스킬(설치 대상 예): `graphio-app-dev` / `graphio-subagent-dev` / `graphio-app-test`
