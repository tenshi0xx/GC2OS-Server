from starlette.responses import Response
from starlette.requests import Request
from starlette.routing import Route
import json
import copy
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from config import COIN_REWARD

from api.database import player_database, results, decrypt_fields_to_user_info, set_device_data_using_decrypted_fields, results_query, set_user_data_using_decrypted_fields, clear_rank_cache
from api.crypt import decrypt_fields
from api.template import START_STAGES, EXP_UNLOCKED_SONGS, RESULT_XML
from api.misc import should_serve

XML_CONTENT_TYPE = "application/xml"
XML_INVALID_REQUEST = """<response><code>10</code><message>Invalid request data.</message></response>"""
XML_ACCESS_DENIED = """<response><code>403</code><message>Access denied.</message></response>"""

MOBILE_MODES = {1, 2, 3}
ARCADE_MODES = {11, 12, 13}

def score_delta(mode, old_score, new_score):
    delta = new_score - old_score
    if mode in MOBILE_MODES:
        return delta, 0, delta
    if mode in ARCADE_MODES:
        return 0, delta, delta
    return 0, 0, 0

def _parse_result_fields(decrypted_fields):
    return {
        'device_id': decrypted_fields[b'vid'][0].decode(),
        'stts': decrypted_fields[b'stts'][0].decode(),
        'song_id': int(decrypted_fields[b'id'][0].decode()),
        'mode': int(decrypted_fields[b'mode'][0].decode()),
        'avatar': int(decrypted_fields[b'avatar'][0].decode()),
        'score': int(decrypted_fields[b'score'][0].decode()),
        'high_score': decrypted_fields[b'high_score'][0].decode(),
        'play_rslt': decrypted_fields[b'play_rslt'][0].decode(),
        'item': int(decrypted_fields[b'item'][0].decode()),
        'device_os': decrypted_fields[b'os'][0].decode(),
        'os_ver': decrypted_fields[b'os_ver'][0].decode(),
        'ver': decrypted_fields[b'ver'][0].decode(),
    }

def _parse_json_fields(fields):
    stts = json.loads(f"[{fields['stts']}]")
    high_score = json.loads(f"[{fields['high_score']}]")
    play_rslt = json.loads(f"[{fields['play_rslt']}]")
    return stts, high_score, play_rslt

async def _update_existing_result(record, fields, stts, high_score, play_rslt):
    mobile_delta, arcade_delta, total_delta = score_delta(fields['mode'], record['score'], fields['score'])
    update_query = results.update().where(results.c.id == record['id']).values(
        device_id=fields['device_id'],
        stts=stts,
        avatar=fields['avatar'],
        score=fields['score'],
        high_score=high_score,
        play_rslt=play_rslt,
        item=fields['item'],
        os=fields['device_os'],
        os_ver=fields['os_ver'],
        ver=fields['ver'],
        created_at=datetime.now(timezone.utc)
    )
    await player_database.execute(update_query)
    return mobile_delta, arcade_delta, total_delta

async def _insert_new_result(user_id, fields, stts, high_score, play_rslt):
    mobile_delta, arcade_delta, total_delta = score_delta(fields['mode'], 0, fields['score'])
    insert_query = results.insert().values(
        device_id=fields['device_id'],
        user_id=user_id,
        stts=stts,
        song_id=fields['song_id'],
        mode=fields['mode'],
        avatar=fields['avatar'],
        score=fields['score'],
        high_score=high_score,
        play_rslt=play_rslt,
        item=fields['item'],
        os=fields['device_os'],
        os_ver=fields['os_ver'],
        ver=fields['ver'],
        created_at=datetime.now(timezone.utc)
    )
    row_id = await player_database.execute(insert_query)
    return row_id, mobile_delta, arcade_delta, total_delta

def _calculate_unlocked_stages(device_info, current_exp):
    my_stage = set(device_info["my_stage"]) if device_info and device_info["my_stage"] else set(START_STAGES)
    for song in EXP_UNLOCKED_SONGS:
        if song["lvl"] <= current_exp:
            my_stage.add(song["id"])
    return sorted(my_stage)

async def result_request(request: Request):
    decrypted_fields, _ = await decrypt_fields(request)
    if not decrypted_fields:
        return Response(XML_INVALID_REQUEST, media_type=XML_CONTENT_TYPE)

    if not await should_serve(decrypted_fields):
        return Response(XML_ACCESS_DENIED, media_type=XML_CONTENT_TYPE)

    user_info, device_info = await decrypt_fields_to_user_info(decrypted_fields)
    fields = _parse_result_fields(decrypted_fields)

    try:
        stts, high_score, play_rslt = _parse_json_fields(fields)
    except json.JSONDecodeError:
        return Response(XML_INVALID_REQUEST, media_type=XML_CONTENT_TYPE)

    await clear_rank_cache(f"{fields['song_id']}-{fields['mode']}")

    tree = copy.deepcopy(RESULT_XML)
    target_row_id = 0
    rank = None
    user_id = user_info['id'] if user_info else None

    if user_id:
        records = await results_query({"song_id": fields['song_id'], "mode": fields['mode'], "user_id": user_id})
        mobile_delta, arcade_delta, total_delta = 0, 0, 0

        if records:
            target_row_id = records[0]['id']
            if fields['score'] > records[0]['score']:
                mobile_delta, arcade_delta, total_delta = await _update_existing_result(records[0], fields, stts, high_score, play_rslt)
        else:
            target_row_id, mobile_delta, arcade_delta, total_delta = await _insert_new_result(user_id, fields, stts, high_score, play_rslt)

        all_records = await results_query({"song_id": fields['song_id'], "mode": fields['mode']})
        for idx, record in enumerate(all_records, start=1):
            if record["id"] == target_row_id:
                rank = idx
                break

        if total_delta:
            await set_user_data_using_decrypted_fields(decrypted_fields, {
                "mobile_delta": user_info['mobile_delta'] + mobile_delta,
                "arcade_delta": user_info['arcade_delta'] + arcade_delta,
                "total_delta": user_info['total_delta'] + total_delta
            })

    current_exp = stts[0]
    update_data = {
        "lvl": current_exp,
        "avatar": fields['avatar'],
        "my_stage": _calculate_unlocked_stages(device_info, current_exp)
    }

    if fields['song_id'] not in range(616, 1024) or fields['mode'] not in range(0, 4):
        coin_mp = user_info['coin_mp'] if user_info else 1
        current_coin = device_info["coin"] if device_info and device_info["coin"] else 0
        update_data["coin"] = current_coin + COIN_REWARD * coin_mp

    await set_device_data_using_decrypted_fields(decrypted_fields, update_data)

    tree.getroot().find('.//after').text = str(rank)
    return Response(ET.tostring(tree.getroot(), encoding='unicode'), media_type=XML_CONTENT_TYPE)

routes = [
    Route('/result.php', result_request, methods=['GET'])
]