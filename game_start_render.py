import os
import io
import time
import httpx
from PIL import Image, ImageDraw, ImageFont
import random

BG_COLOR_TOP = (49, 80, 66)
BG_COLOR_BOTTOM = (28, 35, 44)
AVATAR_SIZE = 312
COVER_W, COVER_H = 479, 718
IMG_W, IMG_H = 2048, 768  # 16:6，画布高度减少三分之一


def get_avatar_path(data_dir, steamid, url, force_update=False):
    avatar_dir = os.path.join(data_dir, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    path = os.path.join(avatar_dir, f"{steamid}.jpg")
    refresh_interval = 24 * 3600
    if os.path.exists(path) and not force_update:
        if time.time() - os.path.getmtime(path) < refresh_interval:
            return path
    try:
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                f.write(resp.content)
            return path
    except Exception:
        pass
    return path if os.path.exists(path) else None

async def get_sgdb_vertical_cover(game_name, sgdb_api_key=None, sgdb_game_name=None, appid=None):
    import httpx
    if not sgdb_api_key:
        return None
    headers = {"Authorization": f"Bearer {sgdb_api_key}"}
    search_name = sgdb_game_name if sgdb_game_name else game_name
    search_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{search_name}"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(search_url, headers=headers)
            data = resp.json()
            if not data.get("success") or not data.get("data"):
                # 兜底：用 appid 查询 SGDB 游戏名
                if appid:
                    print(f"[SGDB兜底] appid={appid}，尝试通过appid查SGDB name")
                    game_url = f"https://www.steamgriddb.com/api/v2/games/steam/{appid}"
                    resp_game = await client.get(game_url, headers=headers)
                    data_game = resp_game.json()
                    if data_game.get("success") and data_game.get("data") and data_game["data"].get("name"):
                        sgdb_name = data_game["data"]["name"]
                        print(f"[SGDB兜底] appid={appid}，查到SGDB name={sgdb_name}，再次尝试查封面")
                        search_url2 = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{sgdb_name}"
                        resp2 = await client.get(search_url2, headers=headers)
                        data2 = resp2.json()
                        if data2.get("success") and data2.get("data"):
                            sgdb_game_id = data2["data"][0]["id"]
                            grid_url = f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_game_id}?dimensions=600x900&type=static&limit=1"
                            resp3 = await client.get(grid_url, headers=headers)
                            data3 = resp3.json()
                            if data3.get("success") and data3.get("data"):
                                print(f"[SGDB兜底] 成功获取到封面: {data3['data'][0]['url']}")
                                return data3["data"][0]["url"]
                        print(f"[SGDB兜底] 通过SGDB name未查到封面: {sgdb_name}")
                print(f"[SGDB兜底] 兜底流程未查到封面 appid={appid}")
                return None
            sgdb_game_id = data["data"][0]["id"]
            grid_url = f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_game_id}?dimensions=600x900&type=static&limit=1"
            resp2 = await client.get(grid_url, headers=headers)
            data2 = resp2.json()
            if not data2.get("success") or not data2.get("data"):
                print(f"[SGDB主查] 查到游戏但未查到封面 sgdb_game_id={sgdb_game_id}")
                # 主查查不到封面时也兜底
                if appid:
                    print(f"[SGDB主查兜底] appid={appid}，尝试通过appid查SGDB name")
                    game_url = f"https://www.steamgriddb.com/api/v2/games/steam/{appid}"
                    resp_game = await client.get(game_url, headers=headers)
                    data_game = resp_game.json()
                    if data_game.get("success") and data_game.get("data") and data_game["data"].get("name"):
                        sgdb_name = data_game["data"]["name"]
                        print(f"[SGDB主查兜底] appid={appid}，查到SGDB name={sgdb_name}，再次尝试查封面")
                        search_url2 = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{sgdb_name}"
                        resp2 = await client.get(search_url2, headers=headers)
                        data2 = resp2.json()
                        if data2.get("success") and data2.get("data"):
                            sgdb_game_id = data2["data"][0]["id"]
                            grid_url = f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_game_id}?dimensions=600x900&type=static&limit=1"
                            resp3 = await client.get(grid_url, headers=headers)
                            data3 = resp3.json()
                            if data3.get("success") and data3.get("data"):
                                print(f"[SGDB主查兜底] 成功获取到封面: {data3['data'][0]['url']}")
                                return data3["data"][0]["url"]
                        print(f"[SGDB主查兜底] 通过SGDB name未查到封面: {sgdb_name}")
                print(f"[SGDB主查兜底] 兜底流程未查到封面 appid={appid}")
                return None
            if data2.get("success") and data2.get("data"):
                # 遍历前3个封面，优先选静态
                for idx, grid in enumerate(data2["data"][:3]):
                    grid_type = grid.get("type")
                    grid_url = grid.get("url")
                    print(f"[SGDB遍历] idx={idx} type={grid_type} url={grid_url}")
                    if grid_type == "static":
                        print(f"[SGDB遍历] 选中静态封面: {grid_url}")
                        return grid_url
                # 如果没有静态，返回第一个可用封面
                if data2["data"]:
                    print(f"[SGDB遍历] 未找到静态，返回第一个封面: {data2['data'][0]['url']}")
                    return data2["data"][0]["url"]
            print(f"[SGDB主查] 成功获取到封面: {data2['data'][0]['url']}")
            return data2["data"][0]["url"]
        except Exception as e:
            print(f"[get_sgdb_vertical_cover] SGDB API异常: {e}")
            return None

