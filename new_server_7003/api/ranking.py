from starlette.responses import HTMLResponse, JSONResponse
from starlette.requests import Request
from starlette.routing import Route
from sqlalchemy import select
import aiofiles

from api.crypt import decrypt_fields
from api.misc import inform_page, should_serve, get_host_string
from api.database import decrypt_fields_to_user_info, get_user_entitlement_from_devices, results_query, set_user_data_using_decrypted_fields, user_id_to_user_info_simple, accounts, player_database, write_rank_cache, get_rank_cache, set_device_data_using_decrypted_fields
from api.template import SONG_LIST, EXP_UNLOCKED_SONGS, TITLE_LISTS, SUM_TITLE_LIST

ERR_INVALID_REQUEST = "Invalid request data"
ERR_ACCESS_DENIED = "Access denied"
ERR_INVALID_DEVICE = "Invalid device information"
JSON_ERR_INVALID_REQUEST = {"state": 0, "message": ERR_INVALID_REQUEST}
JSON_ERR_ACCESS_DENIED = {"state": 0, "message": ERR_ACCESS_DENIED}
JSON_ERR_INVALID_DEVICE = {"state": 0, "message": ERR_INVALID_DEVICE}

def _build_player_ranking(user_info, device_info):
    return {
        "username": user_info["username"] if user_info else "Guest (Not Ranked)",
        "score": 0,
        "position": -1,
        "title": user_info["title"] if user_info else device_info['title'],
        "avatar": device_info["avatar"]
    }

async def _build_ranking_list(records, page_number, page_count, user_id, user_info, score_key="score", id_key="user_id"):
    ranking_list = []
    player_ranking = None
    start_idx = page_number * page_count
    end_idx = start_idx + page_count
    
    for index, record in enumerate(records):
        if start_idx <= index < end_idx:
            rank_user = await user_id_to_user_info_simple(record.get(id_key) or record.get("id"))
            if rank_user:
                ranking_list.append({
                    "position": index + 1,
                    "username": rank_user["username"],
                    "score": record[score_key],
                    "title": rank_user["title"],
                    "avatar": record.get("avatar", rank_user.get("avatar"))
                })
        
        record_id = record.get(id_key) or record.get("id")
        if user_id and record_id == user_id:
            player_ranking = {
                "username": user_info["username"],
                "score": record[score_key],
                "position": index + 1,
                "title": user_info["title"],
                "avatar": user_info["avatar"]
            }
    
    return ranking_list, player_ranking

async def mission(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 5)

    if not await should_serve(decrypted_fields):
        return inform_page(ERR_ACCESS_DENIED, 5)

    _, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return inform_page(ERR_INVALID_DEVICE, 4)

    html = """<div class="f90 a_center pt50">Play Music to level up and unlock free songs!<br>Songs can only be unlocked when you play online.</div><div class='mission-list'>"""

    for song in EXP_UNLOCKED_SONGS:
        song_id = song["id"]
        level_required = song["lvl"]
        song_name = SONG_LIST[song_id]["name_en"] if song_id < len(SONG_LIST) else "Unknown Song"

        html += f"""
            <div class="mission-row">
                <div class="mission-level">Level {level_required}</div>
                <div class="mission-song">{song_name}</div>
            </div>
        """

    html += "</div>"
    try:
        async with aiofiles.open("web/mission.html", "r", encoding="utf-8") as file:
            html_content = (await file.read()).format(text=html)
    except FileNotFoundError:
        return HTMLResponse("""<html><body><h1>Mission file not found</h1></body></html>""", status_code=500)

    return HTMLResponse(html_content)
        
    
async def status(request: Request):
    decrypted_fields, original_fields = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 3)

    if not await should_serve(decrypted_fields):
        return inform_page(ERR_ACCESS_DENIED, 3)
    
    _, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return inform_page(ERR_INVALID_DEVICE, 4)

    try:
        async with aiofiles.open("web/status.html", "r", encoding="utf-8") as file:
            html_content = (await file.read()).format(host_url=await get_host_string(), payload=original_fields)
    except FileNotFoundError:
        return inform_page("Status page not found", 4)

    return HTMLResponse(html_content)

async def status_title_list(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)

    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return JSONResponse({"state": 0, "message": "Invalid user information"}, status_code=400)

    username = user_info["username"] if user_info else "Guest"
    current_title = user_info["title"] if user_info else device_info['title']
    current_avatar = user_info["avatar"] if user_info else device_info['avatar']
    current_lvl = device_info['lvl']

    player_object = {
        "username": username,
        "title": current_title,
        "avatar": current_avatar,
        "lvl": current_lvl
    }

    payload = {
        "state": 1,
        "message": "Success",
        "data": {
            "title_list": TITLE_LISTS,
            "player_info": player_object
        }
    }

    return JSONResponse(payload)

