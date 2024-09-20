from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
import os
import base64
import logging

app = Flask(__name__)
CORS(app)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de GitHub
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Cambia esto para leer el token de las variables de entorno
logger.info(f"GITHUB_TOKEN: {GITHUB_TOKEN}")  # Esto es solo para debugging, retíralo después


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

# Función para encontrar el archivo por nombre en GitHub
def find_file_sha_by_name(file_name):
    url = f'https://api.github.com/repos/Debombii/React/contents/src/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    logger.info(f"Buscando SHA para el archivo: {file_name}")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        sha = response.json()['sha']
        logger.info(f"SHA encontrado: {sha}")
        return sha
    logger.error(f"Error al buscar SHA para {file_name}: {response.status_code} - {response.text}")
    return None

# Función para obtener el contenido del archivo desde GitHub
def get_file_content(file_name):
    url = f'https://api.github.com/repos/Debombii/React/contents/src/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    logger.info(f"Obteniendo contenido del archivo: {file_name}")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        content = base64.b64decode(response.json()['content']).decode('utf-8')
        logger.info(f"Contenido obtenido correctamente para {file_name}")
        return content
    logger.error(f"Error al obtener contenido de {file_name}: {response.status_code} - {response.text}")
    return None

# Función para actualizar el contenido del archivo en GitHub
def update_file_content(file_name, content, sha):
    url = f'https://api.github.com/repos/Debombii/React/contents/src/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    
    # Codificar el contenido en base64
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    data = {
        'message': 'Updating file content',
        'content': encoded_content,
        'sha': sha
    }
    logger.info(f"Actualizando archivo: {file_name}")
    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 200:
        new_sha = response.json()['content']['sha']
        logger.info(f"Archivo {file_name} actualizado correctamente. Nuevo SHA: {new_sha}")
        return new_sha
    logger.error(f"Error al actualizar el archivo {file_name}: {response.status_code} - {response.text}")
    return None

# Función para insertar el nuevo contenido en la plantilla HTML
def insertar_nuevo_contenido(template_html, nuevo_contenido):
    return template_html.replace("<!-- CONTENIDO -->", nuevo_contenido)

# Función para manejar la actualización de archivos de manera secuencial
def update_files(companies, body_content):
    try:
        TEMPLATE_HTML_NAME = {
            'MRG': 'template_MRG.html',
            'Rubicon': 'template_Rubi.html',
            'GERP': 'template_GERP.html'
        }

        for company in companies:
            if company not in TEMPLATE_HTML_NAME:
                logger.warning(f'Compañía inválida: {company}')
                continue

            TEMPLATE_NAME = TEMPLATE_HTML_NAME[company]

            # Buscar el archivo de plantilla en GitHub
            template_file_sha = find_file_sha_by_name(TEMPLATE_NAME)
            if not template_file_sha:
                logger.error(f'Error: No se encontró el archivo de plantilla {TEMPLATE_NAME}')
                continue

            # Obtener la plantilla desde GitHub
            template_content = get_file_content(TEMPLATE_NAME)
            if template_content is None:
                logger.error(f'Error: No se pudo obtener el contenido del archivo de plantilla {TEMPLATE_NAME}')
                continue

            # Insertar el nuevo contenido en la plantilla
            resultado_html = insertar_nuevo_contenido(template_content, body_content)

            # Subir el archivo actualizado a GitHub
            upload_file_sha = update_file_content(TEMPLATE_NAME, resultado_html, template_file_sha)
            if upload_file_sha is None:
                logger.error(f'Error: No se pudo actualizar el archivo en GitHub para la plantilla {TEMPLATE_NAME}')
                continue

            logger.info(f'Archivo actualizado correctamente para {company}')

        logger.info('Archivos actualizados correctamente para todas las empresas')

    except Exception as e:
        logger.error(f'Error: {e}')

# Endpoint para recibir la compañía y contenido en lugar de un archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    try:
        data = request.json
        logger.info(f"Datos recibidos: {data}")

        body_content = data.get('bodyContent')
        companies = data.get('companies', [])

        if not body_content:
            return jsonify({'error': 'No se envió contenido'}), 400

        if not companies:
            return jsonify({'error': 'No se enviaron compañías'}), 400

        # Ejecutar la actualización de archivos
        update_files(companies, body_content)

        return jsonify({'message': 'Los archivos se han actualizado correctamente'}), 200

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
