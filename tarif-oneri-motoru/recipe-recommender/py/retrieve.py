# İstek kartına bakıp data/recipes.json içinden en fazla 5 tarif seçer.
# Yeni tarif yazmaz. Dosyada yoksa en yakın gerçek kaydı getirir ve not düşer.
# Üç yol vardır: özel gün veya diyet, yanına ne gider, normal arama.

import re

from words import tokenize, tr_lower, title_case_tr, BM25Index

# Çikolata ile kakao aynı malzeme sayılır.
SYNONYM_GROUPS = [["çikolata", "kakao"]]
# Un, tuz, su gibi her yerde olanlar tek başına şart koşulmaz.
STAPLES = {
    "un", "şeker", "toz şeker", "tuz", "su", "yağ", "sıvı yağ", "zeytinyağı",
    "tereyağı", "karabiber", "pul biber", "yumurta", "kabartma tozu", "vanilya",
    "maya", "nişasta", "nişaşta",
}
# Model yan tür söylemezse kullanılan hazır eşlik listesi.
PAIR_WITH = {
    "ayran": [["kebap", 1], ["lahmacun", 0.96], ["köfte", 0.92], ["pide", 0.86], ["gözleme", 0.82], ["börek", 0.78], ["mantı", 0.74]],
    "cacık": [["kebap", 1], ["köfte", 0.95], ["lahmacun", 0.9], ["pide", 0.85]],
    "şalgam": [["kebap", 1], ["lahmacun", 0.95], ["köfte", 0.9]],
    "turşu": [["fasulye", 1], ["pilav", 0.9], ["köfte", 0.85]],
    "pilav": [["fasulye", 1], ["nohut", 0.95], ["tavuk", 0.85], ["kebap", 0.8]],
    "yoğurt": [["mantı", 1], ["sarma", 0.95], ["dolma", 0.9], ["kebap", 0.8]],
    "çay": [["börek", 1], ["poğaça", 0.95], ["simit", 0.9], ["kek", 0.8]],
    "fasulye": [["pilav", 1], ["turşu", 0.9], ["yoğurt", 0.84], ["cacık", 0.8]],
    "kebap": [["piyaz", 1], ["ayran", 0.97], ["bulgur", 0.9], ["salata", 0.8]],
}
PAIR_FOOD_NAMES = list(PAIR_WITH.keys())


# Seçilen tarifler ve varsa ekrana yazılacak not.
class Hits(list):
    def __init__(self, items=None, note=None):
        super().__init__(items or [])
        self.note = note


def normalize(value):
    return tr_lower(value)


def synonyms_of(term):
    text = normalize(term)
    for group in SYNONYM_GROUPS:
        if any(name in text for name in group):
            return group
    return [text]


def name_hits_term(name, term):
    left = normalize(name)
    right = normalize(term)
    if not left or not right:
        return False
    parts = [part for part in re.split(r"[^\w]+", left, flags=re.UNICODE) if part]
    return any(part == right or part.startswith(right) for part in parts)


# Tarif bu malzemeyi adında ya da malzeme listesinde taşıyor mu.
def recipe_covers(recipe, wanted):
    hay = [recipe.get("name"), *(recipe.get("ingredient_names") or [])]
    return any(name_hits_term(name, term) for term in synonyms_of(wanted) for name in hay)


def is_staple(term):
    text = normalize(term)
    if text in STAPLES:
        return True
    parts = [part for part in text.split() if part]
    return len(parts) > 1 and all(part in STAPLES for part in parts)


# Bir veya iki özel malzeme varsa onlar şarttır. Üç ve fazlası puanla sıralanır.
def must_have(items):
    all_items = list(dict.fromkeys(normalize(item) for item in (items or []) if normalize(item)))
    distinctive = [item for item in all_items if not is_staple(item)]
    target = distinctive or all_items
    return target if 0 < len(target) <= 2 else []


