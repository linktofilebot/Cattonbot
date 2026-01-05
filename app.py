import os
import requests
import tempfile
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

# --- অ্যাপ সেটআপ ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_mega_key_2026")

# --- ডাটাবেস ও ক্লাউড কনফিগারেশন (নিজেদের কি বসাবেন) ---
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri_here")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "your_tmdb_api_key_here")

cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME", "your_cloud_name"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY", "885392694246946"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET", "a7y3o299JJqLfxmj9rLMK3hNbcg") 
)

# MongoDB কানেকশন ও ক্র্যাশ প্রোটেকশন
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['moviebox_pro_db']
    movies_col = db['movies']
    settings_col = db['settings']
    client.server_info()
except Exception as e:
    print(f"CRITICAL ERROR: Database not connected! {e}")

# এডমিন ডিফল্ট
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# ডিফল্ট সেটিংস লোড ফাংশন
def get_site_settings():
    s = settings_col.find_one({"type": "config"})
    if not s:
        default = {
            "type": "config",
            "popunder": "",
            "banner": "",
            "social_bar": "",
            "native": "",
            "download_url": "https://google.com"
        }
        settings_col.insert_one(default)
        return default
    return s

# --- ডিজাইন (CSS) ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #0b0b0b; --card: #1a1a1a; --text: #fff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); }
    .nav { background: #000; padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { color: var(--main); font-size: 24px; font-weight: bold; text-decoration: none; }
    .container { max-width: 1200px; margin: auto; padding: 15px; }
    .btn { background: var(--main); color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; text-decoration: none; font-weight: bold; display: inline-block; }
    .btn-dl { background: #0084ff; width: 100%; text-align: center; margin-top: 10px; font-size: 18px; }
    
    /* Movie Grid */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; margin-top: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); } }
    .card { background: var(--card); border-radius: 8px; overflow: hidden; border: 1px solid #333; transition: 0.3s; text-decoration: none; color: white; }
    .card:hover { transform: translateY(-5px); border-color: var(--main); }
    .card img { width: 100%; height: 230px; object-fit: cover; }
    @media (max-width: 600px) { .card img { height: 160px; } }
    .card-info { padding: 8px; text-align: center; font-size: 13px; }

    /* Details Page */
    .details { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 20px; }
    .det-img { flex: 1; min-width: 280px; }
    .det-img img { width: 100%; border-radius: 10px; border: 1px solid var(--main); }
    .det-main { flex: 2; min-width: 300px; }
    .player-box { width: 100%; background: #000; border-radius: 10px; overflow: hidden; margin-bottom: 15px; border: 1px solid #444; }
    video { width: 100%; aspect-ratio: 16/9; }

    /* Ad Slots */
    .ad-slot { text-align: center; margin: 15px 0; min-height: 50px; background: rgba(255,255,255,0.05); }

    /* Admin */
    .admin-box { background: var(--card); padding: 20px; border-radius: 10px; margin-bottom: 20px; }
    input, textarea, select { width: 100%; padding: 12px; margin: 8px 0; background: #222; border: 1px solid #444; color: #fff; border-radius: 5px; }
    .prog-box { height: 20px; background: #333; border-radius: 10px; display: none; margin: 10px 0; overflow: hidden; }
    .prog-bar { height: 100%; background: var(--main); width: 0%; text-align: center; font-size: 12px; }
</style>
"""

# --- টেম্পলেটসমূহ ---

# হোমপেজ
HOME_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/admin" class="btn">ADMIN</a></nav>
{{ s.social_bar|safe }}
<div class="container">
    <div class="ad-slot">{{ s.banner|safe }}</div>
    <div class="grid">
        {% for m in movies %}
        <a href="/movie/{{ m._id }}" class="card">
            <img src="{{ m.poster }}" alt="{{ m.title }}">
            <div class="card-info"><b>{{ m.title }}</b><br>{{ m.year }}</div>
        </a>
        {% endfor %}
    </div>
    <div class="ad-slot">{{ s.native|safe }}</div>
</div>
{{ s.popunder|safe }}
"""

# ডিটেইলস পেজ (অটো ডাউনলোড ও প্লেয়ার)
DETAILS_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/" class="btn">HOME</a></nav>
<div class="container">
    <div class="ad-slot">{{ s.banner|safe }}</div>
    <div class="details">
        <div class="det-img">
            <img src="{{ m.poster }}">
            <a href="{{ s.download_url }}" target="_blank" class="btn btn-dl">DOWNLOAD NOW (HD)</a>
        </div>
        <div class="det-main">
            <h1 style="margin-bottom:10px;">{{ m.title }} ({{ m.year }})</h1>
            <div class="player-box">
                <video controls playsinline crossorigin="anonymous">
                    <source src="{{ m.video_url }}" type="video/mp4">
                    Your browser doesn't support casting.
                </video>
            </div>
            <div class="ad-slot">{{ s.native|safe }}</div>
            <p style="color:#aaa;">Enjoy high-quality streaming and fast downloads. Casting supported for Mobile/Desktop.</p>
        </div>
    </div>
</div>
{{ s.popunder|safe }}
"""

# এডমিন প্যানেল
ADMIN_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">ADMIN CONTROL</a><a href="/logout" class="btn">LOGOUT</a></nav>
<div class="container">
    <div class="admin-box">
        <h3>1. Ads & Download Settings</h3>
        <form action="/update_settings" method="POST">
            <label>Direct Download Redirect Link:</label>
            <input type="text" name="download_url" value="{{ s.download_url }}">
            <label>Popunder Ad Script:</label>
            <textarea name="popunder">{{ s.popunder }}</textarea>
            <label>Banner Ad Code:</label>
            <textarea name="banner">{{ s.banner }}</textarea>
            <label>Social Bar Script:</label>
            <textarea name="social_bar">{{ s.social_bar }}</textarea>
            <label>Native Ad Script:</label>
            <textarea name="native">{{ s.native }}</textarea>
            <button class="btn">UPDATE SETTINGS</button>
        </form>
    </div>

    <div class="admin-box">
        <h3>2. Search & Upload Content</h3>
        <div style="display:flex; gap:10px;">
            <input type="text" id="tmdbQ" placeholder="Search Movie on TMDB...">
            <button onclick="findTMDB()" class="btn">SEARCH</button>
        </div>
        <div id="tmdbRes" style="display:flex; overflow-x:auto; gap:10px; padding:10px;"></div>
        
        <form id="uploadForm">
            <input type="text" id="ft" name="title" placeholder="Movie Title" required>
            <input type="text" id="fy" name="year" placeholder="Year">
            <input type="text" id="fp" name="poster" placeholder="Poster URL">
            <input type="file" id="fv" name="video_file" accept="video/mp4" required>
            <div class="prog-box" id="pBox"><div class="prog-bar" id="pBar">0%</div></div>
            <button type="button" onclick="startUpload()" class="btn" style="width:100%;">UPLOAD & SAVE</button>
        </form>
    </div>
</div>
<script>
    async function findTMDB() {
        const q = document.getElementById('tmdbQ').value;
        const res = await fetch(`/api/tmdb?q=${q}`);
        const data = await res.json();
        const div = document.getElementById('tmdbRes'); div.innerHTML = '';
        data.results.forEach(i => {
            const img = document.createElement('img');
            img.src = `https://image.tmdb.org/t/p/w92${i.poster_path}`;
            img.style.cursor = 'pointer'; img.style.borderRadius = '5px';
            img.onclick = () => {
                document.getElementById('ft').value = i.title || i.name;
                document.getElementById('fy').value = (i.release_date || i.first_air_date || '').split('-')[0];
                document.getElementById('fp').value = `https://image.tmdb.org/t/p/w500${i.poster_path}`;
            };
            div.appendChild(img);
        });
    }

    function startUpload() {
        const form = document.getElementById('uploadForm');
        const fd = new FormData(form);
        const xhr = new XMLHttpRequest();
        document.getElementById('pBox').style.display = 'block';
        xhr.upload.onprogress = (e) => {
            const p = Math.round((e.loaded / e.total) * 100);
            document.getElementById('pBar').style.width = p + '%';
            document.getElementById('pBar').innerText = p + '%';
        };
        xhr.onload = () => { if(xhr.status === 200) { alert("Successfully Added!"); location.reload(); } else { alert("Upload Failed!"); } };
        xhr.open("POST", "/add_content");
        xhr.send(fd);
    }
</script>
"""

# --- রাউটস (সহজ ও ক্র্যাশ-ফ্রি) ---

@app.route('/')
def index():
    movies = list(movies_col.find().sort("_id", -1))
    s = get_site_settings()
    return render_template_string(HOME_HTML, movies=movies, s=s)

@app.route('/movie/<id>')
def movie_details(id):
    try:
        m = movies_col.find_one({"_id": ObjectId(id)})
        s = get_site_settings()
        if not m: return redirect('/')
        return render_template_string(DETAILS_HTML, m=m, s=s)
    except: return redirect('/')

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="admin-box" style="max-width:350px; margin:100px auto;"><h2>Login</h2><input type="text" name="u" placeholder="User"><input type="password" name="p" placeholder="Pass"><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    return render_template_string(ADMIN_HTML, s=get_site_settings())

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Invalid Login"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('auth'): return "Unauthorized", 401
    settings_col.update_one({"type": "config"}, {"$set": {
        "download_url": request.form.get('download_url'),
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "native": request.form.get('native')
    }})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb_api():
    q = request.args.get('q')
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}"
    return jsonify(requests.get(url).json())

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "Unauthorized", 401
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name)
            t_path = tf.name
        # ভিডিও আপলোড (বড় ফাইলের জন্য chunked upload)
        up = cloudinary.uploader.upload_large(t_path, resource_type="video", chunk_size=6000000)
        os.remove(t_path)
        
        movies_col.insert_one({
            "title": request.form.get('title'),
            "year": request.form.get('year'),
            "poster": request.form.get('poster'),
            "video_url": up['secure_url']
        })
        return "OK", 200
    return "Error", 400

# --- অ্যাপ রান ---
if __name__ == '__main__':
    # পোর্ট অপ্টিমাইজেশন
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
