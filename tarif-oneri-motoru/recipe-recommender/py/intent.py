# Yazılan cümleyi istek kartına çevirir.
# Kartta tür, malzeme, süre, zorluk, pişirme ve "yanına ne gider" durur.
# Model cümleyi okur. Kod, cümlede olmayan malzemeyi ve uydurulan yöntemi siler.
# Tarif seçmez. Seçim retrieve.py dosyasındadır.

import re
import sys

from retrieve import PAIR_FOOD_NAMES
from words import tr_lower

# "tatlı", "çorba" gibi sözlerin dosyadaki tür adına karşılığı.
CATEGORY_ALIASES = [
    ["ana yemek", ["ana yemek", "ana yemeği", "yemek", "akşam yemeği", "öğle"]],
    ["tatlı", ["tatlı", "tatlısı", "dessert", "kurabiye", "pasta", "kek"]],
    ["çorba", ["çorba", "çorbası"]],
    ["salata", ["salata", "salatası"]],
    ["kahvaltı", ["kahvaltı", "kahvaltılık"]],
    ["atıştırmalık", ["atıştırmalık", "aperatif", "mezze", "meze"]],
    ["içecek", ["içecek", "şerbet", "limonata"]],
    ["turşu", ["turşu"]],
]
# "fırında" denince yöntem fırın olur.
METHOD_ALIASES = [
    ["fırın", ["fırın", "fırında", "fırına"]],
    ["tava", ["tava", "tavada", "tavası"]],
    ["tencere", ["tencere", "tencerede"]],
    ["ızgara", ["ızgara", "ızgarada"]],
    ["haşlama", ["haşlama", "haşla", "haşlanmış"]],
    ["kızartma", ["kızartma", "kızart", "kızarmış"]],
    ["kavurma", ["kavurma", "kavur"]],
    ["ocak", ["ocak", "ocakta"]],
    ["blender", ["blender"]],
    ["mangal", ["mangal", "mangalda"]],
    ["benmari", ["benmari"]],
    ["düdüklü", ["düdüklü", "düdüklüde"]],
]
# "basit" ve "pratik" kolay sayılır. "zor olmayan" ayrıca kolay ve orta demektir.
DIFF_ALIASES = [
    ["kolay", ["kolay", "basit", "hızlı", "pratık", "pratik"]],
    ["orta", ["orta"]],
    ["zor", ["çok zor", "zor", "karmaşık", "zahmetli"]],
]
# Cümlede geçen malzeme bu listedeyse karta yazılır.
INGREDIENT_LEXICON = [
    "kıyma", "tavuk", "et", "balık", "köfte", "yumurta", "süt", "kakao", "çikolata",
    "un", "şeker", "tereyağı", "zeytinyağı", "soğan", "sarımsak", "domates", "biber",
    "patates", "patlıcan", "kabak", "havuç", "pirinç", "bulgur", "makarna", "nohut",
    "mercimek", "fasulye", "yoğurt", "peynir", "kaşar", "maydanoz", "nane", "limon",
    "portakal", "elma", "muz", "ceviz", "fındık", "badem", "bal", "reçel", "ekmek",
    "sucuk", "pastırma", "salam", "mantar", "ıspanak", "lahana", "brokoli", "bezelye",
    "mısır", "zeytin", "salça", "baharat", "kimyon", "sumak", "nar", "üzüm", "incir",
    "irmik", "nişaşta", "nişasta", "krema", "labne", "ayran", "soda", "galeta",
    "vanilya", "tarçın", "kakule", "susam", "tahin", "pekmez", "helva", "lokum",
]
# Bunlar malzeme değildir. "Sebze yemeği" deyince sebze şart koşulmaz.
GENERIC_WORDS = {"sebze", "sebzeler", "yemek", "yemeği", "tatlı", "çorba", "salata"}
SIDE_PRONOUNS = {"şu", "şunun", "şuna", "bu", "bunun", "buna", "o", "onun", "ona", "neyin", "şey", "şeyin"}
VOICED = {"d": "t", "b": "p", "c": "ç", "ğ": "k"}
SIMILAR_HINT = re.compile(r"benzer|gibi|uyan|uyumlu|dün|yedim|yaptım|pişirdim|denedim")
# Modele "yalnız cümlede olanı yaz" diyen tarif. Tarif listesi burada yoktur.
INTENT_SCHEMA_HINT = """Kullanıcının Türkçe yemek isteğini JSON olarak çıkar.
Sadece kullanıcının cümlesinde açıkça geçen bilgileri yaz. Cümlede olmayan malzeme, pişirme yöntemi, zorluk veya tarif adı uydurma.
"çikolatalı var mı" gibi bir soruda malzemeler yalnızca ["çikolata"] olur. Un, yumurta, şeker, süt, kabartma tozu, fırın veya kolay ekleme.
benzer_tarif yalnızca kullanıcı belirli bir yemeğin adını söyleyip ona benzer/uyan bir şey isterse dolu olur. Aksi halde null.
"X ile hangi yemek iyi gider" bir eşlik sorusudur. X'i malzeme yapma.
Sadece JSON döndür. Anahtarlar:
{"kategori":"ana yemek|tatlı|çorba|salata|kahvaltı|atıştırmalık|içecek|turşu|null","malzemeler":["..."],"yontem":"fırın|tava|tencere|ızgara|haşlama|kızartma|null","zorluk":"kolay|orta|zor|null","benzer_tarif":"tarif adı veya null","haric_tutulanlar":["..."],"serbest_not":"kullanıcının cümlesi"}"""
# Vegan ve vejetaryende elenecek et, süt, yumurta sözleri.
ANIMAL_TERMS = ["et", "kıyma", "tavuk", "balık", "hindi", "sucuk", "pastırma", "sosis", "salam", "jambon", "kuzu", "dana", "ciğer", "kuşbaşı", "hamsi", "palamut", "levrek", "somon", "alabalık", "çupra", "lüfer", "ton"]
DAIRY_EGG_TERMS = ["süt", "yoğurt", "peynir", "kaşar", "lor", "labne", "tereyağı", "krema", "yumurta", "bal"]
# Tür, zorluk ve yöntem sözleri. Bunlar malzeme araması olmasın.
COLUMN_WORDS = {"tatlı", "çorba", "salata", "kahvaltı", "atıştırmalık", "içecek", "turşu", "yemek", "kolay", "orta", "zor", "pratik", "hızlı", "basit", "fırın", "tava", "tencere", "ızgara", "haşlama", "kızartma", "kavurma", "ocak"}
NOT_FOOD = {"yapmak", "etmek", "olmak", "bir", "şey", "lütfen"}
# "et istemiyorum" denince kıyma, tavuk, balık da elenir.
MEAT_EXPAND = ["kıyma", "tavuk", "balık", "kuzu", "dana", "sucuk", "köfte", "pastırma", "palamut", "levrek", "hamsi", "somon", "alabalık", "çupra", "lüfer", "ton"]


