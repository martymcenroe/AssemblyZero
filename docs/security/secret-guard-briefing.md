# Secret Guard: Credential Leak Prevention for AI Coding Agents

## The Threat Model

When an AI coding agent (Claude Code, Cursor, Copilot Workspace, etc.) executes shell commands, every byte of stdout and stderr is captured in a plaintext session transcript. This transcript is stored locally and transmitted to the model provider's API. Any credential that touches stdout is:

1. **Persisted to disk** in the session transcript (plaintext JSON)
2. **Transmitted over the wire** to the AI provider's API endpoint
3. **Potentially logged** in the provider's infrastructure
4. **Irrevocable** — you cannot un-send it; the only remediation is rotation

The agent itself is not malicious. The problem is that agents routinely run commands to "check" things, and many CLI tools have built-in "print my credential" subcommands that the agent doesn't recognize as dangerous. The agent is trying to be helpful. The transcript is the attack surface.

## Architecture

### Interception Point

Claude Code supports `PreToolUse` hooks — shell scripts that run before every tool invocation. The hook receives the proposed command in `$CLAUDE_TOOL_INPUT_COMMAND` and can block it by exiting non-zero.

```
User prompt
    |
    v
Claude decides to run: "gh auth token"
    |
    v
PreToolUse hook fires (secret-guard.sh)
    |
    +--> Pattern match? YES --> exit 1 (BLOCKED, command never executes)
    |
    +--> Pattern match? NO  --> exit 0 (command proceeds normally)
```

The hook is configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/secret-guard.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### What the Hook Does NOT Cover

- **Read tool**: Claude Code's built-in file reader bypasses Bash entirely. The hook cannot intercept `Read(".env")`. This is handled by CLAUDE.md instructions that tell the model never to read secret files. (Defense-in-depth gap — the model must cooperate here.)
- **Write tool**: If the agent writes a script that dumps credentials and then runs it, the hook sees the `python script.py` command, not the credential dump inside the script. (Partial mitigation: Category C catches `$SECRET_VAR` in the command string, but not in a Python subprocess.)
- **MCP tools**: If a Model Context Protocol server provides a tool that returns credentials, the hook has no visibility. MCP servers must implement their own guards.

---

## Category Inventory (What We Block Today)

### Category A: Secret File Reads

**Vector:** Agent runs `cat .env` or `head .aws/credentials` to "check" configuration.

**Pattern:** Matches `cat`, `less`, `more`, `head`, `tail` followed by filenames matching `.env`, `.env.*`, `.dev.vars`, `.aws/credentials`, `.aws/config`.

**Blocked examples:**
- `cat .env`
- `head -n 5 .env.production`
- `less .aws/credentials`
- `tail .dev.vars`

**Allowed (no false positives):**
- `cat README.md`
- `head -n 5 main.py`
- `tail -f logs/app.log`

**Limitation:** Does not catch `python -c "print(open('.env').read())"` or `base64 .env`. The set of file-reading commands is not exhaustive.

### Category B: Environment Dumps

**Vector:** Agent runs `printenv` or `env` to survey the environment, dumping every secret in the process.

**Patterns:**
- Standalone `printenv` (no args) — dumps all env vars
- `printenv GITHUB_TOKEN` (targeted secret var) — dumps one secret
- Standalone `env` (no args) — dumps all env vars
- Standalone `set` (no args) — dumps all shell variables
- `export -p` — dumps all exports

**Allowed:**
- `env VAR=val command` — sets a variable for a subprocess (not a dump)
- `set -e`, `set -x` — shell options, not dumps
- `export MY_VAR=hello` — sets a variable, not a dump
- `printenv PATH`, `printenv HOME` — non-secret variables

**Secret variable list (shared with Category C):**
```
GITHUB_TOKEN, GH_TOKEN, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN,
AWS_ACCESS_KEY_ID, OPENAI_API_KEY, ANTHROPIC_API_KEY,
CLOUDFLARE_API_TOKEN, CF_API_TOKEN, NPM_TOKEN, DOCKER_PASSWORD,
DATABASE_URL, DB_PASSWORD, SECRET_KEY, PRIVATE_KEY
```

### Category C: Secret Variable Dereference

**Vector:** Agent runs `echo $GITHUB_TOKEN` or `curl -H "Authorization: Bearer $AWS_SECRET_ACCESS_KEY"` — the shell expands the variable before the command runs, and the value appears in stdout.

**Pattern:** Matches `$SECRET_VAR` or `${SECRET_VAR}` anywhere in the command string, where SECRET_VAR is in the shared secret variable list.

**Blocked examples:**
- `echo $GITHUB_TOKEN`
- `curl -H "Authorization: $OPENAI_API_KEY" https://api.openai.com`
- `echo ${AWS_SECRET_ACCESS_KEY}`

**Allowed:**
- `echo $HOME`
- `echo $PATH`
- `echo "hello world"`

### Category D: CLI Credential Dump Commands (NEW — 2026-03-07)

