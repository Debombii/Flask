from flask import Flask, request, jsonify, render_template, send_from_directory
import requests
import os
import base64
import threading

app = Flask(__name__)

# Configuración de GitHub
GITHUB_TOKEN = 'GITHUB_TOKEN'
GITHUB_REPO = 'Debombii/React'

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

# Función para encontrar el archivo por nombre en GitHub
def find_file_sha_by_name(file_name):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/src/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()['sha']
    return None

# Función para obtener el contenido del archivo desde GitHub
def get_file_content(file_name):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return base64.b64decode(response.json()['content']).decode('utf-8')
    return None

# Función para actualizar el contenido del archivo en GitHub
def update_file_content(file_name, content, sha):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    
    # Codificar el contenido en base64
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    data = {
        'message': 'Updating file content',
        'content': encoded_content,
        'sha': sha
    }
    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 200:
        return response.json()['content']['sha']
    return None

# Función para insertar el nuevo contenido en la plantilla HTML
def insertar_nuevo_contenido(template_html, nuevo_contenido):
    return template_html.replace("<!-- CONTENIDO -->", nuevo_contenido)

# Función para manejar la actualización de archivos en segundo plano
def update_files(companies, body_content):
    try:
        TEMPLATE_HTML_NAME = {
            'MRG': 'template_MRG.html',
            'Rubicon': 'template_Rubi.html',
            'GERP': 'template_GERP.html'
        }

        for company in companies:
            if company not in TEMPLATE_HTML_NAME:
                print(f'Compañía inválida: {company}')
                continue  # O manejar error de otra forma

            TEMPLATE_NAME = TEMPLATE_HTML_NAME[company]

            # Buscar el archivo de plantilla en GitHub
            template_file_sha = find_file_sha_by_name(TEMPLATE_NAME)
            if not template_file_sha:
                print(f'No se encontró el archivo de plantilla {TEMPLATE_NAME}')
                continue

            # Obtener la plantilla desde GitHub
            template_content = get_file_content(TEMPLATE_NAME)
            if template_content is None:
                print('No se pudo obtener el contenido del archivo de plantilla')
                continue

            # Insertar el nuevo contenido en la plantilla
            resultado_html = insertar_nuevo_contenido(template_content, body_content)

            # Subir el archivo actualizado a GitHub
            upload_file_sha = update_file_content(TEMPLATE_NAME, resultado_html, template_file_sha)
            if upload_file_sha is None:
                print(f'No se pudo actualizar el archivo en GitHub para la plantilla {TEMPLATE_NAME}')
                continue

        print('Archivos actualizados correctamente para todas las empresas')
    
    except Exception as e:
        print(f'Error: {e}')

# Endpoint para recibir la compañía y contenido en lugar de un archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    try:
        data = request.json
        print(f"Datos recibidos: {data}")

        body_content = data.get('bodyContent')
        companies = data.get('companies', [])

        if not body_content:
            return jsonify({'error': 'No se envió contenido'}), 400

        if not companies:
            return jsonify({'error': 'No se enviaron compañías'}), 400

        # Ejecutar la actualización de archivos en segundo plano
        thread = threading.Thread(target=update_files, args=(companies, body_content))
        thread.start()

        return jsonify({'message': 'Los archivos se están actualizando en segundo plano'}), 202

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
