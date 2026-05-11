#!/bin/bash
# Replacement for /opt/supervisor-scripts/caddy.sh that adds multi-scheme
# LLM auth (Bearer / x-api-key / api-key) on top of the upstream Caddy config.

utils=/opt/supervisor-scripts/utils
. "${utils}/logging.sh"
. "${utils}/cleanup_generic.sh"
. "${utils}/environment.sh"
. "${utils}/exit_serverless.sh"

# 1. Run the upstream caddy configurator (writes /etc/Caddyfile).
cd /opt/portal-aio/caddy_manager
/opt/portal-aio/venv/bin/python caddy_config_manager.py

# 2. Ensure the portal config file exists if running without PORTAL_CONFIG.
touch /etc/portal.yaml

# 3. Inject extra LLM auth schemes into the vLLM port block.
/opt/portal-aio/venv/bin/python /opt/portal-aio/caddy_manager/inject-llm-auth.py || \
    echo "inject-llm-auth: post-processor failed (continuing with upstream config)"

if [[ -f /etc/Caddyfile ]]; then
    # Frontend log viewer will force a page reload if this string is detected
    echo "Starting Caddy..."
    /opt/portal-aio/caddy_manager/caddy run --config /etc/Caddyfile 2>&1
    exit $?
else
    echo "Skipping Caddy startup - No config file was generated"
fi
