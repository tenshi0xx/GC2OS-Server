from starlette.responses import HTMLResponse, JSONResponse
from starlette.requests import Request
from starlette.routing import Route
import os
import aiofiles

from config import STAGE_PRICE, AVATAR_PRICE, ITEM_PRICE, FMAX_PRICE, EX_PRICE

from api.crypt import decrypt_fields
from api.misc import inform_page, parse_res, should_serve, get_host_string
from api.database import decrypt_fields_to_user_info, get_user_entitlement_from_devices, set_device_data_using_decrypted_fields
from api.template import SONG_LIST, AVATAR_LIST, ITEM_LIST, EXCLUDE_STAGE_EXP

ERR_INVALID_REQUEST = "Invalid request data"
ERR_ACCESS_DENIED = "Access denied"
JSON_ERR_INVALID_REQUEST = {"state": 0, "message": ERR_INVALID_REQUEST}
JSON_ERR_ACCESS_DENIED = {"state": 0, "message": ERR_ACCESS_DENIED}

ITEM_TYPE_STAGE = 0
ITEM_TYPE_AVATAR = 1
ITEM_TYPE_ITEM = 2
ITEM_TYPE_FMAX = 3
ITEM_TYPE_EXTRA = 4

TYPE_TO_LIST = {
    ITEM_TYPE_STAGE: SONG_LIST,
    ITEM_TYPE_AVATAR: AVATAR_LIST,
    ITEM_TYPE_ITEM: ITEM_LIST,
}

def _get_price_for_type(item_type, item=None):
    if item_type == ITEM_TYPE_STAGE and item:
        return STAGE_PRICE * 2 if len(item.get("difficulty_levels", [])) == 6 else STAGE_PRICE
    if item_type == ITEM_TYPE_AVATAR:
        return AVATAR_PRICE
    if item_type == ITEM_TYPE_ITEM:
        return ITEM_PRICE
    if item_type == ITEM_TYPE_FMAX:
        return FMAX_PRICE
    if item_type == ITEM_TYPE_EXTRA:
        return EX_PRICE
    return 0

def _find_item_in_list(list_to_use, item_id):
    return next((item for item in list_to_use if item['id'] == item_id), None) if list_to_use else None

async def web_shop(request: Request):
    decrypted_fields, original_fields = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 6)

    if not await should_serve(decrypted_fields):
        return inform_page(ERR_ACCESS_DENIED, 6)

    _, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return inform_page("Invalid device information", 6)

    try:
        async with aiofiles.open("web/web_shop.html", "r", encoding="utf-8") as file:
            html_content = (await file.read()).format(host_url=await get_host_string(), payload=original_fields)
    except FileNotFoundError:
        return inform_page("Shop page not found", 6)

    return HTMLResponse(html_content)

async def api_shop_player_data(request: Request):
    from api.misc import FMAX_VER
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)
    
    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)
    
    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)

    if user_info:
        my_stage, my_avatar = await get_user_entitlement_from_devices(user_info['id'], should_cap=False)
    elif device_info:
        my_stage = device_info['my_stage']
        my_avatar = device_info['my_avatar']
    else:
        return JSONResponse({"state": 0, "message": "User and device not found"}, status_code=404)

    is_fmax_purchased = False
    is_extra_purchased = False

    stage_list = []
    stage_low_end = 100
    stage_high_end = 615

    stage_list = [
        stage_id for stage_id in range(stage_low_end, stage_high_end)
        if stage_id not in EXCLUDE_STAGE_EXP and stage_id not in my_stage
    ]

    avatar_list = []
    avatar_low_end = 15
    avatar_high_end = 173 if FMAX_VER == 0 else 267

    avatar_list = [
        avatar_id for avatar_id in range(avatar_low_end, avatar_high_end)
        if avatar_id not in my_avatar
    ]

    item_list = list(range(1, 11))

    if 700 in my_stage and os.path.isfile('./files/4max_ver.txt'):
        is_fmax_purchased = True

    if 980 in my_stage and os.path.isfile('./files/4max_ver.txt'):
        is_extra_purchased = True

    payload = {
        "state": 1,
        "message": "Success",
        "data": {
            "coin": device_info['coin'],
            "stage_list": stage_list,
            "avatar_list": avatar_list,
            "item_list": item_list,
            "fmax_purchased": is_fmax_purchased,
            "extra_purchased": is_extra_purchased
        }
    }
    return JSONResponse(payload)

