# Seçilen tarifin altına "neden bu" cümlesini yazar.
# Model açıksa cümleyi o kurar. Kapalıysa aşağıdaki hazır kalıp kurulur.
# Dakika uydurmaz. Hazırlık ve pişirme boşsa süre yazmaz.

import sys

from words import title_case_tr


# Model yokken kullanılan gerekçe. Karttaki gerçek sütunlardan kurulur.
def template_reason(item, intent):
    parts = []
    recipe = item["recipe"]
    matched = item.get("matchedIngredients") or []
    if matched:
        parts.append("Eşleşen malzemeler: " + ", ".join(matched) + ".")
    if intent.get("kategori") and recipe.get("category") == intent["kategori"]:
        parts.append(f"{recipe['category']} kategorisine uyuyor.")
    if intent.get("yontem") and intent["yontem"] in tr_method(recipe.get("method")):
        parts.append(f"Pişirme yöntemi: {recipe.get('method')}.")
    if difficulty_fits(intent, recipe):
        parts.append(f"Zorluk seviyesi {recipe.get('difficulty')}.")
    minutes = None
    if not (recipe.get("prep_minutes") is None and recipe.get("cook_minutes") is None):
        minutes = float(recipe.get("prep_minutes") or 0) + float(recipe.get("cook_minutes") or 0)
    if intent.get("sure_dakika") and minutes is not None:
        parts.append(f"Hazırlık ve pişirme toplamı {int(minutes) if minutes == int(minutes) else minutes} dakika.")
    if intent.get("porsiyon") and recipe.get("portion") not in (None, "") and float(recipe["portion"]) == float(intent["porsiyon"]):
        parts.append(f"{recipe['portion']} kişilik.")
    if (intent.get("baglam") or {}).get("anlam"):
        parts.insert(0, intent["baglam"]["anlam"])
    if intent.get("eslik"):
        parts.insert(0, f"{title_case_tr(intent['eslik'])} ile iyi gider.")
    if intent.get("benzer_tarif") and (item.get("signals") or {}).get("sim", 0) > 0:
        parts.append(f"“{intent['benzer_tarif']}” ile uyumlu / benzer bir seçim.")
    if difficulty_fits(intent, recipe) and intent.get("kategori") and recipe.get("category") != intent["kategori"]:
        parts.append(f"“{recipe.get('difficulty')}” etiketli bir {recipe.get('category')}. Veri setinde bu zorlukta {intent['kategori']} yok.")
    if not parts:
        parts.append(f"Veri setindeki “{recipe.get('name')}” tarifi isteğinize metin benzerliğiyle öne çıktı.")
    return " ".join(parts)


# "Zor olmayan" hem kolay hem ortadır. Tarif bu listedeyse uyar.
def difficulty_fits(intent, recipe):
    wanted = intent.get("zorluk")
    if not wanted:
        return False
    allowed = wanted if isinstance(wanted, list) else [wanted]
    return recipe.get("difficulty") in allowed


# Pişirme yöntemini küçük harfe çevirir. "Fırın" ile "fırın" aynı sayılsın diye.
def tr_method(method):
    from words import tr_lower
    return tr_lower(method or "")


# Her karta bir gerekçe yazar. Model hata verirse hazır cümleye döner.
def explain_recommendations(items, intent, query, llm):
    if not llm or not llm.ok() or not items:
        for item in items:
            item["reason"] = template_reason(item, intent)
            item["reasonSource"] = "template"
        return items
    payload = []
    for index, item in enumerate(items):
        recipe = item["recipe"]
        payload.append({
            "i": index,
            "name": recipe.get("name"),
            "category": recipe.get("category"),
            "method": recipe.get("method"),
            "difficulty": recipe.get("difficulty"),
            "prep_minutes": recipe.get("prep_minutes"),
            "cook_minutes": recipe.get("cook_minutes"),
            "matched": item.get("matchedIngredients"),
            "ingredients": (recipe.get("ingredient_names") or [])[:12],
        })
    try:
        parsed = llm.chat([
            {"role": "system", "content": "Türkçe tarif öneri asistanısın. Her tarif için 1 kısa gerekçe yaz. Bu tarifler zaten seçildi; önerme, uygun değil veya önerilemez yazma. Kategori tutmuyorsa en yakın kayıt diye anlat. Eşlik varsa yanında yenir de, içinde o malzeme var deme. Süre uydurma. prep ve cook boşsa dakika yazma. Doluysa toplamını söyle. JSON: {\"reasons\":[{\"i\":0,\"gerekce\":\"...\"}]}"},
            {"role": "user", "content": __import__("json").dumps({"sorgu": query, "niyet": intent, "adaylar": payload}, ensure_ascii=False)},
        ], 0.4)
        reasons = {row.get("i"): row.get("gerekce") or row.get("reason") for row in parsed.get("reasons") or []}
        for index, item in enumerate(items):
            item["reason"] = reasons.get(index) or template_reason(item, intent)
            item["reasonSource"] = "llm" if index in reasons and reasons[index] else "template"
        return items
    except Exception as err:
        print("Explain LLM failed:", err, file=sys.stderr)
        for item in items:
            item["reason"] = template_reason(item, intent)
            item["reasonSource"] = "template"
        return items
