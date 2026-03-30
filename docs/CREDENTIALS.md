# NanoClaw Credentials Guide

How credentials reach agent containers. Three mechanisms, each for a different use case.

## Quick Reference

| Mechanism | Use case | Where stored | How injected | Agent sees |
|-----------|----------|--------------|--------------|------------|
| **OneCLI vault** | API keys (Anthropic, GitHub, etc.) | OneCLI gateway | HTTPS proxy intercept | Nothing — transparent |
| **SOPS group secrets** | Per-group env vars (DB passwords, custom tokens) | `groups/{folder}/secrets.env` (encrypted) | `-e KEY=VALUE` docker args | Env var |
| **Prompt injection** | Short-lived tokens (GitHub App) | IPC task prompt text | Agent reads from instructions | Token string in prompt |

## 1. OneCLI Vault (primary — for API keys)

OneCLI runs as a local HTTPS gateway on `http://127.0.0.1:10254`. When a container makes an outbound HTTPS request (e.g., to `api.anthropic.com`), OneCLI intercepts it, injects the real API key, and forwards. The container never sees the actual credential.

### Currently registered secrets

```bash
onecli secrets list
```

| Secret | Host pattern | Type |
|--------|-------------|------|
| Anthropic | `api.anthropic.com` | anthropic |
| GitHub PAT (nanoclaw-tasks) | `api.github.com` | generic |

### Add a new API key

```bash
# Anthropic-type (knows the header format)
onecli secrets create \
  --name "Anthropic" \
  --type anthropic \
  --value "sk-ant-..." \
  --host-pattern "api.anthropic.com"

# Generic (you specify the header)
onecli secrets create \
  --name "My API" \
  --type generic \
  --value "key123" \
  --host-pattern "api.example.com"
```

For generic secrets, OneCLI injects `Authorization: Bearer {value}` by default. To customize, use the gateway web UI or API.

### Per-agent access control

Each NanoClaw group gets its own OneCLI agent (created automatically at startup). By default, agents in `all` mode see every secret. To restrict:

```bash
# List agents
onecli agents list

# Switch agent to selective mode (only assigned secrets)
onecli agents set-secret-mode --id <agent-id> --mode selective

# Assign specific secrets to an agent
onecli agents set-secrets --id <agent-id> --secret-ids "secret-id-1,secret-id-2"
```

Example: the `swan-crm` agent is in `selective` mode with only Anthropic and GitHub secrets assigned.

### How it connects to containers

In `src/container-runner.ts`, before spawning a container:

```typescript
const onecliApplied = await onecli.applyContainerConfig(args, {
  addHostMapping: false,
  agent: agentIdentifier,  // e.g. "swan-crm"
});
```

This adds docker args that route the container's HTTPS traffic through the OneCLI gateway. The agent identifier determines which secrets are available.

## 2. SOPS Group Secrets (for per-group env vars)

When a group needs its own credentials as environment variables (not proxied API calls), use SOPS-encrypted files.

### Create group secrets

```bash
# Create the secrets file
cat > groups/pharmacy_crm/secrets.env << 'EOF'
CRM_API_TOKEN=some-secret-token
CUSTOM_KEY=another-value
EOF

# Encrypt with SOPS (requires AGE key configured)
sops encrypt --input-type dotenv --output-type dotenv \
  -i groups/pharmacy_crm/secrets.env
```

The file is now encrypted at rest. NanoClaw decrypts it on the host at container spawn time and injects each key-value pair as `-e KEY=VALUE` docker args.

### How it works

In `src/container-runner.ts`:

```typescript
const groupSecrets = decryptGroupSecrets(groupFolder);
for (const [key, value] of groupSecrets) {
  args.push('-e', `${key}=${value}`);
}
```

The container agent sees these as regular environment variables.

### When to use

- Credentials that the agent needs as env vars (not via HTTPS proxy)
- Per-group isolation (each group has its own secrets file)
- Example: Rails API token for `pharmacy_crm`, database password for a specific integration

## 3. Prompt Injection (for short-lived tokens)

For tokens that must be generated fresh each time (e.g., GitHub App installation tokens that expire in 1 hour), generate on the host and embed in the IPC task prompt.

### Example: GitHub App token in todo-cycle

In `~/.dotfiles/bin/claude-todo-cycle`:

```bash
# Generate on host (has access to PEM file)
GITHUB_APP_TOKEN=$(/home/tomas/.dotfiles/bin/github-app-token)

# Embed in IPC task prompt
cat > "${IPC_DIR}/task.json" << TASK
{
  "type": "schedule_task",
  "prompt": "... export GH_TOKEN='${GITHUB_APP_TOKEN}' ..."
}
TASK
```

The agent reads the token from its instructions and uses it directly.

### When to use

- Short-lived tokens (generated per-session, expire in minutes/hours)
- Tokens that require host-side key material to generate (PEM files, etc.)
- One-off credentials for a specific task

### Security note

The token lives in the IPC task file briefly (deleted after processing) and in the agent's prompt. Since GitHub App tokens expire in 1 hour and the task runs within 30 minutes, the exposure window is acceptable.

## What the container CANNOT see

| Resource | Why |
|----------|-----|
| `.env` file | Shadowed with `/dev/null` at `/workspace/project/.env` |
| `ANTHROPIC_API_KEY` env var | Not set — OneCLI proxies transparently |
| `~/.onecli/` | Not mounted |
| `~/.dotfiles/` | Not mounted |
| Channel tokens (Slack, WhatsApp) | Only the host process uses these |
| Other groups' secrets | Each group only gets its own `secrets.env` |
| Mount allowlist | Stored at `~/.config/nanoclaw/` — never mounted |

## Common Operations

### Add a new API service for all agents

```bash
onecli secrets create --name "OpenAI" --type generic \
  --value "sk-..." --host-pattern "api.openai.com"
```

All agents in `all` secret mode get access immediately. Selective agents need explicit assignment.

### Add a credential for one specific group

```bash
# Create or edit the group's secrets file
sops groups/mygroup/secrets.env
# Add: MY_TOKEN=secret123
# Save and exit — SOPS re-encrypts automatically
```

### Check what an agent can access

```bash
# Find the agent
onecli agents list

# Check its secret mode and assigned secrets
onecli agents secrets --id <agent-id>

# Cross-reference with secret list
onecli secrets list
```

### Rotate a credential

```bash
# Update in OneCLI vault
onecli secrets update --id <secret-id> --value "new-key-value"
```

No container restart needed — the gateway picks up the new value immediately.

## Troubleshooting

**Agent can't reach an API**: Check `onecli secrets list` — is the host pattern registered? Check the agent's secret mode — if `selective`, is the secret assigned?

**"OneCLI gateway not reachable" warning**: The gateway isn't running. Start it:
```bash
cd ~/.onecli && docker compose up -d
```

**Agent sees `ANTHROPIC_API_KEY` in env**: You're using the native credential proxy fallback, not OneCLI. Run `/init-onecli` to migrate.