def letters(text, low, high):
    return re.fullmatch(rf"[^\W\d_]{{{low},{high}}}", text or "") is not None


# Kelime cümlede geçiyor mu. "soğansız" soğan sayılmaz.
def has_word(text, word):
    query = tr_lower(text)
    token = tr_lower(word)
    if not query or not token:
        return False
    if len(token) >= 4:
        return re.search(re.escape(token) + r"(?!s[ıiuü]z)", query) is not None
    return re.search(r"(?:^|[^\w])" + re.escape(token) + r"(?!s[ıiuü]z)(?:[^\w]|$)", query) is not None


def includes_any(text, words):
    return any(has_word(text, word) for word in words)


# "Sodalı Köfte'ye" gibi ekleri yemek adından ayırır.
def tidy_dish_name(name):
    parts = [part for part in str(name or "").strip().split() if part]
    if not parts:
        return name
    last = parts[-1]
    last = re.sub(r"s([ıiuü])n[ae]$", r"s\1", last, flags=re.I)
    last = re.sub(r"[ıiuü]n[ae]$", "", last, flags=re.I)
    last = re.sub(r"y[ae]$", "", last, flags=re.I)
    last = re.sub(r"n[ae]$", "", last, flags=re.I)
    parts[-1] = last
    return " ".join(parts)


