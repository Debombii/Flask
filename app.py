from flask import Flask, request, jsonify, send_from_directory
import requests
import base64
import os

app = Flask(__name__)

# Configuración de GitHub
GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'
GITHUB_REPO = 'YOUR_GITHUB_USER/YOUR_REPO_NAME'

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

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

# Endpoint para recibir la compañía y contenido en lugar de un archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    # Tu código para manejar el endpoint aquí...
    pass

if __name__ == '__main__':
    app.run(debug=True)
