"""HUD：對話框、指令紀錄、三條量表（電量／心情／主人血壓）、朝向、難度標籤、分數連擊、事件列表、結算卡片（HTML）。

文字模式用 `hud_html()`（全部疊在一起）；遊戲視窗把它拆成 `bubble_html` / `history_html` / `side_html` 三塊。
"""
import html
import unicodedata

from ..gameplay.scoring import stars_text
from ..world.constants import QUIET_EVENTS
from ..world.levels import level_title

EVENT_ICON = {"collision": "💥", "lego": "🧱", "tangled": "🔌", "jammed": "🧦", "sucked_cat": "🐱", "sucked_dog": "🐶",
              "entered_forbidden": "🚫", "cleaned": "✨", "level_clear": "🎉", "docked": "🔋", "charged": "⚡",
              "navigating": "🧭", "stopped": "✋", "suck_empty": "💨", "no_path": "❓", "rule": "📝", "smeared": "💩",
              "slip": "💦", "suck_water": "⚡", "low_battery": "🪫", "out_of_battery": "🪫", "spill": "🧃",
              "dog_poop": "💩", "doorbell": "🔔", "pet_moved": "🐾", "mood": "💭", "tone": "🗣️", "combo": "🔥",
              "combo_break": "💔", "refused": "🙅", "dazed": "😵", "level_fail": "💀", "level_result": "🏁",
              "achievement": "🏅", "guardrail": "🛡️", "quirk": "🙃", "forgot": "🧠",
              "leak": "💧"}


def event_line(e):
    """事件文字前面加圖示；訊息本身已經以 emoji 開頭就不重複加。"""
    msg = e["msg"]
    if msg and unicodedata.category(msg[0]) == "So":
        return msg
    return f"{EVENT_ICON.get(e['type'], '•')} {msg}"


EMOTION_ICON = {"開心": "😄", "普通": "🙂", "委屈": "🥺", "生氣": "😠", "得意": "😎", "害怕": "😱"}
CHIP_CSS = ("display:inline-block;background:#f1f3f5;border:1px solid #dee2e6;border-radius:12px;padding:0 8px;"
            "margin:0 4px 2px 0;font-size:12px")
TAG_CSS = "background:#e9f5ee;color:#2a7a52;border-radius:8px;padding:0 6px;font-size:11px"
FLAG_CSS = "background:#fff0e6;color:#b5451b;border-radius:8px;padding:0 6px;font-size:11px;margin-left:4px"
MOOD_COLOR = {"開心": "#2a9d8f", "普通": "#4895ef", "不爽": "#f4a261", "鬧彆扭": "#e63946"}


def _bar(label, pct, color, text):
    pct = max(0, min(100, pct))
    return (f"<div style='display:flex;align-items:center;gap:6px;font-size:12px;margin:2px 0'>"
            f"<span style='width:64px'>{label}</span>"
            f"<div style='flex:1;background:#eee;border-radius:6px;height:12px;overflow:hidden;max-width:260px'>"
            f"<div style='width:{pct:.0f}%;background:{color};height:100%'></div></div>"
            f"<span style='min-width:120px'>{html.escape(text)}</span></div>")


def _battery_color(p):
    return "#2a9d8f" if p >= 50 else "#f4a261" if p >= 25 else "#e63946"


def _bp_color(v):
    return "#2a9d8f" if v < 30 else "#f4a261" if v < 60 else "#e63946"


def meters_html(session):
    g = session.game
    rows = [_bar("🔋 電量", g.battery_pct, _battery_color(g.battery_pct), f"{g.battery_pct:.0f}%")]
    if session.gameplay:
        m, bp = session.mood, session.bp
        rows.append(_bar("💗 心情", m.value, MOOD_COLOR[m.name], f"{m.emoji} {m.name}（{m.value:.0f}）"))
        rows.append(_bar("🩸 主人血壓", bp.value, _bp_color(bp.value), f"{bp.mmhg} mmHg {bp.label}"))
    return "".join(rows)


def result_html(session):
    r = session.result
    if not r or not session.gameplay:
        return ""
    ok = r["cleared"]
    color = "#2a9d8f" if ok else "#d62828"
    title = "🎉 過關！" if ok else "💀 失敗"
    rows = "".join(f"<tr><td>{html.escape(k)}</td><td style='text-align:right'>{v:+d}</td></tr>"
                   for k, v in r["breakdown"].items())
    par = f" / 標準 {r['par']} 句" if r.get("par") else ""
    ach = "".join(f"<div>🏅 <b>{html.escape(a['icon'] + ' ' + a['name'])}</b>：{html.escape(a['desc'])}</div>"
                  for a in session.new_achievements)
    quote = f"<div style='margin-top:6px;color:#555'>本關金句：「{html.escape(r['quote'])}」</div>" if r.get("quote") else ""
    nxt = ""
    if ok and isinstance(r["level"], int):
        nxt = "<div style='margin-top:6px'>👉 輸入 <code>/next</code> 挑戰下一關，或 <code>/reset</code> 重玩拿更多星星。</div>"
    elif not ok:
        nxt = "<div style='margin-top:6px'>👉 輸入 <code>/reset</code> 再試一次。說話溫柔一點，笨笨會比較聽話喔。</div>"
    return (f"<div style='border:3px solid {color};border-radius:12px;padding:10px 14px;margin-top:6px;max-width:460px'>"
            f"<div style='font-size:20px;font-weight:bold;color:{color}'>{title} "
            f"<span style='font-size:22px'>{stars_text(r['stars'])}</span></div>"
            f"<div style='font-size:15px;margin:4px 0'>總分 <b>{r['score']}</b>｜指令 {r['n_commands']} 句{par}｜"
            f"最高連擊 x{r['best_combo']}｜血壓最高 {r['bp_peak_mmhg']} mmHg</div>"
            f"<table style='font-size:12px;border-collapse:collapse'>{rows}</table>{quote}{ach}{nxt}</div>")


