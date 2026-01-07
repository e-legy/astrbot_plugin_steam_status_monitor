# filepath: c:\Users\Maoer\Desktop\AstrBotLauncher-0.1.5.6\AstrBot\data\plugins\steam_status_monitor_V2\game_end_render.py
import os
import io
import time
import asyncio
import httpx
import json
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 更深的蓝紫色到黑色渐变
BG_COLOR_TOP = (24, 18, 48)   # 顶部深蓝紫
BG_COLOR_BOTTOM = (8, 8, 16)  # 底部接近黑色
AVATAR_SIZE = 312
COVER_W, COVER_H = 479, 718
IMG_W, IMG_H = 2048, 768

# 星星素材路径（假定与本文件同目录）
STAR_BG_PATH = os.path.join(os.path.dirname(__file__), "随机散布的小星星767x809xp.png")

SGDB_API_KEY = "00c703ea9a664ce236526aca0faeaaf4"

def get_steam_library_cover_url(appid, api_proxy=None) -> str | None:
    if api_proxy:
        api_url = f"https://{api_proxy.rstrip('/')}/IStoreBrowseService/GetItems/v1/"
    else:
        api_url = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
    
    # 构建多行参数字典
    input_json = {
        "ids": [{"appid": appid}],
        "context": {
            "language": "schinese",
            "country_code": "CN"
        },
        "data_request": {
            "include_assets": True
        }
    }

    params = {
        "input_json": json.dumps(input_json)
    }

    try:
        resp = requests.get(api_url, params=params)
        resp.raise_for_status()
        data = resp.json()

        item = data.get("response", {}).get("store_items", [{}])[0]
        assets = item.get("assets", {})
        
        # 拼接 URL
        format_template = assets.get("asset_url_format")
        filename = assets.get("library_capsule_2x") or assets.get("library_capsule")
        
        if format_template and filename:
            cdn_prefix = "https://shared.steamstatic.com/store_item_assets/"
            return cdn_prefix + format_template.replace("${FILENAME}", filename)
        print("[Steam官方封面] 未找到Steam图片资产")
        return None
    except Exception as e:
        print(f"[Steam官方封面] 发生错误: {e}")
        return None

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
                return None
            print(f"[SGDB主查] 成功获取到封面: {data2['data'][0]['url']}")
            return data2["data"][0]["url"]
        except Exception as e:
            print(f"[get_sgdb_vertical_cover] SGDB API异常: {e}")
            return None