# İstenen malzemelerin kaçı bu tarifte var.
def ingredient_overlap(wanted, recipe):
    if not wanted:
        return {"score": 0, "matched": []}
    matched = []
    for item in wanted:
        if recipe_covers(recipe, item):
            matched.append(item)
    return {"score": len(matched) / len(wanted), "matched": matched}


def method_match(wanted, recipe_method):
    if not wanted:
        return 0
    return 1 if normalize(wanted) in normalize(recipe_method or "") else 0


# "Zor olmayan" listesindeki kolay veya orta da uyar.
def difficulty_match(wanted, recipe_diff):
    if not wanted:
        return 0
    allowed = wanted if isinstance(wanted, (list, tuple)) else [wanted]
    recipe = normalize(recipe_diff)
    return 1 if any(recipe == normalize(item) for item in allowed) else 0


def category_match(wanted, recipe_cat):
    if not wanted:
        return 0
    return 1 if normalize(recipe_cat) == normalize(wanted) else 0


# Hazırlık ve pişirme dakikasını toplar. İkisi de boşsa süre bilinmiyor demektir.
def total_minutes(recipe):
    if recipe.get("prep_minutes") is None and recipe.get("cook_minutes") is None:
        return None
    return float(recipe.get("prep_minutes") or 0) + float(recipe.get("cook_minutes") or 0)


# 30 dakika, yaklaşık 20 ile 40 arasıdır. "En fazla" denirse tavan olur.
def within_time(recipe, intent):
    if not intent.get("sure_dakika"):
        return True
    total = total_minutes(recipe)
    if total is None:
        return False
    if intent.get("sure_en_fazla"):
        return 0 < total <= float(intent["sure_dakika"])
    slack = max(10, int(float(intent["sure_dakika"]) * 0.2 + 0.5))
    return abs(total - float(intent["sure_dakika"])) <= slack


def portion_ok(recipe, intent):
    if not intent.get("porsiyon"):
        return True
    if recipe.get("portion") in (None, ""):
        return False
    return float(recipe["portion"]) == float(intent["porsiyon"])


# Tür, zorluk, süre veya malzeme varsa kelime araması bunların önüne geçemez.
def has_column_constraint(intent):
    return bool(
        intent.get("kategori")
        or intent.get("zorluk")
        or intent.get("yontem")
        or intent.get("sure_dakika")
        or intent.get("porsiyon")
        or (intent.get("malzemeler") or [])
    )


# "Dün Sodalı Köfte yedim" deyince o tarifi dosyada bulur. Kendisi önerilmez.
def find_recipe_by_name(recipes, name):
    if not name:
        return None
    target = normalize(name)
    best = None
    best_score = 0
    for recipe in recipes:
        current = normalize(recipe.get("name"))
        if current == target:
            return recipe
        if target in current or current in target:
            score = min(len(current), len(target)) / max(len(current), len(target))
            if score > best_score:
                best_score = score
                best = recipe
    return best if best_score >= 0.5 else None


# İki tarif ne kadar benziyor: ad, malzeme, tür, pişirme.
def similar_bonus(ref, recipe):
    if not ref:
        return 0
    if normalize(recipe.get("name")) == normalize(ref.get("name")):
        return -1
    name_tokens = set(tokenize(ref.get("name")))
    cand_tokens = set(tokenize(recipe.get("name")))
    shared = sum(1 for token in name_tokens if token in cand_tokens)
    name_sim = shared / len(name_tokens) if name_tokens else 0
    overlap = ingredient_overlap((ref.get("ingredient_names") or [])[:8], recipe)
    same_cat = category_match(ref.get("category"), recipe.get("category"))
    same_method = method_match(str(ref.get("method") or "").split(",")[0].strip(), recipe.get("method")) if ref.get("method") else 0
    return name_sim * 0.45 + overlap["score"] * 0.35 + same_cat * 0.12 + same_method * 0.08


def blob_hits(blob, term):
    text = normalize(term)
    if not text:
        return False
    if len(text) <= 3:
        return re.search(r"(?:^|[^\w])" + re.escape(text) + r"(?:[^\w]|$)", blob) is not None
    return text in blob


