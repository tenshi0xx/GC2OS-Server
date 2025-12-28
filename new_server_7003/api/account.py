from starlette.responses import Response, HTMLResponse
from starlette.requests import Request
from starlette.routing import Route
from datetime import datetime
import secrets
import aiofiles

from api.misc import is_alphanumeric, inform_page, verify_password, hash_password, crc32_decimal, should_serve, generate_salt
from api.database import check_blacklist, user_name_to_user_info, decrypt_fields_to_user_info, set_user_data_using_decrypted_fields, get_user_from_save_id, create_user, logout_user, login_user, get_bind, read_user_save_file, write_user_save_file
from api.crypt import decrypt_fields
from config import AUTHORIZATION_MODE

ERR_MISSING_CREDENTIALS = "FAILED:<br>Missing username or password."
ERR_USERNAME_SAME_AS_PASSWORD = "FAILED:<br>Username cannot be the same as password."
ERR_INVALID_REQUEST = "FAILED:<br>Invalid request data."
ERR_USER_NOT_EXIST = "FAILED:<br>User does not exist."
ERR_NO_PASSWORD_HASH = "FAILED:<br>User has no password hash.<br>This should not happen."
XML_REGISTER_REQUIRED = """<response><code>10</code><message><ja>この機能を使用するには、まずアカウントを登録する必要があります。</ja><en>You need to register an account first before this feature can be used.</en><fr>Vous devez d'abord créer un compte avant de pouvoir utiliser cette fonctionnalité.</fr><it>È necessario registrare un account prima di poter utilizzare questa funzione.</it></message></response>"""
XML_MEDIA_TYPE = "application/xml"

def _build_email_bind_element(original_field):
    return f"""
        <form action="/send_email/?{original_field}" method="post">
            <div class="f60 a_center">
                <label for="email">Email:</label>
                <br>
                <input class="input" id="email" name="email" type="email">
                <br>
                <input class="bt_bg01_narrow" type="submit" value="Send Email">
            </div>
        </form>
        <form action="/verify/?{original_field}" method="post">
            <div class="f60 a_center">
                <label for="code">Verification Code:</label>
                <br>
                <input class="input" id="code" name="code">
                <br>
                <input class="bt_bg01_narrow" type="submit" value="Verify">
            </div>
        </form>
        """

def _build_discord_bind_element(original_field, bind_code):
    return f"""
        <p>To receive a verification code, please join our Discord server 'https://discord.gg/vugfJdc2rk' and use the !bind command with your account name and the following code. Do not leak this code to others.</p>
        <div class="f60 a_center">
            <label>Your bind code:</label>
            <br>
            <input class="input" value="{bind_code}" readonly>
        </div>
        <form action="/verify/?{original_field}" method="post">
            <div class="f60 a_center">
                <label for="code">Verification Code:</label>
                <br>
                <input class="input" id="code" name="code">
                <br>
                <input class="bt_bg01_narrow" type="submit" value="Verify">
            </div>
        </form>
        """

async def _get_bind_element(user_id, original_field):
    if AUTHORIZATION_MODE == 0:
        return '<p>No bind required in current mode.</p>'
    
    bind_state = await get_bind(user_id)
    is_verified = bind_state and bind_state['is_verified'] == 1
    
    if AUTHORIZATION_MODE == 1:
        if is_verified:
            return f'<p>Email verified: {bind_state["bind_account"]}\nTo remove a bind, contact the administrator.</p>'
        return _build_email_bind_element(original_field)
    
    if AUTHORIZATION_MODE == 2:
        bind_code = await generate_salt(user_id)
        if is_verified:
            return f'<p>Discord verified: {bind_state["bind_account"]}<br>To remove a bind, contact the administrator.</p>'
        return _build_discord_bind_element(original_field, bind_code)
    
    return ''

def _validate_username(username):
    if len(username) < 6 or len(username) > 20:
        return "FAILED:<br>Username must be between 6 and 20 characters long."
    if not is_alphanumeric(username):
        return "FAILED:<br>Username must consist entirely of alphanumeric characters."
    return None

async def name_reset(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if not username or not password:
        return inform_page(ERR_MISSING_CREDENTIALS, 0)

    username_error = _validate_username(username)
    if username_error:
        return inform_page(username_error, 0)

    if username == password:
        return inform_page(ERR_USERNAME_SAME_AS_PASSWORD, 0)

    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)

    if not await check_blacklist(decrypted_fields):
        return inform_page("FAILED:<br>Your account is banned and you are not allowed to perform this action.", 0)

    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)
    if not user_info:
        return inform_page(ERR_USER_NOT_EXIST, 0)

    existing_user_info = await user_name_to_user_info(username)
    if existing_user_info:
        return inform_page("FAILED:<br>Another user already has this name.", 0)

    password_hash = user_info['password_hash']
    if not password_hash:
        return inform_page(ERR_NO_PASSWORD_HASH, 0)

    if not verify_password(password, password_hash):
        return inform_page("FAILED:<br>Password is not correct.<br>Please try again.", 0)

    await set_user_data_using_decrypted_fields(decrypted_fields, {"username": username})
    return inform_page("SUCCESS:<br>Username updated.", 0)

