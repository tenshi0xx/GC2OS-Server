from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
import sqlalchemy
import json
from datetime import datetime
import os
import aiofiles

from api.database import player_database, accounts, results, devices, whitelists, blacklists, batch_tokens, binds, webs, logs, is_admin, read_user_save_file, write_user_save_file
from api.misc import crc32_decimal

ERR_INVALID_TOKEN = "Invalid token."
ERR_INVALID_TABLE = "Invalid table name."
ERR_INVALID_ROW_DATA = "Invalid row data: {}"

def _convert_to_int(value, key):
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError(f"Field '{key}' must be an integer.")

def _convert_to_float(value, key):
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValueError(f"Field '{key}' must be a float.")

def _convert_to_bool(value, key):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in ["true", "1"]:
            return True
        if value.lower() in ["false", "0"]:
            return False
    if isinstance(value, int):
        return bool(value)
    raise ValueError(f"Field '{key}' must be a boolean.")

def _convert_to_datetime(value, key):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    raise ValueError(f"Field '{key}' must be a valid ISO datetime string or timestamp.")

def _validate_integer(value, key, for_update):
    if for_update:
        return _convert_to_int(value, key)
    if not isinstance(value, int):
        raise ValueError(f"Field '{key}' must be an integer.")
    return value

def _validate_float(value, key, for_update):
    if for_update:
        return _convert_to_float(value, key)
    if not isinstance(value, (float, int)):
        raise ValueError(f"Field '{key}' must be a float.")
    return value

def _validate_boolean(value, key, for_update):
    if for_update:
        return _convert_to_bool(value, key)
    if not isinstance(value, bool):
        raise ValueError(f"Field '{key}' must be a boolean.")
    return value

def _validate_json(value, key, for_update):
    if isinstance(value, (dict, list)):
        return value
    if not for_update:
        try:
            json.loads(value)
            return value
        except (json.JSONDecodeError, TypeError):
            pass
    raise ValueError(f"Field '{key}' must be a JSON object or array.")

def _validate_string(value, key):
    if not isinstance(value, str):
        raise ValueError(f"Field '{key}' must be a string.")
    return value

TYPE_VALIDATORS = {
    "INTEGER": _validate_integer,
    "FLOAT": _validate_float,
    "BOOLEAN": _validate_boolean,
}

def _get_type_prefix(expected_type):
    for prefix in ["INTEGER", "FLOAT", "BOOLEAN", "JSON", "VARCHAR", "STRING", "DATETIME"]:
        if expected_type.startswith(prefix):
            return prefix
    return None

def _validate_field_type(value, expected_type, key, for_update=False, is_nullable=False):
    if (value == "" or value is None) and is_nullable:
        return value
    
    type_prefix = _get_type_prefix(expected_type)
    
    if type_prefix in TYPE_VALIDATORS:
        return TYPE_VALIDATORS[type_prefix](value, key, for_update)
    if type_prefix == "JSON":
        return _validate_json(value, key, for_update)
    if type_prefix in ("VARCHAR", "STRING"):
        return _validate_string(value, key)
    if type_prefix == "DATETIME":
        return _convert_to_datetime(value, key)
    return value

def _find_primary_key(row_data):
    for pk in ["id", "device_id"]:
        if pk in row_data:
            return pk
    return None

TABLE_MAP = {
        "accounts": (accounts, ["id", "username", "password_hash", "save_crc", "save_timestamp", "save_id", "coin_mp", "title", "avatar", "mobile_delta", "arcade_delta", "total_delta", "created_at", "updated_at"]),
        "results": (results, ["id", "device_id", "stts", "song_id", "mode", "avatar", "score", "high_score", "play_rslt", "item", "os", "os_ver", "ver", "created_at"]),
        "devices": (devices, ["device_id", "user_id", "my_stage", "my_avatar", "item", "daily_day", "coin", "lvl", "title", "avatar", "created_at", "updated_at", "bind_token", "last_login_at"]),
        "whitelist": (whitelists, ["id", "device_id"]),
        "blacklist": (blacklists, ["id", "ban_terms", "reason"]),
        "batch_tokens": (batch_tokens, ["id", "batch_token", "expire_at", "uses_left", "auth_id", "created_at", "updated_at"]),
        "binds": (binds, ["id", "user_id", "bind_account", "bind_code", "is_verified", "bind_date"]),
        "webs": (webs, ["id", "user_id", "permission", "web_token", "last_save_export", "created_at", "updated_at"]),
        "logs": (logs, ["id", "user_id", "filename", "filesize", "timestamp"]),
    }