**Vector:** Agent runs a CLI tool that has a built-in "print my credential" subcommand. This is the most insidious category because the credential is not in a file or environment variable — it's stored in the tool's own credential store, and the tool has a dedicated command to extract it.

**How it was discovered:** During a session, the agent ran `gh auth token` while investigating how to bridge `gh auth login` credentials to a `.env` file. The command succeeded, the GitHub PAT was printed to stdout, and it was captured in the session transcript. The token had to be rotated.

**Patterns blocked:**

| Command | What it dumps |
|---------|--------------|
| `gh auth token` | Active GitHub PAT from gh's credential store |
| `gh auth status --show-token` | GitHub PAT embedded in status output |
| `aws configure get aws_secret_access_key` | AWS secret key from ~/.aws/credentials |
| `aws configure get aws_session_token` | AWS session token |
| `aws configure get aws_access_key_id` | AWS access key ID |
| `aws sts get-session-token` | Temporary AWS credentials (key + secret + token) |
| `aws ssm get-parameter --with-decryption` | Decrypted secrets from Parameter Store |

**Allowed (no false positives):**
- `gh auth login` — interactive, reads stdin, doesn't print token
- `gh auth status` — prints login status without the token
- `gh auth logout` — revokes, doesn't print
- `gh api repos/owner/repo` — normal API usage
- `aws sts get-caller-identity` — returns account ID and ARN, not secrets
- `aws configure get region` — non-secret config value
- `aws ssm get-parameter --name /app/version` — without `--with-decryption`, returns encrypted blob

---

## Complementary Defense: Token Resolver

Blocking `gh auth token` in the hook creates a problem: how does application code get the token without the agent running the command?

Solution: `gh_link_auditor.auth.resolve_github_token()` — a Python function that:
1. Checks `GITHUB_TOKEN` environment variable first
2. Falls back to `subprocess.run(["gh", "auth", "token"], capture_output=True)` internally

The subprocess output goes into a Python variable — it never reaches Claude's stdout. The hook blocks the *agent* from running `gh auth token` in the Bash tool, but Python code running inside a `poetry run` command can still call it safely because the subprocess output is captured internally, not printed to the transcript.

The operator runbook was updated to stop telling users to paste tokens into `.env` files. If they already ran `gh auth login`, the resolver picks it up automatically.

---

## Known Gaps and Limitations

### 1. Non-exhaustive file readers (Category A)
`cat`, `less`, `more`, `head`, `tail` are covered. Not covered: `bat`, `view`, `vim -c ':q'`, `python -c "open('.env').read()"`, `base64 .env`, `xxd .env`, `od .env`, `strings .env`, `awk '{print}' .env`, `sed -n p .env`.

### 2. Indirect execution
If the agent writes a Python/Node/Ruby script that dumps credentials and then runs it, the hook only sees `python script.py`. The credential extraction happens inside the script, invisible to the hook.

### 3. Pipe and redirect evasion
The bash-gate hook blocks `&&`, `|`, and `;` in commands (separate hook), which prevents most pipe-based evasion. But if that gate were disabled, commands like `gh auth token | cat` would need the Category D pattern to match within piped commands.

### 4. Incomplete CLI tool coverage
Category D covers `gh` and `aws`. Many other CLI tools have credential dump commands that we haven't catalogued yet. See the Gemini Deep Research prompt below.

### 5. MCP tool blind spot
If an MCP server provides a `get_credentials` tool, the hook has zero visibility. MCP servers need their own guardrails.

### 6. Model cooperation required
The Read tool (non-Bash file reader) cannot be hooked. The model is instructed via CLAUDE.md to never read `.env`, `.aws/credentials`, etc. This is a soft control — a sufficiently confused or manipulated model could bypass it.

---

## Gemini Deep Research Prompt

The following prompt is designed to be handed to Gemini 2.5 Pro with Deep Research enabled. It asks Gemini to systematically enumerate CLI tools across the developer ecosystem that have built-in "print my credential" subcommands.

---

BEGIN PROMPT

---

# Research Task: Enumerate CLI Tools with Credential Dump Subcommands

## Context

I maintain a security hook for AI coding agents (Claude Code, Cursor, etc.) that blocks shell commands which would print credentials to stdout. The hook intercepts commands before execution using regex pattern matching on the command string.

The hook currently blocks these credential-dumping CLI commands:

**GitHub CLI (gh):**
- `gh auth token` — prints the active PAT
- `gh auth status --show-token` — prints PAT in status output

**AWS CLI (aws):**
- `aws configure get aws_secret_access_key`
- `aws configure get aws_session_token`
- `aws configure get aws_access_key_id`
- `aws sts get-session-token`
- `aws ssm get-parameter --with-decryption`

## What I Need

Systematically enumerate CLI tools that a developer might have installed on a workstation (macOS/Linux/Windows) that have subcommands or flags which print credentials, tokens, secrets, or private keys to stdout.

For each tool, I need:

1. **Tool name** and typical install method (brew, npm, pip, apt, etc.)
2. **Exact command** that dumps the credential (e.g., `tool auth show-token`)
3. **What it prints** (OAuth token, API key, password, private key, etc.)
4. **Safe alternatives** that should NOT be blocked (e.g., `tool auth status` without the token flag)
5. **How common it is** — is this a niche tool or something millions of developers have installed?

## Categories to Investigate

Please cover at minimum:

### Cloud Provider CLIs
- **GCP/gcloud**: `gcloud auth print-access-token`, `gcloud auth print-identity-token`, `gcloud auth application-default print-access-token`, `gcloud secrets versions access`
- **Azure CLI**: `az account get-access-token`, `az keyvault secret show`
- **DigitalOcean**: `doctl auth`
- **Heroku CLI**: `heroku auth:token`
- **Fly.io**: `fly auth token`
- **Vercel**: `vercel env pull`
- **Netlify**: `netlify env:get`
- **CloudFlare**: `wrangler secret list` (does it print values?)
- Any other cloud CLIs with token/credential print commands

### Container and Orchestration
- **Docker**: `docker config inspect`, credential helpers, `~/.docker/config.json` access commands
- **kubectl**: `kubectl config view` (embeds tokens?), `kubectl get secret -o yaml`
- **Helm**: any credential access
- **Podman**: similar to Docker?

### Package Managers and Registries
- **npm**: `npm token list`, `npm config get //registry.npmjs.org/:_authToken`
- **pip/twine**: `keyring get`
- **gem**: credential storage access
- **cargo**: registry token access
- **composer**: auth.json access
- **nuget**: API key commands

### Version Control and CI/CD
- **git**: `git credential fill`, `git config --get user.password`, credential helpers
- **gitlab-cli (glab)**: `glab auth token` or similar
- **bitbucket-cli**: credential access
- **CircleCI CLI**: `circleci context show` or token access
- **Travis CLI**: `travis token`
- **Jenkins CLI**: any credential dump

### Secret Managers
- **Vault (HashiCorp)**: `vault kv get`, `vault read`, `vault token lookup`
- **1Password CLI (op)**: `op item get`, `op read`
- **Bitwarden CLI (bw)**: `bw get`, `bw list`
- **LastPass CLI (lpass)**: `lpass show`
- **AWS Secrets Manager**: `aws secretsmanager get-secret-value`
- **doppler**: `doppler secrets get`
- **infisical**: credential access commands
- **sops**: `sops -d` (decrypts files to stdout)

### Database CLIs
- **psql**: Does it ever print connection strings with passwords?
- **mysql**: `mysql_config_editor print` (does it show passwords?)
- **mongosh**: credential access
- **redis-cli**: `CONFIG GET requirepass`

### Communication/API Tools
- **Slack CLI**: token access
- **Twilio CLI**: credential access
- **Stripe CLI**: `stripe config --list` (shows API keys?)
- **SendGrid**: credential access
- **Postman CLI (newman)**: environment variable extraction with secrets

### SSH and Crypto
- **ssh-agent**: `ssh-add -L` (public keys are fine, but `-l` vs `-L` distinction)
- **ssh-keygen**: Does any flag dump private keys to stdout?
- **gpg**: `gpg --export-secret-keys` to stdout
- **openssl**: `openssl rsa -in key.pem -text` (prints private key material)
- **age**: decryption to stdout

### Terraform and IaC
- **terraform**: `terraform output -json` (can contain secrets), `terraform state pull` (entire state with secrets)
- **pulumi**: `pulumi config get --secret`, `pulumi stack export`
- **ansible-vault**: `ansible-vault view` (decrypts to stdout)

### Miscellaneous
- **ngrok**: `ngrok config check` or auth token access
- **tailscale**: auth key access
- **certbot**: private key access
- **pass** (password store): `pass show`
- **gopass**: credential access
- **chamber**: `chamber read` / `chamber exec`
- **direnv**: does `direnv show` print secret values?
- **dotenv CLI tools**: any that print .env contents to stdout

## Output Format

For each tool, provide a structured entry like:

```
### tool-name (commonality: HIGH/MEDIUM/LOW)

BLOCK:
- `exact command to block` — what it prints
- `another command` — what it prints

ALLOW (safe, do not block):
- `safe command` — why it's safe

REGEX PATTERN:
- Suggested bash regex for the hook
```

## Important Constraints

The hook uses bash `[[ "$command" =~ pattern ]]` regex matching. Patterns must:
- Match the command at the start of a string OR after `;&|` (command separators)
- Not false-positive on safe subcommands of the same tool
- Be specific enough that normal usage isn't blocked

## Bonus

If you're aware of any meta-patterns I'm missing — entire categories of tools or attack vectors beyond "CLI tool prints credential to stdout" — please flag them. For example:
- Tools that write credentials to a temp file and then cat it
- Tools that open a browser but also print a token to the terminal
- Tools that print credentials as part of "debug" or "verbose" output
- API clients that echo request headers (including Authorization) in verbose mode (`curl -v`, `httpie --print=H`)

---

END PROMPT

---
