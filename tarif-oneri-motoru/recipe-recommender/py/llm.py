# Yapay zeka bağlantısı. Model Groq'tadır.
# Cümleyi anlar, yanına ne gider diye tür söyler, kartın altındaki gerekçeyi yazar.
# Tarif listesini görmez. Bu yüzden yeni yemek uyduramaz.
# Model kapalıysa program yine çalışır; gerekçeyi hazır cümleyle kurar.

import json
import os
import urllib.error
import urllib.request

# GitHub'a yüklemeden önce bu anahtar satırını sil.
_FALLBACK_KEY = "OPENAI_API_KEY"


# Anahtar varsa model açıktır. Yoksa program şablon cümleyle devam eder.
class Llm:
    def __init__(self):
        self.key = os.environ.get("OPENAI_API_KEY") or _FALLBACK_KEY
        self.base = os.environ.get("OPENAI_BASE_URL") or "https://api.groq.com/openai/v1"
        self.model = os.environ.get("OPENAI_MODEL") or "openai/gpt-oss-120b"

    def ok(self):
        return bool(self.key)

    # Modele mesaj yollar. Cevabı JSON olarak geri alır.
    def chat(self, messages, temperature):
        body = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        request = urllib.request.Request(
            self.base.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + self.key,
                "Content-Type": "application/json",
                "User-Agent": "tarif-oneri-motoru",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"HTTP {err.code}: {detail}") from err
        content = payload["choices"][0]["message"]["content"] or "{}"
        return json.loads(content)
