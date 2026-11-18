"""文字模式與即時模式共用的「斜線指令」。"""
from ..render.hud import achievements_html, levels_html
from ..world.levels import CAMPAIGN, get_level, level_title

HELP = """<div style='font-family:sans-serif;font-size:13px'>
<b>斜線指令</b>：<code>/levels</code> 選關畫面｜<code>/level 3</code>、<code>/level daily</code> 換關｜<code>/next</code> 下一關｜
<code>/reset</code> 重來｜<code>/mode serious</code>、<code>/mode silly</code> 換模式｜<code>/achievements</code> 成就｜
<code>/guard</code> 開關禁區護欄｜<code>/view</code> 切換 2.5D／俯視視角｜<code>/unlock</code> 解鎖全部關卡｜<code>q</code> 離開<br>
<b>玩法提示</b>：說「請」「謝謝」、稱讚它、道歉 → 笨笨心情變好、比較聽話、比較少恍神；罵它、催它、一直重複 → 它會頂嘴甚至罷工。
出包會讓主人血壓飆高，爆表就失敗。「停」「回充」永遠有效。<br>
<b>看方向</b>：笨笨身上的黃色箭頭＝正前方；前方格子上的 1、2、3… 是「往前走幾格」；
「左」「右」標在它的左手邊、右手邊（是笨笨的左右，不是螢幕的左右）。</div>"""

COAX_LINES = ["笨笨你好棒，拜託你了～", "對不起剛剛太兇了，你最乖了！", "謝謝笨笨，辛苦了！"]


def parse_level_arg(arg):
    arg = arg.strip()
    if arg.isdigit():
        return int(arg)
    if arg == "daily" or arg.startswith("random:"):
        return arg
    raise ValueError(arg)


def change_level(session, level_id):
    """回傳 (成功?, 說明文字)。"""
    try:
        get_level(level_id)
    except (KeyError, RuntimeError):
        return False, f"沒有這一關：{level_id}"
    if not session.progress.is_unlocked(level_id):
        return False, f"🔒 {level_title(level_id)} 還沒解鎖：先通關前一關（或輸入 /unlock）。"
    session.reset(level_id)
    return True, session.game.cfg["intro"]


def next_level(session):
    lid = session.game.level_id
    if lid in CAMPAIGN and CAMPAIGN.index(lid) + 1 < len(CAMPAIGN):
        return change_level(session, CAMPAIGN[CAMPAIGN.index(lid) + 1])
    return change_level(session, "daily")


def handle_slash(session, text):
    """處理斜線指令。回傳 None（不是斜線指令）或 dict(say=..., html=...)。"""
    if not text.startswith("/"):
        return None
    cmd, _, arg = text[1:].partition(" ")
    cmd = cmd.lower()
    if cmd == "help":
        return {"say": "指令說明在下面 👇", "html": HELP}
    if cmd == "levels":
        return {"say": "選一關吧！（/level N）", "html": levels_html(session.progress)}
    if cmd in ("achievements", "ach"):
        return {"say": "看看你解鎖了哪些成就。", "html": achievements_html(session.progress)}
    if cmd == "level":
        try:
            ok, msg = change_level(session, parse_level_arg(arg))
        except ValueError:
            ok, msg = False, f"用法：/level 0～{CAMPAIGN[-1]}、/level daily、/level random:任意文字"
        return {"say": msg, "html": "", "changed": ok}
    if cmd == "next":
        ok, msg = next_level(session)
        return {"say": msg, "html": "", "changed": ok}
    if cmd == "reset":
        session.reset()
        return {"say": session.game.cfg["intro"], "html": "", "changed": True}
    if cmd == "mode":
        session.agent.mode = "serious" if "serious" in arg else "silly"
        return {"say": f"切換成{'正經' if session.mode == 'serious' else '賣蠢'}模式。", "html": ""}
    if cmd in ("guard", "guardrail"):
        if not session.guard_allowed:
            return {"say": "🛡️ 這一關的護欄壞掉了（進階關卡不能開），自己小心禁區！", "html": ""}
        session.guardrail = (arg.strip() != "off") if arg.strip() else not session.guardrail
        state = "開啟：闖禁區的計畫會被程式攔下" if session.guardrail else "關閉：笨笨可能會闖禁區（血壓 +18）"
        return {"say": f"🛡️ 護欄{state}。", "html": ""}
    if cmd == "view":
        session.view = "top" if getattr(session, "view", "iso") == "iso" else "iso"
        return {"say": f"🔄 切換成{'俯視（上方＝北）' if session.view == 'top' else '2.5D 等角'}視角。", "html": ""}
    if cmd == "unlock":
        session.progress.unlock_all = True
        return {"say": "🔓 全部關卡解鎖！", "html": levels_html(session.progress)}
    return {"say": f"看不懂的指令：/{cmd}（輸入 /help 看說明）", "html": ""}