def get_avatar_path(data_dir, steamid, url, force_update=False):
    avatar_dir = os.path.join(data_dir, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    path = os.path.join(avatar_dir, f"{steamid}.jpg")
    refresh_interval = 24 * 3600
    print(f"[game_end_render] get_avatar_path: url={url}, path={path}, exists={os.path.exists(path)}")
    if os.path.exists(path) and not force_update:
        if time.time() - os.path.getmtime(path) < refresh_interval:
            print(f"[game_end_render] 使用本地头像: {path}, size={os.path.getsize(path)}")
            return path
    try:
        import httpx
        resp = httpx.get(url, timeout=10)
        if resp.status_code == 200:
            with open(path, "wb") as f:
                f.write(resp.content)
            print(f"[game_end_render] 下载头像成功: {path}, size={os.path.getsize(path)}")
            return path
        else:
            print(f"[game_end_render] 头像下载失败: HTTP {resp.status_code} url={url}")
    except Exception as e:
        import traceback
        print(f"[game_end_render] 头像下载异常: {e}\n{traceback.format_exc()}")
    return path if os.path.exists(path) else None

def get_steamspy_average_forever(appid: int, steamspy_proxy: str = "") -> float | None:
    """
    从SteamSpy API获取指定APPID游戏的average_forever值
    
    Args:
        appid: 游戏的Steam APPID
        api_proxy: 可选的API代理域名（仅域名部分，如 example.com），
                   程序会自动拼接为完整的API请求地址
    
    Returns:
        int: 成功返回average_forever的值
        None: 失败时返回None
    """
    steamspy_api = "steamspy.com/api.php?request=appdetails&appid={appid}"
    
    # 根据是否提供代理构建完整URL
    if steamspy_proxy:
        final_url = f"https://{steamspy_proxy.rstrip('/')}/api.php?request=appdetails&appid={appid}"
    else:
        # 使用默认的SteamSpy官方地址
        final_url = f"https://{steamspy_api}"
    
    # 替换占位符为实际APPID
    final_url = final_url.format(appid=appid)
    
    try:
        # 发送GET请求，设置超时时间
        response = requests.get(final_url, timeout=10)
        response.raise_for_status()
        
        # 解析JSON数据
        data = response.json()
        
        # 提取并返回average_forever值
        if "average_forever" in data:
            hours = round(int(data["average_forever"]) / 60, 1)
            print(f" [game_end_render.py] 成功获取average_forever: {hours} 小时 (APPID: {appid})")
            return hours
        else:
            print(f" [game_end_render.py] 错误: 响应数据中未找到average_forever字段 - {data}")
            return None
    
    except requests.exceptions.Timeout:
        print(f" [game_end_render.py] 错误: 请求超时 (APPID: {appid})")
        return None
    except requests.exceptions.HTTPError as e:
        print(f" [game_end_render.py] 错误: HTTP请求失败 {e.response.status_code} (APPID: {appid})")
        return None
    except requests.exceptions.ConnectionError:
        print(f" [game_end_render.py] 错误: 连接失败 (APPID: {appid})")
        return None
    except json.JSONDecodeError:
        print(f" [game_end_render.py] 错误: 无法解析JSON响应 (APPID: {appid})")
        return None
    except Exception as e:
        print(f" [game_end_render.py] 未知错误: {str(e)} (APPID: {appid})")
        return None

# 渐变背景函数补充
def render_gradient_bg(img_w, img_h, color_top, color_bottom):
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

# get_cover_path 改为 async def 并 await get_sgdb_vertical_cover
async def get_cover_path(data_dir, gameid, game_name, force_update=False, sgdb_api_key=None, sgdb_game_name=None, appid=None, api_proxy=None):
    from PIL import Image as PILImage
    import httpx
    cover_dir = os.path.join(data_dir, "covers_v")
    os.makedirs(cover_dir, exist_ok=True)
    path = os.path.join(cover_dir, f"{gameid}.jpg")
    # 只在本地不存在时才云端获取
    if os.path.exists(path):
        return path
    
    # 尝试 Steam 官方竖版封面和 SGDB 竖版封面
    steam_url = get_steam_library_cover_url(appid, api_proxy=api_proxy)
    if steam_url:
        try:
            with httpx.stream("GET", steam_url, follow_redirects=True) as response:
                response.raise_for_status() # 确保请求成功
                with open(path, "wb") as f:
                    for chunk in response.iter_bytes(): # 逐块写入
                        f.write(chunk)
                return path
        except Exception as e:
            print(f"[get_cover_path] Steam官方封面下载异常: {e} url={steam_url}")
    url = await get_sgdb_vertical_cover(game_name, sgdb_api_key, sgdb_game_name=sgdb_game_name, appid=appid)
    if url:
        try:
            with httpx.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status() # 确保请求成功
                with open(path, "wb") as f:
                    for chunk in response.iter_bytes(): # 逐块写入
                        f.write(chunk)
                return path
        except Exception as e:
            print(f"[get_cover_path] SGDB下载异常: {e} url={url}")
    
    print(f"[get_cover_path] SGDB未收录或下载失败: {gameid} {game_name}")
    return None

def draw_duration_bar(draw, x, y, width, height, duration_h):
    pad = 1
    # 先画底色和描边
    draw.rounded_rectangle([x-pad, y-pad, x+width+pad, y+height+pad], radius=(height+pad)//2, fill=(0,0,0,180))
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height//2, outline=(0,0,0,255), width=1)
    draw.rounded_rectangle([x-2, y-2, x + width+2, y + height+2], radius=(height+4)//2, outline=(255,255,255,220), width=1)
    bar_colors = [
        (80, 200, 120),    # 1小时 绿色
        (255, 220, 80),    # 3小时 黄色
        (255, 160, 80),    # 5小时 橙色
        (255, 80, 80),     # 7小时 红色
        (200, 80, 160),    # 9小时 紫红色
        (120, 80, 200)     # 12小时 深紫色
    ]
    seg_limits = [1, 3, 5, 7, 9, 12]
    seg_starts = [0] + seg_limits[:-1]
    seg_texts = [None, "2X", "3X", "4X", "5X", "6X"]
    if duration_h > 12:
        # 彩色渐变条
        for i in range(width):
            ratio = i / max(width-1, 1)
            # 渐变色：红橙黄绿青蓝紫
            from colorsys import hsv_to_rgb
            rgb = hsv_to_rgb(ratio, 0.8, 1.0)
            color = tuple(int(c*255) for c in rgb)
            draw.line([(x+i, y), (x+i, y+height)], fill=color, width=1)
        # 叠加MAX文字
        try:
            font = ImageFont.truetype("msyhbd.ttc", height+8)
        except:
            font = ImageFont.load_default()
        text = "MAX"
        text_bbox = draw.textbbox((0,0), text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        center_x = x + width // 2 - text_w // 2
        center_y = y + height // 2 - text_h // 2 - 5
        draw.text((center_x, center_y), text, font=font, fill=(255,255,255,255), stroke_width=2, stroke_fill=(0,0,0,180))
    else:
        # 普通分段条
        for i, (seg_start, seg_end, color) in enumerate(zip(seg_starts, seg_limits, bar_colors)):
            seg_val = min(max(duration_h - seg_start, 0), seg_end - seg_start)
            seg_ratio = seg_val / (seg_end - seg_start) if seg_end > seg_start else 0
            seg_w = int(width * seg_ratio)
            if seg_w > 0:
                draw.rounded_rectangle([x, y, x + seg_w, y + height], radius=height//2, fill=color)
        for i, (seg_start, seg_end, color) in enumerate(zip(seg_starts, seg_limits, bar_colors)):
            if (seg_texts[i] and duration_h > seg_start):
                text = seg_texts[i]
                try:
                    font = ImageFont.truetype("msyhbd.ttc", height+6)
                except:
                    font = ImageFont.load_default()
                text_bbox = draw.textbbox((0,0), text, font=font)
                text_w = text_bbox[2] - text_bbox[0]
                text_h = text_bbox[3] - text_bbox[1]
                center_x = x + width // 2 - text_w // 2
                center_y = y + height // 2 - text_h // 2 - 5
                draw.text((center_x, center_y), text, font=font, fill=color, stroke_width=2, stroke_fill=(0,0,0,180))

def get_font_path(font_name):
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    font_path = os.path.join(fonts_dir, font_name)
    if (os.path.exists(font_path)):
        return font_path
    font_path2 = os.path.join(os.path.dirname(__file__), font_name)
    if (os.path.exists(font_path2)):
        return font_path2
    return font_name

def text_wrap(text, font, max_width):
    lines = []
    if not text:
        return [""]
    line = ""
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

def render_game_end_image(player_name, avatar_path, game_name, cover_path, end_time_str, tip_text, duration_h, playtime_hours, font_path=None, average_time=None):
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
            cover_resized = cover_src.resize((new_w, new_h), resample=1)
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

    # 3. 文本：头像右侧，整体垂直居中，左右留白，无背景
    text_x = avatar_x + avatar_size + status_width + avatar_margin
    text_y = avatar_y
    text_area_w = img_w - text_x - avatar_margin
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

    # “结束游玩”
    draw.text((text_x, text_y + line_height), "结束游玩", font=font_regular_player, fill=(132,133,134,255))
    # 游戏名自适应省略
    font_medium_player = ImageFont.truetype(font_medium, 70)
    game_name_text = text_truncate_with_ellipsis(game_name, font_medium_player, text_area_w)
    draw.text((text_x, text_y + 2 * line_height), game_name_text, font=font_medium_player, fill=(129,173,81,255))
    # 游戏时长
    playtime_forever_x = avatar_x
    playtime_y = img_h - 220
    playtime_margin = 60
    playtime_font = ImageFont.truetype(font_regular, 55)
    draw.text((playtime_forever_x, playtime_y), "已游玩", font=playtime_font, fill=(184,188,177,255))
    if duration_h is not None:
        playtime_str = f"{duration_h:.1f} 小时"
        draw.text((playtime_forever_x, playtime_y + line_height), playtime_str, font=playtime_font, fill=(151,156,136,255))
        print(f"[render_game_start_image] 渲染总游戏时长: {playtime_str}")
    else:
        playtime_str = "0.0 小时"
        print("[render_game_start_image] 未获取到游戏时长，duration_h=None")

    # 总游戏时间与平均游戏时间对比
    time_perscentage = min(int((playtime_hours / average_time) * 100), 100)
    time_text_x = avatar_x + calculate_text_width(playtime_str, font=playtime_font) + playtime_margin
    draw.text((time_text_x, playtime_y), "总游戏时间/平均游戏时间", font=playtime_font, fill=(184,188,177,255))
    bar_x = time_text_x
    bar_y = playtime_y + line_height + 3
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    test_bbox = dummy_draw.textbbox((0, 0), "测试文本", font=playtime_font)
    bar_h = test_bbox[3] - test_bbox[1]
    bar_w = img_w - bar_x - playtime_margin
    bar_radius = bar_h // 2
    # 底色
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=bar_radius, fill=(60, 62, 70, 180))
    # 高亮色
    time_fill = (26, 159, 255, 255)
    fill_w = int(bar_w * time_perscentage / 100)
    if fill_w > 0:
        draw.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), radius=bar_radius, fill=time_fill)
    # 文本
    time_percentage_text = f"{playtime_hours} 小时/{average_time} 小时 ({time_perscentage}%)"
    time_percentage_text_bbox = draw.textbbox((0,0), time_percentage_text, font=ImageFont.truetype(font_regular, 40))
    time_percentage_text_x = bar_x + 10
    time_percentage_text_y = bar_y + bar_h / 2 - (time_percentage_text_bbox[3] - time_percentage_text_bbox[1]) / 2 - 4
    draw.text((time_percentage_text_x, time_percentage_text_y), time_percentage_text, font=ImageFont.truetype(font_regular, 40), fill=(184,188,177,255))

    # 时间
    try:
        from datetime import datetime
        t = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
        time_str = t.strftime("%Y-%m-%d %H:%M")
    except Exception:
        time_str = end_time_str[-5:]
    draw.text((img_w - calculate_text_width(time_str, font=playtime_font) - playtime_margin, 30), time_str, font=playtime_font, fill=(255,255,255,255))

    return img.convert("RGB")

# render_game_end 里 await get_cover_path
async def render_game_end(data_dir, steamid, player_name, avatar_url, gameid, game_name, end_time_str, tip_text, duration_h, sgdb_api_key=None, font_path=None, sgdb_game_name=None, appid=None, api_key=None, api_proxy=None, steamspy_proxy: str=""):
    avatar_path = get_avatar_path(data_dir, steamid, avatar_url)
    cover_path = await get_cover_path(data_dir, gameid, game_name, sgdb_api_key=sgdb_api_key, sgdb_game_name=sgdb_game_name, appid=appid, api_proxy=api_proxy)
    playtime_hours = None
    average_time = get_steamspy_average_forever(gameid, steamspy_proxy=steamspy_proxy)
    print(f"api_key={api_key}, api_proxy={api_proxy}, steamid={steamid}, gameid={gameid}")
    if api_key:
        playtime_hours, *_ = await get_playtime_hours(api_key, steamid, gameid, api_proxy=api_proxy)
        print(f"playertime_hours={playtime_hours}")
    img = render_game_end_image(player_name, avatar_path, game_name, cover_path, end_time_str, tip_text, duration_h, playtime_hours=playtime_hours, font_path=font_path, average_time=average_time)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
