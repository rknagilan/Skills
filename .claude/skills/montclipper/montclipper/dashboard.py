"""Review page: "Upload to Socials/All clips.html" (newest first). Open it by double-clicking in Finder."""
import json, html, os, urllib.parse
from pathlib import Path
from .common import CLIPS

PAGE = CLIPS / "All clips.html"

def _url(rel):
    return urllib.parse.quote(rel)

def build():
    CLIPS.mkdir(parents=True, exist_ok=True)
    (CLIPS / "Done").mkdir(exist_ok=True)
    items = []
    for mj in list(CLIPS.glob("*/.meta.json")) + list(CLIPS.glob("Done/*/.meta.json")):
        try:
            d = json.loads(mj.read_text())
        except Exception:
            continue
        d["_dir"] = mj.parent
        d["_done"] = mj.parent.parent.name == "Done"
        d["_mtime"] = mj.stat().st_mtime
        items.append(d)
    items.sort(key=lambda d: (d["_done"], -d["_mtime"]))
    cards = []
    for d in items:
        rel = os.path.relpath(d["_dir"], CLIPS)
        f = d.get("files", {})
        vid = f.get("vertical") or f.get("wide") or ""
        cov = f.get("cover_vertical", "")
        m = d.get("meta", {})
        link = lambda key, label: (f'<a href="{_url(rel + "/" + f[key])}">{label}</a>' if f.get(key) else "")
        links = " · ".join(x for x in [link("vertical", "Vertical video"), link("cover_vertical", "Vertical cover"),
                                        link("wide", "Wide video"), link("thumb_wide", "Wide thumbnail")] if x)
        cards.append(f"""<div class="card{' done' if d['_done'] else ''}">
<video src="{_url(rel + '/' + vid)}" poster="{_url(rel + '/' + cov) if cov else ''}" controls preload="none" playsinline></video>
<div class="b"><div class="s">{d.get('score', 0)}</div>
<h3>{html.escape(d.get('title', ''))}</h3>
<p class="m">{html.escape(m.get('channel', ''))} · {html.escape(m.get('stamp', ''))}{' · POSTED' if d['_done'] else ''}</p>
<p>{html.escape(d.get('reason', ''))}</p>
{'<p class="w">🎵 Music removed. Listen once before posting.</p>' if d.get('music_status') == 'removed' else ''}
{'<p class="w">⚠️ A song is playing. Remove the music before posting (CapCut: Audio → Isolate voice)</p>' if d.get('music_status') == 'needs_removal' else ''}
{'<p class="w">🎵 Background game music (no singing). Lower risk, usually fine to post.</p>' if d.get('music_status') == 'background_music' else ''}
<p class="l">{links} · <a href="{_url(rel + '/Upload notes.txt')}">Upload notes</a></p>
</div></div>""")
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MontClipper Clips</title>
<style>:root{{--bg:#0B1220;--card:#121C30;--tx:#fff;--mu:#9fb0c8;--ac:#FF7A2F;--te:#19C3B8}}
body{{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 -apple-system,system-ui,sans-serif}}
header{{padding:18px 16px;border-bottom:1px solid #1e2b45}} h1{{margin:0;font-size:22px}} header p{{margin:4px 0 0;color:var(--mu)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;padding:16px}}
.card{{background:var(--card);border-radius:12px;overflow:hidden}} .done{{opacity:.55}}
video{{width:100%;aspect-ratio:9/16;background:#000;display:block;object-fit:cover}}
.b{{padding:10px 12px;position:relative}} h3{{margin:0 48px 4px 0;font-size:16px}} p{{margin:4px 0}} .m{{color:var(--mu);font-size:13px}}
.s{{position:absolute;right:12px;top:10px;font-weight:800;background:var(--ac);color:#0B1220;border-radius:8px;padding:2px 8px}}
a{{color:var(--te)}} .w{{color:var(--ac);font-weight:700;font-size:13px}}</style></head><body><header><h1>MontClipper clips</h1>
<p>{sum(1 for d in items if not d['_done'])} ready to post · newest first · press play on any clip · reload the page to see new clips</p></header>
<div class="grid">{''.join(cards) or '<p style="padding:16px">No clips yet. They appear here as soon as they are ready.</p>'}</div></body></html>"""
    PAGE.write_text(page)
    return PAGE
