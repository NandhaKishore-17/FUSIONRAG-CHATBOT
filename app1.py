import os
import PyPDF2
import streamlit as st

# --- Load PDFs ---
pdf_folder = r"C:\Users\Nandha kishore\Project\data"
pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]

pdf_texts = {}
pdf_page_map = {}

for pdf_file in pdf_files:
    reader = PyPDF2.PdfReader(os.path.join(pdf_folder, pdf_file))
    full_text = ""
    page_map = {}
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        full_text += text + "\n"
        page_map[i + 1] = text  # store text by page number
    pdf_texts[pdf_file] = full_text
    pdf_page_map[pdf_file] = page_map

# --- Streamlit UI ---
st.title("📄 PDF Q&A Viewer")

selected_pdf = st.selectbox("Select a PDF (or choose All PDFs)", ["All PDFs"] + pdf_files)
query = st.text_input("Ask something:")

if st.button("Search") and query:
    results = []
    files_to_search = pdf_files if selected_pdf == "All PDFs" else [selected_pdf]
    
    for pdf_file in files_to_search:
        for page_num, page_text in pdf_page_map[pdf_file].items():
            if query.lower() in page_text.lower():
                snippet = page_text.lower().split(query.lower())[0][-100:] + " " + query + " " + page_text.lower().split(query.lower())[1][:100]
                results.append((pdf_file, page_num, snippet))
    
    if results:
        st.subheader(f"Results for '{query}':")
        for pdf_file, page_num, snippet in results:
            st.markdown(f"**📄 {pdf_file} | Page {page_num}**")
            st.markdown(f"{snippet} ...")
            # Link to local file (opens PDF at page manually)
            file_path = os.path.join(pdf_folder, pdf_file).replace("\\", "/")
            st.markdown(f"[Open PDF](file:///{file_path})")
    else:
        st.info("No results found.")