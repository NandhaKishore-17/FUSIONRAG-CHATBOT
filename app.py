import PyPDF2
import os
import requests
import chromadb
import json
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = r"C:\Users\Nandha kishore\Project\data/"

OLLAMA_URL = "http://localhost:11434"
CHROMA_DB_DIR = "chroma_db"
MODEL_NAME = "qwen2.5:1.5b"

# Initialize ChromaDB with persistent local storage
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
collection = chroma_client.get_or_create_collection(
    name="pdf_documents",
    metadata={"hnsw:space": "cosine"}
)

print(f"ChromaDB loaded. {collection.count()} chunks already indexed.")

def get_ollama_embedding(text):
    """Get embeddings from local Ollama instance"""
    url = f"{OLLAMA_URL}/api/embeddings"
    payload = {
        "model": "nomic-embed-text",
        "prompt": text
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()['embedding']

def embed_and_add_pdf(file_path, file_name):
    """Extract text from PDF, generate embeddings via Ollama, store in ChromaDB"""
    reader = PyPDF2.PdfReader(file_path)
    new_docs = []
    new_meta = []
    new_ids = []
    
    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text and len(page_text.strip()) > 10:
            doc_id = f"{file_name}_page_{page_num + 1}"
            # Skip if this page is already indexed
            existing = collection.get(ids=[doc_id])
            if existing and existing['ids']:
                continue
            new_docs.append(page_text)
            new_meta.append({"source": file_name, "page": page_num + 1})
            new_ids.append(doc_id)
            
    if not new_docs:
        print(f"{file_name}: All pages already indexed.")
        return
        
    print(f"Generating embeddings for {len(new_docs)} new pages from {file_name}...")
    new_embeddings = []
    for doc in new_docs:
        emb = get_ollama_embedding(doc)
        new_embeddings.append(emb)
        
    # Add to ChromaDB (persists automatically to disk)
    collection.add(
        ids=new_ids,
        documents=new_docs,
        embeddings=new_embeddings,
        metadatas=new_meta
    )
    print(f"Added {len(new_docs)} pages. Total chunks in DB: {collection.count()}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/files', methods=['GET'])
def list_files():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        return jsonify({'files': []})
    
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.pdf')]
    return jsonify({'files': files})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
        
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            embed_and_add_pdf(file_path, filename)
            return jsonify({'success': True, 'message': 'File uploaded and processed'})
        except requests.exceptions.ConnectionError:
            return jsonify({'error': 'Cannot connect to Ollama. Make sure Ollama is running and you have pulled nomic-embed-text.'})
        except Exception as e:
            return jsonify({'error': str(e)})
            
    return jsonify({'error': 'Invalid file type'})

@app.route('/delete', methods=['POST'])
def delete_file():
    data = request.json
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'No filename provided'})
    
    # Delete the PDF file from disk only (vectors stay in ChromaDB)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Deleted file: {filename} (vectors preserved in ChromaDB)")
        return jsonify({'success': True, 'message': f'{filename} removed from list'})
    else:
        return jsonify({'error': 'File not found'})

CASUAL_PATTERNS = [
    'hi', 'hello', 'hey', 'hii', 'hiii', 'yo', 'sup', 'hola', 'howdy',
    'good morning', 'good afternoon', 'good evening', 'good night',
    'how are you', 'what\'s up', 'whats up', 'wassup',
    'thanks', 'thank you', 'bye', 'goodbye', 'see you',
    'who are you', 'what can you do', 'help', 'what are you',
    'nice', 'cool', 'okay', 'ok', 'great', 'awesome', 'wow',
]

def is_casual_query(query):
    """Check if the query is a casual/conversational message that doesn't need RAG"""
    cleaned = query.lower().strip().rstrip('?!.,')
    # Direct match
    if cleaned in CASUAL_PATTERNS:
        return True
    # Short greetings (1-4 words, no academic terms)
    words = cleaned.split()
    if len(words) <= 4:
        for pattern in CASUAL_PATTERNS:
            if pattern in cleaned:
                return True
    return False

