#!/usr/bin/env python3
"""mobigen-skill-installer 엔진 — graphio-app-skill-hub 레지스트리에서 스킬을 찾아 설치/갱신.

서브커맨드:
  list    [--query Q] [--domain D] [--group G] [--json]
  install <name> [--user | --dir DIR] [--force]
  update  [<name> | --all] [--user | --dir DIR] [--force]

공통 옵션: [--repo URL] [--ref BRANCH]
fetch 는 shallow + sparse git clone(블롭 필터). 외부 파이썬 의존성 없음(git 필요).
설치 시 대상 폴더에 .skillhub.json 마커(name/version/ref/repo)를 남겨 update 비교에 쓴다.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_REPO = os.environ.get(
    "GRAPHIO_SKILLHUB_REPO", "https://github.com/iris-graphio-apps/graphio-app-skill-hub"
)
MARKER = ".skillhub.json"


def fail(msg):
    print(f"[ERROR] {msg}")
    sys.exit(1)


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def default_ref(repo):
    """원격 HEAD 가 가리키는 기본 브랜치."""
    try:
        out = run(["git", "ls-remote", "--symref", repo, "HEAD"]).stdout
        for line in out.splitlines():
            if line.startswith("ref:"):
                return line.split()[1].rsplit("/", 1)[-1]
    except Exception:
        pass
    return "main"


def clone_hub(repo, ref, paths):
    """shallow+sparse clone → temp Path. paths: 체크아웃할 디렉터리(루트 파일은 cone 모드 기본 포함)."""
    tmp = Path(tempfile.mkdtemp(prefix="skillhub-"))
    try:
        run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
             "--branch", ref, repo, str(tmp)])
    except subprocess.CalledProcessError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        fail(f"clone 실패 (repo={repo}, ref={ref}):\n{e.stderr.strip()}")
    if paths:
        run(["git", "sparse-checkout", "set", *paths], cwd=str(tmp))
    return tmp


def read_registry(hub):
    reg = hub / "registry.json"
    if not reg.exists():
        fail("registry.json 없음 — 이 ref 에 콘텐츠가 머지됐는지 확인(--ref).")
    return json.loads(reg.read_text(encoding="utf-8"))


def find_entry(reg, name):
    for e in reg.get("skills", []):
        if e.get("name") == name:
            return e
    return None


def skills_base(args):
    if args.dir:
        return Path(args.dir)
    if getattr(args, "user", False):
        return Path.home() / ".claude" / "skills"
    return Path.cwd() / ".claude" / "skills"


def read_marker(base, name):
    m = base / name / MARKER
    if m.exists():
        try:
            return json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def install_one(entry, hub, base, force, ref, repo):
    name = entry["name"]
    src = hub / entry["path"]
    if not (src / "SKILL.md").is_file():
        fail(f"{entry['path']}/SKILL.md 가 ref '{ref}' 에 없음(머지 전일 수 있음).")
    dst = base / name
    if dst.exists():
        if not force:
            fail(f"이미 존재: {dst} (--force 로 덮어쓰기, 또는 update 사용)")
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    marker = {"name": name, "version": entry.get("version"), "ref": ref, "repo": repo}
    (dst / MARKER).write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] 설치: {name} v{entry.get('version')} → {dst}")


def cmd_list(args):
    hub = clone_hub(args.repo, args.ref, [])
    try:
        reg = read_registry(hub)
    finally:
        shutil.rmtree(hub, ignore_errors=True)
    q = (args.query or "").lower()
    items = []
    for e in reg.get("skills", []):
        if args.domain and e.get("domain") != args.domain:
            continue
        if args.group and e.get("group") != args.group:
            continue
        if q and q not in (e.get("name", "") + " " + e.get("description", "")).lower():
            continue
        items.append(e)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("(매칭되는 스킬 없음)")
        return
    for e in items:
        print(f"- {e['name']}  (v{e.get('version', '?')}, {e.get('domain')}/{e.get('group', '-')})")
        print(f"    {e.get('description', '')[:160]}")


def cmd_install(args):
    hub = clone_hub(args.repo, args.ref, ["skills/" + args.name])
    try:
        reg = read_registry(hub)
        entry = find_entry(reg, args.name)
        if not entry:
            fail(f"'{args.name}' 가 레지스트리에 없음. `list` 로 확인.")
        install_one(entry, hub, skills_base(args), args.force, args.ref, args.repo)
    finally:
        shutil.rmtree(hub, ignore_errors=True)


def cmd_update(args):
    base = skills_base(args)
    if args.all:
        names = sorted(p.name for p in base.glob("*") if (p / MARKER).exists())
        if not names:
            fail(f"{base} 에 설치된(마커 있는) 스킬 없음")
    else:
        if not args.name:
            fail("update 에는 <name> 또는 --all 필요")
        names = [args.name]
    hub = clone_hub(args.repo, args.ref, ["skills/" + n for n in names])
    try:
        reg = read_registry(hub)
        for n in names:
            entry = find_entry(reg, n)
            if not entry:
                print(f"[skip] {n}: 레지스트리에 없음")
                continue
            cur = read_marker(base, n)
            if cur and cur.get("version") == entry.get("version") and not args.force:
                print(f"[최신] {n}: v{entry.get('version')} (변경 없음)")
                continue
            install_one(entry, hub, base, True, args.ref, args.repo)
    finally:
        shutil.rmtree(hub, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(prog="skillhub", description="graphio-app-skill-hub 스킬 설치기")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--ref", default=os.environ.get("GRAPHIO_SKILLHUB_REF"),
                    help="브랜치/태그 (기본: 원격 기본 브랜치)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="레지스트리 목록/검색")
    pl.add_argument("--query")
    pl.add_argument("--domain")
    pl.add_argument("--group")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)

    pi = sub.add_parser("install", help="스킬 설치")
    pi.add_argument("name")
    g = pi.add_mutually_exclusive_group()
    g.add_argument("--user", action="store_true")
    g.add_argument("--dir")
    pi.add_argument("--force", action="store_true")
    pi.set_defaults(func=cmd_install)

    pu = sub.add_parser("update", help="설치된 스킬 갱신")
    pu.add_argument("name", nargs="?")
    pu.add_argument("--all", action="store_true")
    g2 = pu.add_mutually_exclusive_group()
    g2.add_argument("--user", action="store_true")
    g2.add_argument("--dir")
    pu.add_argument("--force", action="store_true")
    pu.set_defaults(func=cmd_update)

    args = ap.parse_args()
    if not shutil.which("git"):
        fail("git 필요 — git 설치 후 재시도")
    if not args.ref:
        args.ref = default_ref(args.repo)
    args.func(args)


if __name__ == "__main__":
    main()
