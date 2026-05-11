#!/usr/bin/env python3
"""Inject multi-scheme auth into the vLLM port block of /etc/Caddyfile.

The vast.ai base image's caddy_config_manager.py generates a Caddyfile that
only accepts `Authorization: Bearer <token>` for API requests. This
post-processor adds two extra accepted header schemes for the vLLM port:

    x-api-key: <LLM_API_KEY>   (Anthropic-style)
    api-key:   <LLM_API_KEY>   (Azure OpenAI-style)

plus keeps Bearer working against LLM_API_KEY.

LLM_API_KEY is a separate secret from WEB_PASSWORD / OPEN_BUTTON_TOKEN so the
LLM key can be rotated without invalidating the portal login. If LLM_API_KEY
is unset, this script no-ops and the base image's Caddyfile is left as-is.

Only the vLLM application's port is modified. Other portal ports keep their
existing auth.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

CADDYFILE = Path("/etc/Caddyfile")
PORTAL_YAML = Path("/etc/portal.yaml")
CADDY_BIN = "/opt/portal-aio/caddy_manager/caddy"
VLLM_APP_NAME = "vLLM API"


def cel_escape(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "")
    )


def find_vllm_external_port() -> int | None:
    if not PORTAL_YAML.exists():
        return None
    data = yaml.safe_load(PORTAL_YAML.read_text()) or {}
    apps = data.get("applications", {}) or {}
    app = apps.get(VLLM_APP_NAME)
    if not app:
        return None
    return int(app["external_port"])


def build_matcher_snippet(key: str) -> str:
    k = cel_escape(key)
    expr = (
        f'{{http.request.header.Authorization}} == "Bearer {k}" || '
        f'{{http.request.header.X-Api-Key}} == "{k}" || '
        f'{{http.request.header.Api-Key}} == "{k}"'
    )
    return (
        "(has_valid_llm_api_key_matcher) {\n"
        "    @has_valid_llm_api_key {\n"
        f"        expression `{expr}`\n"
        "    }\n"
        "}\n"
    )


def extract_reverse_proxy_block(port_block: str) -> str | None:
    """Pull the inner `reverse_proxy ... { ... }` from the existing
    `@has_valid_bearer_token` route so the injected route uses identical
    upstream settings."""
    m = re.search(
        r"route\s+@has_valid_bearer_token\s*\{\s*handle\s*\{\s*(reverse_proxy[\s\S]*?\})\s*\}\s*\}",
        port_block,
    )
    return m.group(1) if m else None


def inject(caddyfile_text: str, ext_port: int, key: str) -> str:
    snippet = build_matcher_snippet(key)

    # 1. Insert the new global matcher snippet after the existing bearer matcher.
    bearer_snippet_re = re.compile(
        r"\(has_valid_bearer_token_matcher\)\s*\{[\s\S]*?\n\}\n",
    )
    m = bearer_snippet_re.search(caddyfile_text)
    if not m:
        print("inject-llm-auth: bearer matcher snippet not found, skipping", file=sys.stderr)
        return caddyfile_text
    if "(has_valid_llm_api_key_matcher)" not in caddyfile_text:
        caddyfile_text = (
            caddyfile_text[: m.end()] + "\n" + snippet + caddyfile_text[m.end():]
        )

    # 2. Locate the vLLM port block and inject the route.
    port_block_re = re.compile(
        rf"(^:{ext_port}\s*\{{)([\s\S]*?)(^\}})",
        re.MULTILINE,
    )
    pm = port_block_re.search(caddyfile_text)
    if not pm:
        print(f"inject-llm-auth: :{ext_port} block not found, skipping", file=sys.stderr)
        return caddyfile_text

    header, body, footer = pm.group(1), pm.group(2), pm.group(3)
    if "@has_valid_llm_api_key" in body:
        return caddyfile_text  # already injected

    proxy = extract_reverse_proxy_block(body)
    if not proxy:
        print("inject-llm-auth: could not extract upstream proxy block", file=sys.stderr)
        return caddyfile_text

    injected = (
        "\n    import has_valid_llm_api_key_matcher\n"
        "    route @has_valid_llm_api_key {\n"
        "        handle {\n"
        f"            {proxy}\n"
        "        }\n"
        "    }\n"
    )

    # Place injection right before the existing `import token_auth_matcher` line
    # so it runs before the portal-style auth fallback chain.
    new_body, n = re.subn(
        r"(\n\s*import\s+token_auth_matcher\b)",
        injected + r"\1",
        body,
        count=1,
    )
    if n == 0:
        # Fallback: append before the closing brace.
        new_body = body + injected

    return caddyfile_text[: pm.start()] + header + new_body + footer + caddyfile_text[pm.end():]


def main() -> int:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        print("inject-llm-auth: LLM_API_KEY not set, leaving Caddyfile unchanged")
        return 0
    if not CADDYFILE.exists():
        print("inject-llm-auth: /etc/Caddyfile not present, nothing to do")
        return 0

    ext_port = find_vllm_external_port()
    if ext_port is None:
        print(f"inject-llm-auth: no `{VLLM_APP_NAME}` entry in /etc/portal.yaml, skipping")
        return 0

    original = CADDYFILE.read_text()
    updated = inject(original, ext_port, key)
    if updated == original:
        return 0

    CADDYFILE.write_text(updated)
    try:
        subprocess.run([CADDY_BIN, "fmt", "--overwrite", str(CADDYFILE)], check=False)
    except FileNotFoundError:
        pass
    print(
        f"inject-llm-auth: enabled Bearer / x-api-key / api-key auth on :{ext_port} "
        "(value = $LLM_API_KEY)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
