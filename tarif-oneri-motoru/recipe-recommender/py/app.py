# Bu dosya programın kapısıdır.
# Sayfayı açar, kutuya yazılan cümleyi alır, tarifleri seçtirir ve cevabı ekrana geri yollar.
# Yeni tarif yazmaz. Tarifler data/recipes.json dosyasındadır.
# Çalıştırmak: bu klasörde python app.py

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# recipe-recommender klasörü. Tarif dosyası ve site bunun içindedir.
ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from explain import explain_recommendations
from intent import parse_intent
from llm import Llm
from retrieve import build_index, retrieve

# Tarifler bir kez okunur. Kelime puanı da bir kez kurulur.
RECIPES = json.loads((ROOT / "data" / "recipes.json").read_text(encoding="utf-8"))
INDEX = build_index(RECIPES)
LLM = Llm()
PORT = 8090


# İstenen zorlukta tarif yoksa ekrana dürüst bir not yazar.
def coverage_note(intent):
    wanted = intent.get("zorluk")
    if not wanted:
        return None
    allowed = [str(item) for item in wanted] if isinstance(wanted, list) else [str(wanted)]
    label = " veya ".join(allowed)
    matched = [recipe for recipe in RECIPES if str(recipe.get("difficulty") or "") in allowed]
    if not matched:
        return f"Veri setinde “{label}” etiketli tarif yok."
    if intent.get("kategori"):
        in_cat = [recipe for recipe in matched if recipe.get("category") == intent["kategori"]]
        if not in_cat:
            names = ", ".join(recipe.get("name") for recipe in matched)
            return f"Veri setinde “{label}” etiketli {intent['kategori']} yok. Bu etikette yalnızca {len(matched)} tarif var: {names}."
    return None


# Cümleyi karta çevirir, tarifleri seçer, altına neden seçildiğini ekler.
def recommend(query, limit=5):
    query = str(query or "").strip()
    if len(query) < 2:
        return {"error": "query gerekli"}, 400
    limit = min(5, max(3, int(limit or 5)))
    intent, source = parse_intent(query, LLM if LLM.ok() else None)
    candidates = retrieve(RECIPES, INDEX, intent, limit)
    note = " ".join(part for part in (coverage_note(intent), getattr(candidates, "note", None)) if part)
    explained = explain_recommendations(candidates, intent, query, LLM if LLM.ok() else None)
    results = []
    for item in explained:
        recipe = item["recipe"]
        results.append({
            "id": recipe.get("id"),
            "name": recipe.get("name"),
            "category": recipe.get("category"),
            "method": recipe.get("method"),
            "difficulty": recipe.get("difficulty"),
            "prep_minutes": recipe.get("prep_minutes"),
            "cook_minutes": recipe.get("cook_minutes"),
            "portion": recipe.get("portion"),
            "ingredients": recipe.get("ingredients") or [],
            "ingredient_names": recipe.get("ingredient_names") or [],
            "steps": recipe.get("steps") or [],
            "score": round(float(item["score"]), 4),
            "matchedIngredients": item.get("matchedIngredients") or [],
            "reason": item.get("reason"),
            "reasonSource": item.get("reasonSource"),
        })
    return {
        "query": query,
        "intent": intent,
        "intentSource": source,
        "llm": LLM.ok(),
        "note": note,
        "results": results,
    }, 200


# Sayfanın üstündeki "3310 tarif" yazısı buradan gelir.
def meta():
    cats = {}
    for recipe in RECIPES:
        key = recipe.get("category") or "diğer"
        cats[key] = cats.get(key, 0) + 1
    return {"recipeCount": len(RECIPES), "categories": cats, "llm": LLM.ok()}


# Tarayıcıdan gelen isteklere cevap verir: sayfa, sağlık, tarif sayısı, öneri.
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload, code=200):
        self._send(code, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    # Sayfa, css ve js dosyalarını site klasöründen okur.
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            return self._json({"ok": True, "recipes": len(RECIPES), "llm": LLM.ok()})
        if path == "/api/meta":
            return self._json(meta())
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        file_path = (SITE / relative).resolve()
        if not str(file_path).startswith(str(SITE.resolve())) or not file_path.is_file():
            return self._send(404, "bulunamadı", "text/plain; charset=utf-8")
        kind = "text/css" if file_path.suffix == ".css" else "text/html; charset=utf-8" if file_path.suffix == ".html" else "text/javascript; charset=utf-8"
        self._send(200, file_path.read_bytes(), kind)

    # Kutudaki cümle buraya gelir. Cevap tarif kartlarıdır.
    def do_POST(self):
        if not self.path.startswith("/api/recommend"):
            return self._send(404, "bulunamadı", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw or "{}")
            payload, code = recommend(body.get("query"), body.get("limit") or 5)
            self._json(payload, code)
        except Exception as err:
            print(err, file=sys.stderr)
            self._json({"error": "Öneri üretilemedi", "detail": str(err)}, 500)


if __name__ == "__main__":
    print(f"Tarif sayfası http://127.0.0.1:{PORT}", flush=True)
    print(f"Yapay zeka: {'açık' if LLM.ok() else 'kapalı'}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