async def password_reset(request: Request):
    form = await request.form()
    old_password = form.get("old")
    new_password = form.get("new")

    if not old_password or not new_password:
        return inform_page(ERR_MISSING_CREDENTIALS, 0)

    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)

    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)
    if not user_info:
        return inform_page(ERR_USER_NOT_EXIST, 0)

    if user_info['username'] == new_password:
        return inform_page(ERR_USERNAME_SAME_AS_PASSWORD, 0)
    if len(new_password) < 6:
        return inform_page("FAILED:<br>Password must have 6 or more characters.", 0)

    old_hash = user_info['password_hash']
    if not old_hash:
        return inform_page(ERR_NO_PASSWORD_HASH, 0)

    if not verify_password(old_password, old_hash):
        return inform_page("FAILED:<br>Old password is not correct.<br>Please try again.", 0)

    await set_user_data_using_decrypted_fields(decrypted_fields, {"password_hash": hash_password(new_password)})
    return inform_page("SUCCESS:<br>Password updated.", 0)

async def user_coin_mp(request: Request):
    form = await request.form()
    mp = form.get("coin_mp")

    if not mp:
        return inform_page("FAILED:<br>Missing multiplier.", 0)
    
    mp = int(mp)

    if mp < 0 or mp > 5:
        return inform_page("FAILED:<br>Multiplier not acceptable.", 0)

    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)
    
    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)

    if user_info:
        update_data = {
            "coin_mp": mp
        }
        await set_user_data_using_decrypted_fields(decrypted_fields, update_data)
        return inform_page("SUCCESS:<br>Coin multiplier set to " + str(mp) + ".", 0)
    else:
        return inform_page(ERR_USER_NOT_EXIST, 0)

async def save_migration(request: Request):
    form = await request.form()
    save_id = form.get("save_id")

    if not save_id:
        return inform_page("FAILED:<br>Missing save_id.", 0)

    if len(save_id) != 24 or not all(c in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in save_id):
        return inform_page("FAILED:<br>Save ID not acceptable format.", 0)

    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)
    
    should_serve_result = await should_serve(decrypted_fields)

    if not should_serve_result:
        return inform_page("FAILED:<br>You cannot access this feature right now.", 0)

    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)
    if user_info:
        user_id = user_info['id']
        existing_save_user = await get_user_from_save_id(save_id)

        if existing_save_user['id'] == user_id:
            return inform_page("FAILED:<br>Save ID is already associated with your account.", 0)

        existing_save_data = ""
        if existing_save_user:
            existing_save_data = await read_user_save_file(existing_save_user['id'])

        if existing_save_data != "":
            update_data = {
                "save_crc": existing_save_user['crc'],
                "save_timestamp": existing_save_user['timestamp']
            }
            await set_user_data_using_decrypted_fields(decrypted_fields, update_data)
            await write_user_save_file(user_info['id'], existing_save_data)

            return inform_page("SUCCESS:<br>Save migration was applied. If this was done by mistake, press the Save button now.", 0)
        else:
            return inform_page("FAILED:<br>Save ID is not associated with a save file.", 0)

    else:
        return inform_page(ERR_USER_NOT_EXIST, 0)

async def register(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if not username or not password:
        return inform_page(ERR_MISSING_CREDENTIALS, 0)

    if username == password:
        return inform_page(ERR_USERNAME_SAME_AS_PASSWORD, 0)

    if len(username) < 6 or len(username) > 20:
        return inform_page("FAILED:<br>Username must be between 6 and 20<br>characters long.", 0)

    if len(password) < 6:
        return inform_page("FAILED:<br>Password must have<br>6 or above characters.", 0)

    if not is_alphanumeric(username):
        return inform_page("FAILED:<br>Username must consist entirely of<br>alphanumeric characters.", 0)

    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)
    
    user_info = await user_name_to_user_info(username)

    if user_info:
        return inform_page("FAILED:<br>Another user already has this name.", 0)

    await create_user(username, hash_password(password), decrypted_fields[b'vid'][0].decode())

    return inform_page("SUCCESS:<br>Account is registered.<br>You can now backup/restore your save file.<br>You can only log into one device at a time.", 0)

async def logout(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)

    if not await check_blacklist(decrypted_fields):
        return inform_page("FAILED:<br>Your account is banned and you are<br>not allowed to perform this action.", 0)

    device_id = decrypted_fields[b'vid'][0].decode()
    await logout_user(device_id)
    return inform_page("Logout success.", 0)

