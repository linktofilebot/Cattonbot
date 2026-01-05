import os
import requests
import tempfile
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

# --- অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_ultra_premium_master_2026")

# --- ডাটাবেস ও ক্লাউড সেটিংস (আপনার তথ্যগুলো এখানে দিন) ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "7dc544d9253bccc3cfecc1c677f69819")

cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME", "dck0nrnt2"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY", "885392694246946"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET", "a7y3o299JJqLfxmj9rLMK3hNbcg") 
)

# MongoDB কানেকশন ও কালেকশনস
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col = db['movies']
    episodes_col = db['episodes']
    categories_col = db['categories']
    languages_col = db['languages']
    ott_col = db['ott_platforms']
    settings_col = db['settings']
    comments_col = db['comments']
except Exception as e:
    print(f"Database Connection Error: {e}")

# এডমিন ক্রেডেনশিয়াল
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# সাইট সেটিংস লোড ফাংশন
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", 
            "site_name": "MOVIEBOX PRO",
            "ad_link": "https://ad-link.com", 
            "ad_click_limit": 2,
            "notice_text": "Welcome to MovieBox Pro! Latest movies and web series are updated here.",
            "notice_color": "#00ff00",
            "popunder": "", 
            "native": ""
        }
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম রেসপন্সিভ CSS (অটো মোবাইল ও ডেক্সটপ) ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    /* হেডারে মাজখানে রেইনবো লোগো */
    .nav { background: rgba(0,0,0,0.96); padding: 15px; display: flex; justify-content: center; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { 
        font-size: clamp(22px, 6vw, 30px); font-weight: bold; text-decoration: none; text-transform: uppercase; 
        background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: rainbow 5s linear infinite; letter-spacing: 2px;
    }
    @keyframes rainbow { to { background-position: 400% center; } }
    
    .container { max-width: 1400px; margin: auto; padding: 15px; }

    /* নোটিশ ও সার্চ */
    .notice-bar { width: 100%; padding: 12px; margin-bottom: 20px; background: #111; border: 1px dashed #444; border-radius: 8px; text-align: center; font-weight: bold; font-size: 14px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 25px; padding: 5px 20px; border: 1px solid #333; width: 100%; max-width: 550px; margin: 0 auto 30px; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 10px; font-size: 15px; }

    /* কন্টেন্ট গ্রিড ও ব্যাজ সিস্টেম */
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 22px; } }
    
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; position: relative; display: block; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
    .card:hover { border-color: var(--main); transform: translateY(-5px); box-shadow: 0 5px 15px rgba(229, 9, 20, 0.4); }
    
    /* ব্যাজ ডিজাইন (ম্যানুয়াল টেক্সট) */
    .badge-manual { position: absolute; top: 10px; right: 10px; background: var(--main); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase; z-index: 5; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
    .badge-ott { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.85); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase; z-index: 5; border: 1px solid #444; }
    
    .card-title { padding: 10px; text-align: center; font-size: 13px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }

    /* প্লেয়ার ও এপিসোড */
    video { width: 100%; border-radius: 12px; background: #000; aspect-ratio: 16/9; box-shadow: 0 0 20px rgba(0,0,0,0.6); }
    .ep-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(85px, 1fr)); gap: 10px; margin: 20px 0; }
    .ep-btn { background: #222; color: #fff; padding: 12px; text-align: center; border-radius: 6px; cursor: pointer; border: 1px solid #333; font-size: 12px; font-weight: bold; }
    .ep-btn.active { background: var(--main); border-color: var(--main); box-shadow: 0 0 10px var(--main); }

    /* সোশ্যাল বার ও কমেন্ট */
    .action-bar { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; }
    .soc-btn { background: #1a1a1a; color: #fff; padding: 12px 18px; border-radius: 6px; border: 1px solid #333; cursor: pointer; text-decoration: none; font-size: 14px; display: flex; align-items: center; gap: 8px; transition: 0.3s; }
    .soc-btn:hover { background: #333; }

    .com-section { background: #0f0f0f; padding: 20px; border-radius: 12px; margin-top: 35px; border: 1px solid #222; }
    .com-item { background: #161616; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #252525; position: relative; }
    .com-user { color: var(--main); font-weight: bold; font-size: 14px; }
    .com-like-btn { position: absolute; bottom: 12px; right: 20px; font-size: 13px; color: #777; text-decoration: none; display: flex; align-items: center; gap: 5px; }
    .com-like-btn:hover { color: var(--main); }

    /* প্রোগ্রেস বার */
    .progress-container { width: 100%; background: #222; border-radius: 10px; margin: 15px 0; display: none; overflow: hidden; border: 1px solid #444; }
    .progress-bar { width: 0%; height: 20px; background: linear-gradient(to right, #e50914, #ff4d4d); text-align: center; font-size: 12px; line-height: 20px; font-weight: bold; color: #fff; transition: 0.2s; }

    /* এডমিন ড্রয়ার */
    .drw { position: fixed; top: 0; right: -100%; width: 300px; height: 100%; background: #0a0a0a; border-left: 1px solid #333; transition: 0.4s; z-index: 2000; padding-top: 50px; overflow-y: auto; }
    .drw.active { right: 0; }
    .drw a, .drw span { padding: 18px 25px; display: block; color: #fff; font-weight: bold; text-decoration: none; border-bottom: 1px solid #222; cursor: pointer; }
    .drw a:hover, .drw span:hover { background: #1a1a1a; color: var(--main); }
    .sec-box { display: none; background: #111; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #222; }
    input, select, textarea { width: 100%; padding: 14px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }
    .btn-main { background: var(--main); color: #fff; border: none; padding: 14px 25px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; font-size: 16px; text-decoration: none; }
    .stat-card { background: #1a1a1a; padding: 15px; border-radius: 8px; flex: 1; min-width: 120px; text-align: center; border: 1px solid #333; }
    .stat-card b { font-size: 22px; color: var(--main); display: block; }
</style>
"""

# --- টেম্পলেট ১: হোমপেজ ---
HOME_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    <div class="notice-bar" style="color: {{ s.notice_color }};">
        <i class="fas fa-bullhorn"></i> {{ s.notice_text }}
    </div>
    
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies, web series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#888;"><i class="fas fa-search"></i></button>
    </form>

    {% if query %}
        <div class="cat-title">Search Results</div>
        <div class="grid">
            {% for m in movies %}
            <a href="/content/{{ m._id }}" class="card">
                {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                {% if m.ott %}<div class="badge-ott">{{ m.ott }}</div>{% endif %}
                <img src="{{ m.poster }}" loading="lazy">
                <div class="card-title">{{ m.title }} ({{ m.year }})</div>
            </a>
            {% endfor %}
        </div>
    {% else %}
        {% for cat in categories %}
            {% set cat_id_str = cat._id|string %}
            <div class="cat-title">{{ cat.name }}</div>
            <div class="grid">
                {% for m in movies if m.category_id == cat_id_str %}
                <a href="/content/{{ m._id }}" class="card">
                    {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                    {% if m.ott %}<div class="badge-ott">{{ m.ott }}</div>{% endif %}
                    <img src="{{ m.poster }}" loading="lazy">
                    <div class="card-title">{{ m.title }} ({{ m.year }})</div>
                </a>
                {% endfor %}
            </div>
        {% endfor %}
        <div class="cat-title">Recently Added</div>
        <div class="grid">
            {% for m in movies[:24] %}
            <a href="/content/{{ m._id }}" class="card">
                {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                {% if m.ott %}<div class="badge-ott">{{ m.ott }}</div>{% endif %}
                <img src="{{ m.poster }}" loading="lazy">
                <div class="card-title">{{ m.title }}</div>
            </a>
            {% endfor %}
        </div>
    {% endif %}
</div>
{{ s.popunder|safe }}
"""

# --- টেম্পলেট ২: ডিটেইলস পেজ ---
DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div style="background: url('{{ m.backdrop }}') center/cover fixed; position: fixed; top:0; left:0; width:100%; height:100%; filter: blur(35px) brightness(0.2); z-index:-1;"></div>
<div class="container">
    <div style="max-width: 950px; margin: auto;">
        <video id="vBox" controls poster="{{ m.backdrop }}">
            <source src="{% if m.type == 'movie' %}{{ m.video_url }}{% endif %}" type="video/mp4">
        </video>

        {% if m.type == 'series' %}
        <div class="cat-title">Select Episode</div>
        <div class="ep-grid">
            {% for ep in episodes %}
            <div class="ep-btn" onclick="playEp('{{ ep.video_url }}', this)">S{{ ep.season }} E{{ ep.episode }}</div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="social-bar">
            <a href="/like/{{ m._id }}" class="soc-btn"><i class="fas fa-heart" style="color:red;"></i> {{ m.likes or 0 }} Likes</a>
            <div class="soc-btn" onclick="navigator.clipboard.writeText(window.location.href); alert('Link Copied!')"><i class="fas fa-link"></i> Share</div>
            <a href="https://api.whatsapp.com/send?text={{ share_url }}" target="_blank" class="soc-btn" style="background:#25d366;"><i class="fab fa-whatsapp"></i> WhatsApp</a>
        </div>

        <h1 style="font-size:30px; margin-bottom:10px;">{{ m.title }} ({{ m.year }}) <span style="font-size:14px; color:var(--main);">[{{ m.language }}]</span></h1>
        
        <button onclick="dlHandle()" class="btn-main" style="height:65px; font-size:22px; margin-top:15px;">📥 DOWNLOAD NOW</button>
        <p id="dl-msg" style="text-align:center; color:var(--main); margin-top:15px; font-weight:bold;"></p>

        <div class="com-section">
            <h3>Discussions</h3>
            <form action="/comment/{{ m._id }}" method="POST">
                <input type="text" name="user" placeholder="Your Name" required>
                <textarea name="text" rows="3" placeholder="Write a comment..." required></textarea>
                <button class="btn-main" style="width: auto; padding: 10px 30px; margin-top:10px;">Post</button>
            </form>
            {% for c in comments %}
            <div class="com-item">
                <span class="com-user">{{ c.user }} <small style="float:right;">{{ c.date }}</small></span>
                <div class="com-txt">{{ c.text }}</div>
                <a href="/like_comment/{{ m._id }}/{{ c._id }}" class="com-like-btn"><i class="fas fa-thumbs-up"></i> {{ c.likes or 0 }}</a>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
<script>
    let activeUrl = "{% if m.type == 'movie' %}{{ m.video_url }}{% endif %}";
    function playEp(url, el) {
        activeUrl = url; let p = document.getElementById('vBox');
        p.src = url; p.play();
        document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
        el.classList.add('active');
    }
    let ads = 0;
    function dlHandle() {
        if(!activeUrl) { alert("Select episode first!"); return; }
        if(ads < {{ s.ad_click_limit }}) {
            ads++;
            document.getElementById('dl-msg').innerText = "Ads Opening... (" + ads + "/{{ s.ad_click_limit }})";
            window.open("{{ s.ad_link }}", "_blank");
        } else {
            window.location.href = activeUrl.replace("/upload/", "/upload/fl_attachment/");
        }
    }
</script>
"""

# --- টেম্পলেট ৩: এডমিন প্যানেল ---
ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:32px; color:var(--main); position:absolute; right:5%;" onclick="toggleMenu()">☰</div></nav>
<div class="drw" id="drw">
    <a href="/" style="background:var(--main);"><i class="fas fa-eye"></i> 👁️ View Site</a>
    <span onclick="openSec('upBox')"><i class="fas fa-upload"></i> 📤 Upload Content</span>
    <span onclick="openSec('epBox')"><i class="fas fa-plus-circle"></i> 🎞️ Add Episode</span>
    <span onclick="openSec('manageBox')"><i class="fas fa-tasks"></i> 🎬 Manage All</span>
    <span onclick="openSec('ottBox')"><i class="fas fa-tv"></i> 📺 OTT Platforms</span>
    <span onclick="openSec('catBox')"><i class="fas fa-list"></i> 📂 Categories</span>
    <span onclick="openSec('langBox')"><i class="fas fa-language"></i> 🌐 Languages</span>
    <span onclick="openSec('setBox')"><i class="fas fa-cog"></i> ⚙️ Settings</span>
    <a href="/logout" style="color:red;"><i class="fas fa-sign-out-alt"></i> 🔴 Logout</a>
</div>

<div class="container">
    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px;">
        <div class="stat-card"><b>{{ counts.movies }}</b>Movies</div>
        <div class="stat-card"><b>{{ counts.series }}</b>Series</div>
        <div class="stat-card"><b>{{ counts.episodes }}</b>Episodes</div>
    </div>

    <!-- কন্টেন্ট আপলোড উইথ প্রোগ্রেস বার -->
    <div id="upBox" class="sec-box" style="display:block;">
        <h3>📤 Upload Movie/Series</h3>
        <div style="display:flex; gap:10px;"><input type="text" id="tmdbQ"><button onclick="tmdbSearch()" class="btn-main" style="width:100px;">Search</button></div>
        <div id="tmdbRes" style="display:flex; gap:10px; overflow-x:auto; margin:10px 0; background:#000; padding:10px;"></div>
        <form id="upFrm">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <input type="text" name="manual_badge" placeholder="Poster Badge Text (e.g. HD, 4K, New)">
            <select name="type"><option value="movie">Movie</option><option value="series">Web Series</option></select>
            <select name="language">
                <option value="">Language</option>
                {% for l in languages %}<option value="{{ l.name }}">{{ l.name }}</option>{% endfor %}
            </select>
            <select name="ott">
                <option value="">OTT Label</option>
                {% for o in otts %}<option value="{{ o.name }}">{{ o.name }}</option>{% endfor %}
            </select>
            <select name="category_id">
                {% for c in categories %}<option value="{{ c._id|string }}">{{ c.name }}</option>{% endfor %}
            </select>
            <input type="file" name="video_file" id="f_up" accept="video/mp4">
            <div class="progress-container" id="pCont"><div class="progress-bar" id="pBar">0%</div></div>
            <button type="button" onclick="uploadContent()" class="btn-main" style="background:green;">SAVE CONTENT</button>
        </form>
    </div>

    <!-- এপিসোড আপলোড উইথ সার্চ -->
    <div id="epBox" class="sec-box">
        <h3>🎞️ Add Episode</h3>
        <input type="text" id="sSch" placeholder="🔍 Search series name..." onkeyup="findS()" style="border: 2px solid var(--main);">
        <form id="epFrm">
            <select name="series_id" id="sSel">
                {% for m in movies if m.type == 'series' %}<option value="{{ m._id|string }}">{{ m.title }}</option>{% endfor %}
            </select>
            <input type="number" name="season" placeholder="Season" required>
            <input type="number" name="episode" placeholder="Episode" required>
            <input type="file" name="video_file" id="f_ep" accept="video/mp4" required>
            <div class="progress-container" id="epPCont"><div class="progress-bar" id="epPBar">0%</div></div>
            <button type="button" onclick="uploadEp()" class="btn-main" style="background:blue;">UPLOAD EPISODE</button>
        </form>
    </div>

    <!-- ম্যানেজ কন্টেন্ট (সার্চ ও বাল্ক ডিলিট) -->
    <div id="manageBox" class="sec-box">
        <h3>🎬 Manage All Content</h3>
        <input type="text" id="mSch" placeholder="🔍 Search movie/series name to delete..." onkeyup="filterManage()">
        <form action="/bulk_delete" method="POST">
            <div style="max-height: 450px; overflow-y: auto; margin-top:15px;">
                <table style="width:100%; text-align:left; border-collapse:collapse;">
                    <tr style="border-bottom:1px solid #444;">
                        <th><input type="checkbox" onclick="selectAll(this)"></th>
                        <th>Title</th>
                        <th>Type</th>
                        <th>Action</th>
                    </tr>
                    {% for m in movies %}
                    <tr class="m-row" style="border-bottom:1px solid #222;">
                        <td><input type="checkbox" name="ids" value="{{ m._id }}"></td>
                        <td>{{ m.title }}</td>
                        <td>{{ m.type }}</td>
                        <td><a href="/del_movie/{{ m._id }}" style="color:red; text-decoration:none;">Delete</a></td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
            <button class="btn-main" style="margin-top:15px; background:red;">DELETE SELECTED</button>
        </form>
    </div>

    <div id="ottBox" class="sec-box">
        <h3>📺 OTT Labels</h3>
        <form action="/add_ott" method="POST"><input type="text" name="name" required><button class="btn-main">Add</button></form>
        {% for o in otts %}<p style="padding:8px; border-bottom:1px solid #222;">{{ o.name }} <a href="/del_ott/{{ o._id }}" style="color:red; float:right;">X</a></p>{% endfor %}
    </div>

    <div id="catBox" class="sec-box">
        <h3>📂 Categories</h3>
        <form action="/add_cat" method="POST"><input type="text" name="name" required><button class="btn-main">Add</button></form>
        {% for c in categories %}<p style="padding:8px; border-bottom:1px solid #222;">{{ c.name }} <a href="/del_cat/{{ c._id }}" style="color:red; float:right;">X</a></p>{% endfor %}
    </div>

    <div id="langBox" class="sec-box">
        <h3>🌐 Languages</h3>
        <form action="/add_lang" method="POST"><input type="text" name="name" required><button class="btn-main">Add</button></form>
        {% for l in languages %}<p style="padding:8px; border-bottom:1px solid #222;">{{ l.name }} <a href="/del_lang/{{ l._id }}" style="color:red; float:right;">X</a></p>{% endfor %}
    </div>

    <div id="setBox" class="sec-box">
        <h3>⚙️ Settings</h3>
        <form action="/update_settings" method="POST">
            <input type="text" name="site_name" value="{{ s.site_name }}">
            <input type="text" name="notice_text" value="{{ s.notice_text }}">
            <input type="text" name="notice_color" value="{{ s.notice_color }}">
            <input type="text" name="ad_link" value="{{ s.ad_link }}">
            <input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}">
            <button class="btn-main">SAVE SETTINGS</button>
        </form>
    </div>
</div>
<script>
    function toggleMenu() { document.getElementById('drw').classList.toggle('active'); }
    function openSec(id) { document.querySelectorAll('.sec-box').forEach(b => b.style.display='none'); document.getElementById(id).style.display='block'; toggleMenu(); }
    
    function findS() {
        let q = document.getElementById('sSch').value.toLowerCase();
        let sel = document.getElementById('sSel');
        for (let i = 0; i < sel.options.length; i++) { sel.options[i].style.display = sel.options[i].text.toLowerCase().includes(q) ? "block" : "none"; }
    }

    function filterManage() {
        let q = document.getElementById('mSch').value.toLowerCase();
        document.querySelectorAll('.m-row').forEach(row => { row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none"; });
    }

    function selectAll(source) {
        document.querySelectorAll('input[name="ids"]').forEach(cb => cb.checked = source.checked);
    }

    async function tmdbSearch(){
        let q = document.getElementById('tmdbQ').value;
        let r = await fetch(`/api/tmdb?q=${q}`);
        let d = await r.json();
        let res = document.getElementById('tmdbRes'); res.innerHTML = '';
        d.results.slice(0,5).forEach(i => {
            let img = document.createElement('img'); img.src = "https://image.tmdb.org/t/p/w92" + i.poster_path; img.style.height="80px"; img.style.cursor="pointer";
            img.onclick = () => {
                document.getElementById('t').value = i.title || i.name;
                document.getElementById('y').value = (i.release_date || i.first_air_date || '').split('-')[0];
                document.getElementById('p').value = "https://image.tmdb.org/t/p/w500" + i.poster_path;
                document.getElementById('b').value = "https://image.tmdb.org/t/p/original" + i.backdrop_path;
            };
            res.appendChild(img);
        });
    }

    function uploadContent(){
        let fd = new FormData(document.getElementById('upFrm'));
        let xhr = new XMLHttpRequest();
        document.getElementById('pCont').style.display = 'block';
        xhr.upload.onprogress = (e) => {
            let p = Math.round((e.loaded / e.total) * 100);
            document.getElementById('pBar').style.width = p + '%';
            document.getElementById('pBar').innerText = p + '%';
        };
        xhr.open("POST", "/add_content");
        xhr.onload = () => { alert("Saved!"); location.reload(); };
        xhr.send(fd);
    }

    function uploadEp(){
        let fd = new FormData(document.getElementById('epFrm'));
        let xhr = new XMLHttpRequest();
        document.getElementById('epPCont').style.display = 'block';
        xhr.upload.onprogress = (e) => {
            let p = Math.round((e.loaded / e.total) * 100);
            document.getElementById('epPBar').style.width = p + '%';
            document.getElementById('epPBar').innerText = p + '%';
        };
        xhr.open("POST", "/add_episode");
        xhr.onload = () => { alert("Episode Added!"); location.reload(); };
        xhr.send(fd);
    }
</script>
"""

# --- Flask রাউটস (লজিক) ---

@app.route('/')
def index():
    query = request.args.get('q')
    cats = list(categories_col.find())
    if query:
        movies = list(movies_col.find({"title": {"$regex": query, "$options": "i"}}).sort("_id", -1))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(HOME_HTML, categories=cats, movies=movies, query=query, s=get_config())

@app.route('/content/<id>')
def content_detail(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    if not m: return redirect('/')
    episodes = list(episodes_col.find({"series_id": id}).sort([("season", 1), ("episode", 1)]))
    comments = list(comments_col.find({"movie_id": id}).sort("_id", -1))
    share_url = request.url
    return render_template_string(DETAIL_HTML, m=m, episodes=episodes, comments=comments, share_url=share_url, s=get_config())

@app.route('/like/<id>')
def like_content(id):
    movies_col.update_one({"_id": ObjectId(id)}, {"$inc": {"likes": 1}})
    return redirect(f'/content/{id}')

@app.route('/like_comment/<m_id>/<c_id>')
def like_comment(m_id, c_id):
    comments_col.update_one({"_id": ObjectId(c_id)}, {"$inc": {"likes": 1}})
    return redirect(f'/content/{m_id}')

@app.route('/comment/<id>', methods=['POST'])
def add_comment(id):
    comments_col.insert_one({"movie_id": id, "user": request.form.get('user'), "text": request.form.get('text'), "likes": 0, "date": datetime.now().strftime("%d %b, %Y")})
    return redirect(f'/content/{id}')

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin</h2><input type="text" name="u" placeholder="Admin" required><input type="password" name="p" placeholder="Pass" required><button class="btn-main">LOGIN</button></form></div>""")
    counts = {"movies": movies_col.count_documents({"type": "movie"}), "series": movies_col.count_documents({"type": "series"}), "episodes": episodes_col.count_documents({})}
    return render_template_string(ADMIN_HTML, movies=list(movies_col.find().sort("_id", -1)), languages=list(languages_col.find()), categories=list(categories_col.find()), otts=list(ott_col.find()), counts=counts, s=get_config())

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Fail"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "No", 401
    file = request.files.get('video_file')
    v_url = ""
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name)
            up = cloudinary.uploader.upload_large(tf.name, resource_type="video", chunk_size=6000000)
            v_url = up['secure_url']
        os.remove(tf.name)
    movies_col.insert_one({
        "title": request.form.get('title'), "year": request.form.get('year'), "poster": request.form.get('poster'), "backdrop": request.form.get('backdrop'), "type": request.form.get('type'), "manual_badge": request.form.get('manual_badge'), "language": request.form.get('language'), "ott": request.form.get('ott'), "category_id": str(request.form.get('category_id')), "video_url": v_url, "likes": 0
    })
    return "OK"

@app.route('/add_episode', methods=['POST'])
def add_episode():
    if not session.get('auth'): return "No", 401
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name)
            up = cloudinary.uploader.upload_large(tf.name, resource_type="video", chunk_size=6000000)
            episodes_col.insert_one({"series_id": request.form.get('series_id'), "season": int(request.form.get('season')), "episode": int(request.form.get('episode')), "video_url": up['secure_url'], "likes": 0})
        os.remove(tf.name)
    return "OK"

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'):
        movies_col.delete_one({"_id": ObjectId(id)})
        episodes_col.delete_many({"series_id": id})
    return redirect('/admin')

@app.route('/bulk_delete', methods=['POST'])
def bulk_delete():
    if session.get('auth'):
        ids = request.form.getlist('ids')
        for i in ids:
            movies_col.delete_one({"_id": ObjectId(i)})
            episodes_col.delete_many({"series_id": i})
    return redirect('/admin')

@app.route('/add_cat', methods=['POST'])
def add_cat():
    if session.get('auth'): categories_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_cat/<id>')
def del_cat(id):
    if session.get('auth'): categories_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/add_lang', methods=['POST'])
def add_lang():
    if session.get('auth'): languages_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_lang/<id>')
def del_lang(id):
    if session.get('auth'): languages_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/add_ott', methods=['POST'])
def add_ott():
    if session.get('auth'): ott_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_ott/<id>')
def del_ott(id):
    if session.get('auth'): ott_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {
            "site_name": request.form.get('site_name'), "notice_text": request.form.get('notice_text'), "notice_color": request.form.get('notice_color'), "ad_link": request.form.get('ad_link'), "ad_click_limit": int(request.form.get('ad_click_limit', 0))
        }})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