async def web_admin_page(request: Request):
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        response = RedirectResponse(url="/login")
        response.delete_cookie("token")
        return response
    async with aiofiles.open("web/admin.html", "r", encoding="utf-8") as file:
        html_template = await file.read()
    return HTMLResponse(content=html_template)

def serialize_row(row, allowed_fields):
    result = {}
    for field in allowed_fields:
        value = row[field]
        result[field] = value.isoformat() if hasattr(value, "isoformat") else value
    return result

def _build_search_clauses(table, allowed_fields, search):
    clauses = []
    for field in allowed_fields:
        col = getattr(table.c, field, None)
        if col is not None:
            clauses.append(col.like(f"%{search}%"))
    return clauses

def _apply_sort(query, table, sort, dir_, allowed_fields):
    if sort not in allowed_fields:
        return query
    col = getattr(table.c, sort, None)
    if col is None:
        return query
    is_string = isinstance(col.type, sqlalchemy.types.String)
    sort_col = sqlalchemy.func.lower(col) if is_string else col
    return query.order_by(sort_col.desc() if dir_ == "desc" else sort_col.asc())

def _clamp_size(size):
    return max(10, min(100, size))

async def web_admin_get_table(request: Request):
    params = request.query_params
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"data": [], "last_page": 1, "total": 0}, status_code=400)
    
    table_name = params.get("table")
    page = int(params.get("page", 1))
    size = _clamp_size(int(params.get("size", 25)))
    sort = params.get("sort")
    dir_ = params.get("dir", "asc")
    search = params.get("search", "").strip()
    schema_request = params.get("schema", "0") == "1"

    if schema_request:
        table, _ = TABLE_MAP[table_name]
        schema = {col.name: str(col.type).upper() for col in table.columns}
        return JSONResponse(schema)

    if table_name not in TABLE_MAP:
        return JSONResponse({"data": [], "last_page": 1, "total": 0}, status_code=400)

    table, allowed_fields = TABLE_MAP[table_name]
    query = table.select()
    count_query = sqlalchemy.select(sqlalchemy.func.count()).select_from(table)

    if search:
        search_clauses = _build_search_clauses(table, allowed_fields, search)
        if search_clauses:
            query = query.where(sqlalchemy.or_(*search_clauses))
            count_query = count_query.where(sqlalchemy.or_(*search_clauses))

    query = _apply_sort(query, table, sort, dir_, allowed_fields)
    query = query.offset((page - 1) * size).limit(size)

    total = await player_database.fetch_val(count_query)
    last_page = max(1, (total + size - 1) // size)
    rows = await player_database.fetch_all(query)
    data = [serialize_row(row, allowed_fields) for row in rows]

    return JSONResponse({"data": data, "last_page": last_page, "total": total})

async def web_admin_table_set(request: Request):
    params = await request.json()
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TOKEN}, status_code=400)

    table_name = params.get("table")
    row_data = params.get("row")

    if table_name not in TABLE_MAP:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TABLE}, status_code=401)
    
    table, _ = TABLE_MAP[table_name]
    schema = {col.name: str(col.type) for col in table.columns}

    try:
        if not isinstance(row_data, dict):
            raise ValueError("Row data must be a JSON object.")
        
        id_field = _find_primary_key(row_data)
        if not id_field:
            raise ValueError("Row data must contain a primary key ('id' or 'device_id').")
        
        for key, value in row_data.items():
            if key not in schema:
                raise ValueError(f"Field '{key}' does not exist in table schema.")
            row_data[key] = _validate_field_type(value, schema[key], key, for_update=True, is_nullable=table.c[key].nullable)
    except ValueError as e:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_ROW_DATA.format(str(e))}, status_code=402)

    update_data = {k: v for k, v in row_data.items() if k != id_field}
    for key, value in update_data.items():
        if (value == "" or value is None) and not table.c[key].nullable:
            return JSONResponse({"status": "failed", "message": f"Field '{key}' cannot be null."}, status_code=403)
    
    update_query = table.update().where(getattr(table.c, id_field) == row_data[id_field]).values(**update_data)
    await player_database.execute(update_query)

    return JSONResponse({"status": "success", "message": "Row updated successfully."})

