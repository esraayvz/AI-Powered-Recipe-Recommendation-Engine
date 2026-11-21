# AI-Powered-Recipe-Recommendation-Engine
A hybrid recipe recommendation system that understands natural Turkish sentences, selects up to 5 of the most suitable recipes from 3,310 real Turkish cuisine recipes, and explains why each is recommended.

**Technologies Used:** Python, HTML, CSS, JavaScript, Groq API Key (the `openai/gpt-oss-120b` language model/LLM layer that helps read the sentence, suggest what goes well with it, and write the reason under the card; it does not see the recipe list, and if turned off, the program continues with code), BM25 (a search ranking algorithm that scores recipes by filtering out conjunctions/stop words and weighting words that distinguish a recipe from others).

**Project Structure**

recipe-recommender/
├── py/
│   ├── app.py           # Acts as the gateway; opens the page, receives the sentence, and sends the response back
│   ├── intent.py        # Turns the sentence into a card: category, ingredients, duration, difficulty
│   ├── retrieve.py      # Selects recipes from the file using that card
│   ├── words.py         # Splits and scores words
│   ├── explain.py       # Writes why it was selected under the card
│   └── llm.py           # Sends the query to the AI
├── site/
│   ├── index.html       # Skeleton of the page
│   ├── app.css          # Color and layout
│   └── app.js           # Sends the sentence and draws the cards
└── data/
    └── recipes.json     # Recipe list

To run it, open the terminal inside the recipe-recommender\py folder and type python app.py.
