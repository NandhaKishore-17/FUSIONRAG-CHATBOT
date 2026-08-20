import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load files
f1 = os.listdir(r"C:\Users\Nandha kishore\PROJECT\data")

d1 = {}
for i in f1:
    if i.endswith('.txt'):
        content = open("data/" + i, 'r').read()
        d1[i] = content.lower()

# Single input
query = input("Enter the query: ").lower()
words = query.split()

# -------------------------------
# 🔹 METHOD 1: Keyword Frequency
# -------------------------------
keyword_result = {}

for i in d1:
    count = 0
    for j in words:
        count += d1[i].count(j)
    if count > 0:
        keyword_result[i] = count

keyword_result = sorted(keyword_result.items(), key=lambda x: x[1], reverse=True)

print("\n🔍 Keyword Search Results:")
for i, j in keyword_result:
    print(i, j)

# -------------------------------
# 🔹 METHOD 2: TF-IDF Search
# -------------------------------
docs = list(d1.values())
file_names = list(d1.keys())

all_text = [query] + docs

vectorizer = TfidfVectorizer()
vectors = vectorizer.fit_transform(all_text)

similarity = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

tfidf_results = list(zip(file_names, similarity))
tfidf_results = sorted(tfidf_results, key=lambda x: x[1], reverse=True)

print("\n🤖 Smart Search (TF-IDF) Results:")
for file, score in tfidf_results:
    if score > 0:
        print(file, round(score, 3))