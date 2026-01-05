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

# --- ডাটাবেস ও ক্লাউড সেটিংস ---
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
    comments_col = db['comments'] # নতুন কমেন্ট কালেকশন
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
            "popunder": "", "native": "",
            "ad_link": "https://ad-link.com", 
            "ad_click_limit": 3
        }
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম রেসপন্সিভ CSS (সব ফিচার সহ) ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    /* ন্যাভবার ও রেইনবো লোগো */
    .nav { background: rgba(0,0,0,0.95); padding: 12px 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; flex-wrap: wrap; }
    .logo { 
        font-size: 28px; font-weight: bold; text-decoration: none; text-transform: uppercase; 
        background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: rainbow 5s linear infinite; letter-spacing: 1px;
    }
    @keyframes rainbow { to { background-position: 400% center; } }
    
    .container { max-width: 1400px; margin: auto; padding: 15px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 20px; padding: 5px 15px; border: 1px solid #333; width: 100%; max-width: 400px; margin: 10px 0; }
    @media (min-width: 768px) { .search-box { width: 300px; margin: 0; } }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 5px; }

    /* মুভি গ্রিড */
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(135px, 1fr)); gap: 15px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; } }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card:hover { border-color: var(--main); transform: translateY(-5px); }

    /* লাইক, কমেন্ট ও শেয়ার সেকশন */
    .action-bar { display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap; }
    .action-btn { background: #222; color: #fff; padding: 10px 15px; border-radius: 5px; cursor: pointer; border: 1px solid #333; font-size: 14px; text-decoration: none; transition: 0.3s; }
    .action-btn:hover { background: var(--main); }
    .action-btn i { margin-right: 5px; }

    .comment-section { background: #111; padding: 20px; border-radius: 10px; margin-top: 30px; border: 1px solid #222; }
    .comment-box { margin-bottom: 20px; }
    .comment-item { background: #1a1a1a; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #333; }
    .comment-user { color: var(--main); font-weight: bold; font-size: 14px; }
    .comment-text { margin-top: 5px; font-size: 15px; color: #ddd; }

    .share-modal { display: flex; gap: 10px; margin-top: 10px; }
    .share-icon { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px; text-decoration: none; }

    /* ভিডিও ও বাটন */
    .btn { background: var(--main); color: #fff; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; font-weight: bold; display: inline-block; text-align: center; }
    video { width: 100%; border-radius: 10px; background: #000; aspect-ratio: 16/9; }

    /* এডমিন ড্রয়ার */
    .admin-drawer { position: fixed; top: 0; right: -100%; width: 280px; height: 100%; background: #121212; border-left: 1px solid #333; transition: 0.3s; z-index: 2000; padding-top: 60px; }
    .admin-drawer.active { right: 0; }
    .admin-drawer span, .admin-drawer a { padding: 15px 25px; cursor: pointer; border-bottom: 1px solid #222; text-decoration: none; color: #fff; font-weight: bold; display: block; }
    .section-box { display: none; background: #111; padding: 20px; border-radius: 10px; border: 1px solid #222; margin-top: 20px; }
    input, select, textarea { width: 100%; padding: 12px; margin: 8px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 5px; }
</style>
"""

# --- হোমপেজ ---
HOME_HTML = CSS + """
<nav class="nav">
    <a href="/" class="logo">{{ s.site_name }}</a>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#aaa; cursor:pointer;">🔍</button>
    </form>
</nav>

<div class="container">
    {% if query %}
        <h3 class="cat-title">Search Results: {{ query }}</h3>
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
                {% for m in movies if m.category_id == cat._id|string %}
                <a href="/movie/{{ m._id }}" class="card">
                    <img src="{{ m.poster }}" loading="lazy">
                    <div style="padding:10px; text-align:center; font-size:13px;">{{ m.title }}</div>
                </a>
                {% endfor %}
            </div>
        {% endfor %}
    {% endif %}
</div>
{{ s.popunder|safe }}
"""

# --- মুভি ডিটেইলস (লাইক, শেয়ার, কমেন্ট সহ) ---
DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div style="background: url('{{ m.backdrop }}') center/cover fixed; position: fixed; top:0; left:0; width:100%; height:100%; filter: blur(30px) brightness(0.2); z-index:-1;"></div>
<div class="container">
    <div style="display: flex; flex-direction: column; gap: 20px; margin-top: 20px;">
        <div style="width: 100%; max-width: 900px; margin: auto;">
            <video controls poster="{{ m.backdrop }}"><source src="{{ m.video_url }}" type="video/mp4"></video>
            
            <div class="action-bar">
                <a href="/like/{{ m._id }}" class="action-btn"><i class="fas fa-thumbs-up"></i> {{ m.likes or 0 }} Likes</a>
                <div class="action-btn" onclick="copyLink()"><i class="fas fa-link"></i> Copy Link</div>
                <a href="https://www.facebook.com/sharer/sharer.php?u={{ share_url }}" target="_blank" class="action-btn" style="background:#3b5998;"><i class="fab fa-facebook"></i></a>
                <a href="https://api.whatsapp.com/send?text={{ share_url }}" target="_blank" class="action-btn" style="background:#25d366;"><i class="fab fa-whatsapp"></i></a>
                <a href="https://telegram.me/share/url?url={{ share_url }}" target="_blank" class="action-btn" style="background:#0088cc;"><i class="fab fa-telegram"></i></a>
            </div>

            <h1>{{ m.title }} ({{ m.year }})</h1>
            <button onclick="handleDL()" class="btn" style="width:100%; margin-top:20px; height:60px; font-size:20px;">📥 DOWNLOAD NOW</button>
            <p id="dl-msg" style="color:var(--main); text-align:center; margin-top:10px; font-weight:bold;"></p>

            <!-- কমেন্ট সেকশন -->
            <div class="comment-section">
                <h3><i class="fas fa-comments"></i> Discussion</h3>
                <form action="/comment/{{ m._id }}" method="POST" class="comment-box">
                    <input type="text" name="user" placeholder="Your Name" required>
                    <textarea name="text" rows="3" placeholder="Write a comment..." required></textarea>
                    <button class="btn" style="margin-top:10px;">Post Comment</button>
                </form>

                <div class="comment-list">
                    {% for c in comments %}
                    <div class="comment-item">
                        <div class="comment-user">{{ c.user }} <span style="color:#666; font-size:11px; float:right;">{{ c.date }}</span></div>
                        <div class="comment-text">{{ c.text }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
</div>
<script>
    function copyLink() {
        navigator.clipboard.writeText(window.location.href);
        alert("Link Copied!");
    }

    let clicks = 0;
    const limit = {{ s.ad_click_limit }};
    const adUrl = "{{ s.ad_link }}";
    const rawVideoUrl = "{{ m.video_url }}";
    const finalDownloadUrl = rawVideoUrl.replace("/upload/", "/upload/fl_attachment/");

    function handleDL() {
        if(clicks < limit) {
            clicks++;
            document.getElementById('dl-msg').innerText = "Ads Loading... (" + clicks + "/" + limit + ")";
            window.open(adUrl, "_blank");
        } else {
            window.location.href = finalDownloadUrl;
        }
    }
</script>
{{ s.popunder|safe }}
"""

# --- এডমিন প্যানেল ---
ADMIN_HTML = CSS + """
<nav class="nav">
    <a href="/admin" class="logo">ADMIN PANEL</a>
    <div style="cursor:pointer; font-size:30px; color:var(--main);" onclick="toggleMenu()">☰</div>
</nav>

<div class="admin-drawer" id="drawer">
    <div style="text-align:right; padding:10px;"><span onclick="toggleMenu()" style="display:inline; color:red;">[CLOSE]</span></div>
    <span onclick="openSec('upBox')">📤 Upload Movie</span>
    <span onclick="openSec('manageBox')">🎬 Manage Movies</span>
    <span onclick="openSec('comBox')">💬 Manage Comments</span>
    <span onclick="openSec('catBox')">📂 Categories</span>
    <span onclick="openSec('setBox')">⚙️ Site Settings</span>
    <a href="/logout" style="color:red;">🔴 Logout</a>
</div>

<div class="container">
    <div id="upBox" class="section-box" style="display:block;">
        <h3>Upload Movie</h3>
        <input type="text" id="tmdbQ" placeholder="TMDB Search..."><button class="btn" onclick="tmdbSearch()">Search</button>
        <div id="tmdbRes" style="display:flex; gap:10px; overflow-x:auto; margin:10px 0;"></div>
        <form id="uploadForm">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <select name="category_id">
                {% for c in categories %}<option value="{{ c._id|string }}">{{ c.name }}</option>{% endfor %}
            </select>
            <input type="file" name="video_file" accept="video/mp4" required>
            <button type="button" id="upBtn" onclick="submitContent()" class="btn" style="width:100%; background:green;">UPLOAD</button>
        </form>
    </div>

    <div id="manageBox" class="section-box">
        <h3>Movies ({{ total_movies }})</h3>
        {% for m in movies %}
        <div style="display:flex; justify-content:space-between; padding:10px; border-bottom:1px solid #222;">
            <span>{{ m.title }}</span>
            <a href="/del_movie/{{ m._id }}" style="color:red; text-decoration:none;">[DELETE]</a>
        </div>
        {% endfor %}
    </div>

    <div id="comBox" class="section-box">
        <h3>All Comments</h3>
        {% for c in all_comments %}
        <div style="padding:10px; border-bottom:1px solid #222;">
            <b style="color:red;">{{ c.user }}:</b> {{ c.text }}
            <a href="/del_comment/{{ c._id }}" style="float:right; color:gray;">[DELETE]</a>
        </div>
        {% endfor %}
    </div>

    <div id="catBox" class="section-box">
        <h3>Categories</h3>
        <form action="/add_cat" method="POST" style="display:flex; gap:10px;">
            <input type="text" name="name" placeholder="Name" required><button class="btn">Add</button>
        </form>
        {% for c in categories %}
        <p style="margin-top:10px;">{{ c.name }} <a href="/del_cat/{{ c._id }}" style="color:red; float:right;">X</a></p>
        {% endfor %}
    </div>

    <div id="setBox" class="section-box">
        <h3>Settings</h3>
        <form action="/update_settings" method="POST">
            <input type="text" name="site_name" value="{{ s.site_name }}">
            <input type="text" name="ad_link" value="{{ s.ad_link }}">
            <input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}">
            <textarea name="popunder" placeholder="Popunder Code">{{ s.popunder }}</textarea>
            <textarea name="native" placeholder="Native Ad Code">{{ s.native }}</textarea>
            <button class="btn" style="width:100%;">SAVE</button>
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
        d.results.slice(0,6).forEach(i => {
            let img = document.createElement('img');
            img.src = "https://image.tmdb.org/t/p/w92" + i.poster_path;
            img.style.height="100px"; img.style.cursor="pointer";
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
        let xhr = new XMLHttpRequest();
        document.getElementById('upBtn').disabled = true;
        xhr.open("POST", "/add_content");
        xhr.onload = () => { location.reload(); };
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
    comments = list(comments_col.find({"movie_id": id}).sort("_id", -1))
    share_url = request.url
    return render_template_string(DETAIL_HTML, m=m, comments=comments, share_url=share_url, s=get_config())

@app.route('/like/<id>')
def like_movie(id):
    movies_col.update_one({"_id": ObjectId(id)}, {"$inc": {"likes": 1}})
    return redirect(f'/movie/{id}')

@app.route('/comment/<id>', methods=['POST'])
def add_comment(id):
    comments_col.insert_one({
        "movie_id": id,
        "user": request.form.get('user'),
        "text": request.form.get('text'),
        "date": datetime.now().strftime("%d %b %Y")
    })
    return redirect(f'/movie/{id}')

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="section-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin</h2><input type="text" name="u" placeholder="Admin"><input type="password" name="p" placeholder="Pass"><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    movies = list(movies_col.find().sort("_id", -1))
    all_comments = list(comments_col.find().sort("_id", -1))
    return render_template_string(ADMIN_HTML, categories=list(categories_col.find()), movies=movies, all_comments=all_comments, total_movies=len(movies), s=get_config())

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Fail! <a href='/admin'>Back</a>"

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
        up = cloudinary.uploader.upload_large(tf.name, resource_type="video", chunk_size=6000000)
    os.remove(tf.name)
    movies_col.insert_one({
        "title": request.form.get('title'),
        "year": request.form.get('year'),
        "poster": request.form.get('poster'),
        "backdrop": request.form.get('backdrop'),
        "category_id": str(request.form.get('category_id')),
        "video_url": up['secure_url'],
        "likes": 0
    })
    return "OK"

@app.route('/del_comment/<id>')
def del_comment(id):
    if session.get('auth'): comments_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

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
            "site_name": request.form.get('site_name'),
            "ad_link": request.form.get('ad_link'),
            "ad_click_limit": int(request.form.get('ad_click_limit', 0)),
            "popunder": request.form.get('popunder'),
            "native": request.form.get('native')
        }})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}"
    return jsonify(requests.get(url).json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
