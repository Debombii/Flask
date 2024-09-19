import os
import io
import re
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from flask_cors import CORS
from googleapiclient.errors import HttpError

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

# Configuración de Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Recuperar el contenido de las credenciales desde la variable de entorno
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

if not GOOGLE_APPLICATION_CREDENTIALS_JSON:
    raise ValueError('La variable de entorno GOOGLE_APPLICATION_CREDENTIALS_JSON no está definida.')

# Convertir el contenido JSON a un diccionario
creds_info = json.loads(GOOGLE_APPLICATION_CREDENTIALS_JSON)

# Crear las credenciales a partir del contenido JSON
creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
service = build('drive', 'v3', credentials=creds)

# Ruta de la carpeta de Google Drive
FOLDER_LINK = 'https://drive.google.com/drive/folders/1_ss3rYceeMH9pEmWi17-31N3gi_nFpuw?usp=sharing'

# Extraer ID de la carpeta del enlace de Google Drive
def extract_folder_id_from_link(link):
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', link)
    if match:
        return match.group(1)
    else:
        raise ValueError("El enlace de la carpeta no es válido o no contiene un ID de carpeta.")

FOLDER_ID = extract_folder_id_from_link(FOLDER_LINK)

# Buscar archivo en Google Drive por nombre
def find_file_id_by_name(file_name, folder_id):
    query = f"name='{file_name}' and '{folder_id}' in parents"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    return None

# Obtener el contenido del archivo desde Google Drive
def get_file_content(file_id):
    try:
        # Obtener la metadata del archivo para identificar el MIME type
        file_metadata = service.files().get(fileId=file_id, fields='mimeType').execute()
        mime_type = file_metadata.get('mimeType')
        
        # Verificar si el archivo es un documento de Google
        if mime_type in ['application/vnd.google-apps.document', 'application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.presentation']:
            # Exportar el contenido del archivo como HTML
            request = service.files().export_media(fileId=file_id, mimeType='text/html')
            response = request.execute()
        else:
            # Obtener el contenido del archivo para otros tipos de archivo
            request = service.files().get_media(fileId=file_id)
            response = request.execute()

        return response
    except HttpError as error:
        print(f'Error al obtener el contenido del archivo: {error}')
        return None

# Subir archivo a Google Drive
def update_file_content(file_id, new_content):
    try:
        # Crear un objeto de media con el nuevo contenido
        media = MediaIoBaseUpload(io.BytesIO(new_content), mimetype='text/html')
        
        # Actualizar el archivo existente
        updated_file = service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        return updated_file.get('id')
    except HttpError as error:
        print(f'Error al actualizar el archivo: {error}')
        return None

# Leer archivo HTML desde contenido en memoria
def leer_html_from_memory(file_content):
    return file_content.decode('utf-8')

# Insertar nuevo contenido en la plantilla HTML
def insertar_nuevo_contenido(template_html, new_div_html):
    titulo_match = re.search(r'<h2 id="(.*?)">(.*?)</h2>', new_div_html)
    date_match = re.search(r'<p class=\'date\' id="date">(.*?)</p>', new_div_html)

    if titulo_match and date_match:
        id_titulo = titulo_match.group(1)
        titulo = titulo_match.group(2)
        date = date_match.group(1)

        template_html = re.sub(r'(<div class="content">)', r'\1\n' + new_div_html, template_html, 1)

        nueva_entrada_indice = f'<li><a href="#{id_titulo}">{titulo} - {date}</a></li>'
        template_html = re.sub(r'(<ul id="indice">)', r'\1\n' + nueva_entrada_indice, template_html, 1)

    return template_html

# Endpoint para servir el favicon
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Endpoint para recibir la compañía y contenido en lugar de un archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    try:
        # Obtener los datos JSON del cuerpo de la solicitud
        data = request.json
        print(f"Datos recibidos: {data}")  # Registro para depuración

        # Obtener el contenido HTML y las empresas del JSON recibido
        body_content = data.get('bodyContent')
        companies = data.get('companies', [])  # Cambiado de 'company' a 'companies', por defecto es lista vacía

        # Validar que se ha enviado contenido HTML
        if not body_content:
            return jsonify({'error': 'No se envió contenido'}), 400

        if not companies:
            return jsonify({'error': 'No se enviaron compañías'}), 400

        # Mapear compañía a nombre de plantilla
        TEMPLATE_HTML_NAME = {
            'MRG': 'template_MRG.html',
            'Rubicon': 'template_Rubi.html',
            'GERP': 'template_GERP.html'
        }

        for company in companies:
            if company not in TEMPLATE_HTML_NAME:
                return jsonify({'error': f'Compañía inválida: {company}'}), 400

            TEMPLATE_NAME = TEMPLATE_HTML_NAME[company]

            # Buscar el archivo de plantilla en Google Drive
            template_file_id = find_file_id_by_name(TEMPLATE_NAME, FOLDER_ID)
            if not template_file_id:
                return jsonify({'error': f'No se encontró el archivo de plantilla {TEMPLATE_NAME}'}), 500

            print(f"ID del archivo de plantilla: {template_file_id}")  # Registro para depuración

            # Obtener la plantilla desde Google Drive
            template_content = get_file_content(template_file_id)
            if template_content is None:
                return jsonify({'error': 'No se pudo obtener el contenido del archivo de plantilla'}), 500

            template_html = leer_html_from_memory(template_content)

            # Insertar el nuevo contenido en la plantilla
            resultado_html = insertar_nuevo_contenido(template_html, body_content)

            # Subir el archivo actualizado a Google Drive
            upload_file_id = update_file_content(template_file_id, resultado_html.encode('utf-8'))
            if upload_file_id is None:
                return jsonify({'error': f'No se pudo actualizar el archivo en Google Drive para la plantilla {TEMPLATE_NAME}'}), 500

        return jsonify({'message': 'Archivos actualizados correctamente'}), 200
    
    except Exception as e:
        print(f"Error: {e}")  # Registro de error general
        return jsonify({'error': 'Ocurrió un error interno'}), 500

if __name__ == '__main__':
    app.run(debug=True)