# İstenmeyen malzeme tarifin adında veya listesinde varsa elenir.
def excluded(recipe, banned):
    if not banned:
        return False
    blob = normalize(" ".join([recipe.get("name") or "", recipe.get("category") or "", *(recipe.get("ingredient_names") or [])]))
    return any(blob_hits(blob, item) for item in banned)


def terms_from_model(intent, item):
    rows = []
    for index, term in enumerate(intent.get("eslik_yanlar") or []):
        cleaned = normalize(term)
        if cleaned and len(cleaned) >= 3 and cleaned != item:
            rows.append([cleaned, round(1 - index * 0.05, 2)])
    return rows


# "Ayranın yanına ne gider" sorusunun tariflerini seçer. Ayranın kendisini getirmez.
def retrieve_pairings(recipes, intent, limit):
    item = normalize(intent.get("eslik"))
    from_model = [] if intent.get("_sideStatic") or intent.get("_sideGeneric") else terms_from_model(intent, item)
    static_table = PAIR_WITH.get(item) or []
    table = [] if intent.get("_sideGeneric") else (from_model or static_table)
    scored = []
    for recipe in recipes:
        if name_hits_term(recipe.get("name"), item):
            continue
        if recipe.get("category") == "içecek":
            if not any(name_hits_term(recipe.get("name"), term) for term, _weight in table):
                continue
        best = None
        for term, weight in table:
            if name_hits_term(recipe.get("name"), term) and (best is None or weight > best["weight"]):
                best = {"term": term, "weight": weight}
        if best is None and not table and recipe.get("category") == "ana yemek":
            best = {"term": "ana yemek", "weight": 0.4}
        if best is None:
            continue
        score = best["weight"]
        if recipe.get("category") == "ana yemek":
            score += 0.06
        if recipe.get("category") in ("çorba", "tatlı"):
            score -= 0.2
        if re.search(r"(adana|urfa|iskender|şiş|ızgara)", normalize(recipe.get("name"))):
            score += 0.04
        scored.append({
            "recipe": recipe,
            "score": score,
            "family": best["term"],
            "matchedIngredients": [],
            "signals": {"pair": best["weight"], "sim": 0},
        })
    scored.sort(key=lambda row: (-row["score"], tr_lower(row["recipe"].get("name"))))
    picked = Hits()
    family_count = {}
    for row in scored:
        seen = family_count.get(row["family"], 0)
        if table and seen >= 2:
            continue
        family_count[row["family"]] = seen + 1
        picked.append(row)
        if len(picked) >= limit:
            break
    if not picked and from_model and static_table:
        return retrieve_pairings(recipes, {**intent, "_sideStatic": True}, limit)
    if not picked and table and not intent.get("_sideGeneric"):
        return retrieve_pairings(recipes, {**intent, "_sideGeneric": True}, limit)
    if table:
        picked.note = f"{title_case_tr(item)} ile iyi giden yemekler gösterildi."
    else:
        picked.note = f"“{title_case_tr(item)}” için uygun eşlik bulunamadı. Onu içermeyen yemekler gösterildi."
    return picked


def term_forms(term):
    forms = [term]
    if re.search(r"[ıiuü]$", term) and len(term) > 3:
        forms.append(term[:-1])
    return forms


# "kavrulmuş" kavurma sayılır. "acı" pul biberi de tutar.
def token_means(token, term):
    if term == "kavurma" and token.startswith("kavrul"):
        return True
    for form in term_forms(term):
        if token == form:
            return True
        if token.startswith(form) and re.fullmatch(r"(?:l[ıiuü]|s[ıiuü]|[ıiuü]|n[ıiuü]n|[ıiuü]n)", token[len(form):]):
            return True
    return False


def field_tokens(value):
    return [part for part in re.split(r"[^\w]+", normalize(value), flags=re.UNICODE) if part]


