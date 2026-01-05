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

# --- ডাটাবেস ও ক্লাউড সেটিংস ---
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
            "notice_text": "Welcome to MovieBox Pro!",
            "notice_color": "#00ff00",
            "popunder": "", 
            "native_ad": "",
            "banner_ad": "",
            "socialbar_ad": ""
        }
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম রেসপন্সিভ CSS ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    .nav { background: rgba(0,0,0,0.96); padding: 15px; display: flex; justify-content: center; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { 
        font-size: clamp(22px, 6vw, 30px); font-weight: bold; text-decoration: none; text-transform: uppercase; 
        background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: rainbow 5s linear infinite; letter-spacing: 2px;
    }
    @keyframes rainbow { to { background-position: 400% center; } }
    .back-btn { position: absolute; left: 15px; color: #fff; font-size: 22px; cursor: pointer; text-decoration: none; }

    .container { max-width: 1400px; margin: auto; padding: 15px; }
    .ad-slot { text-align: center; margin: 15px 0; width: 100%; overflow: hidden; }

    .notice-bar { width: 100%; padding: 12px; margin-bottom: 20px; background: #111; border: 1px dashed #444; border-radius: 8px; text-align: center; font-weight: bold; font-size: 14px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 25px; padding: 5px 20px; border: 1px solid #333; width: 100%; max-width: 550px; margin: 0 auto 15px; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 10px; font-size: 15px; }

    .ott-slider { display: flex; gap: 15px; overflow-x: auto; padding: 10px 0 20px; scrollbar-width: none; }
    .ott-slider::-webkit-scrollbar { display: none; }
    .ott-circle { flex: 0 0 auto; text-align: center; width: 75px; text-decoration: none; }
    .ott-circle img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 2px solid #333; transition: 0.3s; }
    .ott-circle:hover img { border-color: var(--main); transform: scale(1.05); }
    .ott-circle span { display: block; font-size: 10px; color: #fff; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .h-slider { display: flex; gap: 15px; overflow-x: auto; padding-bottom: 15px; scrollbar-width: none; }
    .h-slider::-webkit-scrollbar { display: none; }
    .h-slider .card { flex: 0 0 140px; }
    @media (min-width: 600px) { .h-slider .card { flex: 0 0 190px; } }

    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 22px; } }
    
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; position: relative; display: block; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
    .badge-manual { position: absolute; top: 10px; right: 10px; background: var(--main); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase; z-index: 5; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
    .badge-ott { position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.85); color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; z-index: 5; border: 1px solid #444; }
    .card-title { padding: 10px; text-align: center; font-size: 13px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }

    video { width: 100%; border-radius: 12px; background: #000; aspect-ratio: 16/9; box-shadow: 0 0 20px rgba(0,0,0,0.6); }
    .ep-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(85px, 1fr)); gap: 10px; margin: 20px 0; }
    .ep-btn { background: #1a1a1a; color: #fff; padding: 12px; text-align: center; border-radius: 6px; cursor: pointer; border: 1px solid #333; font-size: 12px; font-weight: bold; transition: 0.3s; }
    .ep-btn.active { background: var(--main); border-color: var(--main); box-shadow: 0 0 10px var(--main); }
    
    .action-bar { display: flex; gap: 10px; margin: 20px 0; flex-wrap: wrap; }
    .soc-btn { background: #1a1a1a; color: #fff; padding: 12px 18px; border-radius: 6px; border: 1px solid #333; cursor: pointer; text-decoration: none; font-size: 14px; display: flex; align-items: center; gap: 8px; transition: 0.3s; }
    .soc-btn:hover { background: #333; }

    .com-section { background: #0f0f0f; padding: 20px; border-radius: 12px; margin-top: 35px; border: 1px solid #222; }
    .com-item { background: #161616; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #252525; position: relative; }
    .progress-container { width: 100%; background: #222; border-radius: 10px; margin: 15px 0; display: none; overflow: hidden; border: 1px solid #444; }
    .progress-bar { width: 0%; height: 20px; background: linear-gradient(to right, #e50914, #ff4d4d); text-align: center; font-size: 12px; line-height: 20px; font-weight: bold; color: #fff; transition: 0.2s; }

    .drw { position: fixed; top: 0; right: -100%; width: 300px; height: 100%; background: #0a0a0a; border-left: 1px solid #333; transition: 0.4s; z-index: 2000; padding-top: 50px; overflow-y: auto; }
    .drw.active { right: 0; }
    .drw a, .drw span { padding: 18px 25px; display: block; color: #fff; font-weight: bold; text-decoration: none; border-bottom: 1px solid #222; cursor: pointer; }
    .sec-box { display: none; background: #111; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #222; }
    input, select, textarea { width: 100%; padding: 14px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }
    .btn-main { background: var(--main); color: #fff; border: none; padding: 14px 25px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; font-size: 16px; text-decoration: none; }
    .stat-card { background: #1a1a1a; padding: 15px; border-radius: 8px; flex: 1; min-width: 120px; text-align: center; border: 1px solid #333; }
</style>
"""

# --- ১. হোমপেজ টেম্পলেট ---
HOME_HTML = CSS + """
{{ s.popunder|safe }}
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    <div class="ad-slot">{{ s.banner_ad|safe }}</div>
    <div class="notice-bar" style="color: {{ s.notice_color }};">
        <i class="fas fa-bullhorn"></i> {{ s.notice_text }}
    </div>
    
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies, web series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#888;"><i class="fas fa-search"></i></button>
    </form>

    <div class="ott-slider">
        {% for o in otts %}
        <a href="/?q={{ o.name }}" class="ott-circle">
            <img src="{{ o.logo or 'https://via.placeholder.com/60' }}" onerror="this.src='https://via.placeholder.com/60'">
            <span>{{ o.name }}</span>
        </a>
        {% endfor %}
    </div>

    <div class="ad-slot">{{ s.native_ad|safe }}</div>

    {% if query %}
        <div class="cat-title">Search Results</div>
        <div class="grid">
            {% for m in movies %}
            <a href="/content/{{ m._id }}" class="card">
                {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                {% if m.ott %}<div class="badge-ott">{{ m.ott }}</div>{% endif %}
                <img src="{{ m.poster }}" loading="lazy">
                <div class="card-title">{{ m.title }}</div>
            </a>
            {% endfor %}
        </div>
    {% else %}
        <div class="cat-title">Featured Movies <i class="fas fa-fire" style="color:orange;"></i></div>
        <div class="h-slider">
            {% for m in movies if m.type == 'movie' %}
            <a href="/content/{{ m._id }}" class="card">
                {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                <img src="{{ m.poster }}" loading="lazy">
                <div class="card-title">{{ m.title }}</div>
            </a>
            {% endfor %}
        </div>

        <div class="cat-title">Web Series <i class="fas fa-tv" style="color:cyan;"></i></div>
        <div class="h-slider">
            {% for m in movies if m.type == 'series' %}
            <a href="/content/{{ m._id }}" class="card">
                {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                <img src="{{ m.poster }}" loading="lazy">
                <div class="card-title">{{ m.title }}</div>
            </a>
            {% endfor %}
        </div>

        {% for cat in categories %}
            {% set cat_id_str = cat._id|string %}
            <div class="cat-title">{{ cat.name }}</div>
            <div class="grid">
                {% for m in movies if m.category_id == cat_id_str %}
                <a href="/content/{{ m._id }}" class="card">
                    {% if m.manual_badge %}<div class="badge-manual">{{ m.manual_badge }}</div>{% endif %}
                    <img src="{{ m.poster }}" loading="lazy">
                    <div class="card-title">{{ m.title }}</div>
                </a>
                {% endfor %}
            </div>
        {% endfor %}
    {% endif %}
    <div class="ad-slot">{{ s.socialbar_ad|safe }}</div>
</div>
"""

# --- ২. ডিটেইলস পেজ টেম্পলেট ---
DETAIL_HTML = CSS + """
{{ s.popunder|safe }}
<nav class="nav">
    <a href="javascript:history.back()" class="back-btn"><i class="fas fa-arrow-left"></i></a>
    <a href="/" class="logo">{{ s.site_name }}</a>
</nav>
<div style="background: url('{{ m.backdrop }}') center/cover fixed; position: fixed; top:0; left:0; width:100%; height:100%; filter: blur(35px) brightness(0.2); z-index:-1;"></div>
<div class="container">
    <div class="ad-slot">{{ s.banner_ad|safe }}</div>
    <div style="max-width: 950px; margin: auto;">
        
        <video id="vBox" controls poster="{{ m.backdrop }}">
            {% if m.type == 'movie' %}<source src="{{ m.video_url }}" type="video/mp4">
            {% elif episodes %}<source src="{{ episodes[0].video_url }}" type="video/mp4">
            {% endif %}
        </video>

        <div class="ad-slot">{{ s.native_ad|safe }}</div>

        {% if m.type == 'series' %}
        <div class="cat-title">Select Episode</div>
        <div class="ep-grid">
            {% for ep in episodes %}
            <div class="ep-btn {% if loop.first %}active{% endif %}" onclick="playEp('{{ ep.video_url }}', this)">
                S{{ ep.season }} E{{ ep.episode }}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="action-bar">
            <a href="/like/{{ m._id }}" class="soc-btn"><i class="fas fa-heart" style="color:red;"></i> {{ m.likes or 0 }} Likes</a>
            <div class="soc-btn" onclick="navigator.clipboard.writeText(window.location.href); alert('Link Copied!')"><i class="fas fa-link"></i> Share</div>
            <a href="https://api.whatsapp.com/send?text={{ share_url }}" target="_blank" class="soc-btn" style="background:#25d366;"><i class="fab fa-whatsapp"></i> WhatsApp</a>
        </div>

        <h1 style="margin-top:20px;">{{ m.title }} ({{ m.year }}) <span style="font-size:14px; color:var(--main);">[{{ m.language }}]</span></h1>
        
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
                <span style="color:var(--main); font-weight:bold;">{{ c.user }} <small style="float:right; color:#777;">{{ c.date }}</small></span>
                <div style="margin-top:5px;">{{ c.text }}</div>
                <a href="/like_comment/{{ m._id }}/{{ c._id }}" style="color:#777; text-decoration:none; float:right; font-size:13px;"><i class="fas fa-thumbs-up"></i> {{ c.likes or 0 }}</a>
                <div style="clear:both;"></div>
            </div>
            {% endfor %}
        </div>
    </div>
    <div class="ad-slot">{{ s.socialbar_ad|safe }}</div>
</div>
<script>
    let player = document.getElementById('vBox');
    let activeUrl = "{% if m.type == 'movie' %}{{ m.video_url }}{% elif episodes %}{{ episodes[0].video_url }}{% endif %}";

    function playEp(url, el) {
        activeUrl = url; player.src = url; player.load(); player.play();
        document.querySelectorAll('.ep-btn').forEach(b => b.classList.remove('active'));
        el.classList.add('active');
        window.scrollTo({ top: player.offsetTop - 100, behavior: 'smooth' });
    }

    function dlHandle() {
        if(!activeUrl) { alert("Select episode first!"); return; }
        window.open("{{ s.ad_link }}", "_blank");
        document.getElementById('dl-msg').innerText = "Opening Ad... Redirecting to Download";
        setTimeout(() => { window.location.href = activeUrl.replace("/upload/", "/upload/fl_attachment/"); }, 2000);
    }
</script>
"""

# --- ৩. এডমিন প্যানেল টেম্পলেট ---
ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:32px; color:var(--main); position:absolute; right:5%;" onclick="toggleMenu()">☰</div></nav>
<div class="drw" id="drw">
    <a href="/" style="background:var(--main);"><i class="fas fa-eye"></i> 👁️ View Site</a>
    <span onclick="openSec('upBox')"><i class="fas fa-upload"></i> 📤 Upload Content</span>
    <span onclick="openSec('epBox')"><i class="fas fa-plus-circle"></i> 🎞️ Add Episode</span>
    <span onclick="openSec('manageEpBox')"><i class="fas fa-folder-open"></i> 📂 Manage Episodes</span>
    <span onclick="openSec('manageBox')"><i class="fas fa-tasks"></i> 🎬 Bulk Action / Edit</span>
    <span onclick="openSec('adBox')"><i class="fas fa-ad"></i> 💰 Ads Management</span>
    <span onclick="openSec('ottBox')"><i class="fas fa-tv"></i> 📺 OTT Platforms</span>
    <span onclick="openSec('catBox')"><i class="fas fa-list"></i> 📂 Categories</span>
    <span onclick="openSec('langBox')"><i class="fas fa-language"></i> 🌐 Languages</span>
    <span onclick="openSec('setBox')"><i class="fas fa-cog"></i> ⚙️ General Settings</span>
    <a href="/logout" style="color:red;"><i class="fas fa-sign-out-alt"></i> 🔴 Logout</a>
</div>

<div class="container">
    <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:20px;">
        <div class="stat-card"><b>{{ counts.movies }}</b>Movies</div>
        <div class="stat-card"><b>{{ counts.series }}</b>Series</div>
        <div class="stat-card"><b>{{ counts.episodes }}</b>Episodes</div>
    </div>

    <!-- জেনারেল সেটিংস -->
    <div id="setBox" class="sec-box" style="display:block;">
        <h3>⚙️ General Settings</h3>
        <form action="/update_settings" method="POST">
            <input type="hidden" name="form_type" value="general">
            <label>Site Name</label><input type="text" name="site_name" value="{{ s.site_name }}">
            <label>Notice Text</label><input type="text" name="notice_text" value="{{ s.notice_text }}">
            <label>Notice Color (Hex)</label><input type="text" name="notice_color" value="{{ s.notice_color }}">
            <label>Direct Ad/Download Link</label><input type="text" name="ad_link" value="{{ s.ad_link }}">
            <label>Ad Click Limit</label><input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}">
            <button class="btn-main">SAVE SETTINGS</button>
        </form>
    </div>

    <!-- এড ম্যানেজমেন্ট -->
    <div id="adBox" class="sec-box">
        <h3>💰 Ads Management (JS/HTML Code)</h3>
        <form action="/update_settings" method="POST">
            <input type="hidden" name="form_type" value="ads">
            <label>Popunder Code</label><textarea name="popunder" rows="4">{{ s.popunder }}</textarea>
            <label>Banner Ad (Top)</label><textarea name="banner_ad" rows="4">{{ s.banner_ad }}</textarea>
            <label>Native Ad (Between)</label><textarea name="native_ad" rows="4">{{ s.native_ad }}</textarea>
            <label>Social Bar (Bottom)</label><textarea name="socialbar_ad" rows="4">{{ s.socialbar_ad }}</textarea>
            <button class="btn-main">UPDATE ADS</button>
        </form>
    </div>

    <!-- কন্টেন্ট আপলোড -->
    <div id="upBox" class="sec-box">
        <h3>📤 Upload Movie/Series</h3>
        <div style="display:flex; gap:10px;"><input type="text" id="tmdbQ" placeholder="Movie Name..."><button onclick="tmdbSearch()" class="btn-main" style="width:100px;">Search</button></div>
        <div id="tmdbRes" style="display:flex; gap:10px; overflow-x:auto; margin:10px 0; background:#000; padding:10px;"></div>
        <form id="upFrm">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <input type="text" name="manual_badge" placeholder="Badge (e.g. 4K, HD)">
            <select name="type"><option value="movie">Movie</option><option value="series">Web Series</option></select>
            <select name="language">
                <option value="">Select Language</option>
                {% for l in languages %}<option value="{{ l.name }}">{{ l.name }}</option>{% endfor %}
            </select>
            <select name="ott">
                <option value="">Select OTT</option>
                {% for o in otts %}<option value="{{ o.name }}">{{ o.name }}</option>{% endfor %}
            </select>
            <select name="category_id">
                {% for c in categories %}<option value="{{ c._id|string }}">{{ c.name }}</option>{% endfor %}
            </select>
            <input type="file" name="video_file" id="f_up" accept="video/mp4">
            <div class="progress-container" id="pCont"><div class="progress-bar" id="pBar">0%</div></div>
            <button type="button" onclick="uploadContent()" class="btn-main">SAVE CONTENT</button>
        </form>
    </div>

    <!-- এডিট বক্স (Hidden by Default) -->
    <div id="editBox" class="sec-box">
        <h3>✏️ Edit Content</h3>
        <form id="editFrm">
            <input type="hidden" name="id" id="e_id">
            <input type="text" name="title" id="e_t" placeholder="Title" required>
            <input type="text" name="year" id="e_y" placeholder="Year">
            <input type="text" name="poster" id="e_p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="e_b" placeholder="Backdrop URL">
            <input type="text" name="manual_badge" id="e_badge" placeholder="Badge">
            <select name="language" id="e_lang">
                {% for l in languages %}<option value="{{ l.name }}">{{ l.name }}</option>{% endfor %}
            </select>
            <select name="ott" id="e_ott">
                {% for o in otts %}<option value="{{ o.name }}">{{ o.name }}</option>{% endfor %}
            </select>
            <select name="category_id" id="e_cat">
                {% for c in categories %}<option value="{{ c._id|string }}">{{ c.name }}</option>{% endfor %}
            </select>
            <p style="font-size:12px; color:orange;">Keep blank to keep old video</p>
            <input type="file" name="video_file" id="e_f_up" accept="video/mp4">
            <div class="progress-container" id="e_pCont"><div class="progress-bar" id="e_pBar">0%</div></div>
            <button type="button" onclick="updateContentSubmit()" class="btn-main">UPDATE NOW</button>
            <button type="button" onclick="openSec('manageBox')" class="btn-main" style="background:#444; margin-top:10px;">CANCEL</button>
        </form>
    </div>

    <!-- ইপিসোড এড -->
    <div id="epBox" class="sec-box">
        <h3>🎞️ Add Episode</h3>
        <input type="text" id="sSch" placeholder="🔍 Search series..." onkeyup="findS()" style="border:1px solid var(--main);">
        <form id="epFrm">
            <select name="series_id" id="sSel">
                {% for m in movies if m.type == 'series' %}<option value="{{ m._id|string }}">{{ m.title }}</option>{% endfor %}
            </select>
            <input type="number" name="season" placeholder="Season" required>
            <input type="number" name="episode" placeholder="Episode" required>
            <input type="file" name="video_file" id="f_ep" accept="video/mp4">
            <div class="progress-container" id="epPCont"><div class="progress-bar" id="epPBar">0%</div></div>
            <button type="button" onclick="uploadEp()" class="btn-main">UPLOAD EPISODE</button>
        </form>
    </div>

    <!-- ইপিসোড ম্যানেজমেন্ট (Edit/Delete) -->
    <div id="manageEpBox" class="sec-box">
        <h3>📂 Manage Episodes</h3>
        <select id="mSeries" onchange="loadEpisodes(this.value)">
            <option value="">Select Series to see episodes</option>
            {% for m in movies if m.type == 'series' %}<option value="{{ m._id|string }}">{{ m.title }}</option>{% endfor %}
        </select>
        <div id="epList" style="margin-top:15px; border-top:1px solid #333;"></div>
    </div>

    <!-- বাল্ক ডিলিট ও এডিট লিস্ট -->
    <div id="manageBox" class="sec-box">
        <h3>🎬 Bulk Action / Edit Content</h3>
        <form action="/bulk_delete" method="POST">
            <div style="max-height: 500px; overflow-y: auto; border: 1px solid #333; padding: 10px;">
                {% for m in movies %}
                <div style="padding:10px; border-bottom:1px solid #222; display:flex; align-items:center; gap:10px;">
                    <input type="checkbox" name="ids" value="{{ m._id }}"> 
                    <span style="flex:1;">{{ m.title }} ({{ m.type }})</span>
                    <button type="button" onclick="editContent('{{ m._id }}')" style="background:#007bff; color:#fff; border:none; padding:5px 10px; border-radius:4px; cursor:pointer;"><i class="fas fa-edit"></i> Edit</button>
                </div>
                {% endfor %}
            </div>
            <button class="btn-main" style="background:red; margin-top:15px;">DELETE SELECTED</button>
        </form>
    </div>

    <div id="ottBox" class="sec-box">
        <h3>📺 OTT Platforms</h3>
        <form action="/add_ott" method="POST">
            <input type="text" name="name" placeholder="OTT Name" required>
            <input type="text" name="logo" placeholder="Logo URL" required>
            <button class="btn-main">Add OTT</button>
        </form>
        {% for o in otts %}
        <div style="padding:10px; border-bottom:1px solid #222; display:flex; align-items:center;">
            <img src="{{ o.logo }}" style="width:30px; height:30px; border-radius:50%; margin-right:10px;">
            {{ o.name }} <a href="/del_ott/{{ o._id }}" style="color:red; margin-left:auto;">Delete</a>
        </div>
        {% endfor %}
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
</div>

<script>
    function toggleMenu() { document.getElementById('drw').classList.toggle('active'); }
    function openSec(id) { document.querySelectorAll('.sec-box').forEach(b => b.style.display='none'); document.getElementById(id).style.display='block'; if(window.innerWidth < 800) toggleMenu(); }
    
    function findS() {
        let q = document.getElementById('sSch').value.toLowerCase();
        let sel = document.getElementById('sSel');
        for (let i = 0; i < sel.options.length; i++) {
            let match = sel.options[i].text.toLowerCase().includes(q);
            sel.options[i].style.display = match ? "block" : "none";
        }
    }

    async function loadEpisodes(sid) {
        if(!sid) return;
        let r = await fetch(`/api/episodes/${sid}`);
        let eps = await r.json();
        let div = document.getElementById('epList'); div.innerHTML = '';
        if(eps.length === 0) div.innerHTML = '<p style="padding:10px;">No episodes found.</p>';
        eps.forEach(e => {
            div.innerHTML += `<div style="padding:10px; border-bottom:1px solid #222; display:flex; justify-content:space-between; align-items:center;">
                <span>Season ${e.season} - Episode ${e.episode}</span>
                <div>
                    <a href="/del_episode/${e._id}" onclick="return confirm('Delete?')" style="color:red; text-decoration:none; font-weight:bold; margin-left:10px;">Delete</a>
                </div>
            </div>`;
        });
    }

    async function editContent(id) {
        let r = await fetch(`/api/get_content/${id}`);
        let m = await r.json();
        document.getElementById('e_id').value = m._id;
        document.getElementById('e_t').value = m.title;
        document.getElementById('e_y').value = m.year;
        document.getElementById('e_p').value = m.poster;
        document.getElementById('e_b').value = m.backdrop;
        document.getElementById('e_badge').value = m.manual_badge || "";
        document.getElementById('e_lang').value = m.language;
        document.getElementById('e_ott').value = m.ott || "";
        document.getElementById('e_cat').value = m.category_id;
        openSec('editBox');
    }

    function updateContentSubmit(){
        let fd = new FormData(document.getElementById('editFrm'));
        let xhr = new XMLHttpRequest();
        document.getElementById('e_pCont').style.display = 'block';
        xhr.upload.onprogress = (e) => {
            let p = Math.round((e.loaded / e.total) * 100);
            document.getElementById('e_pBar').style.width = p + '%';
            document.getElementById('e_pBar').innerText = p + '%';
        };
        xhr.open("POST", "/update_content_data");
        xhr.onload = () => { alert("Updated!"); location.reload(); };
        xhr.send(fd);
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

# --- ৪. Flask রাউটস ---

@app.route('/')
def index():
    query = request.args.get('q')
    cats, otts = list(categories_col.find()), list(ott_col.find())
    if query:
        movies = list(movies_col.find({"title": {"$regex": query, "$options": "i"}}).sort("_id", -1))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(HOME_HTML, categories=cats, movies=movies, otts=otts, query=query, s=get_config())

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
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin Login</h2><input type="text" name="u" placeholder="Admin" required><input type="password" name="p" placeholder="Pass" required><button class="btn-main">LOGIN</button></form></div>""")
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
    session.clear(); return redirect('/')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        ftype = request.form.get('form_type')
        if ftype == 'general':
            settings_col.update_one({"type": "config"}, {"$set": {
                "site_name": request.form.get('site_name'), "notice_text": request.form.get('notice_text'), 
                "notice_color": request.form.get('notice_color'), "ad_link": request.form.get('ad_link'), 
                "ad_click_limit": int(request.form.get('ad_click_limit', 0))
            }})
        elif ftype == 'ads':
            settings_col.update_one({"type": "config"}, {"$set": {
                "popunder": request.form.get('popunder'), "banner_ad": request.form.get('banner_ad'), 
                "native_ad": request.form.get('native_ad'), "socialbar_ad": request.form.get('socialbar_ad')
            }})
    return redirect('/admin')

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "No", 401
    file, v_url = request.files.get('video_file'), ""
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name); up = cloudinary.uploader.upload_large(tf.name, resource_type="video")
            v_url = up['secure_url']
        os.remove(tf.name)
    movies_col.insert_one({
        "title": request.form.get('title'), "year": request.form.get('year'), "poster": request.form.get('poster'), 
        "backdrop": request.form.get('backdrop'), "type": request.form.get('type'), "manual_badge": request.form.get('manual_badge'), 
        "language": request.form.get('language'), "ott": request.form.get('ott'), "category_id": request.form.get('category_id'), 
        "video_url": v_url, "likes": 0
    })
    return "OK"

# --- নতুন এডিট ও আপডেট রাউটস ---
@app.route('/api/get_content/<id>')
def get_content_api(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    m['_id'] = str(m['_id'])
    return jsonify(m)

@app.route('/update_content_data', methods=['POST'])
def update_content_data():
    if not session.get('auth'): return "No", 401
    mid = request.form.get('id')
    update_data = {
        "title": request.form.get('title'), "year": request.form.get('year'), "poster": request.form.get('poster'), 
        "backdrop": request.form.get('backdrop'), "manual_badge": request.form.get('manual_badge'), 
        "language": request.form.get('language'), "ott": request.form.get('ott'), "category_id": request.form.get('category_id')
    }
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name); up = cloudinary.uploader.upload_large(tf.name, resource_type="video")
            update_data["video_url"] = up['secure_url']
        os.remove(tf.name)
    movies_col.update_one({"_id": ObjectId(mid)}, {"$set": update_data})
    return "OK"

@app.route('/add_episode', methods=['POST'])
def add_episode():
    if not session.get('auth'): return "No", 401
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name); up = cloudinary.uploader.upload_large(tf.name, resource_type="video")
            episodes_col.insert_one({"series_id": request.form.get('series_id'), "season": int(request.form.get('season')), "episode": int(request.form.get('episode')), "video_url": up['secure_url']})
        os.remove(tf.name)
    return "OK"

@app.route('/del_episode/<id>')
def del_episode(id):
    if session.get('auth'): episodes_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/api/episodes/<sid>')
def get_episodes(sid):
    eps = list(episodes_col.find({"series_id": sid}).sort([("season", 1), ("episode", 1)]))
    for e in eps: e['_id'] = str(e['_id'])
    return jsonify(eps)

@app.route('/bulk_delete', methods=['POST'])
def bulk_delete():
    if session.get('auth'):
        for i in request.form.getlist('ids'):
            movies_col.delete_one({"_id": ObjectId(i)}); episodes_col.delete_many({"series_id": i})
    return redirect('/admin')

@app.route('/add_cat', methods=['POST'])
def add_cat():
    if session.get('auth'): categories_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_cat/<id>')
def del_cat(id):
    if session.get('auth'): categories_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/add_ott', methods=['POST'])
def add_ott():
    if session.get('auth'): ott_col.insert_one({"name": request.form.get('name'), "logo": request.form.get('logo')})
    return redirect('/admin')

@app.route('/del_ott/<id>')
def del_ott(id):
    if session.get('auth'): ott_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/add_lang', methods=['POST'])
def add_lang():
    if session.get('auth'): languages_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_lang/<id>')
def del_lang(id):
    if session.get('auth'): languages_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
