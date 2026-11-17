"""HUD：對話框、三條量表（電量／心情／主人血壓）、分數連擊、事件列表、結算卡片（HTML）。"""
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
              "achievement": "🏅", "guardrail": "🛡️"}
def event_line(e):
    """事件文字前面加圖示；訊息本身已經以 emoji 開頭就不重複加。"""
    msg = e["msg"]
    if msg and unicodedata.category(msg[0]) == "So":
        return msg
    return f"{EVENT_ICON.get(e['type'], '•')} {msg}"


EMOTION_ICON = {"開心": "😄", "普通": "🙂", "委屈": "🥺", "生氣": "😠", "得意": "😎", "害怕": "😱"}
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


def hud_html(session, say="", events=(), thinking=False):
    g = session.game
    mode = "賣蠢模式" if session.mode == "silly" else "正經模式"
    emo = EMOTION_ICON.get(session.emotion, "🤖") if session.mode == "silly" else "🤖"
    bubble = "🤔 思考中……（機器人可能還在執行上一串動作）" if thinking else html.escape(say or "……")
    shown = [e for e in events if e["type"] not in QUIET_EVENTS][-6:]
    items = "".join(f"<li>{html.escape(event_line(e))}</li>" for e in shown)
    forb = "、".join(sorted(g.forbidden)) or "無"
    cmd = f"指令 {session.n_commands}"
    if g.cfg.get("par"):
        cmd += f"（標準 {g.cfg['par']}）"
    if session.commands_left() is not None:
        cmd += f"｜<b style='color:#d62828'>剩 {session.commands_left()} 句</b>"
    score = ""
    if session.gameplay:
        combo = f"｜🔥 連擊 x{session.score.combo}" if session.score.combo >= 2 else ""
        score = f"<b>分數 {session.score.score}</b>{combo}｜"
    tip = ""
    if session.n_commands == 0 and g.cfg.get("tip"):
        tip = f"<div style='font-size:12px;color:#777'>💡 {html.escape(g.cfg['tip'])}</div>"
    return (
        "<div style='font-family:sans-serif;max-width:660px;color:#222'>"
        "<div style='background:#fff8e1;border:2px solid #f4a261;border-radius:12px;padding:8px 12px;margin:4px 0'>"
        f"<b>{emo} 笨笨：</b>{bubble}</div>"
        f"{meters_html(session)}"
        f"<div style='font-size:13px;color:#444;margin-top:4px'>{html.escape(level_title(g.level_id))}｜{mode}｜{score}"
        f"灰塵剩 {len(g.dirt)}｜{cmd}｜禁區：{html.escape(forb)}｜違規 {g.violations}</div>{tip}"
        f"<ul style='font-size:13px;margin:4px 0;padding-left:20px'>{items}</ul>"
        f"{result_html(session)}</div>"
    )


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


def achievements_html(progress):
    from ..gameplay.achievements import ACHIEVEMENTS
    got = progress.unlocked_achievements
    items = "".join(
        f"<li style='opacity:{1 if a['id'] in got else 0.45}'>{a['icon'] if a['id'] in got else '❔'} "
        f"<b>{html.escape(a['name'])}</b>：{html.escape(a['desc'])}</li>" for a in ACHIEVEMENTS)
    return (f"<div style='font-family:sans-serif;font-size:13px'><b>成就 {len(got)}/{len(ACHIEVEMENTS)}</b>"
            f"<ul>{items}</ul></div>")
