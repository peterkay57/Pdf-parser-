from flask import Flask, request, jsonify, render_template
import pymupdf
import pandas as pd
import io
import base64
import os

app = Flask(__name__)

# Serve the main webpage
@app.route('/')
def home():
    return render_template('index.html')

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "alive"})

# PDF parsing API (same as before)
@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        pdf_file = request.files['pdf']
        
        if pdf_file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        pdf_bytes = pdf_file.read()
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract text
        full_text = ""
        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            full_text += f"\n--- Page {page_num + 1} ---\n"
            full_text += page_text
        
        # Extract tables
        tables_list = []
        for page_num, page in enumerate(doc):
            tabs = page.find_tables()
            if tabs.tables:
                for tab_idx, tab in enumerate(tabs):
                    try:
                        df = tab.to_pandas()
                        tables_list.append({
                            "page": page_num + 1,
                            "table_index": tab_idx + 1,
                            "data": df.to_dict(orient='records'),
                            "headers": df.columns.tolist()
                        })
                    except Exception as e:
                        tables_list.append({
                            "page": page_num + 1,
                            "table_index": tab_idx + 1,
                            "error": str(e)
                        })
        
        doc.close()
        
        return jsonify({
            "success": True,
            "filename": pdf_file.filename,
            "page_count": len(doc),
            "text": full_text[:10000],
            "text_length": len(full_text),
            "tables": tables_list,
            "full_text_available": len(full_text) > 10000
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
