# claude-seo for OpenCode

This directory ports the Claude Code plugin to **[OpenCode](https://opencode.ai) 2.x**.
It keeps the repository as the single source of truth: skills, agent prompts,
scripts, schema templates and data stay in their normal locations, and the
installer generates the OpenCode layout at install time.

Tested against **OpenCode 2.2.0** on Linux with Python 3.14.

## What gets installed

OpenCode discovers global skills in `~/.config/opencode/skills/<id>/SKILL.md`
and global agents in `~/.config/opencode/agents/<id>.md`. The installer writes:

| Item | Location | Count |
|---|---|---|
| Skills (core + extension) | `~/.config/opencode/skills/seo*` | 33 |
| Agents (converted to OpenCode 2) | `~/.config/opencode/agents/seo-*.md` | 20 |
| `/seo` command | `~/.config/opencode/commands/seo.md` | 1 |
| Python runtime | `~/.config/opencode/skills/seo/{scripts,schema,data,hooks,.venv}` | — |

No `opencode.json` change is required. Use `OPENCODE_CONFIG_DIR` or `--dest` if
your OpenCode config lives elsewhere.

## Requirements

- OpenCode 2.x
- Python 3.11 to 3.14
- `git` (to clone this repository)
- Optional: a headless Chromium, downloaded by the runtime setup. Skip it with
  `--skip-browser` if you only need source-level analysis.

## Install

```bash
git clone --depth 1 https://github.com/arnavpadwal/claude-seo.git
bash claude-seo/opencode/install.sh
```

Then reload OpenCode and run:

```text
/seo audit https://example.com
```

### Options

```bash
bash opencode/install.sh --skip-browser   # core runtime, no Chromium
bash opencode/install.sh --no-setup       # copy files only; run setup later
bash opencode/install.sh --no-extensions  # core skills/agents only
bash opencode/install.sh --dest DIR       # custom OpenCode config directory
bash opencode/install.sh --dry-run        # print the plan, change nothing
```

`--no-setup` is useful for packaging. Run setup afterwards with:

```bash
"${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/seo/scripts/claude-seo" setup
```

## Usage

The `/seo` command is a thin wrapper that loads the `seo` skill and passes the
arguments through. Every Claude Code command has an OpenCode equivalent:

```text
/seo audit https://example.com
/seo page https://example.com/pricing
/seo technical https://example.com
/seo schema https://example.com
/seo geo https://example.com
/seo local https://example.com
```

You can also mention `@seo` in a prompt, or let the model select a sub-skill by
description. The specialist agents (`seo-technical`, `seo-schema`, `seo-geo`,
…) are registered as OpenCode subagents and can be launched by name.

## How the port works

`opencode/port.py` does five things:

1. Copies `skills/*` into the OpenCode skills directory.
2. Copies the shared runtime (`scripts/`, `schema/`, `data/`, `requirements.txt`)
   into `skills/seo/` so every sub-skill uses one launcher.
3. Converts agent frontmatter:
   - removes Claude-only `name`, `model`, `tools` and `maxTurns`
   - adds `mode: subagent`
   - maps `maxTurns` to OpenCode's `steps`
   - keeps the Markdown body as the agent system prompt
4. Rewrites `${CLAUDE_PLUGIN_ROOT}` to the installed absolute path in every
   model-visible Markdown file.
5. Writes the `/seo` command.

The installer is idempotent. It only removes and replaces entries that match
`seo`, `seo-*`, or `seo-*.md`; other skills and agents are left alone.

## Differences from the Claude Code plugin

- **Hooks.** The upstream `PostToolUse` schema validator is not installed. Its
  Claude Code hook contract does not map one-to-one onto OpenCode 2. The
  validator and its launcher are still copied to `skills/seo/hooks/` if you
  want to wire them into a custom OpenCode plugin.
- **Model selection.** Upstream agents request Claude `sonnet`/`opus`. The
  OpenCode agents omit `model`, so a subagent inherits the parent session's
  model. Add a `model: provider/model#variant` line to an agent file if you
  want to pin one.
- **Tool permissions.** Upstream agents list Claude tool names. The OpenCode
  agents inherit the parent's permissions instead of translating those names.
- **Commands.** Claude Code maps `/seo` to the skill; OpenCode uses
  `commands/seo.md`. Command syntax is the same.

## Optional extensions

The extension skills are installed, but each one needs its own MCP server or
credentials before it can return live data:

| Extension | Needs |
|---|---|
| DataForSEO | DataForSEO MCP server + account |
| Firecrawl | Firecrawl MCP server + API key |
| Ahrefs | Ahrefs MCP server + API key |
| Matomo | Matomo URL + token |
| Profound | Profound MCP/API access |
| SE Ranking | SE Ranking API key |
| Bing Webmaster | Bing Webmaster API key |
| Unlighthouse | Local Node/npm (no account) |
| Banana / image-gen | `nanobanana-mcp` + Gemini key |

Google Search Console, CrUX, PageSpeed and GA4 skills need Google credentials;
run the relevant `/seo google` setup flow. Everything else works without any
paid service.

## Runtime checks

```bash
LAUNCHER="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/seo/scripts/claude-seo"
"$LAUNCHER" doctor --json
```

A healthy install reports `"ready": true` and `"browser_ready": true` (or
`false` if you used `--skip-browser`). Re-run `"$LAUNCHER" setup` to rebuild the
isolated environment. The runtime never installs into the system Python.

## Uninstall

```bash
bash opencode/uninstall.sh          # asks for confirmation
bash opencode/uninstall.sh --yes    # no prompt
```

This removes only `skills/seo`, `skills/seo-*`, `agents/seo-*.md` and
`commands/seo.md`. The Python environment lives under `skills/seo/.venv`, so it
is removed with the skill.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Skills do not appear | Reload OpenCode (`/reload`) or restart it. Check the path is `~/.config/opencode/skills`. |
| `ready: false` | Run the launcher's `setup` command; confirm Python is 3.11–3.14. |
| `Permission denied` on the launcher | `chmod +x skills/seo/scripts/claude-seo`; the installer normally does this. |
| Extension skill says the MCP server is missing | Configure that extension's MCP server in `opencode.json`. |
| `/seo` command missing | Confirm `~/.config/opencode/commands/seo.md` exists and reload. |

## License

MIT. The port keeps the upstream copyright and license notice. See
[`LICENSE`](../LICENSE).