async def set_title(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)

    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return JSONResponse({"state": 0, "message": "Invalid user information"}, status_code=400)

    post_data = await request.json()
    new_title = int(post_data.get("title", -1))

    if new_title not in SUM_TITLE_LIST:
        return JSONResponse({"state": 0, "message": "Invalid title"}, status_code=400)
    
    update_data = {
        "title": new_title
    }

    if user_info:
        await set_user_data_using_decrypted_fields(decrypted_fields, update_data)
    
    await set_device_data_using_decrypted_fields(decrypted_fields, update_data)

    return JSONResponse({"state": 1, "message": "Title updated successfully"})


async def ranking(request: Request):
    decrypted_fields, original_fields = await decrypt_fields(request)
    if not decrypted_fields:
        return inform_page(ERR_INVALID_REQUEST, 4)

    if not await should_serve(decrypted_fields):
        return inform_page(ERR_ACCESS_DENIED, 4)
    
    _, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return inform_page(ERR_INVALID_DEVICE, 4)

    try:
        async with aiofiles.open("web/ranking.html", "r", encoding="utf-8") as file:
            html_content = (await file.read()).format(host_url=await get_host_string(), payload=original_fields)
    except FileNotFoundError:
        return inform_page("Ranking page not found", 4)

    return HTMLResponse(html_content)


async def user_song_list(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)
    
    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)

    my_stage = []
    if user_info:
        my_stage, _ = await get_user_entitlement_from_devices(user_info["id"], should_cap=False)
    elif device_info:
        my_stage = device_info['my_stage']

    payload = {
        "state": 1,
        "message": "Success",
        "data": {
            "song_list": SONG_LIST,
            "my_stage": my_stage
        }
    }
    return JSONResponse(payload)

async def user_ranking_individual(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)
    
    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return JSONResponse(JSON_ERR_INVALID_DEVICE, status_code=400)

    post_data = await request.json()
    song_id = int(post_data.get("song_id", -1))
    mode = int(post_data.get("mode", -1))
    page_number = int(post_data.get("page", 0))
    page_count = 50

    if song_id not in range(0, 1000) or mode not in [1, 2, 3, 11, 12, 13]:
        return JSONResponse({"state": 0, "message": "Invalid song_id or mode"}, status_code=400)

    user_id = user_info["id"] if user_info else None
    player_ranking = _build_player_ranking(user_info, device_info)

    cache_key = f"{song_id}-{mode}"
    cached_data = await get_rank_cache(cache_key)
    records = cached_data if cached_data else await results_query({"song_id": song_id, "mode": mode})
    
    if not cached_data:
        await write_rank_cache(cache_key, records)

    ranking_list, found_ranking = await _build_ranking_list(records, page_number, page_count, user_id, user_info)
    if found_ranking:
        player_ranking = found_ranking

    return JSONResponse({
        "state": 1,
        "message": "Success",
        "data": {"ranking_list": ranking_list, "player_ranking": player_ranking, "total_count": len(records)}
    })

async def user_ranking_total(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return JSONResponse(JSON_ERR_INVALID_REQUEST, status_code=400)
    
    if not await should_serve(decrypted_fields):
        return JSONResponse(JSON_ERR_ACCESS_DENIED, status_code=403)

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    if not device_info:
        return JSONResponse(JSON_ERR_INVALID_DEVICE, status_code=400)

    post_data = await request.json()
    mode = int(post_data.get("mode", -1))
    page_number = int(post_data.get("page", 0))
    page_count = 50

    if mode not in [0, 1, 2]:
        return JSONResponse({"state": 0, "message": "Invalid mode"}, status_code=400)

    user_id = user_info["id"] if user_info else None
    player_ranking = _build_player_ranking(user_info, device_info)
    score_columns = ["total_delta", "mobile_delta", "arcade_delta"]
    score_key = score_columns[mode]

    cache_key = f"0-{mode}"
    cached_data = await get_rank_cache(cache_key)
    
    if cached_data:
        records = cached_data
    else:
        query = select(
            accounts.c.id,
            accounts.c.username,
            accounts.c[score_key],
            accounts.c.title,
            accounts.c.avatar,
        ).where(accounts.c[score_key] > 0).order_by(accounts.c[score_key].desc())
        records = [dict(r) for r in await player_database.fetch_all(query)]
        await write_rank_cache(cache_key, records, expire_seconds=120)

    ranking_list, found_ranking = await _build_ranking_list(records, page_number, page_count, user_id, user_info, score_key=score_key, id_key="id")
    if found_ranking:
        player_ranking = found_ranking

    return JSONResponse({
        "state": 1,
        "message": "Success",
        "data": {"ranking_list": ranking_list, "player_ranking": player_ranking, "total_count": len(records)}
    })

routes = [
    Route('/mission.php', mission, methods=['GET']),
    Route('/status.php', status, methods=['GET']),
    Route('/api/status/title_list', status_title_list, methods=['GET']),
    Route('/api/status/set_title', set_title, methods=['POST']),
    Route('/ranking.php', ranking, methods=['GET']),
    Route('/api/ranking/song_list', user_song_list, methods=['GET']),
    Route('/api/ranking/individual', user_ranking_individual, methods=['POST']),
    Route('/api/ranking/total', user_ranking_total, methods=['POST'])
]