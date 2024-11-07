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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

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
    titulo_match = re.search(r'<h2 id="(.*?)">(.*?)</h2>', new_div_html)
    date_match = re.search(r'<p class=\'date\' id="date">(.*?)</p>', new_div_html)

    if not titulo_match or not date_match:
        logger.error("No se encontró un título o fecha en el contenido nuevo.")
        return None 

    id_titulo = titulo_match.group(1)
    titulo = titulo_match.group(2)
    date = date_match.group(1)

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

        template_file_sha = find_file_sha_by_name(TEMPLATE_NAME)
        if not template_file_sha:
            logger.error(f'No se encontró el archivo de plantilla {TEMPLATE_NAME}')
            continue

        template_content = get_file_content(TEMPLATE_NAME)
        if template_content is None:
            logger.error(f'No se pudo obtener el contenido del archivo de plantilla {TEMPLATE_NAME}')
            continue

        resultado_html = insertar_nuevo_contenido(template_content, body_content)
        if resultado_html is None:
            logger.error(f'Error al insertar contenido en la plantilla para {company}.')
            continue

        upload_file_sha = update_file_content(TEMPLATE_NAME, resultado_html, template_file_sha)
        if upload_file_sha is None:
            logger.error(f'No se pudo actualizar el archivo en GitHub para la plantilla {TEMPLATE_NAME}')
            continue

        logger.info(f'Archivo actualizado correctamente para {company}')

    logger.info('Archivos actualizados correctamente para todas las empresas')

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

def listar_titulos_logs(file_name):
    content = get_file_content(file_name)
    if content is None:
        logger.error(f"No se pudo obtener el contenido del archivo: {file_name}")
        return [] 

    titulos = re.findall(
        r"<div class='version'>.*?<h2 id=\"(.*?)\">(.*?)</h2>.*?<p class='date' id=\"date\">(.*?)</p>.*?<h3 class=\"titulo\" id=\".*?\">(.*?)</h3>",
        content,
        re.DOTALL
    )

    logger.info(f'Títulos encontrados: {titulos}')

    return [{'id': t[0], 'titulo': t[3], 'fecha': t[2]} for t in titulos]

    
def eliminar_logs_por_titulo(file_name, ids):
    content = get_file_content(file_name)
    if content is None:
        logger.error(f"No se pudo obtener el contenido del archivo: {file_name}")
        return None

    for id_h2 in ids:
        logger.info(f'Eliminando log con ID "{id_h2}".')

        content = re.sub(
            rf"<div class='version'>\s*<h2 id=\"{id_h2}\">.*?</div>",
            "",
            content,
            flags=re.DOTALL
        )

        content = re.sub(
            rf"<li><a href=\"#{id_h2}\" class=\"base\">.*?</a></li>",
            "",
            content,
            flags=re.DOTALL
        )
    lines = content.splitlines()
    cleaned_lines = []
    previous_line_empty = False

    for line in lines:
        stripped_line = line.strip()

        if stripped_line:
            cleaned_lines.append(line)
            previous_line_empty = False
        elif not previous_line_empty:
            cleaned_lines.append("")
            previous_line_empty = True

    nuevo_contenido = "\n".join(cleaned_lines)

    logger.info(f'Logs con IDs {ids} eliminados del contenido del archivo {file_name}')
    return nuevo_contenido


@app.route('/eliminar-log', methods=['POST'])
def eliminar_log():
    try:
        data = request.json
        empresa = data.get('empresa')
        ids = data.get('ids')

        if not ids or not isinstance(ids, list):
            return jsonify({'error': 'Debe proporcionar una lista de ids'}), 400

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

        nuevo_contenido = eliminar_logs_por_titulo(file_name, ids)
        if nuevo_contenido is None:
            return jsonify({'error': 'No se encontró ningún log con los ids proporcionados'}), 400

        nueva_sha = update_file_content(file_name, nuevo_contenido, template_file_sha)
        if not nueva_sha:
            return jsonify({'error': 'No se pudo actualizar el archivo'}), 500

        return jsonify({'message': 'Logs eliminados correctamente'}), 200

    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500


