from flask import Flask, request, jsonify, render_template
import pymupdf
import pandas as pd
import io
import base64
import os
import traceback
import requests

app = Flask(__name__)

# Serve the main webpage
@app.route('/')
def home():
    return render_template('index.html')

# Health check
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "alive"})

# PDF parsing from FILE UPLOAD
@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        pdf_file = request.files['pdf']
        
        if pdf_file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        # Check if file is empty
        pdf_bytes = pdf_file.read()
        if len(pdf_bytes) == 0:
            return jsonify({"error": "The PDF file is empty (0 bytes)"}), 400
        
        return process_pdf(pdf_bytes, pdf_file.filename)
    
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# PDF parsing from URL
@app.route('/parse-pdf-url', methods=['POST'])
def parse_pdf_url():
    try:
        data = request.get_json()
        pdf_url = data.get('url')
        
        if not pdf_url:
            return jsonify({"error": "No URL provided"}), 400
        
        # Download PDF from URL
        try:
            response = requests.get(pdf_url, timeout=30)
        except requests.exceptions.Timeout:
            return jsonify({"error": "Download timeout. The PDF file took too long to load."}), 500
        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"Failed to download PDF: {str(e)}"}), 500
        
        if response.status_code != 200:
            return jsonify({"error": f"Failed to download PDF. HTTP Status: {response.status_code}"}), 400
        
        # Check if content is PDF
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower() and not pdf_url.lower().endswith('.pdf'):
            return jsonify({"error": "URL does not point to a PDF file"}), 400
        
        pdf_bytes = response.content
        if len(pdf_bytes) == 0:
            return jsonify({"error": "Downloaded PDF file is empty"}), 400
        
        # Extract filename from URL
        filename = pdf_url.split('/')[-1]
        if not filename.endswith('.pdf'):
            filename = filename + '.pdf'
        
        return process_pdf(pdf_bytes, filename)
    
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# Shared PDF processing function
def process_pdf(pdf_bytes, filename):
    try:
        # Try to open the PDF
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        except Exception as pdf_error:
            return jsonify({"error": f"Cannot open PDF: {str(pdf_error)}"}), 400
        
        if len(doc) == 0:
            doc.close()
            return jsonify({"error": "The PDF has no pages"}), 400
        
        # Extract text
        full_text = ""
        for page_num, page in enumerate(doc):
            try:
                page_text = page.get_text()
                if page_text:
                    full_text += f"\n--- Page {page_num + 1} ---\n"
                    full_text += page_text
                else:
                    full_text += f"\n--- Page {page_num + 1} (no text found) ---\n"
            except Exception as e:
                full_text += f"\n--- Page {page_num + 1} (error extracting text: {str(e)}) ---\n"
        
        # Extract tables
        tables_list = []
        for page_num, page in enumerate(doc):
            try:
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    for tab_idx, tab in enumerate(tabs):
                        try:
                            df = tab.to_pandas()
                            tables_list.append({
                                "page": page_num + 1,
                                "table_index": tab_idx + 1,
                                "data": df.to_dict(orient='records')[:50],
                                "headers": df.columns.tolist()
                            })
                        except Exception as e:
                            tables_list.append({
                                "page": page_num + 1,
                                "error": f"Table extraction failed: {str(e)}"
                            })
            except Exception as e:
                tables_list.append({
                    "page": page_num + 1,
                    "error": f"Table detection failed: {str(e)}"
                })
        
        page_count = len(doc)
        doc.close()
        
        return jsonify({
            "success": True,
            "filename": filename,
            "page_count": page_count,
            "text": full_text[:10000],
            "text_length": len(full_text),
            "tables": tables_list,
            "full_text_available": len(full_text) > 10000
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
