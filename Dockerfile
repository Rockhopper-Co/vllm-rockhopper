FROM vastai/vllm:v0.20.0-cuda-13.0

# Install Node.js 20 and Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Bake in vLLM extra args (speculative decoding config)
COPY vllm-args.conf /etc/vllm-args.conf

# Multi-scheme auth for the vLLM port: in addition to the upstream
# Authorization: Bearer flow, the vLLM port also accepts x-api-key and
# api-key headers when LLM_API_KEY is set. See README.md.
COPY inject-llm-auth.py /opt/portal-aio/caddy_manager/inject-llm-auth.py
COPY caddy.sh /opt/supervisor-scripts/caddy.sh
RUN chmod +x /opt/supervisor-scripts/caddy.sh /opt/portal-aio/caddy_manager/inject-llm-auth.py
