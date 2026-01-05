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

# --- ডাটাবেস ও ক্লাউড সেটিংস (আপনার তথ্য বসান) ---
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "your_tmdb_api_key")

cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME", "your_cloud_name"), 
  api_key = "885392694246946", 
  api_secret = "a7y3o299JJqLfxmj9rLMK3hNbcg" 
)

# MongoDB কানেকশন
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col = db['movies']
    categories_col = db['categories']
    ott_col = db['ott_platforms']
    settings_col = db['settings']
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
            "type": "config", "popunder": "", "banner": "", "social_bar": "", "native": "",
            "download_url": "https://download-link.com", "ad_link": "https://ad-link.com", "ad_click_limit": 3
        }
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম CSS ডিজাইন ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    .nav { background: rgba(0,0,0,0.95); padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { color: var(--main); font-size: 26px; font-weight: bold; text-decoration: none; letter-spacing: 1px; }
    .container { max-width: 1300px; margin: auto; padding: 15px; }
    .btn { background: var(--main); color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; font-weight: bold; display: inline-block; transition: 0.3s; text-align: center; }
    .btn:hover { opacity: 0.8; transform: scale(1.05); }

    /* ক্যাটাগরি ও মুভি গ্রিড */
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 35px 0 15px; font-size: 22px; font-weight: bold; text-transform: uppercase; color: #fff; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 18px; }
    @media (max-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; } }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; position: relative; transition: 0.4s; }
    .card:hover { border-color: var(--main); transform: translateY(-5px); }
    .card img { width: 100%; height: 250px; object-fit: cover; }
    @media (max-width: 600px) { .card img { height: 165px; } }
    .ott-badge { position: absolute; top: 8px; left: 8px; width: 30px; height: 30px; background: rgba(0,0,0,0.7); padding: 4px; border-radius: 6px; }

    /* ৩-ডট মেনু ডিজাইন */
    .menu-btn { font-size: 32px; cursor: pointer; color: var(--main); user-select: none; }
    .admin-drawer { position: fixed; top: 75px; right: 5%; background: #181818; border: 1px solid #333; border-radius: 8px; display: none; flex-direction: column; z-index: 3000; width: 250px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
    .admin-drawer span, .admin-drawer a { padding: 15px 20px; cursor: pointer; border-bottom: 1px solid #252525; font-weight: 600; text-decoration: none; color: #fff; }
    .admin-drawer span:hover, .admin-drawer a:hover { background: #252525; color: var(--main); }

    /* অ্যাডমিন সেকশন বক্স */
    .section-box { display: none; background: #111; padding: 25px; border-radius: 12px; border: 1px solid #222; margin-top: 20px; }
    input, select, textarea { width: 100%; padding: 12px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }

    /* ডিটেইলস পেজ */
    .backdrop-bg { position: absolute; top: 0; left: 0; width: 100%; height: 500px; background-size: cover; background-position: center; filter: blur(15px) brightness(0.3); z-index: -1; }
    .det-wrap { display: flex; flex-wrap: wrap; gap: 40px; margin-top: 120px; }
    .det-left { flex: 1; min-width: 280px; }
    .det-right { flex: 2; min-width: 320px; }
    video { width: 100%; border-radius: 12px; background: #000; border: 1px solid #444; margin-top: 20px; }
    .ad-slot { background: rgba(255,255,255,0.03); padding: 10px; text-align: center; margin: 20px 0; min-height: 80px; border: 1px dashed #333; }
</style>
"""

# --- টেম্পলেটসমূহ ---

# হোমপেজ
HOME_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/admin" class="btn">ADMIN</a></nav>
{{ s.social_bar|safe }}
<div class="container">
    {% for cat in categories %}
    <div class="cat-title">{{ cat.name }}</div>
    <div class="grid">
        {% for m in movies if m.category_id == cat._id|string %}
        <a href="/movie/{{ m._id }}" class="card">
            {% if m.ott_logo %}<img src="{{ m.ott_logo }}" class="ott-badge">{% endif %}
            <img src="{{ m.poster }}" loading="lazy">
            <div style="padding:10px; text-align:center; font-size:14px; font-weight:bold;">{{ m.title }}</div>
        </a>
        {% endfor %}
    </div>
    {% endfor %}
</div>
<div class="ad-slot">{{ s.native|safe }}</div>
{{ s.popunder|safe }}
"""

# ডিটেইলস পেজ
DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/" class="btn">HOME</a></nav>
<div class="backdrop-bg" style="background-image: url('{{ m.backdrop }}');"></div>
<div class="container">
    <div class="det-wrap">
        <div class="det-left">
            <img src="{{ m.poster }}" style="width:100%; border-radius:12px; box-shadow: 0 0 25px rgba(229, 9, 20, 0.4);">
            <button onclick="dlHandle()" class="btn" style="width:100%; margin-top:20px; background:#007bff; font-size:18px; height:55px;">DOWNLOAD NOW</button>
            <p id="msg" style="text-align:center; margin-top:10px; font-size:14px; color:var(--main); font-weight:bold;"></p>
        </div>
        <div class="det-right">
            <h1 style="font-size:40px; margin-bottom:10px;">{{ m.title }} ({{ m.year }})</h1>
            <p style="color:#aaa; margin-bottom:20px;">Quality: 1080p Web-DL | Casting Supported</p>
            <div class="video-box">
                <video controls playsinline preload="metadata">
                    <source src="{{ m.video_url }}" type="video/mp4">
                </video>
            </div>
            <div style="margin-top:20px;">
                {% if m.trailer %}<a href="{{ m.trailer }}" target="_blank" class="btn" style="background:#ff0000;">WATCH TRAILER</a>{% endif %}
            </div>
            <div class="ad-slot">{{ s.native|safe }}</div>
        </div>
    </div>
</div>
<script>
    let clicks = 0;
    function dlHandle() {
        if(clicks < {{ s.ad_click_limit }}) {
            clicks++;
            document.getElementById('msg').innerText = "Unlocking Link... Ad " + clicks + "/{{ s.ad_click_limit }}";
            window.open("{{ s.ad_link }}", "_blank");
        } else {
            window.location.href = "{{ s.download_url }}";
        }
    }
</script>
{{ s.popunder|safe }}
"""

# এডমিন প্যানেল
ADMIN_HTML = CSS + """
<nav class="nav">
    <a href="/admin" class="logo">ADMIN PANEL</a>
    <div class="menu-btn" onclick="toggleMenu()">⋮</div>
</nav>

<div class="admin-drawer" id="drawer">
    <span onclick="openSec('upBox')">Upload Content</span>
    <span onclick="openSec('catBox')">Manage Categories</span>
    <span onclick="openSec('ottBox')">Manage OTT Platforms</span>
    <span onclick="openSec('setBox')">Global Settings</span>
    <a href="/logout">Logout</a>
</div>

<div class="container">
    <!-- ১. আপলোড -->
    <div id="upBox" class="section-box" style="display:block;">
        <h3>Upload New Content</h3>
        <div style="display:flex; gap:10px; margin-bottom:15px;">
            <input type="text" id="tmdbQ" placeholder="Search Movie on TMDB...">
            <button class="btn" onclick="tmdbSearch()">SEARCH</button>
        </div>
        <div id="tmdbRes" style="display:flex; overflow-x:auto; gap:10px; margin-bottom:20px;"></div>
        
        <form id="uploadForm">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <input type="text" name="trailer" id="tr" placeholder="Trailer URL">
            <select name="category_id">
                <option value="">Select Category</option>
                {% for c in categories %}<option value="{{ c._id }}">{{ c.name }}</option>{% endfor %}
            </select>
            <select name="ott_id">
                <option value="">Select OTT Provider</option>
                {% for o in otts %}<option value="{{ o._id }}">{{ o.name }}</option>{% endfor %}
            </select>
            <label>Select MP4 Video File:</label>
            <input type="file" name="video_file" accept="video/mp4" required>
            <button type="button" onclick="submitContent()" class="btn" style="width:100%; background:green; margin-top:10px;">UPLOAD & SAVE</button>
        </form>
    </div>

    <!-- ২. ক্যাটাগরি -->
    <div id="catBox" class="section-box">
        <h3>Category Management</h3>
        <form action="/add_cat" method="POST" style="display:flex; gap:10px;">
            <input type="text" name="name" placeholder="Category Name" required>
            <input type="number" name="order" placeholder="Serial Order" required>
            <button class="btn">ADD</button>
        </form>
        <div style="margin-top:15px;">
            {% for c in categories %}
            <div style="padding:10px; border-bottom:1px solid #333;">
                {{ c.order }}. {{ c.name }} <a href="/del_cat/{{ c._id }}" style="color:red; float:right; text-decoration:none;">Delete</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ৩. OTT -->
    <div id="ottBox" class="section-box">
        <h3>OTT Platform Management</h3>
        <form action="/add_ott" method="POST">
            <input type="text" name="name" placeholder="OTT Name" required>
            <input type="text" name="logo" placeholder="Logo URL" required>
            <input type="number" name="order" placeholder="Serial Order" required>
            <button class="btn" style="width:100%;">ADD OTT PLATFORM</button>
        </form>
        <div style="margin-top:15px;">
            {% for o in otts %}
            <div style="padding:10px; border-bottom:1px solid #333;">
                <img src="{{ o.logo }}" width="20"> {{ o.name }} <a href="/del_ott/{{ o._id }}" style="color:red; float:right; text-decoration:none;">Delete</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ৪. সেটিংস -->
    <div id="setBox" class="section-box">
        <h3>Ad & Redirect Settings</h3>
        <form action="/update_settings" method="POST">
            <input type="text" name="download_url" value="{{ s.download_url }}" placeholder="Final File Download Link">
            <input type="text" name="ad_link" value="{{ s.ad_link }}" placeholder="Ad Redirect Link">
            <input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}" placeholder="How many ads on download click?">
            <textarea name="popunder" placeholder="Popunder Script">{{ s.popunder }}</textarea>
            <textarea name="banner" placeholder="Banner Ad HTML/Script">{{ s.banner }}</textarea>
            <textarea name="social_bar" placeholder="Social Bar Script">{{ s.social_bar }}</textarea>
            <textarea name="native" placeholder="Native Ad Script">{{ s.native }}</textarea>
            <button class="btn" style="width:100%;">SAVE GLOBAL SETTINGS</button>
        </form>
    </div>
</div>

<script>
    function toggleMenu() { let d = document.getElementById('drawer'); d.style.display = (d.style.display == 'flex') ? 'none' : 'flex'; }
    function openSec(id) {
        document.querySelectorAll('.section-box').forEach(b => b.style.display = 'none');
        document.getElementById(id).style.display = 'block';
        toggleMenu();
    }
    async function tmdbSearch(){
        let q = document.getElementById('tmdbQ').value;
        let r = await fetch(`/api/tmdb?q=${q}`);
        let d = await r.json();
        let resDiv = document.getElementById('tmdbRes'); resDiv.innerHTML = '';
        d.results.slice(0,6).forEach(i => {
            let img = document.createElement('img');
            img.src = "https://image.tmdb.org/t/p/w92"+i.poster_path;
            img.style.cursor="pointer"; img.style.borderRadius="6px";
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
        xhr.open("POST", "/add_content");
        xhr.onload = () => { if(xhr.status==200){ alert("Uploaded!"); location.reload(); } };
        xhr.send(fd);
    }
</script>
"""

# --- রাউটস ---

@app.route('/')
def index():
    categories = list(categories_col.find().sort("order", 1))
    movies = list(movies_col.find())
    return render_template_string(HOME_HTML, categories=categories, movies=movies, s=get_config())

@app.route('/movie/<id>')
def movie_detail(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    return render_template_string(DETAIL_HTML, m=m, s=get_config())

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="section-box" style="display:block; max-width:320px; margin:100px auto;"><h2>Admin Login</h2><input type="text" name="u" placeholder="Admin"><input type="password" name="p" placeholder="Pass"><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    return render_template_string(ADMIN_HTML, 
        categories=list(categories_col.find().sort("order", 1)),
        otts=list(ott_col.find().sort("order", 1)),
        s=get_config()
    )

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Login Fail"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ক্যাটাগরি ও OTT হ্যান্ডলার
@app.route('/add_cat', methods=['POST'])
def add_cat():
    if session.get('auth'): categories_col.insert_one({"name": request.form.get('name'), "order": int(request.form.get('order', 0))})
    return redirect('/admin')

@app.route('/del_cat/<id>')
def del_cat(id):
    if session.get('auth'): categories_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/add_ott', methods=['POST'])
def add_ott():
    if session.get('auth'): ott_col.insert_one({"name": request.form.get('name'), "logo": request.form.get('logo'), "order": int(request.form.get('order', 0))})
    return redirect('/admin')

@app.route('/del_ott/<id>')
def del_ott(id):
    if session.get('auth'): ott_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

# সেটিংস ও কন্টেন্ট হ্যান্ডলার
@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {
            "download_url": request.form.get('download_url'),
            "ad_link": request.form.get('ad_link'),
            "ad_click_limit": int(request.form.get('ad_click_limit', 0)),
            "popunder": request.form.get('popunder'),
            "banner": request.form.get('banner'),
            "social_bar": request.form.get('social_bar'),
            "native": request.form.get('native')
        }})
    return redirect('/admin')

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "Unauthorized", 401
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name)
            up = cloudinary.uploader.upload_large(tf.name, resource_type="video", chunk_size=6000000)
        os.remove(tf.name)
        
        ott_logo = ""
        ott = ott_col.find_one({"_id": ObjectId(request.form.get('ott_id'))}) if request.form.get('ott_id') else None
        if ott: ott_logo = ott['logo']

        movies_col.insert_one({
            "title": request.form.get('title'),
            "year": request.form.get('year'),
            "poster": request.form.get('poster'),
            "backdrop": request.form.get('backdrop'),
            "trailer": request.form.get('trailer'),
            "category_id": request.form.get('category_id'),
            "ott_logo": ott_logo,
            "video_url": up['secure_url']
        })
        return "OK"
    return "Fail", 400

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
