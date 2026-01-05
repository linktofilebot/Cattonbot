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

# --- ডাটাবেস ও ক্লাউড সেটিংস (আপনার তথ্য এখানে বসান) ---
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
            "type": "config", 
            "site_name": "MOVIEBOX PRO",
            "popunder": "", "banner": "", "social_bar": "", "native": "",
            "download_url": "https://download-link.com", 
            "ad_link": "https://ad-link.com", 
            "ad_click_limit": 3
        }
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম CSS ডিজাইন (লাইটিং ইফেক্ট ও প্রোগ্রেস বার সহ) ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    /* লোগো গ্লোয়িং লাইটিং ইফেক্ট */
    .logo { 
        color: var(--main); 
        font-size: 28px; 
        font-weight: bold; 
        text-decoration: none; 
        letter-spacing: 2px;
        text-transform: uppercase;
        animation: glow 1.5s ease-in-out infinite alternate;
    }
    @keyframes glow {
        from { text-shadow: 0 0 5px #fff, 0 0 10px #fff, 0 0 15px var(--main), 0 0 20px var(--main); }
        to { text-shadow: 0 0 10px #fff, 0 0 20px #ff4d4d, 0 0 30px #ff4d4d, 0 0 40px #ff4d4d; }
    }

    .nav { background: rgba(0,0,0,0.95); padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .container { max-width: 1300px; margin: auto; padding: 15px; }
    .btn { background: var(--main); color: #fff; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; font-weight: bold; display: inline-block; transition: 0.3s; text-align: center; }
    .btn:hover { opacity: 0.8; transform: scale(1.05); }

    /* মুভি কার্ড ডিজাইন */
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 35px 0 15px; font-size: 22px; font-weight: bold; text-transform: uppercase; color: #fff; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; } }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; position: relative; transition: 0.4s; }
    .card:hover { border-color: var(--main); transform: translateY(-5px); box-shadow: 0 5px 15px rgba(229, 9, 20, 0.3); }
    .card img { width: 100%; height: 260px; object-fit: cover; }
    @media (max-width: 600px) { .card img { height: 170px; } }
    .ott-badge { position: absolute; top: 8px; left: 8px; width: 30px; height: 30px; background: rgba(0,0,0,0.7); padding: 4px; border-radius: 6px; z-index: 10; }

    /* প্রোগ্রেস বার স্টাইল */
    .progress-container { width: 100%; background: #222; border-radius: 10px; margin: 20px 0; display: none; overflow: hidden; }
    .progress-bar { width: 0%; height: 20px; background: linear-gradient(90deg, #e50914, #ff4d4d); text-align: center; line-height: 20px; color: white; font-size: 12px; transition: width 0.3s; }

    /* এডমিন প্যানেল */
    .menu-btn { font-size: 32px; cursor: pointer; color: var(--main); }
    .admin-drawer { position: fixed; top: 75px; right: 5%; background: #181818; border: 1px solid #333; border-radius: 8px; display: none; flex-direction: column; z-index: 3000; width: 260px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); }
    .admin-drawer span, .admin-drawer a { padding: 15px 20px; cursor: pointer; border-bottom: 1px solid #252525; font-weight: 600; text-decoration: none; color: #fff; }
    .admin-drawer span:hover { background: #252525; color: var(--main); }
    .section-box { display: none; background: #111; padding: 25px; border-radius: 12px; border: 1px solid #222; margin-top: 20px; }
    input, select, textarea { width: 100%; padding: 12px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }
</style>
"""

# --- টেম্পলেটসমূহ ---

# ১. হোমপেজ
HOME_HTML = CSS + """
<nav class="nav">
    <a href="/" class="logo">{{ s.site_name }}</a>
    <a href="/admin" class="btn">ADMIN</a>
</nav>
{{ s.social_bar|safe }}
<div class="container">
    {% for cat in categories %}
    <div class="cat-title">{{ cat.name }}</div>
    <div class="grid">
        {% for m in movies if m.category_id == cat._id|string %}
        <a href="/movie/{{ m._id }}" class="card">
            {% if m.ott_logo %}<img src="{{ m.ott_logo }}" class="ott-badge">{% endif %}
            <img src="{{ m.poster }}" loading="lazy">
            <div style="padding:10px; text-align:center; font-size:14px; font-weight:bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ m.title }}</div>
        </a>
        {% endfor %}
    </div>
    {% endfor %}
</div>
<div class="ad-slot">{{ s.native|safe }}</div>
{{ s.popunder|safe }}
"""

# ২. ডিটেইলস পেজ
DETAIL_HTML = CSS + """
<nav class="nav">
    <a href="/" class="logo">{{ s.site_name }}</a>
    <a href="/" class="btn">HOME</a>
</nav>
<div style="background: url('{{ m.backdrop }}') center/cover; position: fixed; top:0; left:0; width:100%; height:100vh; filter: blur(25px) brightness(0.2); z-index:-1;"></div>
<div class="container">
    <div style="display: flex; flex-wrap: wrap; gap: 40px; margin-top: 80px;">
        <div style="flex: 1; min-width: 300px;">
            <img src="{{ m.poster }}" style="width:100%; border-radius:15px; border: 3px solid var(--main); box-shadow: 0 0 20px rgba(229, 9, 20, 0.5);">
            <button onclick="dlHandle()" class="btn" style="width:100%; margin-top:20px; height:60px; font-size:20px;">DOWNLOAD NOW</button>
            <p id="msg" style="color:var(--main); text-align:center; margin-top:10px; font-weight:bold;"></p>
        </div>
        <div style="flex: 2; min-width: 350px;">
            <h1 style="font-size:40px; margin-bottom:15px;">{{ m.title }} ({{ m.year }})</h1>
            <video controls preload="metadata" style="width:100%; border-radius:12px; border:1px solid #444; background:#000;">
                <source src="{{ m.video_url }}" type="video/mp4">
            </video>
            <div style="margin-top:25px;">{{ s.native|safe }}</div>
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

# ৩. এডমিন প্যানেল (প্রোগ্রেস বার ও সেটিংস সহ)
ADMIN_HTML = CSS + """
<nav class="nav">
    <a href="/admin" class="logo">ADMIN CONTROL</a>
    <div class="menu-btn" onclick="toggleMenu()">⋮</div>
</nav>

<div class="admin-drawer" id="drawer">
    <span onclick="openSec('upBox')">Upload Content</span>
    <span onclick="openSec('manageBox')">Manage Movies</span>
    <span onclick="openSec('catBox')">Categories</span>
    <span onclick="openSec('ottBox')">OTT Platforms</span>
    <span onclick="openSec('setBox')">Site Settings</span>
    <a href="/logout" style="color: red;">Logout</a>
</div>

<div class="container">
    <!-- আপলোড সেকশন -->
    <div id="upBox" class="section-box" style="display:block;">
        <h3>Upload New Movie</h3>
        <div style="display:flex; gap:10px; margin-bottom:15px;">
            <input type="text" id="tmdbQ" placeholder="Search Movie Name...">
            <button class="btn" onclick="tmdbSearch()">Search</button>
        </div>
        <div id="tmdbRes" style="display:flex; overflow-x:auto; gap:10px; margin-bottom:20px;"></div>
        
        <form id="uploadForm">
            <input type="text" name="title" id="t" placeholder="Movie Title" required>
            <input type="text" name="year" id="y" placeholder="Year">
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <select name="category_id" required>
                <option value="">Select Category</option>
                {% for c in categories %}<option value="{{ c._id }}">{{ c.name }}</option>{% endfor %}
            </select>
            <select name="ott_id">
                <option value="">Select OTT Platform</option>
                {% for o in otts %}<option value="{{ o._id }}">{{ o.name }}</option>{% endfor %}
            </select>
            <label>Select Video File (MP4):</label>
            <input type="file" name="video_file" id="video_file" accept="video/mp4" required>
            
            <div class="progress-container" id="pContainer">
                <div class="progress-bar" id="pBar">0%</div>
            </div>
            <p id="upStatus" style="text-align:center; font-size:14px; color:var(--main);"></p>

            <button type="button" id="upBtn" onclick="submitContent()" class="btn" style="width:100%; background:green; margin-top:10px;">START UPLOAD</button>
        </form>
    </div>

    <!-- মুভি লিস্ট ম্যানেজ -->
    <div id="manageBox" class="section-box">
        <h3>Manage Movies</h3>
        <div style="max-height: 500px; overflow-y: auto;">
        {% for m in movies %}
        <div style="display:flex; justify-content:space-between; padding:12px; border-bottom:1px solid #222; align-items:center;">
            <span>{{ m.title }} ({{ m.year }})</span>
            <a href="/del_movie/{{ m._id }}" style="color:red; text-decoration:none; font-weight:bold;" onclick="return confirm('Delete this movie?')">Delete</a>
        </div>
        {% endfor %}
        </div>
    </div>

    <!-- সেটিংস সেকশন -->
    <div id="setBox" class="section-box">
        <h3>Global Site Settings</h3>
        <form action="/update_settings" method="POST">
            <label>Site Name (Displayed with Lighting Effect):</label>
            <input type="text" name="site_name" value="{{ s.site_name }}" required>
            
            <label>Ad & Download Settings:</label>
            <input type="text" name="download_url" value="{{ s.download_url }}" placeholder="Final Download Link">
            <input type="text" name="ad_link" value="{{ s.ad_link }}" placeholder="Ad Link">
            <input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}" placeholder="Ad Clicks">
            
            <label>Ad Scripts:</label>
            <textarea name="popunder" rows="3" placeholder="Popunder Script">{{ s.popunder }}</textarea>
            <textarea name="native" rows="3" placeholder="Native/Banner Script">{{ s.native }}</textarea>
            <textarea name="social_bar" rows="3" placeholder="Social Bar Script">{{ s.social_bar }}</textarea>
            
            <button class="btn" style="width:100%;">UPDATE SETTINGS</button>
        </form>
    </div>

    <!-- ক্যাটাগরি সেকশন -->
    <div id="catBox" class="section-box">
        <h3>Categories</h3>
        <form action="/add_cat" method="POST" style="display:flex; gap:10px;">
            <input type="text" name="name" placeholder="Cat Name" required>
            <input type="number" name="order" placeholder="Order" required>
            <button class="btn">Add</button>
        </form>
        {% for c in categories %}
        <div style="padding:10px; border-bottom:1px solid #333;">{{ c.name }} <a href="/del_cat/{{ c._id }}" style="color:red; float:right;">Delete</a></div>
        {% endfor %}
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
        let form = document.getElementById('uploadForm');
        let fd = new FormData(form);
        let xhr = new XMLHttpRequest();

        // প্রোগ্রেস বার দেখানো
        document.getElementById('pContainer').style.display = 'block';
        document.getElementById('upBtn').disabled = true;
        document.getElementById('upStatus').innerText = "Uploading to server...";

        // আপলোড প্রোগ্রেস ট্র্যাক
        xhr.upload.addEventListener("progress", function(e) {
            if (e.lengthComputable) {
                let percent = Math.round((e.loaded / e.total) * 100);
                document.getElementById('pBar').style.width = percent + "%";
                document.getElementById('pBar').innerText = percent + "%";
                if(percent === 100) {
                    document.getElementById('upStatus').innerText = "Processing & Saving (Please wait)...";
                }
            }
        });

        xhr.open("POST", "/add_content");
        xhr.onload = () => {
            if(xhr.status == 200) {
                alert("Upload Successful!");
                location.reload();
            } else {
                alert("Upload Failed!");
                document.getElementById('upBtn').disabled = false;
            }
        };
        xhr.send(fd);
    }
</script>
"""

# --- সার্ভার সাইড লজিক/রাউটস ---

@app.route('/')
def index():
    return render_template_string(HOME_HTML, categories=list(categories_col.find().sort("order", 1)), movies=list(movies_col.find()), s=get_config())

@app.route('/movie/<id>')
def movie_detail(id):
    return render_template_string(DETAIL_HTML, m=movies_col.find_one({"_id": ObjectId(id)}), s=get_config())

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="section-box" style="display:block; max-width:320px; margin:100px auto;"><h2>Admin Login</h2><input type="text" name="u" placeholder="Username"><input type="password" name="p" placeholder="Password"><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    return render_template_string(ADMIN_HTML, categories=list(categories_col.find().sort("order",1)), otts=list(ott_col.find()), movies=list(movies_col.find().sort("_id", -1)), s=get_config())

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Invalid Credentials"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "Unauthorized", 401
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name)
            # ক্লাউডিনারিতে আপলোড (বড় ফাইলের জন্য upload_large)
            up = cloudinary.uploader.upload_large(tf.name, resource_type="video", chunk_size=6000000)
        os.remove(tf.name)
        
        ott_logo = ""
        if request.form.get('ott_id'):
            ott = ott_col.find_one({"_id": ObjectId(request.form.get('ott_id'))})
            if ott: ott_logo = ott['logo']

        movies_col.insert_one({
            "title": request.form.get('title'),
            "year": request.form.get('year'),
            "poster": request.form.get('poster'),
            "backdrop": request.form.get('backdrop'),
            "category_id": request.form.get('category_id'),
            "ott_logo": ott_logo,
            "video_url": up['secure_url']
        })
        return "OK"
    return "Fail", 400

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'): movies_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {
            "site_name": request.form.get('site_name'),
            "download_url": request.form.get('download_url'),
            "ad_link": request.form.get('ad_link'),
            "ad_click_limit": int(request.form.get('ad_click_limit', 0)),
            "popunder": request.form.get('popunder'),
            "native": request.form.get('native'),
            "social_bar": request.form.get('social_bar')
        }})
    return redirect('/admin')

@app.route('/add_cat', methods=['POST'])
def add_cat():
    if session.get('auth'): categories_col.insert_one({"name": request.form.get('name'), "order": int(request.form.get('order', 0))})
    return redirect('/admin')

@app.route('/del_cat/<id>')
def del_cat(id):
    if session.get('auth'): categories_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
