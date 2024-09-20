from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import os

app = Flask(__name__)

# Identificación del folder en Google Drive
FOLDER_ID = 'YOUR_FOLDER_ID'

# Función para encontrar el archivo por nombre en Google Drive
def find_file_id_by_name(file_name, folder_id):
    # Autentica con Google Drive API y busca el archivo
    try:
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)

        query = f"name = '{file_name}' and '{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        return None
    except Exception as e:
        print(f"Error finding file: {e}")
        return None

# Función para obtener el contenido del archivo desde Google Drive
def get_file_content(file_id):
    try:
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)

        file = service.files().get_media(fileId=file_id).execute()
        return file.decode('utf-8')
    except Exception as e:
        print(f"Error getting file content: {e}")
        return None

# Función para actualizar el contenido del archivo en Google Drive
def update_file_content(file_id, content):
    try:
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive'])
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {'name': 'updated_template.html'}
        media = MediaFileUpload(content, mimetype='text/html')
        updated_file = service.files().update(
            fileId=file_id,
            media_body=media,
            fields='id'
        ).execute()
        return updated_file['id']
    except Exception as e:
        print(f"Error updating file: {e}")
        return None

# Función para leer HTML desde un archivo en memoria
def leer_html_from_memory(content):
    return content  # Ya se obtiene el contenido desde Drive

# Función para insertar el nuevo contenido en la plantilla HTML
def insertar_nuevo_contenido(template_html, nuevo_contenido):
    # Insertar el nuevo contenido en la plantilla
    return template_html.replace("<!-- CONTENIDO -->", nuevo_contenido)

# Endpoint para recibir la compañía y contenido en lugar de un archivo
@app.route('/upload-file', methods=['POST'])
def upload_file_endpoint():
    try:
        # Obtener los datos JSON del cuerpo de la solicitud
        data = request.json
        print(f"Datos recibidos: {data}")

        # Obtener el contenido HTML y las empresas del JSON recibido
        body_content = data.get('bodyContent')
        companies = data.get('companies', [])

        # Validar que se ha enviado contenido HTML
        if not body_content:
            return jsonify({'error': 'No se envió contenido'}), 400

        if not companies:
            return jsonify({'error': 'No se enviaron compañías'}), 400

        # AÑADIR MÁS PROYECTOS SI HACE FALTA
        TEMPLATE_HTML_NAME = {
            'MRG': 'template_MRG.html',
            'Rubicon': 'template_Rubi.html',
            'GERP': 'template_GERP.html'
        }

        # Procesar cada empresa secuencialmente
        for company in companies:
            if company not in TEMPLATE_HTML_NAME:
                return jsonify({'error': f'Compañía inválida: {company}'}), 400

            TEMPLATE_NAME = TEMPLATE_HTML_NAME[company]

            # Buscar el archivo de plantilla en Google Drive
            template_file_id = find_file_id_by_name(TEMPLATE_NAME, FOLDER_ID)
            if not template_file_id:
                return jsonify({'error': f'No se encontró el archivo de plantilla {TEMPLATE_NAME}'}), 500

            print(f"ID del archivo de plantilla: {template_file_id}")

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

        return jsonify({'message': 'Archivos actualizados correctamente para todas las empresas'}), 200
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Ocurrió un error interno'}), 500

if __name__ == '__main__':
    app.run(debug=True)
