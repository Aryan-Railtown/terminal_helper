# Sage — Terminal Helper for Windows and macOS

**sage is not another terminal chatbot.** Think of it as a **local context engine with an agent attached**. Its value comes from what it knows about *your* machine at the moment you ask: which shell you're in, which folder, what git says, which commands you just ran, and the error you just piped into it. Only after gathering that context does a model reason over it.

So `sage why did that fail?` isn't answered from generic knowledge. sage looks at your actual shell history and repo state first, then answers in your shell's syntax (PowerShell, cmd or Git Bash on Windows; zsh, bash or fish on macOS and Linux).

### The pieces

| Piece | What it does | Where |
|---|---|---|
| **Context engine** | Detects your shell and current folder, reads piped output, and has read-only tools for files, `which`, command help, git status/log/diff, and your recent shell history (with secrets redacted). It gathers facts instead of guessing. | `shell.py`, `tools.py`, `cli.py` |
| **Agent** | A Railtracks `agent_node` that decides which context to pull, then answers concisely, streamed live as markdown. Short follow-ups reuse recent turns. | `agent.py`, `render.py`, `history.py` |
| **Gated actions** | The one tool that changes things, `run_command`, sits behind a Railtracks `pre_verifier` (`user_approval`). You see the exact command and approve with y/N; destructive commands are refused outright. | `verifiers.py` |
| **Observability** | Every run, including each tool call and each approve or decline, is logged locally and browsable in the Railtracks visualizer. | `~/.sage/.railtracks` |
| **Bring your own model** | Gemini (free tier) by default; OpenAI, Claude or a local Ollama model with a one-line config change. | `config.py` |