async def get_cover_path(data_dir, gameid, game_name, force_update=False, sgdb_api_key=None, sgdb_game_name=None, appid=None):
    from PIL import Image as PILImage
    import httpx
    cover_dir = os.path.join(data_dir, "covers_v")
    os.makedirs(cover_dir, exist_ok=True)
    path = os.path.join(cover_dir, f"{gameid}.jpg")
    # 只在本地不存在时才云端获取
    if os.path.exists(path):
        return path
    # 只尝试 SGDB 竖版封面
    url = await get_sgdb_vertical_cover(game_name, sgdb_api_key, sgdb_game_name=sgdb_game_name, appid=appid)
    if url:
        try:
            resp = httpx.get(url, timeout=10)
            if resp.status_code == 200:
                with open(path, "wb") as f:
                    f.write(resp.content)
                return path
        except Exception as e:
            print(f"[get_cover_path] SGDB下载异常: {e} url={url}")
    print(f"[get_cover_path] SGDB未收录或下载失败: {gameid} {game_name}")
    return None

def text_wrap(text, font, max_width):
    """自动换行，返回行列表"""
    lines = []
    if not text:
        return [""]
    line = ""
    # 创建临时画布用于测量
    dummy_img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy_img)
    for char in text:
        bbox = draw.textbbox((0, 0), line + char, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            line += char
        else:
            lines.append(line)
            line = char
    if line:
        lines.append(line)
    return lines

def text_truncate_with_ellipsis(text, font, max_width, ellipsis="..."):
    """
    文本超出指定宽度后截断，末尾添加省略号（保证最终宽度≤max_width）
    :param text: 原始文本（str）
    :param font: Pillow ImageFont 对象（指定字体和字号）
    :param max_width: 最大允许宽度（像素）
    :param ellipsis: 省略号字符（默认"..."，可自定义如"…"）
    :return: 截断后的文本（str）
    """
    # 边界条件1：空文本直接返回空
    if not text:
        return ""
    # 边界条件2：最大宽度≤0，直接返回空（避免无效计算）
    if max_width <= 0:
        return ""
    
    # 创建临时绘图对象（仅用于测量文本宽度，轻量化）
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    
    # 第一步：先测量省略号自身的宽度（避免省略号占宽后超限）
    ellipsis_bbox = dummy_draw.textbbox((0, 0), ellipsis, font=font)
    ellipsis_width = ellipsis_bbox[2] - ellipsis_bbox[0]
    
    # 若省略号宽度已超过最大宽度，直接返回空（极端情况）
    if ellipsis_width >= max_width:
        return ""
    
    # 第二步：逐字符拼接文本，实时测量宽度（核心逻辑）
    truncated_text = ""
    # 剩余可用于正文的宽度 = 最大宽度 - 省略号宽度
    available_width = max_width - ellipsis_width
    
    for char in text:
        # 预计算：当前拼接文本 + 新字符 的宽度
        test_text = truncated_text + char
        test_bbox = dummy_draw.textbbox((0, 0), test_text, font=font)
        test_width = test_bbox[2] - test_bbox[0]
        
        # 若当前文本+新字符 ≤ 可用宽度，继续拼接
        if test_width <= available_width:
            truncated_text = test_text
        # 否则停止拼接，添加省略号并退出循环
        else:
            break
    
    # 第三步：最终处理（仅当原始文本被截断时才加省略号）
    # 测量原始文本完整宽度，判断是否需要加省略号
    original_bbox = dummy_draw.textbbox((0, 0), text, font=font)
    original_width = original_bbox[2] - original_bbox[0]
    
    if original_width > max_width:
        # 文本超限，返回「截断文本+省略号」
        return truncated_text + ellipsis
    else:
        # 文本未超限，返回原始文本
        return text
    
def calculate_text_width(text, font=None, font_size=20):
    if font is None:
        font = ImageFont.load_default(size=font_size)
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    return width

def get_chinese_length(text):
    """估算中文字符长度（1中文=2英文）"""
    length = 0
    for c in text:
        if '\u4e00' <= c <= '\u9fff':
            length += 1
        else:
            length += 0.5
    return int(length + 0.5)

def pad_game_name(game_name, min_cn_len=10):
    """游戏名后方补空格，渲染满10个中文字符宽度"""
    cur_len = get_chinese_length(game_name)
    pad_len = max(0, min_cn_len - cur_len)
    return game_name + "　" * pad_len + "   "  # 中文全角空格+3半角空格

def render_gradient_bg(img_w, img_h, color_top, color_bottom):
    """生成竖向渐变背景"""
    base = Image.new("RGB", (img_w, img_h), color_top)
    top_r, top_g, top_b = color_top
    bot_r, bot_g, bot_b = color_bottom
    for y in range(img_h):
        ratio = y / (img_h - 1)
        r = int(top_r * (1 - ratio) + bot_r * ratio)
        g = int(top_g * (1 - ratio) + bot_g * ratio)
        b = int(top_b * (1 - ratio) + bot_b * ratio)
        for x in range(img_w):
            base.putpixel((x, y), (r, g, b))
    return base

async def get_playtime_hours(api_key, steamid, appid, retry_times=3, api_proxy=None):
    """通过 Steam Web API 获取某玩家某游戏的总游玩小时数（异步实现，失败自动重试）"""
    import asyncio
    if api_proxy:
        url = (
            f"https://{api_proxy.rstrip('/')}/IPlayerService/GetOwnedGames/v1/"
            f"?key={api_key}&steamid={steamid}&include_appinfo=0&include_played_free_games=true&appids_filter={appid}"
        )
    else:
        url = (
            f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
            f"?key={api_key}&steamid={steamid}&include_appinfo=0&include_played_free_games=true&appids_filter={appid}"
    )
    for attempt in range(retry_times):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"[get_playtime_hours] API返回: {data}")
                    games = data.get("response", {}).get("games", [])
                    for g in games:
                        if str(g.get("appid")) == str(appid):
                            playtime_min = g.get("playtime_forever", 0)
                            playtime_2weeks_min = g.get("playtime_2weeks", 0)
                            playtime_hours = round(playtime_min / 60, 1)
                            playtime_2weeks_hours = round(playtime_2weeks_min / 60, 1)
                            return playtime_hours, playtime_2weeks_hours
                    print(f"[get_playtime_hours] 未找到目标游戏: steamid={steamid} appid={appid} games={games}")
                else:
                    print(f"[get_playtime_hours] HTTP状态码异常: {resp.status_code} url={url}")
        except Exception as e:
            print(f"[get_playtime_hours] 获取游玩时间异常: {e} url={url}")
        if attempt < retry_times - 1:
            await asyncio.sleep(1)
    return 0.0, 0.0

