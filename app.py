import os
import requests
import tempfile
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
    categories_col = db['categories']
    settings_col = db['settings']
except Exception as e:
    print(f"DB Error: {e}")

# ডিফল্ট অ্যাডমিন পাসওয়ার্ড
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# সাইট সেটিংস লোড করা
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", 
            "site_name": "MOVIEBOX PRO",
            "ad_link": "https://ad-link.com", 
            "ad_click_limit": 3
        }
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম CSS ডিজাইন ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    .logo { color: var(--main); font-size: 26px; font-weight: bold; text-decoration: none; text-transform: uppercase; text-shadow: 0 0 10px var(--main); }
    .nav { background: rgba(0,0,0,0.95); padding: 10px 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; flex-wrap: wrap; }
    .container { max-width: 1300px; margin: auto; padding: 15px; }
    
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 20px; padding: 5px 15px; border: 1px solid #333; width: 300px; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 5px; }

    .btn { background: var(--main); color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; font-weight: bold; transition: 0.3s; display: inline-block; }
    .btn:hover { opacity: 0.8; transform: scale(1.05); }

    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 18px; }
    @media (max-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; } }
    
    .card { background: var(--card); border-radius: 8px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; position: relative; }
    .card img { width: 100%; height: 250px; object-fit: cover; }
    @media (max-width: 600px) { .card img { height: 165px; } }

    .progress-container { width: 100%; background: #222; border-radius: 10px; margin: 15px 0; display: none; }
    .progress-bar { width: 0%; height: 15px; background: var(--main); border-radius: 10px; text-align: center; font-size: 10px; color: #fff; }

    .admin-drawer { position: fixed; top: 70px; right: 5%; background: #181818; border: 1px solid #333; border-radius: 8px; display: none; flex-direction: column; z-index: 3000; width: 250px; }
    .admin-drawer span, .admin-drawer a { padding: 15px; cursor: pointer; border-bottom: 1px solid #252525; text-decoration: none; color: #fff; }
    
    .section-box { display: none; background: #111; padding: 20px; border-radius: 10px; border: 1px solid #222; margin-top: 20px; }
    input, select { width: 100%; padding: 12px; margin: 8px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 5px; }
    video { width: 100%; border-radius: 10px; background: #000; aspect-ratio: 16/9; }
</style>
"""

# --- হোমপেজ ---
HOME_HTML = CSS + """
<nav class="nav">
    <a href="/" class="logo">{{ s.site_name }}</a>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#aaa;">🔍</button>
    </form>
    <a href="/admin" class="btn">ADMIN</a>
</nav>

<div class="container">
    {% if query %}
        <h3 class="cat-title">Results: {{ query }}</h3>
        <div class="grid">
            {% for m in movies %}
            <a href="/movie/{{ m._id }}" class="card">
                <img src="{{ m.poster }}" loading="lazy">
                <div style="padding:10px; text-align:center; font-size:13px;">{{ m.title }}</div>
            </a>
            {% endfor %}
        </div>
    {% else %}
        {% for cat in categories %}
            <div class="cat-title">{{ cat.name }}</div>
            <div class="grid">
                {% for m in movies %}
                    {% if m.category_id == cat._id|string %}
                    <a href="/movie/{{ m._id }}" class="card">
                        <img src="{{ m.poster }}" loading="lazy">
                        <div style="padding:10px; text-align:center; font-size:13px;">{{ m.title }}</div>
                    </a>
                    {% endif %}
                {% endfor %}
            </div>
        {% endfor %}
        
        <div class="cat-title">All Movies</div>
        <div class="grid">
            {% for m in movies %}
            <a href="/movie/{{ m._id }}" class="card">
                <img src="{{ m.poster }}" loading="lazy">
                <div style="padding:10px; text-align:center; font-size:13px;">{{ m.title }}</div>
            </a>
            {% endfor %}
        </div>
    {% endif %}
</div>
"""

# --- ডিটেইলস পেজ ---
DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a><a href="/" class="btn">HOME</a></nav>
<div style="background: url('{{ m.backdrop }}') center/cover fixed; position: fixed; top:0; left:0; width:100%; height:100%; filter: blur(25px) brightness(0.2); z-index:-1;"></div>
<div class="container">
    <div style="display: flex; flex-wrap: wrap; gap: 30px; margin-top: 40px;">
        <div style="flex: 1; min-width: 300px;">
            <img src="{{ m.poster }}" style="width:100%; border-radius:12px; border: 2px solid var(--main);">
            <button onclick="dlHandle()" class="btn" style="width:100%; margin-top:20px; padding:15px; font-size:18px;">📥 DOWNLOAD NOW</button>
            <p id="msg" style="text-align:center; color:var(--main); margin-top:15px; font-weight:bold;"></p>
        </div>
        <div style="flex: 2; min-width: 350px;">
            <h1 style="margin-bottom:15px;">{{ m.title }} ({{ m.year }})</h1>
            <video controls poster="{{ m.backdrop }}"><source src="{{ m.video_url }}" type="video/mp4"></video>
        </div>
    </div>
</div>
<script>
    let clicks = 0;
    function dlHandle() {
        if(clicks < {{ s.ad_click_limit }}) {
            clicks++;
            document.getElementById('msg').innerText = "Ad Opening... (" + clicks + "/{{ s.ad_click_limit }})";
            window.open("{{ s.ad_link }}", "_blank");
        } else {
            document.getElementById('msg').innerText = "Starting Download...";
            let dUrl = "{{ m.video_url }}".replace("/upload/", "/upload/fl_attachment/");
            window.location.href = dUrl;
        }
    }
</script>
"""

# --- এডমিন প্যানেল ---
ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:28px;" onclick="toggleMenu()">☰</div></nav>
<div class="admin-drawer" id="drawer">
    <span onclick="openSec('upBox')">Upload Movie</span>
    <span onclick="openSec('manageBox')">Manage Movies</span>
    <span onclick="openSec('catBox')">Categories</span>
    <span onclick="openSec('setBox')">Settings</span>
    <a href="/logout" style="color:red;">Logout</a>
</div>
<div class="container">
    <div id="upBox" class="section-box" style="display:block;">
        <h3>Upload Movie</h3>
        <input type="text" id="tmdbQ" placeholder="Search TMDB..."><button class="btn" onclick="tmdbSearch()">Search</button>
        <div id="tmdbRes" style="display:flex; gap:10px; overflow-x:auto; margin:10px 0;"></div>
        <form id="uploadForm">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <select name="category_id" required>
                {% for c in categories %}<option value="{{ c._id|string }}">{{ c.name }}</option>{% endfor %}
            </select>
            <input type="file" name="video_file" accept="video/mp4" required>
            <div class="progress-container" id="pCont"><div class="progress-bar" id="pBar">0%</div></div>
            <button type="button" id="upBtn" onclick="submitContent()" class="btn" style="width:100%; background:green;">UPLOAD NOW</button>
        </form>
    </div>
    <div id="manageBox" class="section-box">
        <h3>Movies ({{ total_movies }})</h3>
        {% for m in movies %}
        <div style="display:flex; justify-content:space-between; padding:10px; border-bottom:1px solid #222;">
            <span>{{ m.title }}</span>
            <a href="/del_movie/{{ m._id }}" style="color:red; text-decoration:none;">Delete</a>
        </div>
        {% endfor %}
    </div>
    <div id="catBox" class="section-box">
        <h3>Categories</h3>
        <form action="/add_cat" method="POST"><input type="text" name="name" placeholder="New Category"><button class="btn">Add</button></form>
        {% for c in categories %}<p>{{ c.name }} <a href="/del_cat/{{ c._id }}" style="float:right; color:red;">X</a></p>{% endfor %}
    </div>
    <div id="setBox" class="section-box">
        <h3>Settings</h3>
        <form action="/update_settings" method="POST">
            <input type="text" name="site_name" value="{{ s.site_name }}">
            <input type="text" name="ad_link" value="{{ s.ad_link }}">
            <input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}">
            <button class="btn">Save</button>
        </form>
    </div>
</div>
<script>
    function toggleMenu() { let d = document.getElementById('drawer'); d.style.display = (d.style.display=='flex')?'none':'flex'; }
    function openSec(id) { document.querySelectorAll('.section-box').forEach(b=>b.style.display='none'); document.getElementById(id).style.display='block'; toggleMenu(); }
    async function tmdbSearch(){
        let q = document.getElementById('tmdbQ').value;
        let r = await fetch(`/api/tmdb?q=${q}`);
        let d = await r.json();
        let resDiv = document.getElementById('tmdbRes'); resDiv.innerHTML = '';
        d.results.slice(0,5).forEach(i => {
            let img = document.createElement('img'); img.src = "https://image.tmdb.org/t/p/w92"+i.poster_path; img.style.cursor="pointer";
            img.onclick = () => {
                document.getElementById('t').value = i.title || i.name;
                document.getElementById('y').value = (i.release_date || i.first_air_date || '').split('-')[0];
                document.getElementById('p').value = "https://image.tmdb.org/t/p/w500"+i.poster_path;
                document.getElementById('b').value = "https://image.tmdb.org/t/p/original"+i.backdrop_path;
            };
            resDiv.appendChild(img);
        });
    }
    function submitContent(){
        let fd = new FormData(document.getElementById('uploadForm'));
        let xhr = new XMLHttpRequest();
        document.getElementById('pCont').style.display = 'block';
        document.getElementById('upBtn').disabled = true;
        xhr.upload.onprogress = (e) => {
            let p = Math.round((e.loaded / e.total) * 100);
            document.getElementById('pBar').style.width = p + '%'; document.getElementById('pBar').innerText = p + '%';
        };
        xhr.open("POST", "/add_content");
        xhr.onload = () => { alert("Success!"); location.reload(); };
        xhr.send(fd);
    }
</script>
"""

# --- Flask রাউটস ---

@app.route('/')
def index():
    query = request.args.get('q')
    cats = list(categories_col.find())
    if query:
        movies = list(movies_col.find({"title": {"$regex": query, "$options": "i"}}).sort("_id", -1))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(HOME_HTML, categories=cats, movies=movies, query=query, s=get_config())

@app.route('/movie/<id>')
def movie_detail(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    if not m: return redirect('/')
    return render_template_string(DETAIL_HTML, m=m, s=get_config())

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="section-box" style="display:block; max-width:320px; margin:100px auto;"><h2>Login</h2><input type="text" name="u" placeholder="User"><input type="password" name="p" placeholder="Pass"><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    m_list = list(movies_col.find().sort("_id", -1))
    return render_template_string(ADMIN_HTML, categories=list(categories_col.find()), movies=m_list, total_movies=len(m_list), s=get_config())

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
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        file.save(tf.name)
        up = cloudinary.uploader.upload_large(tf.name, resource_type="video")
    os.remove(tf.name)
    movies_col.insert_one({
        "title": request.form.get('title'), "year": request.form.get('year'),
        "poster": request.form.get('poster'), "backdrop": request.form.get('backdrop'),
        "category_id": request.form.get('category_id'), "video_url": up['secure_url']
    })
    return "OK"

@app.route('/add_cat', methods=['POST'])
def add_cat():
    if session.get('auth'): categories_col.insert_one({"name": request.form.get('name')})
    return redirect('/admin')

@app.route('/del_cat/<id>')
def del_cat(id):
    if session.get('auth'): categories_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'): movies_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {
            "site_name": request.form.get('site_name'), "ad_link": request.form.get('ad_link'),
            "ad_click_limit": int(request.form.get('ad_click_limit', 0))
        }})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
