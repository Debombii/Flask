from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import requests
import os
import base64
import logging
import re
import traceback

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

# Funciones para interactuar con GitHub
def find_file_sha_by_name(file_name):
    url = f'https://api.github.com/repos/Debombii/React/contents/public/{file_name}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    logger.info(f"Buscando SHA para el archivo: {file_name}")
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        sha = response.json()['sha']
        logger.info(f"SHA encontrado: {sha}")
        return sha
    logger.error(f"Error al buscar SHA para {file_name}: {response.status_code} - {response.text}")
    return None

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

def insertar_nuevo_contenido(template_html, new_div_html):
    # Expresiones regulares para extraer título y fecha
    titulo_match = re.search(r'<h2 id="(.*?)">(.*?)</h2>', new_div_html)
    date_match = re.search(r'<p class=\'date\' id="date">(.*?)</p>', new_div_html)

    if not titulo_match or not date_match:
        logger.error("No se encontró un título o fecha en el contenido nuevo.")
        return None 

    id_titulo = titulo_match.group(1)
    titulo = titulo_match.group(2)
    date = date_match.group(1)

    # Insertar nuevo contenido en la plantilla
    template_html = re.sub(r'(<div class="content">)', r'\1\n' + new_div_html, template_html, 1)
    nueva_entrada_indice = f'<li><a href="#{id_titulo}">{titulo} - {date}</a></li>'
    template_html = re.sub(r'(<ul id="indice">)', r'\1\n' + nueva_entrada_indice, template_html, 1)

    return template_html

def update_files(companies, body_content):
    TEMPLATE_HTML_NAME = {
        'MRG': 'template_MRG.html',
        'Rubicon': 'template_Rubi.html',
        'GERP': 'template_GERP.html',
        'Godiz': 'template_Godiz.html',
        'OCC': 'template_OCC.html'
    }

    for company in companies:
        if company not in TEMPLATE_HTML_NAME:
            logger.warning(f'Compañía inválida: {company}')
            continue

        TEMPLATE_NAME = TEMPLATE_HTML_NAME[company]

        # Buscar y obtener el archivo de plantilla
        template_file_sha = find_file_sha_by_name(TEMPLATE_NAME)
        if not template_file_sha:
            logger.error(f'No se encontró el archivo de plantilla {TEMPLATE_NAME}')
            continue

        template_content = get_file_content(TEMPLATE_NAME)
        if template_content is None:
            logger.error(f'No se pudo obtener el contenido del archivo de plantilla {TEMPLATE_NAME}')
            continue

        # Insertar nuevo contenido
        resultado_html = insertar_nuevo_contenido(template_content, body_content)
        if resultado_html is None:
            logger.error(f'Error al insertar contenido en la plantilla para {company}.')
            continue

        # Actualizar archivo en GitHub
        upload_file_sha = update_file_content(TEMPLATE_NAME, resultado_html, template_file_sha)
        if upload_file_sha is None:
            logger.error(f'No se pudo actualizar el archivo en GitHub para la plantilla {TEMPLATE_NAME}')
            continue

        logger.info(f'Archivo actualizado correctamente para {company}')

    logger.info('Archivos actualizados correctamente para todas las empresas')

def listar_titulos_logs(file_name):
    content = get_file_content(file_name)
    if content is None:
        logger.error(f"No se pudo obtener el contenido del archivo: {file_name}")
        return [] 
        
    titulos = re.findall(
        r"<div class='version'>.*?<h2 id=\"(.*?)\">(.*?)</h2>.*?<p class='date' id=\"date\">(.*?)</p>.*?<h3 class=\"titulo\">(.*?)</h3>",
        content,
        re.DOTALL  # Permite que el '.' capture nuevas líneas
    )

    # Registro de títulos encontrados
    logger.info(f'Títulos encontrados: {titulos}')
    
    return [{'id': t[0], 'titulo': t[3], 'fecha': t[2]} for t in titulos]

@app.route('/listar-titulos', methods=['POST'])
def listar_titulos():
    try:
        data = request.json
        empresa = data.get('empresa')

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
        titulos = listar_titulos_logs(file_name)

        return jsonify({'titulos': titulos}), 200

    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

def eliminar_log_por_titulo(file_name, titulo):
    content = get_file_content(file_name)
    if content is None:
        return None
    
    # Utiliza una expresión regular para encontrar y eliminar todo el div con class 'version' que contenga el título
    nuevo_contenido = re.sub(
        rf"<div class='version'>.*?<h2 id=\"{titulo}\">.*?</div>", 
        "", 
        content, 
        flags=re.DOTALL
    )

    # Registro de la eliminación
    logger.info(f'Log "{titulo}" y su contenedor eliminado del contenido del archivo {file_name}')
    
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
        template_file_sha = find_file_sha_by_name(file_name)

        if not template_file_sha:
            return jsonify({'error': 'No se encontró el archivo de la empresa'}), 400

        nuevo_contenido = eliminar_log_por_titulo(file_name, titulo)
        if nuevo_contenido is None:
            return jsonify({'error': 'No se encontró el log con ese título'}), 400

        nueva_sha = update_file_content(file_name, nuevo_contenido, template_file_sha)
        if not nueva_sha:
            return jsonify({'error': 'No se pudo actualizar el archivo'}), 500

        return jsonify({'message': 'Log eliminado correctamente'}), 200

    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

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

        # Ejecutar actualización de archivos
        update_files(companies, body_content)

        return jsonify({'message': 'Los archivos se han actualizado correctamente'}), 200

    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