async def web_admin_table_delete(request: Request):
    params = await request.json()
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TOKEN}, status_code=400)

    table_name = params.get("table")
    row_id = params.get("id")

    if not row_id:
        row_id = params.get("device_id")
        if not row_id:
            return JSONResponse({"status": "failed", "message": "Row ID is required."}, status_code=402)

    if table_name not in TABLE_MAP:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TABLE}, status_code=401)
    
    if not row_id:
        return JSONResponse({"status": "failed", "message": "Row ID is required."}, status_code=402)
    
    table, _ = TABLE_MAP[table_name]

    if table_name in ["devices"]:
        delete_query = table.delete().where(table.c.device_id == row_id)
    else:
        delete_query = table.delete().where(table.c.id == row_id)

    await player_database.execute(delete_query)

    return JSONResponse({"status": "success", "message": "Row deleted successfully."})

async def web_admin_table_insert(request: Request):
    params = await request.json()
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TOKEN}, status_code=400)

    table_name = params.get("table")
    row_data = params.get("row")

    if table_name not in TABLE_MAP:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TABLE}, status_code=401)
    
    table, _ = TABLE_MAP[table_name]
    schema = {col.name: str(col.type) for col in table.columns}

    try:
        if not isinstance(row_data, dict):
            raise ValueError("Row data must be a JSON object.")
        
        for key, value in row_data.items():
            if key not in schema:
                raise ValueError(f"Field '{key}' does not exist in table schema.")
            row_data[key] = _validate_field_type(value, schema[key], key, for_update=False, is_nullable=False)
    except ValueError as e:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_ROW_DATA.format(str(e))}, status_code=402)

    insert_data = {k: v for k, v in row_data.items() if k in schema}
    insert_query = table.insert().values(**insert_data)
    result = await player_database.execute(insert_query)
    return JSONResponse({"status": "success", "message": "Row inserted successfully.", "inserted_id": result})

async def web_admin_data_get(request: Request):
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TOKEN}, status_code=400)
    
    params = request.query_params
    uid = int(params.get("id"))

    data = await read_user_save_file(uid)

    return JSONResponse({"status": "success", "data": data})

async def web_admin_data_save(request: Request):
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TOKEN}, status_code=400)
    
    params = await request.json()
    uid = int(params['id'])
    save_data = params['data']

    crc = crc32_decimal(save_data)
    formatted_time = datetime.now()

    query = accounts.update().where(accounts.c.id == uid).values(save_crc=crc, save_timestamp=formatted_time)
    await player_database.execute(query)
    await write_user_save_file(uid, save_data)

    return JSONResponse({"status": "success", "message": "Data saved successfully."})

async def web_admin_update_maintenance(request: Request):
    adm = await is_admin(request.cookies.get("token"))
    if not adm:
        return JSONResponse({"status": "failed", "message": ERR_INVALID_TOKEN}, status_code=400)
    
    params = await request.json()
    status = params.get("status")
    message_en = params.get("message_en")
    message_ja = params.get("message_ja")
    message_fr = params.get("message_fr")
    message_it = params.get("message_it")

    # Create the XML structure directly
    notice_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <response>
            <code>{status}</code>
            <message>
                <en>{message_en}</en>
                <ja>{message_ja}</ja>
                <fr>{message_fr}</fr>
                <it>{message_it}</it>
            </message>
        </response>
        """

    # Save the XML to the file
    notice_file_path = os.path.join('files/notice.xml')
    try:
        async with aiofiles.open(notice_file_path, 'w', encoding='utf-8') as f:
            await f.write(notice_xml)
        return JSONResponse({"status": "success", "message": "Maintenance settings updated successfully."})
    except OSError as e:
        return JSONResponse({"status": "failed", "message": f"An error occurred: {str(e)}"}, status_code=500)

routes = [
    Route("/admin", web_admin_page, methods=["GET"]),
    Route("/admin/", web_admin_page, methods=["GET"]),
    Route("/admin/table", web_admin_get_table, methods=["GET"]),
    Route("/admin/table/update", web_admin_table_set, methods=["POST"]),
    Route("/admin/table/delete", web_admin_table_delete, methods=["POST"]),
    Route("/admin/table/insert", web_admin_table_insert, methods=["POST"]),
    Route("/admin/data", web_admin_data_get, methods=["GET"]),
    Route("/admin/data/save", web_admin_data_save, methods=["POST"]),
    Route("/admin/update_maintenance", web_admin_update_maintenance, methods=["POST"])
]