@app.route('/modificar-log', methods=['POST'])
def modificar_log():
    try:
        data = request.json
        empresa = data.get('empresa')
        log_id = data.get('id')
        nuevo_titulo = data.get('nuevoTitulo')
        nuevo_contenido = data.get('nuevoContenido')
        if not log_id:
            return jsonify({'error': 'Debe proporcionar un id válido'}), 400
        if not nuevo_titulo or not nuevo_contenido:
            return jsonify({'error': 'Debe proporcionar el nuevo título y el nuevo contenido'}), 400

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

        template_content = get_file_content(file_name)
        if template_content is None:
            return jsonify({'error': 'No se pudo obtener el contenido del archivo de la empresa'}), 400

        nuevo_contenido_html = modificar_logs(template_content, [log_id], nuevo_titulo, nuevo_contenido)

        new_sha = update_file_content(file_name, nuevo_contenido_html, template_file_sha)
        if not new_sha:
            return jsonify({'error': 'No se pudo actualizar el archivo en GitHub'}), 500

        return jsonify({'message': 'Log modificado correctamente'}), 200

    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

def modificar_logs(content, ids, nuevo_titulo, nuevo_contenido):
    for id_h2 in ids:
        logger.info(f'Modificando log con ID "{id_h2}".')

        nuevo_id_titulo = re.sub(r'\s+', '-', nuevo_titulo).lower()

        pattern_titulo = rf"(<div class='version'>.*?<h2[^>]*id=\"{id_h2}\"[^>]*class=\"[^\"]*base[^\"]*\"[^>]*>.*?</h2>.*?<p class='date' id=\"date\">.*?</p>.*?<h3 class=\"titulo\" id=\").*?(\">)(.*?)(</h3>)"
        content = re.sub(
            pattern_titulo,
            r"\1" + nuevo_id_titulo + r"\2" + nuevo_titulo + r"\4",
            content,
            flags=re.DOTALL
        )

        pattern_contenido = rf"(<h3 class=\"titulo\" id=\"{nuevo_id_titulo}\">.*?</h3>)(.*?)(</div>)"
        content = re.sub(
            pattern_contenido,
            r"\1" + nuevo_contenido + r"\3",
            content,
            flags=re.DOTALL
        )

        logger.info(f'Log con ID "{id_h2}" modificado.')

    return content

@app.route('/obtener-log', methods=['POST'])
def obtener_log():
    try:
        data = request.json
        empresa = data.get('empresa')
        id_log = data.get('id')
        if not id_log:
            return jsonify({'error': 'Debe proporcionar el ID del log'}), 400

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

        template_content = get_file_content(file_name)
        if template_content is None:
            return jsonify({'error': 'No se pudo obtener el contenido del archivo de la empresa'}), 400

        contenido_log = obtener_contenido_log(template_content, id_log)
        if contenido_log:
            return jsonify({
                'id': contenido_log['id'],
                'titulo': contenido_log['titulo'],
                'contenido': contenido_log['contenido'],
                'fecha': contenido_log['fecha']
            }), 200
        else:
            return jsonify({'error': 'Log no encontrado'}), 404
    except Exception as e:
        logger.error(f"Error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

def obtener_contenido_log(content, id_log):
    match = re.search(
        rf"<div class='version'>.*?<h2 id=\"{id_log}\">(.*?)</h2>.*?<p class='date' id=\"date\">(.*?)</p>.*?"
        rf"<h3 class=\"titulo\" id=\".*?\">(.*?)</h3>(.*?)</div>",
        content,
        flags=re.DOTALL
    )

    if match:
        log_id = match.group(1)
        fecha = match.group(2)
        titulo = match.group(3)
        contenido = match.group(4)

        elementos = []
        for elemento in re.finditer(r'<(p|a|h2|h3)(.*?)>(.*?)</\1>', contenido, flags=re.DOTALL):
            tag = elemento.group(1)
            contenido_tag = elemento.group(3).strip()
            if contenido_tag:
                elementos.append(f"<{tag}>{contenido_tag}</{tag}>")

        contenido_completo = "\n".join(elementos)

        return {
            'id': log_id,
            'titulo': titulo,
            'contenido': contenido_completo,
            'fecha': fecha
        }
    return None


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
