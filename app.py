from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
import os
import base64
import logging
import re

app = Flask(__name__)
CORS(app)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de GitHub
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Asegúrate de que tu token esté configurado en las variables de entorno

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

# Función para encontrar el archivo por nombre en GitHub
def find_file_sha_by_name(file_name):
    url = f'https://api.github.com/repos/Debombii/React/contents/{file_name}'  # Asegúrate de que la ruta sea correcta
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    logger.error(f"Buscando SHA para el archivo: {file_name}")
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        sha = response.json()['sha']
        logger.error(f"SHA encontrado: {sha}")
        return sha
    logger.error(f"Error al buscar SHA para {file_name}: {response.status_code} - {response.text}")
    return None

# Función para obtener el contenido del archivo desde GitHub
def get_file_content(file_name):
    url = f'https://api.github.com/repos/Debombii/React/contents/{file_name}'  # Asegúrate de que la ruta sea correcta
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    logger.error(f"Obteniendo contenido del archivo: {file_name}")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        content = base64.b64decode(response.json()['content']).decode('utf-8')
        logger.error(f"Contenido obtenido correctamente para {file_name}")
        return content
    logger.error(f"Error al obtener contenido de {file_name}: {response.status_code} - {response.text}")
    return None

# Función para actualizar el contenido del archivo en GitHub
def update_file_content(file_name, content, sha):
    url = f'https://api.github.com/repos/Debombii/React/contents/{file_name}'  # Asegúrate de que la ruta sea correcta
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    
    # Codificar el contenido en base64
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    data = {
        'message': 'Updating file content',
        'content': encoded_content,
        'sha': sha
    }
    logger.error(f"Actualizando archivo: {file_name}")
    response = requests.put(url, json=data, headers=headers)

    if response.status_code == 200:
        new_sha = response.json()['content']['sha']
        logger.error(f"Archivo {file_name} actualizado correctamente. Nuevo SHA: {new_sha}")
        return new_sha
    logger.error(f"Error al actualizar el archivo {file_name}: {response.status_code} - {response.text}")
    return None

# Función para insertar el nuevo contenido en la plantilla HTML
def insertar_nuevo_contenido(template_html, new_div_html):
    titulo_match = re.search(r'<h2 id="(.*?)">(.*?)</h2>', new_div_html)
    date_match = re.search(r'<p class=\'date\' id="date">(.*?)</p>', new_div_html)

    if not titulo_match:
        logger.error("No se encontró un título en el contenido nuevo.")
        return None  # O manejarlo de otra manera

    if not date_match:
        logger.error("No se encontró una fecha en el contenido nuevo.")
        return None  # O manejarlo de otra manera

    id_titulo = titulo_match.group(1)
    titulo = titulo_match.group(2)
    date = date_match.group(1)

    # Insertar el nuevo contenido en la sección correspondiente
    template_html = re.sub(r'(<div class="content">)', r'\1\n' + new_div_html, template_html, 1)

    # Crear nueva entrada en el índice
    nueva_entrada_indice = f'<li><a href="#{id_titulo}">{titulo} - {date}</a></li>'
    template_html = re.sub(r'(<ul id="indice">)', r'\1\n' + nueva_entrada_indice, template_html, 1)

    return template_html



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

            if resultado_html is None:
                logger.error(f'Error al insertar contenido en la plantilla para {company}.')
                continue

            # Subir el archivo actualizado a GitHub
            upload_file_sha = update_file_content(TEMPLATE_NAME, resultado_html, template_file_sha)
            if upload_file_sha is None:
                logger.error(f'Error: No se pudo actualizar el archivo en GitHub para la plantilla {TEMPLATE_NAME}')
                continue

            logger.error(f'Archivo actualizado correctamente para {company}')

        logger.error('Archivos actualizados correctamente para todas las empresas')

    except Exception as e:
        logger.error(f'Error: {e}')

# Endpoint para recibir la compañía y contenido en lugar de un archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    try:
        data = request.json
        logger.error(f"Datos recibidos: {data}")

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
