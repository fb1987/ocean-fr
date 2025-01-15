import os
import pandas as pd
import re
import openai
import time
from flask import Flask, request, jsonify, send_file, render_template
from werkzeug.utils import secure_filename

# Flask app configuration
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Load environment variables
openai.api_key = os.getenv('OPENAI_API_KEY')

# Function to check for overlap between NB Legend terms and product strings
def find_matches(english_terms, product_string, glossary):
    product_string = str(product_string).lower()  # Convert product string to lowercase
    found_terms = []
    for term in english_terms:
        if isinstance(term, str):
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            if re.search(pattern, product_string):
                found_terms.append(f"{term} ({glossary[term.lower()]})")
    return found_terms

# Function to translate a string using GPT-4 and incorporate glossary terms
def translate_string(text, found_terms):
    if found_terms:
        glossary_terms = "\n".join(found_terms)
        prompt = f"Translate the following string to Canadian French. Ensure you use the appropriate translations for these terms:\n\n{glossary_terms}\n\n{text}"
    else:
        prompt = f"Translate the following string to Canadian French:\n\nText: {text}"

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a professional software product translator specialized in Canadian French translations for a healthcare IT audience. You never translate terms within curly brackets and you avoid changing punctuation marks."},
            {"role": "user", "content": prompt}
        ]
    )
    translated_text = response['choices'][0]['message']['content'].strip()
    return translated_text

# Function to process and translate the uploaded file
def process_file(file_path):
    # Load the NB Legend Excel file
    nb_legend_df = pd.read_excel('NB Legend.xlsx')
    glossary = dict(zip(nb_legend_df['English'].str.lower(), nb_legend_df['French']))
    english_terms = nb_legend_df['English'].tolist()

    # Load the uploaded file
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # Prepare for translation
    product_strings = df['English'].to_dict()
    translations = []

    # Translate in batches
    batch_size = 20
    for i in range(0, len(product_strings), batch_size):
        batch = list(product_strings.items())[i:i+batch_size]
        for product_code, product_string in batch:
            found_terms = find_matches(english_terms, product_string, glossary)
            translated_string = translate_string(product_string, found_terms)
            translations.append({
                'Code Location': product_code,
                'Product String': product_string,
                'Translated String': translated_string,
                'NB Legend Term(s)': ', '.join(found_terms) if found_terms else None
            })

    # Save results
    output_file = os.path.join(app.config['OUTPUT_FOLDER'], 'translated_file.xlsx')
    pd.DataFrame(translations).to_excel(output_file, index=False)
    return output_file

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    # Handle file upload
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Process the file
    output_file = process_file(file_path)
    return send_file(output_file, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