async def api_shop_item_data(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)
    
    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)
    
    _, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return JSONResponse({"state": 0, "message": "Invalid device information"}, status_code=400)

    post_data = await request.json()
    item_type = int(post_data.get("mode"))
    item_id = int(post_data.get("item_id"))

    list_to_use = TYPE_TO_LIST.get(item_type, [])
    item = _find_item_in_list(list_to_use, item_id)

    if not item and item_type not in [ITEM_TYPE_FMAX, ITEM_TYPE_EXTRA]:
        return JSONResponse({"state": 0, "message": "Item not found"})

    prop_first, prop_second, prop_third = "", "", ""
    price = _get_price_for_type(item_type, item)

    if item_type == ITEM_TYPE_STAGE and item:
        prop_first = item['name_en']
        prop_second = item['author_en']
        prop_third = "/".join(map(str, item.get("difficulty_levels", [])))
    elif item_type == ITEM_TYPE_AVATAR and item:
        prop_first, prop_second = item['name'], item['effect']
    elif item_type == ITEM_TYPE_ITEM and item:
        prop_first, prop_second = item['name'], item['effect']
    elif item_type == ITEM_TYPE_FMAX:
        from api.misc import FMAX_VER, FMAX_RES
        prop_first, prop_second = FMAX_VER, parse_res(FMAX_RES)

    return JSONResponse({
        "state": 1, "message": "Success",
        "data": {"price": price, "property_first": prop_first, "property_second": prop_second, "property_third": prop_third}
    })

def _check_already_owned(item_type, item_id, my_stage, my_avatar):
    ownership_checks = {
        ITEM_TYPE_STAGE: (item_id in my_stage, "Stage already owned. Exit the shop and it will be added to the game."),
        ITEM_TYPE_AVATAR: (item_id in my_avatar, "Avatar already owned. Exit the shop and it will be added to the game."),
        ITEM_TYPE_FMAX: (700 in my_stage, "FMAX already owned. Exit the shop and it will be added to the game."),
        ITEM_TYPE_EXTRA: (980 in my_stage, "EXTRA already owned. Exit the shop and it will be added to the game."),
    }
    check = ownership_checks.get(item_type)
    if check and check[0]:
        return check[1]
    return None

def _apply_purchase(item_type, item_id, my_stage, my_avatar, item_pending):
    if item_type == ITEM_TYPE_STAGE:
        my_stage.add(item_id)
    elif item_type == ITEM_TYPE_AVATAR:
        my_avatar.add(item_id)
    elif item_type == ITEM_TYPE_ITEM:
        item_pending.append(item_id)
    elif item_type == ITEM_TYPE_FMAX:
        my_stage.update(range(615, 926))
    elif item_type == ITEM_TYPE_EXTRA:
        my_stage.update(range(926, 985))

async def api_shop_purchase_item(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)
    
    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)

    post_data = await request.json()
    item_type = int(post_data.get("mode"))
    item_id = int(post_data.get("item_id"))

    list_to_use = TYPE_TO_LIST.get(item_type, [])
    item = _find_item_in_list(list_to_use, item_id)
    price = _get_price_for_type(item_type, item)

    if price == 0:
        return JSONResponse({"state": 0, "message": "Item not found"})

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not user_info and not device_info:
        return JSONResponse({"state": 0, "message": "User and device not found"}, status_code=404)

    if user_info:
        my_stage, my_avatar = await get_user_entitlement_from_devices(user_info['id'], should_cap=False)
    else:
        my_stage, my_avatar = device_info['my_stage'], device_info['my_avatar']

    my_stage, my_avatar = set(my_stage), set(my_avatar)
    item_pending = device_info['item'] or [] if device_info else []

    owned_msg = _check_already_owned(item_type, item_id, my_stage, my_avatar)
    if owned_msg:
        return JSONResponse({"state": 0, "message": owned_msg}, status_code=400)

    if price > device_info['coin']:
        return JSONResponse({"state": 0, "message": "Insufficient coins."}, status_code=400)

    new_coin_amount = device_info['coin'] - price
    _apply_purchase(item_type, item_id, my_stage, my_avatar, item_pending)

    await set_device_data_using_decrypted_fields(decrypted_fields, {
        "coin": new_coin_amount,
        "my_stage": list(my_stage),
        "my_avatar": list(my_avatar),
        "item": item_pending
    })

    return JSONResponse({"state": 1, "message": "Purchase successful.", "data": {"coin": new_coin_amount}})

routes = [
    Route('/web_shop.php', web_shop, methods=['GET', 'POST']),
    Route('/api/shop/player_data', api_shop_player_data, methods=['GET']),
    Route('/api/shop/item_data', api_shop_item_data, methods=['POST']),
    Route('/api/shop/purchase_item', api_shop_purchase_item, methods=['POST']),
]