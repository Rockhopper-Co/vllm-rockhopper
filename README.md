# vllm-rockhopper

A [vast.ai](https://vast.ai) Docker image that layers [Claude Code](https://github.com/anthropics/claude-code) on top of the official `vastai/vllm` image, with speculative decoding pre-configured via MTP.

## What's inside

- **Base**: `vastai/vllm:latest`
- **Added**: Node.js 20 + Claude Code CLI (`@anthropic-ai/claude-code`)
- **vLLM config**: speculative decoding with MTP, 1 speculative token (`vllm-args.conf`)

## Build

```bash
docker build -t vllm-rockhopper .
```

## Usage

Deploy on vast.ai using this image. The vLLM extra args are baked in via `/etc/vllm-args.conf`:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}'
```