@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    query = data.get('query')
    marks = data.get('marks', None)  # None if not provided (normal mode)
    
    if not query:
        return jsonify({'error': 'Empty query'})
    
    # Handle casual / conversational queries without RAG
    if is_casual_query(query):
        url = f"{OLLAMA_URL}/api/chat"
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "You are FusionRAG, a friendly AI study assistant. Respond naturally and conversationally. Keep your response short and friendly. You help students by answering questions from their uploaded PDF documents."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "options": {
                "num_ctx": 2048,
                "num_predict": 256,
                "temperature": 0.7
            },
            "stream": True
        }
        
        def generate_casual():
            # No sources for casual chat
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            try:
                response = requests.post(url, json=payload, stream=True, timeout=60)
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if 'message' in chunk and 'content' in chunk['message']:
                            content = chunk['message']['content']
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                yield "data: [DONE]\n\n"
            except requests.exceptions.ConnectionError:
                yield f"data: {json.dumps({'error': 'Cannot connect to Ollama.'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(generate_casual(), mimetype='text/event-stream')
        
    if collection.count() == 0:
        return jsonify({'error': 'No documents indexed yet. Please upload a PDF first.'})
    
    # Set answer length instructions based on marks (only if marks is provided)
    if marks == '2':
        length_instruction = (
            "Write a SHORT answer of about 5 lines (roughly 80-100 words). "
            "Be concise but complete. Use 2-3 clear sentences to define or explain the concept."
        )
        num_predict = 512
        num_ctx = 4096
    elif marks == '5':
        length_instruction = (
            "Write a MEDIUM-LENGTH answer of about 15 lines (roughly 250-350 words). "
            "Structure your answer with:\n"
            "- A brief introduction (1-2 sentences)\n"
            "- Key points explained clearly using bullet points or numbered lists\n"
            "- A short conclusion if appropriate\n"
            "Use markdown formatting: **bold** for key terms, bullet points for lists."
        )
        num_predict = 1024
        num_ctx = 4096
    elif marks == '10':
        length_instruction = (
            "Write a LONG, DETAILED answer of about 30 lines (roughly 500-650 words). "
            "You MUST structure your answer professionally like a textbook:\n"
            "- Start with a clear **Introduction** defining the topic\n"
            "- Use **numbered points** or **subheadings** for each major idea\n"
            "- Explain each point in 2-3 sentences with examples where possible\n"
            "- Include a brief **Conclusion** summarizing the key takeaways\n"
            "Use markdown formatting: ## for headings, **bold** for key terms, "
            "bullet points and numbered lists for organization. "
            "Do NOT write a single paragraph — break it into clear sections."
        )
        num_predict = 2048
        num_ctx = 4096
    elif marks == '16':
        length_instruction = (
            "Write a VERY LONG, COMPREHENSIVE, essay-style answer of about 60 lines (roughly 1000-1300 words). "
            "This is a high-marks exam answer and MUST be extremely detailed and well-structured.\n\n"
            "MANDATORY STRUCTURE:\n"
            "## Introduction\n"
            "Define the topic and provide context (3-4 sentences).\n\n"
            "## Main Body\n"
            "Cover ALL aspects of the topic. Use **multiple subheadings** (### Subheading) for each major concept. "
            "Under each subheading:\n"
            "- Provide a clear definition\n"
            "- Explain with detailed reasoning (3-5 sentences per point)\n"
            "- Give real-world examples or illustrations\n"
            "- Use bullet points, numbered lists, and **bold key terms**\n\n"
            "## Key Features / Characteristics / Advantages (if applicable)\n"
            "List and explain relevant features in bullet points.\n\n"
            "## Conclusion\n"
            "Summarize the main points in 3-4 sentences.\n\n"
            "IMPORTANT: Do NOT write a single paragraph. Use headings, subheadings, bullet points, "
            "and numbered lists extensively. The answer must look like a well-organized textbook chapter. "
            "Write AT LEAST 1000 words."
        )
        num_predict = 4096
        num_ctx = 8192
    else:
        length_instruction = (
            "Provide a clear, helpful, and well-structured answer. "
            "Use bullet points or numbered lists if there are multiple points. "
            "Use **bold** for key terms."
        )
        num_predict = 2048
        num_ctx = 4096
        
    try:
        # 1. Embed query using local Ollama
        query_embedding = get_ollama_embedding(query)
        
        # 2. Query ChromaDB for relevant chunks (more chunks for higher marks)
        n_chunks = 3 if marks not in ('10', '16') else min(5, collection.count())
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_chunks, collection.count())
        )
        
        retrieved_context = "\n\n".join(results['documents'][0])
        sources = []
        for meta in results['metadatas'][0]:
            sources.append(f"{meta['source']} (Page {meta['page']})")
            
        # 3. Generate Answer using local Ollama Qwen model
        url = f"{OLLAMA_URL}/api/chat"
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are FusionRAG, an expert academic assistant that writes well-structured, "
                        "detailed exam answers. You ALWAYS format your answers using markdown with headings, "
                        "subheadings, bullet points, numbered lists, and bold text for key terms. "
                        "You NEVER write a single unformatted paragraph. "
                        "If the answer is not in the context, politely explain that the uploaded documents "
                        "do not seem to contain this information, but still try to answer from your own knowledge.\n\n"
                        f"LENGTH REQUIREMENT:\n{length_instruction}"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Answer the following question using the provided context as your primary source. "
                        f"Supplement with your own academic knowledge to ensure the answer is complete and meets "
                        f"the required length.\n\n"
                        f"**Context from uploaded documents:**\n{retrieved_context}\n\n"
                        f"**Question:** {query}\n\n"
                        f"**CRITICAL:** {length_instruction}\n"
                        f"Format your answer with proper markdown: use ## headings, ### subheadings, "
                        f"**bold key terms**, bullet points (- ), and numbered lists (1. 2. 3.). "
                        f"DO NOT write a wall of text."
                    )
                }
            ],
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": 0.4,
                "repeat_penalty": 1.1
            },
            "stream": True
        }
        
        def generate():
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
            try:
                response = requests.post(url, json=payload, stream=True, timeout=300)
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if 'message' in chunk and 'content' in chunk['message']:
                            content = chunk['message']['content']
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                yield "data: [DONE]\n\n"
            except requests.exceptions.ConnectionError:
                yield f"data: {json.dumps({'error': 'Cannot connect to Ollama. Make sure it is installed and running on your machine.'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': f'Internal Server Error: {str(e)}'})}\n\n"

        return Response(generate(), mimetype='text/event-stream')
        
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Cannot connect to Ollama. Make sure it is installed and running on your machine.'})
    except Exception as e:
        return jsonify({'error': f"Internal Server Error: {str(e)}"})

if __name__ == '__main__':
    print("\n" + "="*50)
    print(" SERVER IS READY!")
    print("Open your web browser and go to: http://127.0.0.1:5000")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)