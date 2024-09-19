import os
import io
import re
import json
from flask import Flask, render_template, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from flask_cors import CORS
from googleapiclient.errors import HttpError

app = Flask(__name__)
CORS(app)

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

# Eliminar archivo en Google Drive
def delete_file(file_id):
    try:
        service.files().delete(fileId=file_id).execute()
        print(f"Archivo {file_id} eliminado exitosamente.")
    except HttpError as error:
        if error.resp.status == 403:
            print(f"Permiso denegado para eliminar el archivo {file_id}. Asegúrate de que las credenciales tengan permisos adecuados.")
        elif error.resp.status == 404:
            print(f"Archivo {file_id} no encontrado. Asegúrate de que el ID del archivo es correcto.")
        else:
            print(f"Error al eliminar el archivo {file_id}: {error}")

# Descargar archivo de Google Drive
def download_file(file_name, folder_id, destination):
    file_id = find_file_id_by_name(file_name, folder_id)
    if not file_id:
        print(f"No se encontró el archivo {file_name}")
        return False
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(destination, mode='wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f'Descargado {int(status.progress() * 100)}%')
    return True

# Subir archivo a Google Drive
def upload_file(file_path, folder_id):
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    response = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return response['id']

# Leer archivo HTML
def leer_html(ruta_archivo):
    with open(ruta_archivo, 'r', encoding='utf-8') as archivo:
        return archivo.read()

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

# Endpoint para recibir la compañía y archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400

    file = request.files['file']
    company = request.form.get('company')

    if not company or company not in ['MRG', 'Rubicon', 'GERP']:
        return jsonify({'error': 'Compañía inválida'}), 400

    # Guardar el archivo subido localmente
    file.save('changelog.html')

    # Mapear compañía a nombre de plantilla
    TEMPLATE_HTML_NAME = {
        'MRG': 'template_MRG.html',
        'Rubicon': 'template_Rubi.html',
        'GERP': 'template_GERP.html'
    }[company]

    # Descargar la plantilla específica de la compañía desde Google Drive
    if not download_file(TEMPLATE_HTML_NAME, FOLDER_ID, TEMPLATE_HTML_NAME):
        return jsonify({'error': f'No se pudo descargar la plantilla {TEMPLATE_HTML_NAME}'}), 500

    # Leer la plantilla descargada y el contenido del archivo changelog.html
    template_html = leer_html(TEMPLATE_HTML_NAME)
    new_div_html = leer_html('changelog.html')

    # Insertar el nuevo contenido en la plantilla
    resultado_html = insertar_nuevo_contenido(template_html, new_div_html)

    # Guardar el resultado en el archivo correspondiente
    with open(TEMPLATE_HTML_NAME, 'w', encoding='utf-8') as archivo_final:
        archivo_final.write(resultado_html)

    # Subir el archivo actualizado a Google Drive
    existing_file_id = find_file_id_by_name(TEMPLATE_HTML_NAME, FOLDER_ID)
    if existing_file_id:
        delete_file(existing_file_id)

    upload_file_id = upload_file(TEMPLATE_HTML_NAME, FOLDER_ID)

    # Limpiar archivos locales
    os.remove('changelog.html')
    os.remove(TEMPLATE_HTML_NAME)

    return jsonify({'message': 'Archivo subido y procesado correctamente', 'file_id': upload_file_id})

# Nuevo endpoint para recibir la compañía seleccionada
@app.route('/api/send-company', methods=['POST'])
def send_company():
    data = request.get_json()
    company = data.get('company')
    return jsonify({'message': f'Compañía recibida: {company}'})

if __name__ == '__main__':
    app.run(debug=True)
