from starlette.responses import Response, FileResponse
from starlette.requests import Request
from starlette.routing import Route
from sqlalchemy import select
import openpyxl
from io import BytesIO
import os

from api.database import player_database, devices, binds, batch_tokens, log_download, get_downloaded_bytes
from config import AUTHORIZATION_MODE, DAILY_DOWNLOAD_LIMIT

ALLOWED_FOLDERS = {"audio", "stage", "pak"}
ALLOWED_EXTENSIONS = (".zip", ".pak")

async def _check_batch_token(auth_token):
    query = select(batch_tokens).where((batch_tokens.c.batch_token == auth_token) & (batch_tokens.c.uses_left > -1))
    return await player_database.fetch_one(query)

async def _check_device_auth(auth_token):
    query = select(devices).where(devices.c.device_id == auth_token)
    return await player_database.fetch_one(query)

async def _check_bind_auth(auth_token):
    device_query = select(devices).where(devices.c.bind_token == auth_token)
    device = await player_database.fetch_one(device_query)
    if not device:
        return None, "Unauthorized - device not found"
    
    bind_query = select(binds).where((binds.c.user_id == device['user_id']) & (binds.c.is_verified == 1))
    bind = await player_database.fetch_one(bind_query)
    if not bind:
        return None, "Unauthorized - bind not verified"
    
    daily_bytes = await get_downloaded_bytes(bind['user_id'], 24)
    if daily_bytes >= DAILY_DOWNLOAD_LIMIT:
        return None, "Daily download limit exceeded"
    
    return bind, None

def _get_safe_path(folder, filename):
    safe_path = os.path.realpath(os.path.join(os.getcwd(), "files", "gc2", folder, filename))
    base_dir = os.path.realpath(os.path.join(os.getcwd(), "files", "gc2", folder))
    return safe_path if safe_path.startswith(base_dir) else None

async def serve_file(request: Request):
    auth_token = request.path_params['auth_token']
    folder = request.path_params['folder']
    filename = request.path_params['filename']

    if folder not in ALLOWED_FOLDERS or not filename.endswith(ALLOWED_EXTENSIONS):
        return Response("Unauthorized", status_code=403)
    
    batch_result = await _check_batch_token(auth_token)
    bind_result = None
    
    if not batch_result:
        if AUTHORIZATION_MODE == 0:
            if not await _check_device_auth(auth_token):
                return Response("Unauthorized", status_code=403)
        else:
            bind_result, error = await _check_bind_auth(auth_token)
            if error:
                return Response(error, status_code=403)

    file_path = _get_safe_path(folder, filename)
    if not file_path:
        return Response("Unauthorized", status_code=403)

    if not os.path.isfile(file_path):
        return Response("File not found", status_code=404)

    if AUTHORIZATION_MODE != 0 and not batch_result and bind_result:
        await log_download(bind_result['user_id'], filename, os.path.getsize(file_path))
    
    return FileResponse(file_path)

async def serve_public_file(request: Request):
    path = request.path_params['path']
    safe_filename = os.path.realpath(os.path.join(os.getcwd(), "files", path))
    base_directory = os.path.realpath(os.path.join(os.getcwd(), "files"))

    if not safe_filename.startswith(base_directory):
        return Response("Unauthorized", status_code=403)

    if os.path.isfile(safe_filename):
        return FileResponse(safe_filename)
    return Response("File not found", status_code=404)
    
def convert_user_export_data(data):
    wb = openpyxl.Workbook()

    default_sheet = wb.active
    wb.remove(default_sheet)

    for sheet_name, rows in data.items():
        ws = wb.create_sheet(title=sheet_name)

        if isinstance(rows, list):
            write_dict_list_to_sheet(ws, rows)

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def write_dict_list_to_sheet(ws, rows):
    if not rows:
        return

    headers = list(rows[0].keys())
    ws.append(headers)

    for row in rows:
        ws.append([row.get(h, "") for h in headers])

routes = [
    Route("/files/gc2/{auth_token}/{folder}/{filename}", serve_file, methods=["GET"]),
    Route("/files/{path:path}", serve_public_file, methods=["GET"]),
]