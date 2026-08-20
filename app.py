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

@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    query = data.get('query')
    marks = data.get('marks', '2')  # Default to 2 marks
    
    if not query:
        return jsonify({'error': 'Empty query'})
        
    if collection.count() == 0:
        return jsonify({'error': 'No documents indexed yet. Please upload a PDF.'})
    
    # Set answer length instructions based on marks
    if marks == '2':
        length_instruction = "You MUST provide a brief and concise answer (3-5 sentences maximum)."
    elif marks == '5':
        length_instruction = "You MUST provide a moderately detailed answer with key points (around 8-12 sentences)."
    elif marks == '10':
        length_instruction = "You MUST provide a detailed and thorough answer with explanations and examples (around 15-25 sentences). Organize with clear points."
    elif marks == '16':
        length_instruction = "You MUST provide a very comprehensive, long, essay-style answer. Cover all aspects in extreme depth with definitions, explanations, and examples. Use headings and bullet points. Write a very detailed response suitable for a 16-mark exam answer."
    else:
        length_instruction = "Provide a clear and helpful answer."
        
    try:
        # 1. Embed query using local Ollama
        query_embedding = get_ollama_embedding(query)
        
        # 2. Query ChromaDB for the top 3 most relevant chunks to keep context optimal
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(3, collection.count())
        )
        
        retrieved_context = "\n\n".join(results['documents'][0])
        sources = []
        for meta in results['metadatas'][0]:
            sources.append(f"{meta['source']} (Page {meta['page']})")
            
        # 3. Generate Answer using local Ollama Qwen model (using /api/chat for instruction-tuned models)
        url = f"{OLLAMA_URL}/api/chat"
        payload = {
            "model": "qwen",
            "messages": [
                {
                    "role": "system",
                    "content": f"You are a helpful academic assistant.\n{length_instruction}\nIf the answer is not in the context, politely explain that the current PDF documents do not seem to contain this information."
                },
                {
                    "role": "user",
                    "content": f"Using the following context as a foundation, answer the question. Feel free to expand with your own academic knowledge to meet the length requirements.\n\nContext:\n{retrieved_context}\n\nQuestion:\n{query}\n\nIMPORTANT REQUIREMENT: {length_instruction}"
                }
            ],
            "options": {
                "num_ctx": 4096,
                "num_predict": 2048,
                "temperature": 0.3
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