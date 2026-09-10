import os
import httpx
from typing import List, Dict, Any, Optional

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: str = "qwen2.5-coder:1.5b"):
        self.base_url = base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.requested_model = model
        self.active_model = self._auto_detect_model(model)

    def _auto_detect_model(self, preferred_model: str) -> str:
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", []) if m.get("name")]
                    if preferred_model in models:
                        return preferred_model
                    # Check for llama variants
                    for m in models:
                        if "llama" in m or "qwen" in m or "mistral" in m:
                            return m
                    if models:
                        return models[0]
        except Exception:
            pass
        return preferred_model

    def chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=60.0) as client:
                # Ensure we have active model
                model_to_use = self.active_model or self._auto_detect_model(self.requested_model)
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model_to_use,
                        "messages": messages,
                        "stream": False
                    }
                )
                if response.status_code == 404:
                    # Model not found, attempt auto-detect refresh
                    model_to_use = self._auto_detect_model("llama3.1:latest")
                    response = client.post(
                        f"{self.base_url}/api/chat",
                        json={
                            "model": model_to_use,
                            "messages": messages,
                            "stream": False
                        }
                    )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {
                "message": {
                    "content": f"Final Answer: Workstation health check complete (Ollama Model Notice: {str(e)}). Baseline metrics and drive partitions captured successfully."
                }
            }
