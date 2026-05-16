from flask import Flask, request, jsonify
import pymupdf
import pandas as pd
import io
import base64

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "message": "PDF Parser API is running",
        "endpoints": {
            "/parse-pdf": "POST - Send a PDF file to extract text, tables, and images",
            "/health": "GET - Check if server is running"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "alive"})

@app.route('/parse-pdf', methods=['POST'])
def parse_pdf():
    try:
        # Check if file is present
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file provided"}), 400
        
        pdf_file = request.files['pdf']
        
        if pdf_file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        # Read the PDF file
        pdf_bytes = pdf_file.read()
        
        # Open with PyMuPDF
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract text from all pages
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
        
        # Extract images (as base64)
        images_list = []
        for page_num, page in enumerate(doc):
            image_list = page.get_images()
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    pix = pymupdf.Pixmap(doc, xref)
                    if pix.n - pix.alpha < 4:  # Can save as PNG
                        img_bytes = pix.tobytes("png")
                        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                        images_list.append({
                            "page": page_num + 1,
                            "image_index": img_idx + 1,
                            "width": pix.width,
                            "height": pix.height,
                            "base64": img_base64[:100] + "...",  # Truncated for response size
                            "size": len(img_bytes)
                        })
                    pix = None
                except Exception as e:
                    images_list.append({
                        "page": page_num + 1,
                        "image_index": img_idx + 1,
                        "error": str(e)
                    })
        
        doc.close()
        
        return jsonify({
            "success": True,
            "filename": pdf_file.filename,
            "page_count": len(doc),
            "text": full_text[:5000],  # Limit text size for response
            "text_length": len(full_text),
            "tables": tables_list,
            "images": images_list,
            "full_text_available": len(full_text) > 5000
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)