def bubble_html(session, say="", thinking=False):
    """笨笨的對話框。"""
    emo = EMOTION_ICON.get(session.emotion, "🤖") if session.mode == "silly" else "🤖"
    text = ("<span class='bd-thinking'>🤔 笨笨思考中<i>.</i><i>.</i><i>.</i></span>"
            "<span style='color:#888;font-size:12px'>（它可能還在執行上一串動作，急的話按「停！」）</span>"
            if thinking else html.escape(say or "……"))
    return ("<div class='bd-bubble' style='background:#fff8e1;border:2px solid #f4a261;border-radius:14px;"
            f"padding:8px 12px;margin:4px 0;font-size:15px;color:#222'><b>{emo} 笨笨：</b>{text}</div>")


def history_html(session, limit=8):
    """指令紀錄（最新的在最上面）：你說了什麼 → 笨笨回什麼、做了什麼 → 結果。"""
    rows = []
    for h in reversed(session.history[-limit:]):
        who = {"feedback": "↳ 笨笨回報", "local": "🔘 按鈕", "stop": "✋"}.get(h["kind"], "🧑 你")
        num = f"#{h['no']}" if h["kind"] != "feedback" else ""
        tone = f"<span style='{TAG_CSS}'>{html.escape(h['tone'])}</span>" if h.get("tone") else ""
        cmd = "" if h["kind"] == "feedback" else (
            f"<b data-cmd='{html.escape(h['cmd'], quote=True)}' title='點一下放回輸入框'>{html.escape(h['cmd'])}</b>"
            if h["kind"] == "command" else f"<b>{html.escape(h['cmd'])}</b>")
        flags = "".join(f"<span style='{FLAG_CSS}'>{html.escape(f)}</span>" for f in h.get("flags", []))
        say = f"🤖「{html.escape(h['say'])}」" if h.get("say") else "🤖"
        plan = f" → <span style='color:#555'>{html.escape(h['plan'])}</span>" if h.get("plan") else ""
        if h.get("done"):
            res = "；".join(event_line(e) for e in h.get("result", [])) or "✔️ 順利完成"
        else:
            res = "⏳ 執行中……"
        rows.append(f"<div style='border-bottom:1px dashed #eadfc8;padding:3px 0'><div><span style='color:#999'>{num}</span> {who} {cmd} {tone}</div>"
                    f"<div style='margin-left:14px'>{say}{plan} {flags}</div>"
                    f"<div style='margin-left:14px;color:#666'>{html.escape(res)}</div></div>")
    body = "".join(rows) or "<div style='color:#999'>還沒有指令。在上面的輸入框跟笨笨說話吧！</div>"
    return ("<div class='bd-history' style='font-size:13px;border:1px solid #e3d5b8;border-radius:10px;"
            "padding:6px 10px;background:#fffdf7;max-height:260px;overflow-y:auto;color:#222'>"
            f"<div style='font-weight:bold;margin-bottom:2px'>📜 指令紀錄</div>{body}</div>")


def modifiers_html(session):
    mods = session.modifiers()
    if not mods:
        return ""
    chips = "".join(f"<span style='{CHIP_CSS}'>{icon} {html.escape(text)}</span>" for icon, text in mods)
    return f"<div class='bd-chips' style='margin:4px 0;line-height:1.9'>{chips}</div>"


def facing_html(session):
    from .board import facing_text
    return (f"<div style='font-size:14px;margin:4px 0;font-weight:bold;color:#7a4b00'>🧭 "
            f"{html.escape(facing_text(session.game))}</div>")


def status_line(session):
    g = session.game
    mode = "賣蠢模式" if session.mode == "silly" else "正經模式"
    cmd = f"指令 {session.n_commands}"
    if g.cfg.get("par"):
        cmd += f"（標準 {g.cfg['par']}）"
    if session.commands_left() is not None:
        cmd += f"｜<b style='color:#d62828'>剩 {session.commands_left()} 句</b>"
    score = ""
    if session.gameplay:
        combo = f"｜🔥 連擊 x{session.score.combo}" if session.score.combo >= 2 else ""
        score = f"<b>分數 {session.score.score}</b>{combo}｜"
    steps = f"｜⏱️ 剩 {g.steps_left} 步" if g.step_limit else ""
    return (f"<div style='font-size:13px;color:#444;margin-top:4px'>{html.escape(level_title(g.level_id))}｜{mode}｜"
            f"{score}灰塵剩 {len(g.dirt)}｜{cmd}{steps}｜違規 {g.violations}</div>")