def get_font_path(font_name):
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    font_path = os.path.join(fonts_dir, font_name)
    if os.path.exists(font_path):
        return font_path
    font_path2 = os.path.join(os.path.dirname(__file__), font_name)
    if os.path.exists(font_path2):
        return font_path2
    return font_name

def render_game_start_image(player_name, avatar_path, game_name, cover_path, playtime_hours=None, online_count=None, font_path=None, playtime_2weeks_hours=None, unlocked_achievements=None, total_achievements=None):
    # 字体
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    font_regular = os.path.join(fonts_dir, 'HarmonyOS_Sans_SC_Regular.ttf')
    font_medium = os.path.join(fonts_dir, 'HarmonyOS_Sans_SC_Medium.ttf')
    if not os.path.exists(font_regular):
        font_regular = os.path.join(os.path.dirname(__file__), 'NotoSansHans-Regular.otf')
    if not os.path.exists(font_medium):
        font_medium = os.path.join(os.path.dirname(__file__), 'NotoSansHans-Medium.otf')
    try:
        font_bold = ImageFont.truetype(font_medium, 28)
        font = ImageFont.truetype(font_regular, 20)
        font_small = ImageFont.truetype(font_regular, 16)
    except:
        font_bold = font = font_small = ImageFont.load_default()

    res_dir = os.path.join(os.path.dirname(__file__), 'resources')
    background_img = os.path.join(res_dir, 'background.png')
    img_w = IMG_W
    img_h = IMG_H
    img = Image.open(background_img).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # 1. 封面图贴左，等比例缩放高度，宽度自适应，左贴右留空，不裁剪
    cover_area_h = COVER_H
    new_w = COVER_W  # 默认宽度，防止后续变量未定义
    if cover_path and os.path.exists(cover_path):
        try:
            cover_src = Image.open(cover_path).convert("RGBA")
            scale = cover_area_h / cover_src.height
            new_w = int(cover_src.width * scale)
            new_h = cover_area_h
            cover_resized = cover_src.resize((new_w, new_h), Image.LANCZOS)
            img.paste(cover_resized, (35, 25), cover_resized)
        except Exception as e:
            print(f"[render_game_start_image] 封面渲染失败: {e}")
            new_w = COVER_W  # 渲染失败时使用默认宽度

    # 2. 头像位置参数（不再渲染头像）
    avatar_size = AVATAR_SIZE  # 正方形头像边长
    avatar_margin = 86  # 头像与右侧文本的距离
    cover_margin = 131  # 封面与头像的距离
    cover_right = int(new_w)  # 封面右侧边界的Y坐标
    status_width = 17  # 在线状态条宽度
    avatar_x = cover_right + cover_margin  # 头像的X坐标
    avatar_y = 117

    # 新增：右上角显示在线人数，提前计算宽度
    online_text = None
    online_text_w = 0
    if online_count is not None:
        online_text = f"\u25CF{online_count}"
        online_text_w = calculate_text_width(online_text, font=ImageFont.truetype(font_regular, 55))  # 使用游戏时间字体

    # 3. 文本：头像右侧，整体垂直居中，左右留白，无背景
    text_x = avatar_x + avatar_size + status_width + avatar_margin
    text_y = avatar_y
    text_area_w = img_w - text_x - avatar_margin - online_text_w - 60
    line_height = 115  # 单行文本高度

    # 头像渲染（只保留一次）
    if avatar_path and os.path.exists(avatar_path):
        try:
            avatar = Image.open(avatar_path).convert("RGBA").resize((avatar_size, avatar_size))
            # 状态条
            status_bar = Image.new("RGBA", (status_width, avatar_size), (38, 157, 96, 255))
            avatar_img = Image.new("RGBA", (avatar_size + status_width, avatar_size), (0, 0, 0, 0))
            avatar_img.alpha_composite(avatar, (0, 0))
            avatar_img.alpha_composite(status_bar, (avatar_size, 0))
            img.alpha_composite(avatar_img, (avatar_x, avatar_y))
        except Exception as e:
            print(f"[render_game_start_image] 头像渲染失败: {e}")

    # 玩家名自适应省略，防止出界和与在线人数重叠
    font_regular_player = ImageFont.truetype(font_regular, 70)
    player_name_text = text_truncate_with_ellipsis(player_name, font_regular_player, text_area_w)
    draw.text((text_x, text_y), player_name_text, font=font_regular_player, fill=(190,214,165,255))

    # “正在玩”
    draw.text((text_x, text_y + line_height), "正在玩", font=font_regular_player, fill=(132,133,134,255))
    # 游戏名自适应省略
    font_medium_player = ImageFont.truetype(font_medium, 70)
    game_name_text = text_truncate_with_ellipsis(game_name, font_medium_player, img_w - text_x - avatar_margin)
    draw.text((text_x, text_y + 2 * line_height), game_name_text, font=font_medium_player, fill=(129,173,81,255))
    # 游戏时长
    playtime_2weeks_x = avatar_x
    playtime_y = img_h - 220
    playtime_margin = 60
    playtime_font = ImageFont.truetype(font_regular, 55)
    draw.text((playtime_2weeks_x, playtime_y), "过去两周", font=playtime_font, fill=(184,188,177,255))
    playtime_forever_x = playtime_2weeks_x + calculate_text_width("过去两周", font=playtime_font) + playtime_margin
    draw.text((playtime_forever_x, playtime_y), "总游戏时间", font=playtime_font, fill=(184,188,177,255))
    if playtime_2weeks_hours is not None:
        playtime_2weeks_str = f"{playtime_2weeks_hours} 小时"
        y_time = playtime_y + line_height
        draw.text(
            (playtime_2weeks_x, y_time),
            playtime_2weeks_str, font=playtime_font, fill=(151,156,136,255)
        )
        print(f"[render_game_start_image] 渲染近两周游戏时长: {playtime_2weeks_str}")
    else:
        print("[render_game_start_image] 未获取到近两周游戏时长，playtime_2weeks_hours=None")
    if playtime_hours is not None:
        playtime_str = f"{playtime_hours} 小时"
        y_time = playtime_y + line_height
        draw.text(
            (playtime_forever_x, y_time),
            playtime_str, font=playtime_font, fill=(151,156,136,255)
        )
        print(f"[render_game_start_image] 渲染总游戏时长: {playtime_str}")
    else:
        print("[render_game_start_image] 未获取到游戏时长，playtime_hours=None")

    # 时间
    from datetime import datetime
    now = datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M")
    draw.text((img_w - calculate_text_width(time_str, font=playtime_font) - playtime_margin, 30), time_str, font=playtime_font, fill=(255,255,255,255))


    # 在线人数渲染（放在最后，确保不会被玩家名遮挡）
    if online_text:
        draw.text((img_w - online_text_w - playtime_margin, avatar_y), online_text, font=playtime_font, fill=(120,180,255,180))

    # 成就进度条
    achievement_x = playtime_forever_x + calculate_text_width("总游戏时间", font=playtime_font) + playtime_margin
    draw.text((achievement_x, playtime_y), "成就", font=playtime_font, fill=(184,188,177,255))
    progress_percent = int(unlocked_achievements / total_achievements * 100) if total_achievements else 0
    bar_x = achievement_x
    bar_y = playtime_y + line_height + 3
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    test_bbox = dummy_draw.textbbox((0, 0), "测试文本", font=playtime_font)
    bar_h = test_bbox[3] - test_bbox[1]
    bar_w = img_w - bar_x - playtime_margin
    bar_radius = bar_h // 2
    # 底色
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=bar_radius, fill=(60, 62, 70, 180))
    # 高亮色
    progress_fill = (26, 159, 255, 255)
    fill_w = int(bar_w * progress_percent / 100)
    if fill_w > 0:
        draw.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), radius=bar_radius, fill=progress_fill)
    # 文本
    progress_text = f"{unlocked_achievements}/{total_achievements} ({progress_percent}%)"
    progress_text_bbox = draw.textbbox((0, 0), progress_text, font=playtime_font)
    progress_text_w = progress_text_bbox[2] - progress_text_bbox[0]
    draw.text((achievement_x + bar_w - progress_text_w, playtime_y), progress_text, fill=(142, 207, 255), font=playtime_font)

    return img.convert("RGB")

async def render_game_start(data_dir, steamid, player_name, avatar_url, gameid, game_name, details: dict, api_key=None, online_count=None, sgdb_api_key=None, font_path=None, sgdb_game_name=None, appid=None, api_proxy=None, unlocked_set: set = None):
    avatar_path = get_avatar_path(data_dir, steamid, avatar_url)
    cover_path = await get_cover_path(data_dir, gameid, game_name, sgdb_api_key=sgdb_api_key, sgdb_game_name=sgdb_game_name, appid=appid)
    playtime_hours = None
    playtime_2weeks_hours = None
    unlocked_achievements = len(unlocked_set)
    total_achievements = len(details)
    if api_key:
        playtime_hours, playtime_2weeks_hours = await get_playtime_hours(api_key, steamid, gameid, api_proxy=api_proxy)
    img = render_game_start_image(player_name, avatar_path, game_name, cover_path, playtime_hours, online_count, font_path=font_path, playtime_2weeks_hours=playtime_2weeks_hours, unlocked_achievements=unlocked_achievements, total_achievements=total_achievements)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
