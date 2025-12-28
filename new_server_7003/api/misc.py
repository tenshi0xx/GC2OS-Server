from starlette.responses import HTMLResponse
import requests
import json
import binascii
import secrets
import bcrypt
import hashlib
import re
import xml.etree.ElementTree as ET
import copy
import os
import aiofiles
from config import MODEL, TUNEFILE, SKIN, AUTHORIZATION_NEEDED, AUTHORIZATION_MODE, GRANDFATHERED_ACCOUNT_LIMIT, BIND_SALT, OVERRIDE_HOST, HOST, PORT
from api.database import get_bind, check_whitelist, check_blacklist, decrypt_fields_to_user_info, user_id_to_user_info_simple, get_device_info, refresh_bind
from api.template import START_XML

GC2_FILES_PATH = "files/gc2/"

FMAX_VER = None
FMAX_RES = None

def get_4max_version_string():
    url = "https://studio.code.org/v3/sources/3-aKHy16Y5XaAPXQHI95RnFOKlyYT2O95ia2HN2jKIs/main.json"
    global FMAX_VER
    try:
        with open("./files/4max_ver.txt", 'r') as file:
            FMAX_VER = file.read().strip()
    except Exception as e:
        print(f"An unexpected error occurred when loading files/4max_ver.txt: {e}")
    
    def fetch():
        global FMAX_RES
        try:
            response = requests.get(url)
            if 200 <= response.status_code <= 207:
                try:
                    response_json = response.json()
                    FMAX_RES = json.loads(response_json['source'])
                except (json.JSONDecodeError, KeyError):
                    
                    FMAX_RES = 500
            else:
                FMAX_RES = response.status_code
        except requests.RequestException:
            FMAX_RES = 400
    
    fetch()

def parse_res(res):
    parsed_data = []
    if isinstance(res, int) or res == None:
        return "Failed to fetch version info: Error " + str(res)
    
    for item in res:
        if item.get("isOpen"):
            version = item.get("version", 0)
            changelog = "<br>".join(item.get("changeLog", {}).get("en", []))
            parsed_data.append(f"<strong>Version: {version}</strong><p><strong>Changelog:</strong><br>{changelog}</p>")
    return "".join(parsed_data)

def crc32_decimal(data):
    crc32_hex = binascii.crc32(data.encode())
    return int(crc32_hex & 0xFFFFFFFF)

