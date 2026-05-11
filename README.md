# vllm-rockhopper

A [vast.ai](https://vast.ai) Docker image that layers [Claude Code](https://github.com/anthropics/claude-code) on top of the official `vastai/vllm` image, with speculative decoding pre-configured via MTP.

## What's inside

- **Base**: `vastai/vllm:v0.20.0-cuda-13.0`
- **Added**: Node.js 20 + Claude Code CLI (`@anthropic-ai/claude-code`)
- **vLLM config**: speculative decoding with MTP, 1 speculative token (`vllm-args.conf`)

## Build

```bash
docker build -t vllm-rockhopper .
```

## Usage

Deploy on vast.ai using this image. Replace `<DOCKERHUB_USERNAME>` with your Docker Hub username.

```bash
vastai create instance <OFFER_ID> \
  --image <DOCKERHUB_USERNAME>/vllm-rockhopper:latest \
  --env '-p 8000:8000 -e VLLM_MODEL="<model>" -e VLLM_ARGS="<args>"' \
  --onstart-cmd 'entrypoint.sh' \
  --disk 64 --ssh --direct
```

### GPU handling

The image entrypoint auto-detects the number of available GPUs at startup and sets `--tensor-parallel-size` accordingly. This avoids CDI device errors on machines with varying GPU counts.

- Works on 1–N GPU machines without reconfiguration
- `AUTO_PARALLEL=true` is not needed (and should be omitted — it causes CDI failures on machines where the CDI registry has fewer entries than the instance allocation claims)
- If you set `--tensor-parallel-size` explicitly in `VLLM_ARGS`, that value is used as-is

### Baked-in vLLM args

Additional args from `/etc/vllm-args.conf` are loaded by the base image entrypoint:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}'
```
