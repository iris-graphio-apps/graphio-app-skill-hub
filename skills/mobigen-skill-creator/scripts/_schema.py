"""mobigen-skill-creator 공유 코어.

회사 registry 스키마(references/registry.schema.json)를 **단일 진실원천**으로 읽어,
도메인 enum·패턴·길이 제약을 코드에 하드코딩하지 않고 스키마에서 끌어온다.
스키마에 표현 못 하는 두 가지 prose 규칙(name 이 domain prefix 로 시작 / path == skills/<name>)만
코드로 추가 검증한다.
"""
import json
import re
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "registry.schema.json"


def load_schema(path=None):
    return json.loads(Path(path or SCHEMA_PATH).read_text(encoding="utf-8"))


def _entry(schema):
    return schema["$defs"]["skillEntry"]


def _props(schema):
    return _entry(schema)["properties"]


def domains(schema=None):
    return list(_props(schema or load_schema())["domain"]["enum"])


def infer_domain(name, schema=None):
    """name 이 'mobigen-...' 처럼 승인 domain 으로 시작하면 그 domain 을 돌려준다.

    경계는 하이픈 또는 정확히 일치('agentic-x' 는 'agent' 에 매칭되지 않음). 가장 긴 후보 선택.
    """
    cands = [d for d in domains(schema) if name == d or name.startswith(d + "-")]
    return max(cands, key=len) if cands else None


def parse_frontmatter(skill_md):
    """SKILL.md 의 YAML frontmatter 를 dict 로. pyyaml 있으면 사용, 없으면 name/description regex 폴백."""
    text = Path(skill_md).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        raise ValueError(f"{skill_md}: '--- ... ---' frontmatter 가 없음")
    fm = m.group(1)
    try:
        import yaml

        data = yaml.safe_load(fm)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    out = {}
    for key in ("name", "description"):
        km = re.search(rf"^{key}:\s*(.*)$", fm, re.MULTILINE)
        if km:
            v = km.group(1).strip()
            if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
                v = v[1:-1]
            out[key] = v
    return out


def validate_entry(entry, schema=None):
    """단일 skillEntry 를 스키마 + prose 규칙으로 검증. (ok, [errors])."""
    schema = schema or load_schema()
    props = _props(schema)
    required = set(_entry(schema)["required"])
    allowed = set(props.keys())
    errs = []

    keys = set(entry.keys())
    for k in sorted(required - keys):
        errs.append(f"required '{k}' 누락")
    for k in sorted(keys - allowed):
        errs.append(f"허용되지 않은 키 '{k}'")

    def check_pattern(k):
        if k in entry and "pattern" in props[k]:
            if not re.match(props[k]["pattern"], str(entry[k])):
                errs.append(f"'{k}' 패턴 위반: {entry[k]!r}")

    name = entry.get("name", "")
    if "name" in entry:
        check_pattern("name")
        if len(name) > props["name"]["maxLength"]:
            errs.append(f"name 길이 초과(>{props['name']['maxLength']}): {len(name)}")
    if "description" in entry:
        d, dp = entry["description"], props["description"]
        if not (dp["minLength"] <= len(d) <= dp["maxLength"]):
            errs.append(f"description 길이 {len(d)} (허용 {dp['minLength']}–{dp['maxLength']})")
        if "<" in d or ">" in d:
            errs.append("description 에 꺾쇠(< >) 금지")
    if "domain" in entry and entry["domain"] not in props["domain"]["enum"]:
        errs.append(f"domain '{entry['domain']}' 화이트리스트 밖 (허용: {props['domain']['enum']})")
    check_pattern("version")
    check_pattern("path")
    check_pattern("group")

    # 스키마로 표현 못 하는 prose 규칙
    dom = entry.get("domain")
    if dom and name and not (name == dom or name.startswith(dom + "-")):
        errs.append(f"name 은 domain '{dom}' 를 prefix 로 시작해야 함")
    if "path" in entry and name and entry["path"] != f"skills/{name}":
        errs.append(f"path 는 'skills/{name}' 여야 함 (현재 {entry['path']!r})")
    return (not errs), errs


def validate_registry(obj, schema=None):
    """registry 전체를 검증. (ok, [errors]). jsonschema 없이도 동작하는 수동 미러."""
    schema = schema or load_schema()
    errs = []
    const = schema["properties"]["schemaVersion"]["const"]
    if obj.get("schemaVersion") != const:
        errs.append(f"schemaVersion 은 '{const}' 이어야 함 (현재 {obj.get('schemaVersion')!r})")
    extra = set(obj.keys()) - set(schema["properties"].keys())
    if extra:
        errs.append(f"루트에 허용되지 않은 키: {sorted(extra)}")
    if not isinstance(obj.get("skills"), list):
        errs.append("skills 는 배열이어야 함")
        return False, errs
    names = []
    for i, e in enumerate(obj["skills"]):
        ok, e_errs = validate_entry(e, schema)
        for m in e_errs:
            errs.append(f"skills[{i}] ({e.get('name', '?')}): {m}")
        names.append(e.get("name"))
    dupes = sorted({n for n in names if names.count(n) > 1 and n})
    if dupes:
        errs.append(f"name 전역 유일성 위반(중복): {dupes}")
    return (not errs), errs


def jsonschema_validate(obj, schema=None):
    """jsonschema(draft 2020-12) 설치 시 권위 검증. (ok|None, [errors], used:bool)."""
    schema = schema or load_schema()
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return None, ["jsonschema 미설치"], False
    errs = [
        f"{list(e.path)}: {e.message}"
        for e in sorted(Draft202012Validator(schema).iter_errors(obj), key=lambda e: list(e.path))
    ]
    return (not errs), errs, True
