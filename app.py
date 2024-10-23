import os
import re
import logging
import traceback
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
import base64

app = Flask(__name__)
CORS(app)

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Token de GitHub desde variables de entorno
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

# Función para obtener el contenido del archivo
def get_file_content(file_name):
    url = f'https://api.github.com/repos/Debombii/React/contents/public/{file_name}'
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
    url = f'https://api.github.com/repos/Debombii/React/contents/public/{file_name}'
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

# Función para eliminar un log por título
def eliminar_log_por_titulo(file_name, titulo):
    content = get_file_content(file_name)
    if content is None:
        logger.error(f"No se pudo obtener el contenido del archivo: {file_name}")
        return None
    
    # Usar una expresión regular para encontrar y eliminar el div con class 'version' que contenga el título específico
    nuevo_contenido = re.sub(
        rf"<div class='version'>.*?<h3 class=\"titulo\" id=\"{titulo}\">.*?</div>",
        "", 
        content, 
        flags=re.DOTALL
    )
    
    # Registro de la eliminación
    if content != nuevo_contenido:
        logger.info(f'Log "{titulo}" y su contenedor eliminado del contenido del archivo {file_name}')
    else:
        logger.warning(f'No se encontró un log con el título "{titulo}" en el archivo {file_name}')
    
    return nuevo_contenido

@app.route('/eliminar-log', methods=['POST'])
def eliminar_log():
    try:
        data = request.json
        empresa = data.get('empresa')
        titulo = data.get('titulo')

        TEMPLATE_HTML_NAME = {
            'MRG': 'template_MRG.html',
            'Rubicon': 'template_Rubi.html',
            'GERP': 'template_GERP.html',
            'Godiz': 'template_Godiz.html',
            'OCC': 'template_OCC.html'
        }

        if empresa not in TEMPLATE_HTML_NAME:
            return jsonify({'error': 'Empresa no válida'}), 400

        file_name = TEMPLATE_HTML_NAME[empresa]

        # Obtener SHA del archivo
        template_file_sha = find_file_sha_by_name(file_name)
        if not template_file_sha:
            return jsonify({'error': 'No se encontró el archivo de la empresa'}), 400

        # Eliminar el log y obtener el nuevo contenido
        nuevo_contenido = eliminar_log_por_titulo(file_name, titulo)
        if nuevo_contenido is None:
            return jsonify({'error': 'No se encontró el log con ese título'}), 400

        # Actualizar el contenido en GitHub
        nueva_sha = update_file_content(file_name, nuevo_contenido, template_file_sha)
        if not nueva_sha:
            return jsonify({'error': 'No se pudo actualizar el archivo'}), 500

        return jsonify({'message': 'Log eliminado correctamente'}), 200

    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

if __name__ == '__main__':
    app.run(debug=True)
