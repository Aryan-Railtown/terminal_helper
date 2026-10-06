# Sage — Terminal Helper for windows

A terminal helper agent for Windows, built on [railtracks](https://docs.railtracks.org). Ask it anything from your shell:

```powershell
sage how do I find what is using port 3000
sage is git installed and what version
sage "what's in `$env:PATH?"
sage and only the ones under Program Files   # follow-ups use recent context
sage "why is git telling me my branch has diverged?"
sage "what did I just break?"                # looks at recent commands + git state
npm run build 2>&1 | sage explain this error # pipe output in
sage .                                       # what is this folder / how do I run it
```
## Demo — what it looks like 
![Demo](demo.png)

## Modes

| Command | What it does |
|---|---|
| `sage <question>` | Ask anything; quotes optional. |
| `sage .` | Overview of the current directory: project type, key files, how to build/run/test. |
| `... \| sage [question]` | Explains piped output. With no question it defaults to "explain this / fix the error". |
| `sage --model sonnet ...` | Use another model for one call. Aliases: `sonnet`, `opus`, `haiku`, `fable`, `flash-lite`. Also accepts any id (`claude-…`, `gemini-…`, `gpt-…`) or `provider:id`. |
| `sage --model sonnet` | With no question, shows what the alias resolves to and whether its key is set. |
| `sage --debug ...` | Logs each tool call to stderr, prints tracebacks, keeps railtracks run logs in `~/.sage/.railtracks`. |
| `sage --debug` | With no question, prints diagnostics: config, model, key status, shell, history. |
| `sage --tools` | Lists the tools sage can use, and which ones ask first. |
| `sage --plain ...` | Prints raw text instead of live-rendered markdown (automatic when output is piped). |
| `sage --new` | Forgets the recent conversation. |

sage knows which shell you're in (PowerShell 7, Windows PowerShell, cmd or Git Bash) and your current directory, and answers in that shell's syntax.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```powershell
git clone <this repo>; cd terminal_helper
uv tool install -e .
```

Then add a key. The default model is Gemini Flash-Lite, which has a free tier ([get a key](https://aistudio.google.com/apikey)):

```powershell
mkdir ~/.sage -Force; Add-Content ~/.sage/.env "GEMINI_API_KEY=your-key"
```

## Swapping models

Create `~/.sage/config.toml`:

```toml
provider = "gemini"          # gemini | anthropic | openai | openai_compatible
model = "gemini-3.1-flash-lite"
# api_base = "http://localhost:11434/v1"   # for openai_compatible (e.g. Ollama)
# history_turns = 6
# history_ttl_minutes = 30
```

Keys are read from `~/.sage/.env` or your environment: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. To try a model once, run `sage --model <id> ...`.

## Safety model

- **Read-only tools run freely:** environment info, directory listing, reading text files, `which`, command help, git status/log/diff stats, and your recent shell commands.
- **Shell history is sent to the model** when sage uses `recent_commands` (PowerShell's PSReadLine history or `~/.bash_history`). Obvious secrets (`*_KEY=`, `token:`, `sk-…`) are redacted, but don't count on that for everything.
- **Running a command always asks first.** sage shows the exact command and why, then waits for `y`. Anything else declines. With no interactive console it always declines.
- **A small denylist** (format, diskpart, `reg delete`, shutdown, `rm -rf /`, …) is refused even if you say yes.

## Usage notes

- `sage --new` forgets the recent conversation. History expires after 30 minutes anyway.
- In PowerShell, quote questions containing `$`, `?`, `|`, `;`, `(` or `&`, e.g. `sage "why does $x | foo fail?"`.
- `--debug` (or `SAGE_DEBUG=1`) keeps railtracks run logs in `~/.sage/.railtracks`; view them with `railtracks viz` from `~/.sage`.

## Development

```powershell
uv sync
uv run pytest                 # offline unit tests
uv run pytest -m live         # real-model checks; needs a key. Pick the model with SAGE_LIVE_MODEL=sonnet
```
