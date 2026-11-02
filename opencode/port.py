#!/usr/bin/env python3
"""Install claude-seo into an OpenCode configuration.

OpenCode 2.x discovers skills from ``<config>/skills/<id>/SKILL.md`` and agents
from ``<config>/agents/<id>.md``. claude-seo already ships Claude Code skills in
the same ``SKILL.md`` format, so this port only has to:

* copy the core and extension skills into the OpenCode config,
* copy the shared Python runtime into ``skills/seo/``,
* convert agent frontmatter from Claude Code to OpenCode 2 fields,
* rewrite ``${CLAUDE_PLUGIN_ROOT}`` to the installed path, and
* create a ``/seo`` command.

Run it through ``opencode/install.sh``; direct use is supported for packagers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = Path(
    os.environ.get(
        "OPENCODE_CONFIG_DIR",
        str(Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "opencode"),
    )
)
SEO_SKILL_RE = re.compile(r"^seo($|-)")
AGENT_DROP_RE = re.compile(r"^(name|model|tools|maxSteps)\s*:")
MAX_TURNS_RE = re.compile(r"^maxTurns\s*:\s*(\d+)")


def say(message: str) -> None:
    print(message, flush=True)


def remove_previous(dest: Path) -> None:
    """Remove only a previous claude-seo install, never unrelated user files."""
    skills = dest / "skills"
    if skills.is_dir():
        for entry in skills.iterdir():
            if not entry.is_dir() or not SEO_SKILL_RE.match(entry.name):
                continue
            # Preserve the isolated Python environment and its browser cache
            # across reinstalls. The runtime's own state file decides whether
            # the environment still matches the requirements; a stale env is
            # rebuilt by `claude-seo setup`.
            keep = {".venv", "runtime-state.json", "ms-playwright"}
            if entry.name == "seo" and (entry / ".venv").is_dir():
                for child in entry.iterdir():
                    if child.name in keep:
                        continue
                    if child.is_dir() and not child.is_symlink():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
            else:
                shutil.rmtree(entry)
    agents = dest / "agents"
    if agents.is_dir():
        for entry in agents.glob("seo-*.md"):
            entry.unlink()
    command = dest / "commands" / "seo.md"
    if command.exists():
        command.unlink()


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    return text[3:end], text[end + 4:]


def convert_agent(text: str) -> str:
    """Convert Claude Code agent frontmatter to OpenCode 2 agent frontmatter.

    OpenCode reads the Markdown body as the agent's system prompt. It derives
    the agent id from the filename and expects ``mode``/``steps`` rather than
    Claude's ``model``/``maxTurns``/``tools`` fields.
    """
    frontmatter, body = split_frontmatter(text)
    out: list[str] = []
    steps: int | None = None
    for line in frontmatter.splitlines():
        match = MAX_TURNS_RE.match(line)
        if match:
            steps = int(match.group(1))
            continue
        if AGENT_DROP_RE.match(line):
            continue
        out.append(line)
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    if not any(line.startswith("description:") for line in out):
        out.insert(0, "description: SEO subagent")
    out.append("mode: subagent")
    if steps is not None:
        out.append(f"steps: {steps}")
    return "---\n" + "\n".join(out) + "\n---\n\n" + body.lstrip("\n")


def rewrite_text(text: str, dest: Path) -> str:
    skills_root = dest / "skills"
    seo_root = skills_root / "seo"
    text = text.replace("${CLAUDE_PLUGIN_ROOT}/skills/", str(skills_root) + "/")
    text = text.replace(
        "${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo",
        str(seo_root) + "/scripts/claude-seo",
    )
    text = text.replace("${CLAUDE_PLUGIN_ROOT}", str(seo_root))
    text = text.replace("$HOME/.claude/skills", str(skills_root))
    text = text.replace("~/.claude/skills", str(skills_root))
    return text


def rewrite_markdown(root: Path, dest: Path) -> int:
    changed = 0
    for path in root.rglob("*.md"):
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated = rewrite_text(original, dest)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def chmod_executables(seo_root: Path) -> None:
    for path in seo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix in {".sh", ".py"} or path.name == "claude-seo":
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install(dest: Path, with_extensions: bool, dry_run: bool) -> dict[str, object]:
    skills_dir = dest / "skills"
    agents_dir = dest / "agents"
    commands_dir = dest / "commands"
    seo_root = skills_dir / "seo"
    summary: dict[str, object] = {
        "dest": str(dest),
        "dry_run": dry_run,
        "skills": [],
        "agents": [],
        "extensions": [],
    }

    if not REPO_ROOT.joinpath("skills", "seo", "SKILL.md").is_file():
        raise SystemExit(f"error: {REPO_ROOT} does not look like the claude-seo repo")

    if dry_run:
        skills = {p.name for p in (REPO_ROOT / "skills").iterdir() if p.is_dir()}
        agents = {p.stem for p in (REPO_ROOT / "agents").glob("*.md")}
        extensions: list[str] = []
        if with_extensions:
            for extension in sorted(p for p in (REPO_ROOT / "extensions").iterdir() if p.is_dir()):
                extensions.append(extension.name)
                if (extension / "skills").is_dir():
                    skills.update(p.name for p in (extension / "skills").iterdir() if p.is_dir())
                if (extension / "agents").is_dir():
                    agents.update(p.stem for p in (extension / "agents").glob("*.md"))
        summary["skills"] = sorted(skills)
        summary["agents"] = sorted(agents)
        summary["extensions"] = extensions
        return summary

    for directory in (skills_dir, agents_dir, commands_dir):
        directory.mkdir(parents=True, exist_ok=True)

    remove_previous(dest)

    # 1. Core skills
    core_names: list[str] = []
    for skill in sorted(p for p in (REPO_ROOT / "skills").iterdir() if p.is_dir()):
        copy_tree(skill, skills_dir / skill.name)
        core_names.append(skill.name)

    # 2. Shared runtime for the orchestrator skill
    for name in ("scripts", "schema", "data", "hooks"):
        source = REPO_ROOT / name
        if source.is_dir():
            copy_tree(source, seo_root / name)
    for name in ("requirements.txt", "pyproject.toml"):
        if (REPO_ROOT / name).is_file():
            shutil.copy2(REPO_ROOT / name, seo_root / name)
    shutil.copy2(REPO_ROOT / ".claude-plugin" / "plugin.json", seo_root / "runtime-plugin.json")

    # 3. Core agents, converted to OpenCode 2 format
    agent_names: list[str] = []
    for agent in sorted((REPO_ROOT / "agents").glob("*.md")):
        text = convert_agent(agent.read_text(encoding="utf-8"))
        (agents_dir / agent.name).write_text(rewrite_text(text, dest), encoding="utf-8")
        agent_names.append(agent.stem)

    # 4. Optional extensions. They may override a core skill or agent with the
    #    same name (upstream install.sh has the same ordering).
    extension_names: list[str] = []
    if with_extensions:
        for extension in sorted(p for p in (REPO_ROOT / "extensions").iterdir() if p.is_dir()):
            extension_names.append(extension.name)
            skills = extension / "skills"
            if skills.is_dir():
                for skill in sorted(p for p in skills.iterdir() if p.is_dir()):
                    copy_tree(skill, skills_dir / skill.name)
            agents = extension / "agents"
            if agents.is_dir():
                for agent in sorted(agents.glob("*.md")):
                    text = convert_agent(agent.read_text(encoding="utf-8"))
                    (agents_dir / agent.name).write_text(rewrite_text(text, dest), encoding="utf-8")
            for sub in ("references", "scripts"):
                if (extension / sub).is_dir():
                    copy_tree(extension / sub, seo_root / "extensions" / extension.name / sub)

    # 5. Rewrite model-visible paths
    rewritten = 0
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if SEO_SKILL_RE.match(skill.name):
            rewritten += rewrite_markdown(skill, dest)
    for agent in sorted(agents_dir.glob("seo-*.md")):
        original = agent.read_text(encoding="utf-8")
        updated = rewrite_text(original, dest)
        if updated != original:
            agent.write_text(updated, encoding="utf-8")
            rewritten += 1

    chmod_executables(seo_root)

    # 6. /seo command
    (commands_dir / "seo.md").write_text(
        "---\n"
        "description: Run claude-seo (audit, page, technical, schema, sitemap, geo, etc.)\n"
        "---\n\n"
        "Load the `seo` skill with the `skill` tool, then execute this request exactly\n"
        "as the skill documents it. Pass the command and URL/topic through unchanged.\n\n"
        "$ARGUMENTS\n",
        encoding="utf-8",
    )

    summary["skills"] = sorted(
        p.name for p in skills_dir.iterdir()
        if p.is_dir() and SEO_SKILL_RE.match(p.name) and (p / "SKILL.md").is_file()
    )
    summary["agents"] = sorted(p.stem for p in agents_dir.glob("seo-*.md"))
    summary["extensions"] = extension_names
    summary["markdown_files_rewritten"] = rewritten
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install claude-seo into OpenCode")
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"OpenCode config directory (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--no-extensions",
        action="store_true",
        help="skip optional extension skills/agents",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be installed without writing anything",
    )
    parser.add_argument("--json", action="store_true", help="print a JSON summary")
    args = parser.parse_args(argv)

    dest = args.dest.expanduser().resolve()
    summary = install(dest, with_extensions=not args.no_extensions, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        verb = "Would install" if args.dry_run else "Installed"
        say(f"{verb} into {summary['dest']}")
        say(f"  skills: {len(summary['skills'])}")
        say(f"  agents: {len(summary['agents'])}")
        if summary.get("extensions"):
            say(f"  extensions: {', '.join(summary['extensions'])}")
        if not args.dry_run:
            say(f"  markdown files rewritten: {summary.get('markdown_files_rewritten', 0)}")
            say("  command: /seo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