# "soğansız" içinden soğanı çıkarır.
def negated_words(text):
    found = []
    for match in re.finditer(r"(?:^|[^\w])([^\W\d_]{2,})s[ıiuü]z", tr_lower(text)):
        if match.group(1) not in found:
            found.append(match.group(1))
    return found


def difficulty_from(query):
    # "zor olmayan" = zor hariç: kolay ve orta. Tek başına "kolay" veya "orta" aşağıda kalır.
    if re.search(r"çok\s+zor", query) and not re.search(r"çok\s+zor\s+(?:olmayan|değil|olmasın)", query):
        return "zor"
    if re.search(r"zor\s+(?:olmayan|değil|olmasın|istemiyorum|istemem)", query):
        return ["kolay", "orta"]
    if re.search(r"kolay\s+(?:olmayan|değil|olmasın)", query) or re.search(r"basit\s+(?:olmayan|değil)", query):
        return "orta"
    for canon, aliases in DIFF_ALIASES:
        if includes_any(query, aliases):
            return canon
    return None


# "30 dk", "yarım saat", "en fazla" gibi süre sözlerini dakikaya çevirir.
def parse_duration(query):
    maximum = re.search(r"en fazla|en çok|aşmasın|geçmesin|süremesin|kadar sür", query) is not None
    numbered = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:dk|dakika(?:da|lık)?)\b", query)
    if numbered:
        dakika = float(numbered.group(1).replace(",", "."))
    elif re.search(r"yarım\s+saat", query):
        dakika = 30
    elif re.search(r"bir\s+buçuk\s+saat|1[.,]5\s*saat", query):
        dakika = 90
    elif re.search(r"(?:^|[^\d])(?:bir|1)\s+saat", query):
        dakika = 60
    else:
        hours = re.search(r"(\d+)\s+saat", query)
        dakika = float(hours.group(1)) * 60 if hours else None
    if dakika is None:
        return {"dakika": None, "enFazla": False}
    return {"dakika": dakika, "enFazla": maximum}


# "4 kişilik" yazısını sayıya çevirir.
def parse_portion(query):
    match = re.search(r"(\d+)\s*kişilik", query)
    return float(match.group(1)) if match else None


