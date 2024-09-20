from flask import Flask, request, jsonify
import requests
import base64
import os

app = Flask(__name__)

# Configuración de GitHub
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Asegúrate de establecer esto en tu configuración de Vercel
GITHUB_REPO = os.environ.get('GITHUB_REPO')    # Asegúrate de establecer esto también

# Función para encontrar el archivo por nombre en GitHub
def find_file_sha_by_name(file_name):
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{file_name}'
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

# Función para leer HTML desde un archivo en memoria
def leer_html_from_memory(content):
    return content

# Función para insertar el nuevo contenido en la plantilla HTML
def insertar_nuevo_contenido(template_html, nuevo_contenido):
    return template_html.replace("<!-- CONTENIDO -->", nuevo_contenido)

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

        TEMPLATE_HTML_NAME = {
            'MRG': 'template_MRG.html',
            'Rubicon': 'template_Rubi.html',
            'GERP': 'template_GERP.html'
        }

        for company in companies:
            if company not in TEMPLATE_HTML_NAME:
                return jsonify({'error': f'Compañía inválida: {company}'}), 400

            TEMPLATE_NAME = TEMPLATE_HTML_NAME[company]

            template_file_sha = find_file_sha_by_name(TEMPLATE_NAME)
            if not template_file_sha:
                return jsonify({'error': f'No se encontró el archivo de plantilla {TEMPLATE_NAME}'}), 500

            print(f"SHA del archivo de plantilla: {template_file_sha}")

            template_content = get_file_content(TEMPLATE_NAME)
            if template_content is None:
                return jsonify({'error': 'No se pudo obtener el contenido del archivo de plantilla'}), 500

            template_html = leer_html_from_memory(template_content)

            resultado_html = insertar_nuevo_contenido(template_html, body_content)

            upload_file_sha = update_file_content(TEMPLATE_NAME, resultado_html, template_file_sha)
            if upload_file_sha is None:
                return jsonify({'error': f'No se pudo actualizar el archivo en GitHub para la plantilla {TEMPLATE_NAME}'}), 500

        return jsonify({'message': 'Archivos actualizados correctamente para todas las empresas'}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

if __name__ == '__main__':
    app.run()
