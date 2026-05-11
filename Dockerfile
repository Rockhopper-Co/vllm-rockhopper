FROM vastai/vllm:v0.20.0-cuda-13.0

# Install Node.js 20 and Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Bake in vLLM extra args (speculative decoding config)
COPY vllm-args.conf /etc/vllm-args.conf

# Entrypoint: auto-detects GPU count, sets --tensor-parallel-size, delegates to base
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