def clean_null(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or tr_lower(text) == "null" or text == "yok":
        return None
    return text


# "pilavın" -> pilav, "ayranın" -> ayran. Yanına ne gider sorusu için.
def food_stem(raw):
    word = tr_lower(raw).replace("'", "").replace("’", "")
    if not word or word in SIDE_PRONOUNS:
        return None
    keys = sorted(set([*PAIR_FOOD_NAMES, *INGREDIENT_LEXICON]), key=len, reverse=True)
    for key in keys:
        if word == key or word.startswith(key):
            return key
    for key in keys:
        soft = next((letter for letter, hard in VOICED.items() if hard == key[-1]), None)
        if soft and word.startswith(key[:-1] + soft):
            return key
    return None


# "X ile ne gider" ve "X'in yanına ne" sorusundan X'i bulur.
# Yalnız "ne yapayım" eşlik sorusu sayılmaz.
def pairing_subject(query):
    text = tr_lower(query)
    asks = re.search(r"(?:ile|la|le)\s+(?:hangi\s+yemek|ne|neyi|iyi|güzel)", text) or re.search(r"iyi\s+gider|güzel\s+gider|yanına", text)
    if not asks or re.search(r"ile\s+yap", text):
        return {"food": None, "asked": False}
    match = (
        re.search(r"(.+?)\s+ile\s+(?:hangi|ne|neyi|iyi|güzel)", text)
        or re.search(r"(.+?)\s+yanına\b", text)
        or re.search(r"(.+?)(?:la|le)\s+(?:hangi|ne|neyi|iyi|güzel)", text)
    )
    if not match:
        return {"food": None, "asked": False}
    chunk = re.sub(r"^(bana|lütfen|bugün|dün)\s+", "", match.group(1).strip())
    tokens = [part.replace("'", "").replace("’", "") for part in chunk.split() if len(part) > 2 and part not in SIDE_PRONOUNS]
    stems = [food_stem(part) for part in tokens]
    stems = [stem for stem in stems if stem]
    if stems:
        return {"food": stems[-1], "asked": True}
    return {"food": tokens[-1] if tokens else None, "asked": True}


# Model kapalıyken kartı kod kurar. Kelime listelerine bakar.
def heuristic_intent(query):
    text = tr_lower(query)
    intent = {
        "kategori": None,
        "malzemeler": [],
        "yontem": None,
        "zorluk": None,
        "benzer_tarif": None,
        "eslik": None,
        "haric_tutulanlar": [],
        "serbest_not": query,
    }
    for canon, aliases in CATEGORY_ALIASES:
        if includes_any(text, aliases):
            intent["kategori"] = canon
            break
    for canon, aliases in METHOD_ALIASES:
        if includes_any(text, aliases):
            intent["yontem"] = canon
            break
    intent["zorluk"] = difficulty_from(text)
    duration = parse_duration(text)
    intent["sure_dakika"] = duration["dakika"]
    intent["sure_en_fazla"] = duration["enFazla"]
    intent["porsiyon"] = parse_portion(text)
    similar = re.search(r"(?:dün|geçen|önceki).{0,40}?(?:yaptım|yedim|pişirdim|denedim)", text) or re.search(r"(.+?)\s+(?:gibi|benzeri|benzer|uyan|uyanır|uyumlu)", text)
    if similar:
        name_match = re.search(r"(?:dün|geçen)\s+(.+?)\s+(?:yaptım|yedim|pişirdim)", str(query), re.I) or re.search(r"([A-ZÇĞİÖŞÜa-zçğıöşü][A-ZÇĞİÖŞÜa-zçğıöşü\s]{2,40}?)\s+(?:gibi|benzeri|benzer|uyan)\b", str(query), re.I)
        if name_match:
            intent["benzer_tarif"] = tidy_dish_name(re.sub(r"^(dün|geçen)\s+", "", name_match.group(1), flags=re.I).strip())
    excluded = re.search(r"(?:istemiyorum|istemem|olmasın|hariç)[:\s]+([\w\s,]+)", text) or re.search(r"([\w]{2,})\s+(?:istemiyorum|istemem|olmasın)\b", text)
    if excluded:
        intent["haric_tutulanlar"] = [part.strip() for part in re.split(r",| ve ", excluded.group(1)) if part.strip()]
    for word in negated_words(text):
        if word not in intent["haric_tutulanlar"]:
            intent["haric_tutulanlar"].append(word)
    found = [ing for ing in INGREDIENT_LEXICON if has_word(text, ing)]
    hand = re.search(r"elimde\s+(.+?)(?:\s+var|\s+ile|$)", text)
    if hand:
        for part in re.split(r",| ve | ile ", hand.group(1)):
            piece = part.strip()
            if piece not in found and 1 < len(piece) < 30:
                found.append(piece)
    if intent["benzer_tarif"]:
        name = tr_lower(intent["benzer_tarif"])
        intent["malzemeler"] = [ing for ing in found if ing not in name or ing in text.replace(name, " ")]
    else:
        intent["malzemeler"] = found
    side = pairing_subject(query)
    intent["eslik"] = side["food"]
    intent["eslik_eksik"] = side["asked"] and not side["food"]
    if intent["eslik"]:
        intent["malzemeler"] = [ing for ing in intent["malzemeler"] if ing != intent["eslik"]]
        intent["benzer_tarif"] = None
    return intent


# Modelin yazdığı malzemeden, cümlede geçmeyeni atar.
def mentioned_ingredients(query, proposed):
    found = []

    def add(item):
        name = tr_lower(item).strip()
        if len(name) < 2 or name in found:
            return
        found.append(name)

    for ing in INGREDIENT_LEXICON:
        if has_word(query, ing):
            add(ing)
    for item in proposed or []:
        name = tr_lower(item).strip()
        if not name or name == "null":
            continue
        tokens = [token for token in name.split() if len(token) >= 3]
        if tokens and all(has_word(query, token) for token in tokens):
            add(name)
    return found


def category_mentioned(query, kategori):
    row = next((item for item in CATEGORY_ALIASES if item[0] == kategori), None)
    return includes_any(query, row[1]) if row else has_word(query, kategori)


def alias_mentioned(table, query, value):
    row = next((item for item in table if item[0] == value), None)
    return includes_any(query, row[1]) if row else has_word(query, value)


# Modelin uydurduğu tür, yöntem ve malzemeyi cümleyle karşılaştırıp siler.
def ground_intent(query, intent):
    text = tr_lower(query)
    grounded = {
        **intent,
        "kategori": clean_null(intent.get("kategori")),
        "yontem": clean_null(intent.get("yontem")),
        "zorluk": clean_null(intent.get("zorluk")),
        "benzer_tarif": clean_null(intent.get("benzer_tarif")),
        "serbest_not": query,
    }
    if grounded["kategori"] and not category_mentioned(text, grounded["kategori"]):
        grounded["kategori"] = None
    if grounded["yontem"] and not alias_mentioned(METHOD_ALIASES, text, grounded["yontem"]):
        grounded["yontem"] = None
    duration = parse_duration(text)
    grounded["zorluk"] = difficulty_from(text)
    grounded["sure_dakika"] = duration["dakika"]
    grounded["sure_en_fazla"] = duration["enFazla"]
    grounded["porsiyon"] = parse_portion(text)
    if grounded["benzer_tarif"]:
        name = tr_lower(grounded["benzer_tarif"])
        tokens = [token for token in name.split() if len(token) > 2]
        hits = sum(1 for token in tokens if token in text)
        named = name in text or hits >= min(2, len(tokens) or 0)
        if not SIMILAR_HINT.search(text) or not named:
            grounded["benzer_tarif"] = None
    if not grounded["benzer_tarif"] and SIMILAR_HINT.search(text):
        guessed = heuristic_intent(query).get("benzer_tarif")
        if guessed:
            grounded["benzer_tarif"] = guessed
    said_no = re.search(r"([\w]{2,})\s+(?:istemiyorum|istemem|olmasın)\b", text)
    excluded = set()
    for item in intent.get("haric_tutulanlar") or []:
        excluded.add(tr_lower(item).strip())
    excluded.update(negated_words(text))
    if said_no and said_no.group(1) not in NOT_FOOD:
        excluded.add(said_no.group(1))
    grounded["haric_tutulanlar"] = [item for item in excluded if item and item != "null" and item not in NOT_FOOD]
    if "et" in grounded["haric_tutulanlar"]:
        for meat in MEAT_EXPAND:
            if meat not in grounded["haric_tutulanlar"]:
                grounded["haric_tutulanlar"].append(meat)
    grounded["malzemeler"] = [
        item for item in mentioned_ingredients(query, intent.get("malzemeler"))
        if item not in GENERIC_WORDS and not any(item == banned or item.startswith(banned) or banned.startswith(item) for banned in grounded["haric_tutulanlar"])
    ]
    if grounded["benzer_tarif"]:
        name = tr_lower(grounded["benzer_tarif"])
        grounded["malzemeler"] = [ing for ing in grounded["malzemeler"] if ing not in name or has_word(text.replace(name, " "), ing)]
    side = pairing_subject(query)
    grounded["eslik"] = side["food"]
    grounded["eslik_eksik"] = side["asked"] and not side["food"]
    if grounded["eslik"]:
        grounded["malzemeler"] = [ing for ing in grounded["malzemeler"] if ing != grounded["eslik"]]
        grounded["benzer_tarif"] = None
    if re.search(r"beyaz\s+et|deniz\s+ürün|deniz\s+mahsul", text):
        grounded["malzemeler"] = [ing for ing in grounded["malzemeler"] if ing != "et"]
    return grounded


def bare_food_name(word):
    value = tr_lower(word).strip()
    if len(value) >= 6 and re.search(r"[ıiuü]n$", value):
        return value[:-2]
    return value


def clean_side_term(raw, food):
    parts = [part for part in tr_lower(raw).strip().split() if part]
    term = parts[-1] if parts else ""
    item = tr_lower(food).strip()
    if not letters(term, 3, 18):
        return None
    if term in {"yemek", "şey", "tarif", "yan", "yanı", "içecek"}:
        return None
    if term == item or item.startswith(term) or term.startswith(item):
        return None
    return term


# Modele "bunun yanına ne gider" diye sorar. Tarif adı değil, tür ister.
def suggest_sides(query, food, llm):
    parsed = llm.chat([
        {"role": "system", "content": "Türk mutfağında bu yemeğin veya içeceğin yanında yenilen yemek türlerini söyle. Tarif adı uydurma. Her öğe kısa bir tür olsun: kebap, köfte, pilav, börek, salata, cacık, ayran, piyaz, turşu, sucuk, peynir, ekmek. Verilen yemeğin kendisini yazma. En fazla 6 tür. yemek alanına ek koyma: mantının değil mantı. JSON: {\"yemek\":\"mantı\",\"yanlar\":[\"cacık\",\"salata\"]}"},
        {"role": "user", "content": query},
    ], 0.2)
    proposed = bare_food_name(str(parsed.get("yemek") or "").split()[0] if str(parsed.get("yemek") or "").split() else "")
    raw_food = bare_food_name(food)
    head = proposed[:4]
    related = len(proposed) >= 3 and (raw_food.startswith(proposed) or proposed.startswith(raw_food) or (len(head) >= 4 and raw_food.startswith(head)))
    named = proposed if related and len(proposed) <= len(raw_food) else raw_food
    sides = []
    for item in parsed.get("yanlar") or []:
        term = clean_side_term(item, named)
        if term and term not in sides:
            sides.append(term)
    return {"food": named, "yanlar": sides[:6]}


def diet_of(query):
    text = tr_lower(query)
    if "vegan" in text:
        return "vegan"
    if "vejet" in text:
        return "vejetaryen"
    return None


def diet_terms(diet):
    if diet == "vegan":
        return [*ANIMAL_TERMS, *DAIRY_EGG_TERMS]
    if diet == "vejetaryen":
        return list(ANIMAL_TERMS)
    return []


def clean_context_term(raw):
    skip = {"yemek", "yemeği", "tarif", "tarifi", "şey", "özel", "gün", "günü", "zaman", "bir", "için"}
    parts = [part for part in tr_lower(raw).strip().split() if part and part not in skip]
    term = parts[-1] if parts else None
    if not term or not letters(term, 3, 20):
        return None
    return term


# Vegan et, süt, yumurta ve balı eler. Vejetaryen yalnız eti ve balığı eler.
def diet_context(query):
    diet = diet_of(query)
    if not diet:
        return None
    vegan = diet == "vegan"
    return {
        "diyet": diet,
        "anlam": "Vegan tarif: et, balık, süt ürünü, yumurta ve bal yok." if vegan else "Vejetaryen tarif: et ve balık yok.",
        "aranan": ["zeytinyağlı", "mercimek", "nohut", "salata", "sebze"] if vegan else ["sebze", "yumurta", "peynir", "mercimek", "makarna"],
        "haric": diet_terms(diet),
    }


# Beyaz et tavuk ve hindidir. Kırmızı et kıyma, kuzu ve danadır. Deniz ürünü balıktır.
def meat_context(query):
    text = tr_lower(query)
    if re.search(r"beyaz\s+et", text):
        return {"diyet": None, "anlam": "Beyaz et: tavuk ve hindi.", "aranan": ["tavuk", "hindi", "piliç"], "haric": ["kıyma", "dana", "kuzu", "kuşbaşı", "bonfile", "sucuk", "pastırma", "jambon"], "cesit": False}
    if re.search(r"kırmızı\s+et", text):
        return {"diyet": None, "anlam": "Kırmızı et: dana, kuzu ve kıyma.", "aranan": ["kıyma", "kuzu", "dana", "kuşbaşı", "bonfile"], "haric": ["tavuk", "hindi", "piliç", "balık", "hamsi", "karides", "midye"], "cesit": True}
    if re.search(r"deniz\s+ürün|deniz\s+mahsul", text):
        return {"diyet": None, "anlam": "Deniz ürünleri: balık ve kabuklu deniz ürünü.", "aranan": ["balık", "hamsi", "levrek", "somon", "midye", "kalamar"], "haric": ["tavuk", "hindi", "kıyma", "dana", "kuzu", "sucuk"], "cesit": True}
    return None


# Sahur hafif olur. İftar çorba, pide ve güllaç arar.
def meal_context(query):
    text = tr_lower(query)
    if "sahur" in text:
        return {"diyet": None, "anlam": "Sahur için hafif tarif.", "aranan": ["yumurta", "peynir", "çorba", "börek"], "haric": ["acı", "kızartma", "sucuk", "kavurma"]}
    if "iftar" in text:
        return {"diyet": None, "anlam": "İftar için çorba ve pide.", "aranan": ["çorba", "pide", "güllaç"], "haric": []}
    return None


# Model "tatlı, pratik" deyip aramayı bozmasın. Özel gün yoksa bu kartı kapatır.
def clean_context(raw, query):
    raw = raw or {}
    diet = raw.get("diyet") if raw.get("diyet") in ("vegan", "vejetaryen") else diet_of(query)
    aranan = []
    banned = set(diet_terms(diet))
    for item in raw.get("aranan") or []:
        term = clean_context_term(item)
        if term and term not in aranan and term not in banned:
            aranan.append(term)
    for item in raw.get("haric") or []:
        term = clean_context_term(item)
        if term:
            banned.add(term)
    anlam = str(raw.get("anlam") or "").strip()
    meat = meat_context(query)
    occasion = meat or diet_context(query) or meal_context(query)
    if not (raw.get("gerekli") or diet or aranan or occasion):
        return None
    fallback = occasion
    merged = []
    preferred = list((fallback or {}).get("aranan") or []) + list(aranan)
    for term in preferred:
        if meat and term == "et" and "et" not in meat["aranan"]:
            continue
        if term not in merged:
            merged.append(term)
    for term in (fallback or {}).get("haric") or []:
        banned.add(term)
    if not occasion and all(term in COLUMN_WORDS for term in merged):
        return None
    return {
        "diyet": diet,
        "anlam": (meat or {}).get("anlam") or (fallback or {}).get("anlam") or (anlam if len(anlam.split()) >= 4 else ""),
        "aranan": merged[:6],
        "haric": list(banned),
        "cesit": meat["cesit"] is not False if meat else True,
    }


# Modele vegan, sahur, yılbaşı gibi bir anlam var mı diye sorar.
def interpret_context(query, llm):
    try:
        parsed = llm.chat([
            {"role": "system", "content": "Kullanıcı bir diyet, özel gün, öğün zamanı ya da bedensel sınırdan söz ediyorsa bunu tarif aramasına çevir. Sıradan malzeme isteğinde gerekli false olsun. Tatlı, çorba, kolay, 30 dakika, fırın gibi sütun isteklerinde de gerekli false olsun. Vegan: et, balık, süt, peynir, yumurta, bal yok. Vejetaryen: et ve balık yok. Şu cümlelerde gerekli true: vegan, vejeteryan, yılbaşı, şükran, iftar, sahur, mide yanmasın, acı olmasın. Beyaz et tavuk ve hindidir. Kırmızı et kıyma, kuzu ve danadır. Deniz ürünü balık ve midyedir. Şükran ve yılbaşı için hindi, iftar için çorba ve pide, sahur için yumurta, peynir ve çorba yaz. Sahurda iç yanmasın diyorsa haric: acı, kızartma, sucuk, kavurma. Tarif adı uydurma. JSON: {\"gerekli\":false,\"anlam\":\"\",\"diyet\":null,\"aranan\":[],\"haric\":[]}"},
            {"role": "user", "content": query},
        ], 0)
        return clean_context(parsed, query)
    except Exception as err:
        print("Context LLM failed:", err, file=sys.stderr)
        return diet_context(query) or meal_context(query) or meat_context(query)


# Eşlik sorusuysa modelden yanına gidecek türleri ister.
def attach_sides(query, intent, llm):
    if not llm or not intent.get("eslik"):
        return intent
    try:
        side = suggest_sides(query, intent["eslik"], llm)
        if side["food"]:
            intent["eslik"] = side["food"]
        if side["yanlar"]:
            intent["eslik_yanlar"] = side["yanlar"]
    except Exception as err:
        print("Side LLM failed:", err, file=sys.stderr)
    return intent


def request_intent(query, llm):
    return llm.chat([
        {"role": "system", "content": INTENT_SCHEMA_HINT},
        {"role": "user", "content": query},
    ], 0)


# Bu dosyanın kapısı. Önce kod kartı kurar, model varsa onun kartını da okur, sonra ikisini temizler.
def parse_intent(query, llm=None):
    fallback = ground_intent(query, heuristic_intent(query))
    if not llm or not llm.ok():
        fallback["baglam"] = diet_context(query) or meal_context(query) or meat_context(query)
        return fallback, "heuristic"
    try:
        parsed = request_intent(query, llm)
        baglam = interpret_context(query, llm)
        malzemeler = parsed.get("malzemeler")
        intent = {
            "kategori": parsed.get("kategori") or fallback.get("kategori"),
            "malzemeler": [tr_lower(item) for item in malzemeler] if isinstance(malzemeler, list) else list(fallback.get("malzemeler") or []),
            "yontem": parsed.get("yontem") or fallback.get("yontem"),
            "zorluk": parsed.get("zorluk") or fallback.get("zorluk"),
            "benzer_tarif": parsed.get("benzer_tarif") or fallback.get("benzer_tarif"),
            "haric_tutulanlar": parsed.get("haric_tutulanlar") if isinstance(parsed.get("haric_tutulanlar"), list) else list(fallback.get("haric_tutulanlar") or []),
            "serbest_not": parsed.get("serbest_not") or fallback.get("serbest_not"),
        }
        for item in fallback.get("malzemeler") or []:
            if item not in intent["malzemeler"]:
                intent["malzemeler"].append(item)
        grounded = ground_intent(query, intent)
        grounded["baglam"] = baglam
        attach_sides(query, grounded, llm)
        return grounded, "llm"
    except Exception as err:
        print("Intent LLM failed, using heuristic:", err, file=sys.stderr)
        fallback["baglam"] = diet_context(query) or meal_context(query) or meat_context(query)
        attach_sides(query, fallback, llm)
        return fallback, "heuristic"
