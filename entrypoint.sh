#!/bin/bash
set -e

# Detect GPUs that are actually accessible (not what the instance metadata claims)
GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l || echo 1)
GPU_COUNT=$((GPU_COUNT > 0 ? GPU_COUNT : 1))

export CUDA_VISIBLE_DEVICES=$(seq -s, 0 $((GPU_COUNT - 1)))

# Disable AUTO_PARALLEL — we manage tensor-parallel-size here to avoid CDI errors
# when the CDI registry has fewer GPUs than the instance allocation claims.
export AUTO_PARALLEL=false

# Inject --tensor-parallel-size into VLLM_ARGS if not already set
if [ -n "$VLLM_ARGS" ] && ! echo "$VLLM_ARGS" | grep -q "tensor-parallel-size"; then
  export VLLM_ARGS="--tensor-parallel-size $GPU_COUNT $VLLM_ARGS"
elif [ -z "$VLLM_ARGS" ]; then
  export VLLM_ARGS="--tensor-parallel-size $GPU_COUNT"
fi

exec /opt/instance-tools/bin/entrypoint.sh "$@"