def recipe_hits_term(recipe, term, name_only=False):
    fields = [recipe.get("name")] if name_only else [recipe.get("name"), recipe.get("method"), *(recipe.get("ingredient_names") or [])]
    if any(token_means(token, term) for field in fields for token in field_tokens(field)):
        return True
    compact = lambda field: normalize(field).replace(" ", "")
    if term.startswith("tereyağ"):
        return any("tereyağ" in compact(field) for field in fields)
    if term in ("acı", "pulbiber", "isot"):
        return any(any(piece in compact(field) for piece in ("pulbiber", "acıbiber", "isot")) for field in fields)
    return False


# Sahur, iftar, vegan, beyaz et gibi isteklerin tarifini seçer.
def retrieve_context(recipes, intent, limit):
    baglam = intent.get("baglam") or {}
    wanted = list(baglam.get("aranan") or [])
    if len(wanted) == 1:
        primary = sum(1 for recipe in recipes if recipe_hits_term(recipe, wanted[0]))
        if primary < 3:
            for term in ("pilav", "salata", "börek", "tatlı"):
                if term not in wanted:
                    wanted.append(term)
    banned = baglam.get("haric") or []

    def blocked(recipe):
        return any(recipe_hits_term(recipe, term) for term in banned)

    scored = []
    for recipe in recipes:
        if blocked(recipe):
            continue
        best = None
        for index, term in enumerate(wanted):
            in_name = recipe_hits_term(recipe, term, name_only=True)
            anywhere = in_name or recipe_hits_term(recipe, term)
            if not anywhere:
                continue
            weight = len(wanted) - index + (0.25 if in_name else 0)
            if best is None or weight > best["weight"]:
                best = {"term": term, "weight": weight}
        if best is None and wanted:
            continue
        if best is None:
            best = {"term": "uygun", "weight": 0.3}
        score = best["weight"]
        if recipe.get("category") in ("ana yemek", "çorba"):
            score += 0.04
        scored.append({
            "recipe": recipe,
            "score": score,
            "family": best["term"],
            "matchedIngredients": [] if best["term"] == "uygun" else [best["term"]],
            "signals": {"context": best["weight"], "sim": 0},
        })
    scored.sort(key=lambda row: (-row["score"], tr_lower(row["recipe"].get("name"))))
    picked = Hits()
    family_count = {}
    cap = limit if baglam.get("cesit") is False else 2
    for row in scored:
        seen = family_count.get(row["family"], 0)
        if wanted and seen >= cap:
            continue
        family_count[row["family"]] = seen + 1
        picked.append(row)
        if len(picked) >= limit:
            break
    scarce = []
    for index, term in enumerate(wanted):
        count = sum(1 for recipe in recipes if not blocked(recipe) and recipe_hits_term(recipe, term))
        shown = any(row["family"] == term for row in picked)
        if count < 2 and (index == 0 or shown):
            scarce.append(term)
    bits = [baglam.get("anlam")] if baglam.get("anlam") else []
    if not bits:
        bits.append("Bu istek için uygun kayıtlar gösterildi.")
    if scarce:
        bits.append("Veri setinde " + ", ".join(f"“{term}”" for term in scarce) + " az geçiyor.")
    if not picked:
        bits.append("Bu sınıra uyan tarif bulunamadı.")
    picked.note = " ".join(bits)
    return picked


# Her tarifin arama metnini bir kez puanlamaya hazırlar.
def build_index(recipes):
    return BM25Index([recipe.get("search_text") or recipe.get("name") for recipe in recipes])