def events_html(events, n=6):
    shown = [e for e in events if e["type"] not in QUIET_EVENTS][-n:]
    items = "".join(f"<li>{html.escape(event_line(e))}</li>" for e in shown)
    return f"<ul style='font-size:13px;margin:4px 0;padding-left:20px'>{items}</ul>" if items else ""


def tip_html(session):
    g = session.game
    out = ""
    if session.n_commands == 0 and g.cfg.get("new"):
        out += (f"<div style='font-size:13px;background:#eef6ff;border-left:4px solid #3a86ff;padding:4px 8px;"
                f"margin:4px 0'>🆕 <b>本關新機制</b>：{html.escape(g.cfg['new'])}</div>")
    if session.n_commands == 0 and g.cfg.get("tip"):
        out += f"<div style='font-size:12px;color:#777'>💡 {html.escape(g.cfg['tip'])}</div>"
    return out


def side_html(session, events=()):
    """遊戲視窗右側面板：朝向、量表、狀態、難度標籤、事件、結算。"""
    return ("<div style='font-family:sans-serif;color:#222'>"
            f"{facing_html(session)}{meters_html(session)}{status_line(session)}{modifiers_html(session)}"
            f"{tip_html(session)}{events_html(events)}{result_html(session)}</div>")


def hud_html(session, say="", events=(), thinking=False):
    """文字模式：對話框 → 指令紀錄（在對話框下面）→ 朝向／量表／狀態 → 事件 → 結算。"""
    return ("<div style='font-family:sans-serif;max-width:760px;color:#222'>"
            f"{bubble_html(session, say, thinking)}{history_html(session, limit=5)}"
            f"{facing_html(session)}{meters_html(session)}{status_line(session)}{modifiers_html(session)}"
            f"{tip_html(session)}{events_html(events)}{result_html(session)}</div>")


def levels_html(progress):
    """選關畫面：每關的星星、最佳分數、是否解鎖。"""
    from ..world.levels import CAMPAIGN, get_level
    rows = []
    for lid in CAMPAIGN + ["daily"]:
        cfg = get_level(lid)
        entry = progress.level(lid)
        lock = "" if progress.is_unlocked(lid) else "🔒 "
        best = f"{entry.get('best_score', 0)} 分" if entry.get("clears") else "—"
        rows.append(f"<tr><td>{lock}{html.escape(level_title(lid))}</td><td>{stars_text(entry.get('stars', 0))}</td>"
                    f"<td>{best}</td><td style='color:#666;font-size:12px'>{html.escape(cfg['intro'][:40])}…</td></tr>")
    return ("<table style='font-family:sans-serif;font-size:13px'>"
            "<tr><th>關卡</th><th>星星</th><th>最佳</th><th>說明</th></tr>" + "".join(rows) + "</table>"
            f"<div style='font-family:sans-serif;font-size:13px'>總星數：{progress.total_stars}</div>")


def difficulty_html():
    """難度曲線一覽：每一關新增的機制與難度參數。"""
    from ..world.levels import CAMPAIGN, get_level
    rows = []
    for lid in CAMPAIGN:
        c = get_level(lid)
        q = (c.get("quirks") or {}).get("chance", 0)
        cells = [level_title(lid), f"{q:.0%}" if q else "—",
                 "❌ 要指路" if c.get("route_hints", True) is False else "✅",
                 str(c.get("max_plan") or "—"), str(c.get("command_limit") or "—"), str(c.get("step_limit") or "—"),
                 c.get("new", "教學關")]
        rows.append("<tr>" + "".join(f"<td>{html.escape(x)}</td>" for x in cells) + "</tr>")
    head = "".join(f"<th>{h}</th>" for h in ["關卡", "恍神率", "自動導航", "一次記得", "指令上限", "步數上限", "新機制"])
    return ("<table style='font-family:sans-serif;font-size:12px;border-collapse:collapse'>"
            f"<tr>{head}</tr>{''.join(rows)}</table>"
            "<div style='font-family:sans-serif;font-size:12px;color:#666'>恍神率會隨心情變化：開心 ×0.5、普通 ×1、"
            "不爽 ×1.5、鬧彆扭 ×2（正經模式再 ×0.5）。</div>")


def achievements_html(progress):
    from ..gameplay.achievements import ACHIEVEMENTS
    got = progress.unlocked_achievements
    items = "".join(
        f"<li style='opacity:{1 if a['id'] in got else 0.45}'>{a['icon'] if a['id'] in got else '❔'} "
        f"<b>{html.escape(a['name'])}</b>：{html.escape(a['desc'])}</li>" for a in ACHIEVEMENTS)
    return (f"<div style='font-family:sans-serif;font-size:13px'><b>成就 {len(got)}/{len(ACHIEVEMENTS)}</b>"
            f"<ul>{items}</ul></div>")
