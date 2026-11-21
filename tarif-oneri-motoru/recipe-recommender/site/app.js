// Ekranın beyni. React yok, düz JavaScript.
// Kutuya yazılan cümleyi Python'a yollar. Gelen tarifleri kart olarak dizer.
// Karta basınca malzeme ve yapılış açılır.

// Kutunun altına konan hazır örnek cümleler.
const examples = [
  "Elimde kıyma, soğan ve patates var; fırında kolay bir ana yemek istiyorum.",
  "Süt ve kakao ile yapılabilecek bir tatlı öner.",
  "Dün Sodalı Köfte yaptım, ona uyan bir şey istiyorum.",
];

const queryBox = document.getElementById("query");
const send = document.getElementById("send");
const hint = document.getElementById("hint");
const status = document.getElementById("status");
const results = document.getElementById("sonuclar");
const exampleBox = document.getElementById("examples");

// Sayfa açılınca tarif sayısını ve modelin açık olup olmadığını yazar.
fetch("/api/meta")
  .then((response) => response.json())
  .then((meta) => {
    hint.textContent = `${Number(meta.recipeCount).toLocaleString("tr-TR")} tarif · ${meta.llm ? "AI gerekçe açık" : "şablon gerekçe"}`;
  })
  .catch(() => {
    hint.textContent = "Veri setinden önerir";
  });

// Örnek düğmesine basınca o cümle aranır.
examples.forEach((example) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "example";
  button.textContent = example.length > 56 ? `${example.slice(0, 54)}…` : example;
  button.addEventListener("click", () => {
    queryBox.value = example;
    recommend(example);
  });
  exampleBox.appendChild(button);
});

document.getElementById("form").addEventListener("submit", (event) => {
  event.preventDefault();
  recommend(queryBox.value);
});

// Cümleyi sunucuya yollar. Cevap gelince kartları çizer.
async function recommend(text) {
  const trimmed = text.trim();
  if (!trimmed) return;
  send.disabled = true;
  send.textContent = "Aranıyor…";
  status.textContent = "";
  try {
    const response = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: trimmed, limit: 5 }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "İstek başarısız");
    draw(data);
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    status.textContent = error.message || "Bir hata oluştu";
  } finally {
    send.disabled = false;
    send.textContent = "Tarif öner";
  }
}

// Başlık, not ve kart listesini sonuç alanına basar.
function draw(data) {
  const bits = ["niyet: " + data.intentSource];
  if (data.intent.kategori) bits.push(data.intent.kategori);
  if (data.intent.yontem) bits.push(data.intent.yontem);
  if (data.intent.zorluk) bits.push(Array.isArray(data.intent.zorluk) ? data.intent.zorluk.join(" veya ") : data.intent.zorluk);
  if (data.intent.sure_dakika) bits.push(data.intent.sure_dakika + " dk");
  results.hidden = false;
  results.innerHTML = "";
  const head = document.createElement("div");
  head.className = "results-head";
  head.innerHTML = `<h2>Öneriler</h2><span class="meta-pill"></span>`;
  head.querySelector(".meta-pill").textContent = bits.join(" · ");
  results.appendChild(head);
  if (data.note) {
    const note = document.createElement("p");
    note.className = "note";
    note.textContent = data.note;
    results.appendChild(note);
  }
  data.results.forEach((recipe, index) => results.appendChild(card(recipe, index)));
}

// Tek tarif kartı. Üstte ad ve gerekçe, açılınca malzeme ve yapılış.
function card(recipe, index) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "card";
  button.style.animationDelay = `${0.05 * index}s`;
  button.setAttribute("aria-expanded", "false");
  const tags = [recipe.category, recipe.method, recipe.difficulty, recipe.cook_minutes != null ? `${recipe.cook_minutes} dk pişirme` : null].filter(Boolean);
  const top = document.createElement("div");
  top.className = "card-top";
  const body = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = recipe.name;
  const tagRow = document.createElement("div");
  tagRow.className = "tags";
  tags.forEach((tag) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = tag;
    tagRow.appendChild(span);
  });
  const reason = document.createElement("p");
  reason.className = "reason";
  reason.textContent = recipe.reason || "";
  body.append(title, tagRow, reason);
  const chev = document.createElement("span");
  chev.className = "chev";
  chev.textContent = "▾";
  top.append(body, chev);
  const details = document.createElement("div");
  details.className = "details";
  details.hidden = true;
  details.innerHTML = "<div><h4>Malzemeler</h4><ul></ul></div>";
  const list = details.querySelector("ul");
  (recipe.ingredients || []).slice(0, 18).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });
  if ((recipe.steps || []).length) {
    const steps = document.createElement("div");
    steps.innerHTML = "<h4>Yapılış</h4><ul></ul>";
    (recipe.steps || []).slice(0, 10).forEach((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      steps.querySelector("ul").appendChild(li);
    });
    details.appendChild(steps);
  }
  details.addEventListener("click", (event) => event.stopPropagation());
  button.append(top, details);
  button.addEventListener("click", () => {
    const open = details.hidden;
    details.hidden = !open;
    button.setAttribute("aria-expanded", open ? "true" : "false");
  });
  return button;
}