# Asıl seçim. Önce özel gün, sonra eşlik, sonra tür-süre-zorluk süzgeci ve kelime puanı.
def retrieve(recipes, index, intent, limit=5, relaxed_method=False, relaxed_time=False, relaxed_portion=False):
    if intent.get("baglam") and not intent.get("eslik") and not relaxed_method and not has_column_constraint(intent):
        contextual = retrieve_context(recipes, intent, limit)
        if contextual or contextual.note:
            return contextual
    if intent.get("eslik_eksik") and not relaxed_method:
        return Hits(note="Yanına ne gideceğini söylemem için yemeğin adını da yaz. Örneğin: pilavın yanına ne gider.")
    if intent.get("eslik") and not relaxed_method:
        paired = retrieve_pairings(recipes, intent, limit)
        if paired:
            return paired

    ref = find_recipe_by_name(recipes, intent.get("benzer_tarif"))
    enriched = dict(intent)
    if ref:
        if not enriched.get("kategori"):
            enriched["kategori"] = ref.get("category")
        if not enriched.get("yontem") and ref.get("method"):
            enriched["yontem"] = str(ref["method"]).split(",")[0].strip()
        ref_ings = [name for name in (ref.get("ingredient_names") or []) if len(name) > 2 and normalize(name) not in {"tuz", "su", "yağ", "karabiber"}]
        merged = list(enriched.get("malzemeler") or [])
        for ing in ref_ings[:6]:
            if not any(normalize(item) == normalize(ing) for item in merged):
                merged.append(ing)
        name_blob = normalize(ref.get("name"))
        enriched["malzemeler"] = [
            item for item in merged
            if not (
                normalize(item) in name_blob
                and not any(normalize(ri) == normalize(item) or normalize(item) in normalize(ri) for ri in ref_ings)
            )
        ]

    user_ingredients = list(intent.get("malzemeler") or [])
    required = [] if ref else must_have(user_ingredients)
    query_terms = [syn for ing in user_ingredients for syn in synonyms_of(ing)]
    query_parts = " ".join(
        str(part) for part in [
            enriched.get("serbest_not"),
            enriched.get("kategori"),
            enriched.get("yontem"),
            enriched.get("zorluk") if isinstance(enriched.get("zorluk"), str) else None,
            *query_terms,
            *(enriched.get("malzemeler") or []),
            f"{ref.get('name')} {' '.join((ref.get('ingredient_names') or [])[:8])}" if ref else enriched.get("benzer_tarif"),
        ] if part
    )
    banned = list(enriched.get("haric_tutulanlar") or [])
    for term in (intent.get("baglam") or {}).get("haric") or []:
        if term not in banned:
            banned.append(term)

    def allow(i):
        # Tür, zorluk, süre ve yasak malzeme uymayan tarifi havuza almaz.
        recipe = recipes[i]
        if excluded(recipe, banned):
            return False
        if enriched.get("kategori") and not category_match(enriched["kategori"], recipe.get("category")):
            return False
        if enriched.get("zorluk") and not difficulty_match(enriched["zorluk"], recipe.get("difficulty")):
            return False
        if not relaxed_time and not within_time(recipe, enriched):
            return False
        if not relaxed_portion and not portion_ok(recipe, enriched):
            return False
        if not relaxed_method and enriched.get("yontem") and not method_match(enriched["yontem"], recipe.get("method")):
            return False
        if ref and normalize(recipe.get("name")) == normalize(ref.get("name")):
            return False
        if enriched.get("benzer_tarif") and normalize(recipe.get("name")) == normalize(enriched["benzer_tarif"]):
            return False
        return True

    pool = index.rank(query_parts, top_k=120, filter_fn=allow)
    if required:
        for i, recipe in enumerate(recipes):
            if not allow(i) or any(not recipe_covers(recipe, req) for req in required):
                continue
            if not any(row["index"] == i for row in pool):
                pool.append({"index": i, "score": index.score(query_parts, i)})
    if enriched.get("kategori"):
        cat = normalize(enriched["kategori"])
        for i, recipe in enumerate(recipes):
            if not allow(i) or normalize(recipe.get("category")) != cat:
                continue
            if not any(row["index"] == i for row in pool):
                pool.append({"index": i, "score": index.score(query_parts, i) * 0.5})
    if isinstance(enriched.get("zorluk"), list) and len(pool) < limit:
        for i, recipe in enumerate(recipes):
            if not allow(i) or any(row["index"] == i for row in pool):
                continue
            pool.append({"index": i, "score": 0})

    max_bm25 = max([row["score"] for row in pool] + [1e-6])
    scored = []
    for row in pool:
        recipe = recipes[row["index"]]
        if required and any(not recipe_covers(recipe, req) for req in required):
            continue
        overlap = ingredient_overlap(enriched.get("malzemeler"), recipe)
        cat = category_match(enriched.get("kategori"), recipe.get("category"))
        meth = method_match(enriched.get("yontem"), recipe.get("method"))
        diff = difficulty_match(enriched.get("zorluk"), recipe.get("difficulty"))
        sim = similar_bonus(ref, recipe)
        minutes = total_minutes(recipe)
        time_score = 0
        if enriched.get("sure_dakika") and minutes is not None:
            time_score = 1 - min(1, abs(minutes - enriched["sure_dakika"]) / max(enriched["sure_dakika"], 1))
        penalty = 0.25 if enriched.get("yontem") and not meth else 0
        text_score = row["score"] / max_bm25
        sim_weight = 0.35 if ref else 0.1
        text_weight = 0.2 if ref else 0.35
        ing_weight = 0.25 if ref else 0.35
        total = (
            text_score * text_weight
            + overlap["score"] * ing_weight
            + cat * 0.12
            + meth * 0.1
            + diff * 0.05
            + time_score * 0.45
            + max(sim, 0) * sim_weight
            - penalty
        )
        scored.append({
            "recipe": recipe,
            "score": total,
            "matchedIngredients": overlap["matched"],
            "signals": {"textScore": text_score, "ingredient": overlap["score"], "cat": cat, "meth": meth, "diff": diff, "sim": sim},
        })
    scored.sort(key=lambda row: row["score"], reverse=True)
    picked = Hits()
    seen = set()
    allowed = enriched.get("zorluk") if isinstance(enriched.get("zorluk"), list) else None

    def take(item):
        key = normalize(item["recipe"].get("name"))[:24]
        if key in seen:
            return False
        seen.add(key)
        picked.append(item)
        return True

    if allowed and len(allowed) > 1:
        # "Zor olmayan" deyince kolay ve orta sırayla gelsin. Biri diğerini kapatmasın.
        buckets = {normalize(name): [] for name in allowed}
        for item in scored:
            buckets.get(normalize(item["recipe"].get("difficulty")), []).append(item)
        while len(picked) < limit:
            progressed = False
            for name in allowed:
                bucket = buckets[normalize(name)]
                while bucket and len(picked) < limit:
                    if take(bucket.pop(0)):
                        progressed = True
                        break
            if not progressed:
                break
    else:
        for item in scored:
            take(item)
            if len(picked) >= limit:
                break
    if not picked and enriched.get("porsiyon") and not relaxed_portion:
        fallback = retrieve(recipes, index, intent, limit, relaxed_method, relaxed_time, True)
        fallback.note = f"{enriched['porsiyon']} kişilik kayıt bulunamadı. Porsiyonu yazan tarifler bitince diğerleri gösterildi."
        return fallback
    if not picked and enriched.get("sure_dakika") and not relaxed_time:
        # Süre penceresi boşsa aynı türde en yakın dakikayı göster. Türden çıkma.
        fallback = retrieve(recipes, index, intent, limit, relaxed_method, True, relaxed_portion)
        label = f"{enriched['kategori']} tarif" if enriched.get("kategori") else "tarif"
        fallback.note = f"Yaklaşık {enriched['sure_dakika']} dakikalık {label} bulunamadı. Aynı tür ve zorlukta, süresi en yakın kayıtlar gösterildi."
        return fallback
    if not picked and enriched.get("yontem") and not relaxed_method:
        fallback = retrieve(recipes, index, intent, limit, True, relaxed_time, relaxed_portion)
        fallback.note = f"Veri setinde “{enriched['yontem']}” yöntemiyle uyan tarif yok. En yakın kayıtlar gösterildi."
        return fallback
    return picked
