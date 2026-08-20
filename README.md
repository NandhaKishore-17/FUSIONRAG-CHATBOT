# FUSIONRAG-CHATBOT 🧠📚

**FUSIONRAG** is a local, privacy-preserving PDF Question Answering web application. It uses a Retrieval-Augmented Generation (RAG) pipeline to ingest PDF documents, store their contents in a vector database, and answer your questions intelligently using entirely local AI models. 

This project requires **NO external API keys** and runs completely on your machine using **Ollama**.

## 🌟 Features

* **Upload & Manage PDFs**: Easily upload multiple PDF documents through a beautiful web interface.
* **Local Vector Database**: Uses **ChromaDB** to chunk and embed documents locally on your disk.
* **Context-Aware AI Answers**: Queries a local LLM via Ollama using the most relevant pages of your PDFs as context.
* **Dynamic Answer Lengths**: Allows users to select how detailed the answer should be based on an exam-style "marks" system (e.g., 2 marks for a short summary, 16 marks for a comprehensive essay).
* **Streaming Responses**: AI responses stream in real-time to the web interface.
* **Privacy First**: Everything is processed locally. Your documents never leave your computer.
* **Streamlit Fallback**: Includes an alternative simple keyword-search interface built with Streamlit (`app1.py`).

## 🛠️ Technology Stack

* **Backend Framework**: [Flask](https://flask.palletsprojects.com/)
* **Vector Database**: [ChromaDB](https://www.trychroma.com/) (Persistent Local Storage)
* **LLM Engine**: [Ollama](https://ollama.com/)
* **Embeddings Model**: `nomic-embed-text` (via Ollama)
* **Chat Model**: `qwen` (via Ollama)
* **PDF Processing**: `PyPDF2`
* **Frontend**: Custom HTML, CSS (Vanilla), and JavaScript

---

## 🚀 Getting Started

### 1. Prerequisites

Before running the application, make sure you have the following installed:
* **Python 3.8+**
* **Ollama**: Download and install from [ollama.com](https://ollama.com/)

### 2. Pull Required AI Models

You need to pull the specific models used by this application into your local Ollama instance. Open a terminal and run:

```bash
ollama pull nomic-embed-text
ollama pull qwen
```

*(Note: Ensure the Ollama server is running in the background before pulling or running the app.)*

### 3. Clone the Repository

```bash
git clone https://github.com/NandhaKishore-17/FUSIONRAG-.git
cd FUSIONRAG-
```

### 4. Set Up a Virtual Environment (Recommended)

```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

### 5. Install Dependencies

Install the required Python packages using the provided `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 6. Run the Application

Start the Flask server:

```bash
python app.py
```

The application will now be available in your web browser at: **`http://127.0.0.1:5000`**

---

## 📖 How to Use

1. **Upload**: Use the file uploader on the left sidebar to add PDF files. The system will automatically extract text, create embeddings, and save them to ChromaDB.
2. **Select Detail Level**: Choose the desired length of your answer using the "Marks" dropdown (2, 5, 10, or 16 Marks).
3. **Ask Questions**: Type a question about the contents of your PDFs into the chat box and hit send. 
4. **View Sources**: The app will display which document and page number it used to generate the answer.
5. **Manage Files**: You can delete previously uploaded PDFs from the sidebar. (Note: This deletes the file from disk, but vector embeddings are preserved for speed).

## 🗂️ Project Structure

```text
📦 FUSIONRAG-
 ┣ 📂 chroma_db/        # Auto-generated ChromaDB persistent storage (Git-ignored)
 ┣ 📂 data/             # Uploaded PDF files are stored here (Git-ignored)
 ┣ 📂 static/           # CSS and JS files for the frontend
 ┃ ┣ 📜 script.js       # Frontend logic and Server-Sent Events (SSE) handling
 ┃ ┗ 📜 style.css       # Application styling
 ┣ 📂 templates/        # HTML templates
 ┃ ┗ 📜 index.html      # Main application interface
 ┣ 📜 app.py            # Main Flask application and RAG backend
 ┣ 📜 app1.py           # Alternative Streamlit app (Simple keyword search)
 ┣ 📜 requirements.txt  # Python dependencies
 ┗ 📜 .gitignore        # Ignored files for Git
```

## ⚠️ Troubleshooting

* **`Cannot connect to Ollama`**: Ensure the Ollama application is running on your machine.
* **`Model not found` errors**: Make sure you have pulled `nomic-embed-text` and `qwen` via the `ollama pull` command.
* **No context found**: Ensure the PDF you uploaded contains selectable text (not just scanned images). `PyPDF2` requires actual text characters to extract.

---