Built with [Railtracks](https://docs.railtracks.org) **1.5.6** (`railtracks==1.5.6`). Runs locally on a laptop; the only thing you need is a model API key, and Gemini's free tier works.

## Quick start (about 2 minutes)

You need git and an API key. You don't need Python: the installer sets up [uv](https://docs.astral.sh/uv/), which fetches Python for you. sage is tested on Windows, macOS and Linux in CI.

**Windows** (PowerShell):

```powershell
git clone https://github.com/Aryan-Railtown/terminal_helper.git
cd terminal_helper
powershell -ExecutionPolicy Bypass -File .\install.ps1
notepad $HOME\.sage\.env      # paste your key after GEMINI_API_KEY=  (free key: https://aistudio.google.com/apikey)
```

**macOS / Linux** (Terminal):

```bash
git clone https://github.com/Aryan-Railtown/terminal_helper.git
cd terminal_helper
./install.sh
open -e ~/.sage/.env          # macOS; on Linux use your editor. Paste your key after GEMINI_API_KEY=
```

Then open a **new** terminal:

```bash
sage --debug                    # checks setup: model, key found, shell detected
sage how do I find what is using port 3000
```

The installer is safe to re-run; it upgrades sage and never overwrites your `.env` or config.

## Examples

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

### Visualizer
![Observability](viz.png)
## Modes

| Command | What it does |
|---|---|
| `sage <question>` | Ask anything; quotes optional. |
| `sage .` | Overview of the current directory: project type, key files, how to build/run/test. |
| `... \| sage [question]` | Explains piped output. With no question it defaults to "explain this / fix the error". |
| `sage --model sonnet ...` | Use another model for one call. Aliases: `sonnet`, `opus`, `haiku`, `fable`, `flash-lite`. Also accepts any id (`claude-…`, `gemini-…`, `gpt-…`) or `provider:id`. |
| `sage --model sonnet` | With no question, shows what the alias resolves to and whether its key is set. |
| `sage --debug ...` | Logs each tool call to stderr and prints tracebacks. |
| `sage --debug` | With no question, prints diagnostics: config, model, key status, shell, history. |
| `sage --tools` | Lists the tools sage can use, and which ones ask first. |
| `sage --plain ...` | Prints raw text instead of live-rendered markdown (automatic when output is piped). |
| `sage --new` | Forgets the recent conversation. |

sage knows which shell you're in (PowerShell 7, Windows PowerShell, cmd and Git Bash on Windows; zsh, bash, fish and pwsh on macOS/Linux) and your current directory, and answers in that shell's syntax. On macOS it knows the BSD tool flavours (`lsof -i :PORT`, `sed -i ''`, `pbcopy`, `brew`).

## Manual install

If you already have [uv](https://docs.astral.sh/uv/):

```powershell
uv tool install .               # from the repo folder; puts `sage` on your PATH
uv tool update-shell            # first time only, then open a new terminal
mkdir $HOME\.sage -Force
copy .env.example $HOME\.sage\.env
copy config.example.toml $HOME\.sage\config.toml
```

With plain pip (Python 3.11+): `pip install .` installs the same `sage` command. Exact dependency versions are pinned in `uv.lock` and `requirements.txt`.

**Configuration** lives in `~/.sage/` (`%USERPROFILE%\.sage\` on Windows):

| File | Purpose | Template |
|---|---|---|
| `.env` | API keys (only the one for your provider is needed) | [`.env.example`](.env.example) |
| `config.toml` | provider, model, history settings | [`config.example.toml`](config.example.toml) |

**Uninstall:** `uv tool uninstall terminal-helper`, then delete `~/.sage`.

## Swapping models

Edit `~/.sage/config.toml`; it has ready-made blocks for Gemini, OpenAI, Claude and local Ollama. Uncomment one:

```toml
provider = "gemini"          # gemini | anthropic | openai | openai_compatible
model = "gemini-3.1-flash-lite"
```

Keys are read from `~/.sage/.env` or your environment: `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. To try a model once, run `sage --model <id> ...`.

## Safety model

- **Read-only tools run freely:** environment info, directory listing, reading text files, `which`, command help, git status/log/diff stats, and your recent shell commands.
- **Shell history is sent to the model** when sage uses `recent_commands` (PowerShell's PSReadLine history, `~/.zsh_history`, `~/.bash_history` or fish's history). Obvious secrets (`*_KEY=`, `token:`, `sk-…`) are redacted, but don't count on that for everything.
- **Running a command always asks first.** `run_command` is gated by a Railtracks [`pre_verifier`](https://docs.railtracks.org/documentation/agent_design/middleware/verifiers/overview/) named `user_approval`. sage shows the exact command and why, then waits for `y`; anything else declines, and with no interactive console it always declines. On a decline the command never runs, and the model is told why so it gives the command as advice instead. Every approve or decline is recorded in the run logs, so you can see it in `railtracks viz`.
- **A small denylist** (format, diskpart, `reg delete`, shutdown, `rm -rf /`, …) is refused even if you say yes.

## Usage notes

- `sage --new` forgets the recent conversation. History expires after 30 minutes anyway.
- Quote questions with special characters. In PowerShell that means `$`, `?`, `|`, `;`, `(` and `&`, e.g. `sage "why does $x | foo fail?"`. In zsh, `?` and `*` are globs (`zsh: no matches found`), so use `sage "what did I just break?"`.
- **zsh users:** zsh writes history to disk only when a shell exits, so `recent_commands` may not see commands from your current session. Add `setopt INC_APPEND_HISTORY` to `~/.zshrc` to write each command immediately.

## Viewing runs (Railtracks visualizer)

Every sage run is logged by Railtracks to `~/.sage/.railtracks`, no matter which terminal or folder you ran it from. That's about 80 KB per question. The logs hold your questions and tool output, and they never leave your machine. To browse them, run this from the project folder:

```powershell
uv run railtracks viz --beta      # then open http://localhost:3031
```

This works because the installer (`install.ps1` or `install.sh`) adds one line to the project's gitignored `.env`, pointing the visualizer at sage's logs instead of the project folder:

```
RAILTRACKS_HOME=/full/path/to/your/home/.sage
```

If you installed manually, add that line yourself. To turn logging off, set `RAILTRACKS_DISABLE_EVENTS=True`.

## Development

```powershell
uv sync
uv run pytest                 # offline unit tests
uv run pytest -m live         # real-model checks; needs a key. Pick the model with SAGE_LIVE_MODEL=sonnet
```

## License

[MIT](LICENSE)
