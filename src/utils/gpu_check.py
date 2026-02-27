"""GPU detection utility for optimizing LLM inference configuration."""

import subprocess
import json


def detect_gpu() -> dict:
    """Detect available GPU and return info for model selection."""
    info = {"gpu_available": False, "name": None, "vram_mb": 0, "driver": None}

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            info["gpu_available"] = True
            info["name"] = parts[0] if len(parts) > 0 else None
            info["vram_mb"] = int(parts[1]) if len(parts) > 1 else 0
            info["driver"] = parts[2] if len(parts) > 2 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return info


def recommend_model(gpu_info: dict) -> str:
    """Recommend an Ollama model based on available VRAM."""
    vram = gpu_info.get("vram_mb", 0)

    if vram >= 8000:
        return "llama3.1:8b"      # Full fit in 8GB+ VRAM
    elif vram >= 4000:
        return "llama3.2:3b"      # Fits entirely in 4GB VRAM
    elif vram >= 2000:
        return "qwen2.5:1.5b"     # Fits in 2GB VRAM
    else:
        return "llama3.2:3b"      # CPU fallback, smaller is faster


if __name__ == "__main__":
    gpu = detect_gpu()
    print(json.dumps(gpu, indent=2))
    if gpu["gpu_available"]:
        model = recommend_model(gpu)
        print(f"\nRecommended model: {model}")
    else:
        print("\nNo GPU detected. Using CPU inference (will be slower).")