async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if not username or not password:
        return inform_page(ERR_MISSING_CREDENTIALS, 0)

    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)

    user_record = await user_name_to_user_info(username)
    if user_record:
        user_id = user_record['id']

        password_hash_record = user_record['password_hash']
        if password_hash_record and verify_password(password, password_hash_record):
            device_id = decrypted_fields[b'vid'][0].decode()
            await login_user(user_id, device_id)

            return inform_page("SUCCESS:<br>You are logged in.", 0)
        else:
            return inform_page("FAILED:<br>Username or password incorrect.", 0)
    else:
        return inform_page("FAILED:<br>Username or password incorrect.", 0)

async def load(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return Response(XML_REGISTER_REQUIRED, media_type=XML_MEDIA_TYPE)
    
    should_serve_result = await should_serve(decrypted_fields)

    if not should_serve_result:
        return Response("""<response><code>10</code><message><ja>この機能を使用するには、現在アクセスできません。</ja><en>You cannot access this feature right now.</en><fr>Vous ne pouvez pas accéder à cette fonctionnalité pour le moment.</fr><it>Non è possibile accedere a questa funzione in questo momento.</it></message></response>""", media_type="application/xml")

    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)
    if not user_info:
        return Response(XML_REGISTER_REQUIRED, media_type=XML_MEDIA_TYPE)
    data = await read_user_save_file(user_info['id'])
    if data and data != "":
        crc = user_info['save_crc']
        timestamp = user_info['save_timestamp']
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?><response><code>0</code>
            <data>{data}</data>
            <crc>{crc}</crc>
            <date>{timestamp}</date>
            </response>"""
        return Response(xml_data, media_type=XML_MEDIA_TYPE)
    else:
        return Response("""<response><code>12</code><message><ja>セーブデータが無いか、セーブデータが破損しているため、ロードできませんでした。</ja><en>Unable to load; either no save data exists, or the save data is corrupted.</en><fr>Chargement impossible : les données de sauvegarde sont absentes ou corrompues.</fr><it>Impossibile caricare. Non esistono dati salvati o quelli esistenti sono danneggiati.</it></message></response>""", media_type=XML_MEDIA_TYPE)

async def save(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return Response(XML_REGISTER_REQUIRED, media_type=XML_MEDIA_TYPE)
    
    should_serve_result = await should_serve(decrypted_fields)

    if not should_serve_result:
        return Response("""<response><code>10</code><message><ja>この機能を使用するには、現在アクセスできません。</ja><en>You cannot access this feature right now.</en><fr>Vous ne pouvez pas accéder à cette fonctionnalité pour le moment.</fr><it>Non è possibile accedere a questa funzione in questo momento.</it></message></response>""", media_type=XML_MEDIA_TYPE)

    data = await request.body()
    data = data.decode("utf-8")

    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)

    username = user_info['username']
    if username:
        crc = crc32_decimal(data)
        formatted_time = datetime.now()
        is_save_id_unique = False
        while not is_save_id_unique:
            save_id = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(24))

            existing_user = await get_user_from_save_id(save_id)
            if not existing_user:
                is_save_id_unique = True

        await write_user_save_file(user_info['id'], data)

        update_data = {
            "save_crc": crc,
            "save_id": save_id,
            "save_timestamp": formatted_time
        }
        await set_user_data_using_decrypted_fields(decrypted_fields, update_data)

        return Response("""<response><code>0</code></response>""", media_type=XML_MEDIA_TYPE)
    else:
        return Response(XML_REGISTER_REQUIRED, media_type=XML_MEDIA_TYPE)

async def ttag(request: Request):
    decrypted_fields, original_field = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 0)
    
    user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)

    if not user_info:
        async with aiofiles.open("web/register.html", "r") as file:
            html_content = (await file.read()).format(pid=original_field)
        return HTMLResponse(html_content)

    bind_element = await _get_bind_element(user_info['id'], original_field)
    gcoin_mp = user_info['coin_mp']
    
    gcoin_selections = {f'gcoin_mp_{i}': 'selected' if gcoin_mp == i else '' for i in range(6)}

    async with aiofiles.open("web/profile.html", "r") as file:
        html_content = (await file.read()).format(
            bind_element=bind_element,
            pid=original_field,
            user=user_info['username'],
            savefile_id=user_info['save_id'],
            debug_info=original_field,
            **gcoin_selections
        )

    return HTMLResponse(html_content)

routes = [
    Route('/name_reset/', name_reset, methods=['POST']),
    Route('/password_reset/', password_reset, methods=['POST']),
    Route('/coin_mp/', user_coin_mp, methods=['POST']),
    Route('/save_migration/', save_migration, methods=['POST']),
    Route('/register/', register, methods=['POST']),
    Route('/logout/', logout, methods=['POST']),
    Route('/login/', login, methods=['POST']),
    Route('/load.php', load, methods=['GET']),
    Route('/save.php', save, methods=['POST']),
    Route('/ttag.php', ttag, methods=['GET']),
]