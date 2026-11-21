# Cümleyi kelimelere böler ve tarifleri kelime puanıyla sıralar.
# BM25, sık geçen "ve" gibi kelimeleri değil, tarifi diğerlerinden ayıran kelimeyi önemser.
# "ve", "bir", "ile" puana katılmaz.

import math
import re
import unicodedata

# Aramada işe yaramayan bağlaçlar.
STOP = {
    "ve", "veya", "ile", "için", "bir", "bu", "da", "de", "mi", "mı", "mu", "mü",
    "çok", "daha", "kadar", "gibi", "olan", "olarak", "sonra", "önce", "ama",
    "fakat", "ya", "ki", "ne", "hem", "her", "şey", "var", "yok",
}


def tr_lower(value):
    # Türkçede I -> ı, İ -> i. Python'un kendi lower'ı İ harfini bozar.
    text = str(value or "")
    text = text.replace("İ", "i").replace("I", "ı")
    return unicodedata.normalize("NFC", text.lower())


# Kartta "ayran" yazısını "Ayran" diye göstermek için.
def title_case_tr(word):
    text = str(word or "")
    if not text:
        return text
    first = {"i": "İ", "ı": "I"}.get(text[0], text[0].upper())
    return first + text[1:]


# Noktalama atılır, kısa kelime ve bağlaç elenir.
def tokenize(text):
    if not text:
        return []
    cleaned = re.sub(r"[^\w\s]", " ", tr_lower(text), flags=re.UNICODE)
    return [part for part in cleaned.split() if len(part) > 1 and part not in STOP]


class BM25Index:
    # Bütün tariflerin kelime listesi. Soru gelince hangisi daha yakın, onu puanlar.
    def __init__(self, documents, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(doc) for doc in documents]
        self.n = len(documents)
        total = sum(len(tokens) for tokens in self.doc_tokens)
        self.avgdl = total / max(1, self.n)
        self.df = {}
        for tokens in self.doc_tokens:
            for token in set(tokens):
                self.df[token] = self.df.get(token, 0) + 1
        self.tf_list = []
        for tokens in self.doc_tokens:
            counts = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            self.tf_list.append(counts)

    # Her yerde geçen kelimenin puanı düşer. Nadir kelimenin puanı artar.
    def idf(self, term):
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    # Bir tarifin, sorudaki kelimelere ne kadar uyduğunu sayar.
    def score(self, query, doc_index):
        tokens = tokenize(query)
        if not tokens:
            return 0
        tf = self.tf_list[doc_index]
        length = len(self.doc_tokens[doc_index]) or 1
        total = 0
        seen = set()
        for term in tokens:
            if term in seen:
                continue
            seen.add(term)
            freq = tf.get(term, 0)
            if not freq:
                continue
            denom = freq + self.k1 * (1 - self.b + (self.b * length) / self.avgdl)
            total += self.idf(term) * ((freq * (self.k1 + 1)) / denom)
        return total

    # En yüksek puanlı tarifleri üstte tutar. Filtre uymayanı hiç listeye almaz.
    def rank(self, query, top_k=50, filter_fn=None):
        scores = []
        for i in range(self.n):
            if filter_fn and not filter_fn(i):
                continue
            value = self.score(query, i)
            if value > 0:
                scores.append({"index": i, "score": value})
        scores.sort(key=lambda row: row["score"], reverse=True)
        return scores[:top_k]
