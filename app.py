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
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_premium_final_2026")

# --- ডাটাবেস ও ক্লাউড সেটিংস (আপনার তথ্যগুলো এখানে দিন) ---
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "your_tmdb_api_key")

cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME", "your_cloud_name"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY", "your_api_key"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET", "your_api_secret") 
)

# MongoDB কানেকশন
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col = db['movies']
    episodes_col = db['episodes']
    categories_col = db['categories']
    languages_col = db['languages'] # ভাষার জন্য নতুন কালেকশন
    settings_col = db['settings']
    comments_col = db['comments']
except Exception as e:
    print(f"DB Error: {e}")

# এডমিন ক্রেডেনশিয়াল
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# সাইট সেটিংস ফাংশন
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", 
            "site_name": "MOVIEBOX PRO",
            "popunder": "", 
            "native": "",
            "ad_link": "https://ad-link.com", 
            "ad_click_limit": 3,
            "notice_text": "Welcome to our site! Join our telegram for updates.",
            "notice_color": "#ffffff"
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
    
    /* লোগো মাজখানে এবং হেডার ডিজাইন */
    .nav { background: rgba(0,0,0,0.95); padding: 15px 5%; display: flex; align-items: center; justify-content: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { 
        font-size: clamp(20px, 5vw, 28px); font-weight: bold; text-decoration: none; text-transform: uppercase; 
        background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: rainbow 5s linear infinite; letter-spacing: 1px;
    }
    @keyframes rainbow { to { background-position: 400% center; } }
    
    .container { max-width: 1400px; margin: auto; padding: 15px; }

    /* নোটিশ বার ও সার্চ */
    .notice-bar { width: 100%; padding: 12px; margin-bottom: 15px; background: #111; border: 1px dashed #333; border-radius: 8px; text-align: center; font-weight: bold; font-size: 14px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 20px; padding: 5px 15px; border: 1px solid #333; width: 100%; max-width: 500px; margin: 0 auto 30px auto; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 8px; font-size: 14px; }

    /* মুভি গ্রিড ও ব্যাজ */
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; } }
    
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; position: relative; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card:hover { border-color: var(--main); transform: translateY(-5px); }
    
    /* ল্যাঙ্গুয়েজ ব্যাজ */
    .lang-badge { position: absolute; top: 10px; right: 10px; background: rgba(229, 9, 20, 0.9); color: #fff; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; text-transform: uppercase; z-index: 5; }

    .card-title { padding: 10px; text-align: center; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* ভিডিও ও বাটন */
    .btn { background: var(--main); color: #fff; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; transition: 0.3s; }
    .btn:hover { opacity: 0.8; }
    video { width: 100%; border-radius: 10px; background: #000; aspect-ratio: 16/9; }

    /* এডমিন ড্রয়ার */
    .admin-drawer { position: fixed; top: 0; right: -100%; width: 280px; height: 100%; background: #121212; border-left: 1px solid #333; transition: 0.3s; z-index: 2000; padding-top: 60px; }
    .admin-drawer.active { right: 0; }
    .admin-drawer span, .admin-drawer a { padding: 15px 25px; cursor: pointer; border-bottom: 1px solid #222; text-decoration: none; color: #fff; display: block; font-weight: bold; }
    .section-box { display: none; background: #111; padding: 20px; border-radius: 10px; border: 1px solid #222; margin-top: 20px; }
    input, select, textarea { width: 100%; padding: 12px; margin: 8px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 5px; }
</style>
"""

# --- হোমপেজ ---
HOME_HTML = CSS + """
<nav class="nav">
    <a href="/" class="logo">{{ s.site_name }}</a>
</nav>

<div class="container">
    <div class="notice-bar" style="color: {{ s.notice_color }};">
        <i class="fas fa-bullhorn"></i> {{ s.notice_text }}
    </div>

    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies or web series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#aaa; cursor:pointer;"><i class="fas fa-search"></i></button>
    </form>

    {% for cat in categories %}
        <div class="cat-title">{{ cat.name }}</div>
        <div class="grid">
            {% for m in movies if m.category_id == cat._id|string %}
            <a href="/content/{{ m._id }}" class="card">
                <div class="lang-badge">{{ m.language }}</div>
                <img src="{{ m.poster }}" loading="lazy">
                <div class="card-title">{{ m.title }} ({{ m.year }})</div>
            </a>
            {% endfor %}
        </div>
    {% endfor %}
</div>
{{ s.popunder|safe }}
"""

# --- ডিটেইলস পেজ ---
DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div style="background: url('{{ m.backdrop }}') center/cover fixed; position: fixed; top:0; left:0; width:100%; height:100%; filter: blur(30px) brightness(0.2); z-index:-1;"></div>
<div class="container">
    <div style="max-width: 900px; margin: auto;">
        <video id="mainVideo" controls poster="{{ m.backdrop }}">
            <source src="{% if m.type == 'movie' %}{{ m.video_url }}{% endif %}" type="video/mp4">
        </video>
        
        {% if m.type == 'series' %}
        <div class="cat-title">Episodes</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 10px; margin-bottom: 20px;">
            {% for ep in episodes %}
            <div style="background:#222; padding:10px; text-align:center; border-radius:5px; cursor:pointer; font-size:12px;" onclick="playEp('{{ ep.video_url }}')">S{{ ep.season }} E{{ ep.episode }}</div>
            {% endfor %}
        </div>
        {% endif %}

        <h1>{{ m.title }} ({{ m.year }}) <span style="font-size:14px; color:var(--main);">[{{ m.language }}]</span></h1>
        <button id="dlBtn" onclick="handleDL()" class="btn" style="width:100%; margin-top:20px; height:60px; font-size:20px;">📥 DOWNLOAD NOW</button>
        <p id="dl-msg" style="color:var(--main); text-align:center; margin-top:10px; font-weight:bold;"></p>
    </div>
</div>
<script>
    let currentUrl = "{% if m.type == 'movie' %}{{ m.video_url }}{% endif %}";
    function playEp(url) {
        currentUrl = url;
        let v = document.getElementById('mainVideo');
        v.src = url; v.play();
    }
    let clicks = 0;
    function handleDL() {
        if(!currentUrl) { alert("Select an episode first!"); return; }
        if(clicks < {{ s.ad_click_limit }}) {
            clicks++;
            document.getElementById('dl-msg').innerText = "Ad Loading... (" + clicks + "/{{ s.ad_click_limit }})";
            window.open("{{ s.ad_link }}", "_blank");
        } else {
            window.location.href = currentUrl.replace("/upload/", "/upload/fl_attachment/");
        }
    }
</script>
"""

# --- এডমিন প্যানেল ---
ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:30px; color:var(--main); position:absolute; right:5%;" onclick="toggleMenu()">☰</div></nav>
<div class="admin-drawer" id="drawer">
    <span onclick="openSec('upBox')">Upload Content</span>
    <span onclick="openSec('epBox')">Add Episode</span>
    <span onclick="openSec('catBox')">Categories</span>
    <span onclick="openSec('langBox')">Languages</span>
    <span onclick="openSec('setBox')">Settings</span>
    <a href="/logout" style="color:red;">Logout</a>
</div>

<div class="container">
    <div id="upBox" class="section-box" style="display:block;">
        <h3>Upload Movie/Series</h3>
        <input type="text" id="tmdbQ" placeholder="Search TMDB..."><button class="btn" onclick="tmdbSearch()">Search</button>
        <div id="tmdbRes" style="display:flex; gap:10px; overflow-x:auto; margin:10px 0;"></div>
        <form id="uploadForm">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <select name="type"><option value="movie">Movie</option><option value="series">Series</option></select>
            <select name="language">
                {% for l in languages %}<option value="{{ l.name }}">{{ l.name }}</option>{% endfor %}
            </select>
            <select name="category_id">
                {% for c in categories %}<option value="{{ c._id|string }}">{{ c.name }}</option>{% endfor %}
            </select>
            <input type="file" name="video_file" accept="video/mp4">
            <button type="button" onclick="submitContent()" class="btn" style="width:100%; background:green;">UPLOAD INFO</button>
        </form>
    </div>

    <div id="epBox" class="section-box">
        <h3>Add Episode</h3>
        <form id="epForm">
            <select name="series_id">
                {% for m in movies if m.type == 'series' %}<option value="{{ m._id|string }}">{{ m.title }}</option>{% endfor %}
            </select>
            <input type="number" name="season" placeholder="Season" required>
            <input type="number" name="episode" placeholder="Episode" required>
            <input type="file" name="video_file" accept="video/mp4" required>
            <button type="button" onclick="submitEpisode()" class="btn" style="width:100%; background:blue;">UPLOAD EPISODE</button>
        </form>
    </div>

    <div id="langBox" class="section-box">
        <h3>Languages</h3>
        <form action="/add_lang" method="POST"><input type="text" name="name" placeholder="Language Name (e.g. Hindi)"><button class="btn">Add</button></form>
        {% for l in languages %}<p style="margin-top:10px;">{{ l.name }} <a href="/del_lang/{{ l._id }}" style="color:red; float:right;">Delete</a></p>{% endfor %}
    </div>

    <div id="setBox" class="section-box">
        <h3>Site Settings</h3>
        <form action="/update_settings" method="POST">
            <label>Site Name:</label><input type="text" name="site_name" value="{{ s.site_name }}">
            <label>Notice Text:</label><input type="text" name="notice_text" value="{{ s.notice_text }}">
            <label>Notice Color (Hex):</label><input type="text" name="notice_color" value="{{ s.notice_color }}">
            <label>Ad Link:</label><input type="text" name="ad_link" value="{{ s.ad_link }}">
            <label>Ad Click Limit:</label><input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}">
            <button class="btn" style="width:100%;">SAVE SETTINGS</button>
        </form>
    </div>
</div>
<script>
    function toggleMenu() { document.getElementById('drawer').classList.toggle('active'); }
    function openSec(id) { document.querySelectorAll('.section-box').forEach(b => b.style.display = 'none'); document.getElementById(id).style.display = 'block'; toggleMenu(); }
    async function tmdbSearch(){
        let q = document.getElementById('tmdbQ').value;
        let r = await fetch(`/api/tmdb?q=${q}`);
        let d = await r.json();
        let resDiv = document.getElementById('tmdbRes'); resDiv.innerHTML = '';
        d.results.slice(0,5).forEach(i => {
            let img = document.createElement('img'); img.src = "https://image.tmdb.org/t/p/w92" + i.poster_path; img.style.height="80px";
            img.onclick = () => {
                document.getElementById('t').value = i.title || i.name;
                document.getElementById('y').value = (i.release_date || i.first_air_date || '').split('-')[0];
                document.getElementById('p').value = "https://image.tmdb.org/t/p/w500" + i.poster_path;
                document.getElementById('b').value = "https://image.tmdb.org/t/p/original" + i.backdrop_path;
            };
            resDiv.appendChild(img);
        });
    }
    function submitContent(){
        let fd = new FormData(document.getElementById('uploadForm'));
        let xhr = new XMLHttpRequest(); xhr.open("POST", "/add_content");
        xhr.onload = () => { alert("Saved!"); location.reload(); }; xhr.send(fd);
    }
    function submitEpisode(){
        let fd = new FormData(document.getElementById('epForm'));
        let xhr = new XMLHttpRequest(); xhr.open("POST", "/add_episode");
        xhr.onload = () => { alert("Episode Added!"); location.reload(); }; xhr.send(fd);
    }
</script>
"""

# --- রাউটস ---

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
    return render_template_string(DETAIL_HTML, m=m, episodes=episodes, s=get_config())

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="section-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin</h2><input type="text" name="u" placeholder="Admin" required><input type="password" name="p" placeholder="Pass" required><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    movies = list(movies_col.find().sort("_id", -1))
    langs = list(languages_col.find())
    cats = list(categories_col.find())
    return render_template_string(ADMIN_HTML, movies=movies, languages=langs, categories=cats, total_movies=len(movies), s=get_config())

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Fail! <a href='/admin'>Retry</a>"

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
        "title": request.form.get('title'),
        "year": request.form.get('year'),
        "poster": request.form.get('poster'),
        "backdrop": request.form.get('backdrop'),
        "type": request.form.get('type'),
        "language": request.form.get('language'),
        "category_id": str(request.form.get('category_id')),
        "video_url": v_url,
        "likes": 0
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
            episodes_col.insert_one({
                "series_id": request.form.get('series_id'),
                "season": int(request.form.get('season')),
                "episode": int(request.form.get('episode')),
                "video_url": up['secure_url']
            })
        os.remove(tf.name)
    return "OK"

@app.route('/add_lang', methods=['POST'])
def add_lang():
    if session.get('auth'): languages_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_lang/<id>')
def del_lang(id):
    if session.get('auth'): languages_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {
            "site_name": request.form.get('site_name'),
            "notice_text": request.form.get('notice_text'),
            "notice_color": request.form.get('notice_color'),
            "ad_link": request.form.get('ad_link'),
            "ad_click_limit": int(request.form.get('ad_click_limit', 0))
        }})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}"
    return jsonify(requests.get(url).json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