def hash_password(password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

def verify_password(password, hashed_password):
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')

    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def is_alphanumeric(username):
    pattern = r"^[a-zA-Z0-9]+$"
    return bool(re.match(pattern, username))

async def get_model_pak(decrypted_fields, user_id):
    mid = ET.Element("model_pak")
    rid = ET.Element("date")
    uid = ET.Element("url")
    device_id = decrypted_fields[b'vid'][0].decode()

    host = await get_host_string()

    if AUTHORIZATION_MODE == 0:
        auth_token = device_id
        rid.text = MODEL
        uid.text = host + GC2_FILES_PATH + auth_token + "/pak/model" + MODEL + ".pak"
    else:
        if user_id:
            device_info = await get_device_info(device_id)
            bind_info = await get_bind(user_id)
            if bind_info and bind_info['is_verified'] == 1:
                auth_token = device_info['bind_token']
                if not auth_token:
                    auth_token = await refresh_bind(user_id, device_id)
                rid.text = MODEL
                uid.text = host + GC2_FILES_PATH + auth_token + "/pak/model" + MODEL + ".pak"
            else:
                rid.text = "1"
                uid.text = host + "files/gc/model1.pak"
        else:
            rid.text = "1"
            uid.text = host + "files/gc/model1.pak"

    mid.append(rid)
    mid.append(uid)
    return mid

async def get_tune_pak(decrypted_fields, user_id):
    mid = ET.Element("tuneFile_pak")
    rid = ET.Element("date")
    uid = ET.Element("url")
    device_id = decrypted_fields[b'vid'][0].decode()

    host = await get_host_string()

    if AUTHORIZATION_MODE == 0:
        auth_token = device_id
        rid.text = TUNEFILE
        uid.text = host + GC2_FILES_PATH + auth_token + "/pak/tuneFile" + TUNEFILE + ".pak"
    else:
        if user_id:
            device_info = await get_device_info(device_id)
            bind_info = await get_bind(user_id)
            if bind_info and bind_info['is_verified'] == 1:
                auth_token = device_info['bind_token']
                rid.text = TUNEFILE
                uid.text = host + GC2_FILES_PATH + auth_token + "/pak/tuneFile" + TUNEFILE + ".pak"
            else:
                rid.text = "1"
                uid.text = host + "files/gc/tuneFile1.pak"
        else:
            rid.text = "1"
            uid.text = host + "files/gc/tuneFile1.pak"

    mid.append(rid)
    mid.append(uid)
    return mid

async def get_skin_pak(decrypted_fields, user_id):
    mid = ET.Element("skin_pak")
    rid = ET.Element("date")
    uid = ET.Element("url")
    device_id = decrypted_fields[b'vid'][0].decode()

    host = await get_host_string()

    if AUTHORIZATION_MODE == 0:
        auth_token = device_id
        rid.text = SKIN
        uid.text = host + GC2_FILES_PATH + auth_token + "/pak/skin" + SKIN + ".pak"
    else:
        if user_id:
            device_info = await get_device_info(device_id)
            bind_info = await get_bind(user_id)
            if bind_info and bind_info['is_verified'] == 1:
                auth_token = device_info['bind_token']
                rid.text = SKIN
                uid.text = host + GC2_FILES_PATH + auth_token + "/pak/skin" + SKIN + ".pak"
            else:
                rid.text = "1"
                uid.text = host + "files/gc/skin1.pak"
        else:
            rid.text = "1"
            uid.text = host + "files/gc/skin1.pak"

    mid.append(rid)
    mid.append(uid)
    return mid
    
async def get_m4a_path(decrypted_fields, user_id):
    host = await get_host_string()
    device_id = decrypted_fields[b'vid'][0].decode()
    if AUTHORIZATION_MODE == 0:
        auth_token = device_id
        mid = ET.Element("m4a_path")
        mid.text = host + GC2_FILES_PATH + auth_token + "/audio/"
    else:
        if user_id:
            device_info = await get_device_info(device_id)
            bind_info = await get_bind(user_id)
            if bind_info and bind_info['is_verified'] == 1:
                mid = ET.Element("m4a_path")
                mid.text = host + GC2_FILES_PATH + device_info['bind_token'] + "/audio/"
            else:
                mid = ET.Element("m4a_path")
                mid.text = host
        else:
            mid = ET.Element("m4a_path")
            mid.text = host
        
    return mid

async def get_stage_path(decrypted_data, user_id):
    host = await get_host_string()
    device_id = decrypted_data[b'vid'][0].decode()
    if AUTHORIZATION_MODE == 0:
        auth_token = device_id
        mid = ET.Element("stage_path")
        mid.text = host + GC2_FILES_PATH + auth_token + "/stage/"
    else:
        if user_id:
            device_info = await get_device_info(device_id)
            bind_info = await get_bind(user_id)
            if bind_info and bind_info['is_verified'] == 1:
                mid = ET.Element("stage_path")
                mid.text = host + GC2_FILES_PATH + device_info['bind_token'] + "/stage/"
            else:
                mid = ET.Element("stage_path")
                mid.text = host
        else:
            mid = ET.Element("stage_path")
            mid.text = host
    
    return mid

def get_stage_zero():
    sid = ET.Element("my_stage")
    did = ET.Element("stage_id")
    cid = ET.Element("ac_mode")
    did.text = "0"
    cid.text = "0"
    sid.append(did)
    sid.append(cid)
    return sid

# Mapping for inform_page mode to image paths
INFORM_PAGE_IMAGES = {
    0: "/files/web/ttl_taitoid.png",
    1: "/files/web/ttl_information.png",
    2: "/files/web/ttl_buy.png",
    3: "/files/web/ttl_title.png",
    4: "/files/web/ttl_rank.png",
    5: "/files/web/ttl_mission.png",
    6: "/files/web/ttl_shop.png",
}

# Cache for inform.html template
_inform_html_cache = None

def inform_page(text, mode):
    global _inform_html_cache
    img = INFORM_PAGE_IMAGES.get(mode, INFORM_PAGE_IMAGES[0])
    if _inform_html_cache is None:
        with open("web/inform.html", "r") as file:
            _inform_html_cache = file.read()
    return HTMLResponse(_inform_html_cache.format(text=text, img=img))
    
def safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None

def generate_otp():
    otp = ''.join(secrets.choice('0123456789') for _ in range(6))
    hashed_otp = hash_otp(otp)
    return otp, hashed_otp

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def check_email(email):
    STRICT_EMAIL_REGEX = r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*@[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?:\.[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)*\.[A-Za-z]{2,}$"
    return re.match(STRICT_EMAIL_REGEX, email) is not None

async def should_serve(decrypted_fields):
    should_serve = True
    if AUTHORIZATION_NEEDED:
        should_serve = await check_whitelist(decrypted_fields) and not await check_blacklist(decrypted_fields)
    
    if AUTHORIZATION_MODE and should_serve:
        user_info, _ = await decrypt_fields_to_user_info(decrypted_fields)
        if not user_info:
            return False
        bind_info = await get_bind(user_info["id"])
        if not bind_info or bind_info['is_verified'] != 1:
            should_serve = False

    return should_serve

async def should_serve_init(decrypted_fields):
    should_serve = True
    if AUTHORIZATION_NEEDED:
        should_serve = await check_whitelist(decrypted_fields) and not await check_blacklist(decrypted_fields)
    
    return should_serve

async def should_serve_web(user_id):
    user_id = safe_int(user_id)
    should_serve = True
    if AUTHORIZATION_MODE:
        bind_info = await get_bind(user_id)
        if not bind_info or bind_info['is_verified'] != 1:
            should_serve = False
        if user_id < GRANDFATHERED_ACCOUNT_LIMIT:
            should_serve = True

    return should_serve

async def generate_salt(user_id):
    user_info = await user_id_to_user_info_simple(user_id)
    user_pw_hash = user_info['password_hash']
    username = user_info['username']

    combined = f"{username}{user_id}{user_pw_hash}{BIND_SALT}".encode('utf-8')
    crc32_hash = binascii.crc32(combined) & 0xFFFFFFFF
    return str(crc32_hash)

async def get_host_string():
    return OVERRIDE_HOST if OVERRIDE_HOST is not None else f"http://{HOST}:{PORT}/"

async def get_start_xml():
    root = copy.deepcopy(START_XML.getroot())
    async with aiofiles.open('files/notice.xml', 'r', encoding='utf-8') as f:
        content = await f.read()
        response_xml = ET.fromstring(content)
        for child in response_xml:
            root.append(child)
    return root