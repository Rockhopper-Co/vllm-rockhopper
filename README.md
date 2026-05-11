# vllm-rockhopper

A [vast.ai](https://vast.ai) Docker image that layers [Claude Code](https://github.com/anthropics/claude-code) on top of the official `vastai/vllm` image, with speculative decoding pre-configured via MTP **and** multi-scheme authentication on the vLLM endpoint so it works with the auth header conventions of every common LLM client.

## What's inside

- **Base**: `vastai/vllm:v0.20.0-cuda-13.0`
- **Added**: Node.js 20 + Claude Code CLI (`@anthropic-ai/claude-code`)
- **vLLM config**: speculative decoding with MTP, 1 speculative token (`vllm-args.conf`)
- **Caddy auth extension**: the vLLM port accepts three authentication header schemes side-by-side (see [Authentication](#authentication))

## Build

```bash
docker build --platform linux/amd64 -t vllm-rockhopper .
```

## Deploying on vast.ai

Deploy the image as a vast.ai instance. The vLLM extra args are baked in via `/etc/vllm-args.conf`:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}'
```

Set these environment variables on the instance:

| Variable | Purpose |
| --- | --- |
| `VLLM_MODEL` | HuggingFace repo or local path of the model to serve (required by upstream `vllm.sh`) |
| `LLM_API_KEY` | **The API key clients use to call the LLM endpoint.** Separate from the portal login so you can rotate it independently. If unset, the vLLM port falls back to accepting only `Authorization: Bearer $OPEN_BUTTON_TOKEN` (upstream behaviour). |
| `VLLM_ARGS` | (optional) Extra vLLM CLI args |

The vLLM OpenAI-compatible API is exposed on **external port `8000`** (vast.ai maps this to a public host:port pair shown in the instance details). The web portal stays on port `1111` and continues to use `WEB_PASSWORD` / `OPEN_BUTTON_TOKEN` — `LLM_API_KEY` does **not** unlock the portal.

## Authentication

When `LLM_API_KEY` is set, the vLLM endpoint (port `8000`) accepts requests authenticated by **any** of the following schemes. All three carry the same secret — `$LLM_API_KEY` — and are equivalent. Pick whichever your client supports.

| Scheme | Header / param | Used by |
| --- | --- | --- |
| OpenAI / Bearer | `Authorization: Bearer $LLM_API_KEY` | OpenAI SDK, vLLM, LM Studio, Ollama-with-auth, Cohere, Mistral, HF TGI, Together, Groq, Continue.dev, Cline, Roo Code, **Goose (`openai`)**, VS Code Copilot custom model |
| Anthropic-style | `x-api-key: $LLM_API_KEY` | Anthropic SDK, some OpenAI-compatible wrappers, MCP clients, scripts mirroring Anthropic conventions |
| Azure-style | `api-key: $LLM_API_KEY` | Azure OpenAI SDK, tools targeting Azure-compatible endpoints |

For backwards compatibility, `Authorization: Bearer $OPEN_BUTTON_TOKEN` and `Authorization: Bearer $WEB_PASSWORD` also continue to work on port `8000` (so the vast.ai "Open" button and existing scripts keep working).

The base URL clients should use is:

```
https://<HOST>:<PORT>/v1
```

where `<HOST>:<PORT>` is the public address vast.ai assigns to internal port `8000` (find it under your instance's "IP & Port Info"). vast.ai terminates TLS for you, so always use `https://` from outside the data centre.

### curl examples

```bash
export ENDPOINT="https://<HOST>:<PORT>/v1"
export LLM_API_KEY="<your-key>"

# Bearer (OpenAI style)
curl "$ENDPOINT/models" -H "Authorization: Bearer $LLM_API_KEY"

# x-api-key (Anthropic style)
curl "$ENDPOINT/models" -H "x-api-key: $LLM_API_KEY"

# api-key (Azure style)
curl "$ENDPOINT/models" -H "api-key: $LLM_API_KEY"

# Chat completion
curl "$ENDPOINT/chat/completions" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'"$VLLM_MODEL"'",
    "messages": [{"role": "user", "content": "Say hi."}]
  }'
```

## Connecting from VS Code

The endpoint is OpenAI-compatible. Configure your client with the base URL `https://<HOST>:<PORT>/v1` and your `LLM_API_KEY`.

### Continue.dev

Edit `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "vllm-rockhopper",
      "provider": "openai",
      "model": "<your-model-id>",
      "apiBase": "https://<HOST>:<PORT>/v1",
      "apiKey": "<LLM_API_KEY>"
    }
  ]
}
```

Continue sends the key as `Authorization: Bearer …`, so the default Bearer scheme is used.

### Cline / Roo Code

In the extension settings, choose **OpenAI Compatible**:

- **Base URL**: `https://<HOST>:<PORT>/v1`
- **API Key**: your `LLM_API_KEY`
- **Model ID**: whatever you set as `VLLM_MODEL`

### GitHub Copilot Chat — bring-your-own-model

In Copilot Chat's *Manage Models* → *Add custom model*, pick the OpenAI-compatible provider and use the same base URL + `LLM_API_KEY`.

### Generic OpenAI SDK in a VS Code workspace

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://<HOST>:<PORT>/v1",
    api_key="<LLM_API_KEY>",
)
print(client.chat.completions.create(
    model="<your-model-id>",
    messages=[{"role": "user", "content": "hi"}],
).choices[0].message.content)
```

## Connecting from Goose

Goose treats this endpoint as an OpenAI-compatible provider.

### CLI configuration

```bash
goose configure
# → Configure Providers → OpenAI
#   API Host: https://<HOST>:<PORT>
#   API Key:  <LLM_API_KEY>
#   Model:    <your-model-id>
```

### Or edit `~/.config/goose/config.yaml` directly

```yaml
GOOSE_PROVIDER: openai
GOOSE_MODEL: <your-model-id>

OPENAI_HOST: https://<HOST>:<PORT>
OPENAI_API_KEY: <LLM_API_KEY>
OPENAI_BASE_PATH: v1/chat/completions
```

The OpenAI provider sends `Authorization: Bearer $OPENAI_API_KEY`, which this endpoint accepts.

### Goose Desktop (IDE / app)

In **Settings → Providers**, edit *OpenAI*:

- **Host**: `https://<HOST>:<PORT>`
- **API key**: your `LLM_API_KEY`
- **Model**: `VLLM_MODEL`

Save and start a session — Goose will route tool calls and chat through the vLLM endpoint.

## Security notes

- `LLM_API_KEY` should be a long random string. Treat it like an API key: never commit it, rotate on suspected exposure.
- The key is separate from the portal credentials (`WEB_PASSWORD` / `OPEN_BUTTON_TOKEN`) — rotating one does not affect the other.
- TLS is terminated by vast.ai's edge for the public port, so external traffic is encrypted. From inside the data centre, prefer `https://`.
- The header names `x-api-key` and `api-key` are matched case-insensitively (Caddy normalises header names).
- If `LLM_API_KEY` is unset, the vLLM port silently falls back to upstream behaviour — only `Authorization: Bearer $OPEN_BUTTON_TOKEN` works. Set it to enable the multi-scheme auth.

## How it works internally

The base image launches vLLM behind a Caddy reverse proxy. Caddy's config is generated at boot by `/opt/portal-aio/caddy_manager/caddy_config_manager.py` (part of the vast.ai base image) and written to `/etc/Caddyfile`. This repo replaces `/opt/supervisor-scripts/caddy.sh` with a wrapper that:

1. Runs the upstream config manager unchanged.
2. Runs `inject-llm-auth.py`, which adds a new CEL matcher and route to the vLLM port block so `Bearer` / `x-api-key` / `api-key` headers carrying `$LLM_API_KEY` short-circuit to the upstream proxy.
3. Re-formats and starts Caddy.

Other portal ports (Jupyter, Ray dashboard, Model UI, Instance Portal) are not touched and keep their original auth.
