from ollama import GenerateResponse


class OllamaError(Exception):
    pass

try:
    import ollama
    from ollama import ListResponse
except Exception as ex:
    raise OllamaError(f"Failed to import ollama client, install ollama package with 'pip install ollama'.\nError: {ex}")

class OllamaHandler:
    ollama_host: str

    def __init__(self, host: str, port: int):
        self.ollama_host = self._build_ollama_host(host, port)
        self.client = ollama.Client(host=self.ollama_host)

    def _build_ollama_host(self, host: str, port: int) -> str:
        if host.startswith("http://") or host.startswith("https://"):
            return f"{host}:{port}" if ":" not in host.split("//", 1)[1] else host
        return f"http://{host}:{port}"

    def test_connection(self) -> bool:
        try:
            self.client.ps()
            return True
        except Exception as ex:
            raise OllamaError(f"Ollama is not responding: {ex}")
        
    def fetch_ollama_models(self) -> list[str]:
        try:
            resp = self.client.list()
        except Exception as ex:
            raise OllamaError(f"Ollama is not responding: {ex}")

        models: list[str] = []
        if isinstance(resp, ListResponse) and isinstance(resp.models, list):
            for m in resp.models:
                if isinstance(m, ListResponse.Model) and isinstance(m.model, str):
                    models.append(m.model)
        return models

    def generate(self, model: str, prompt: str, images: list[str]) -> str:
        try:
            resp = self.client.generate(model=model, prompt=prompt, images=images)
        except Exception as ex:
            raise OllamaError(f"Failed to generate description from Ollama: {ex}")

        text = resp.response if isinstance(resp, GenerateResponse) else None
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Invalid response from Ollama generate.")
        return text.strip()

