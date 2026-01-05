import os
import requests
import tempfile
import time
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient, errors
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- কনফিগারেশন (Environment Variables) ---
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_pro_v3_2026")
MONGO_URI = os.environ.get("MONGO_URI")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Cloudinary Setup
cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY", "885392694246946"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET", "a7y3o299JJqLfxmj9rLMK3hNbcg") 
)

# --- MongoDB কানেকশন ও ক্র্যাশ প্রোটেকশন ---
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['moviebox_db']
    movies_collection = db['movies']
    settings_collection = db['settings']
    # কানেকশন চেক
    client.server_info()
except errors.ServerSelectionTimeoutError:
    print("Error: Could not connect to MongoDB. Check your MONGO_URI.")

# ডিফল্ট অ্যাড সেটিংস চেক ও তৈরি
def get_settings():
    s = settings_collection.find_one({"type": "ads"})
    if not s:
        default_s = {
            "type": "ads",
            "popunder": "",
            "banner": "",
            "social_bar": "",
            "native": "",
            "download_redirect_url": "https://download-link.com"
        }
        settings_collection.insert_one(default_s)
        return default_s
    return s

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# --- ডিজাইন (CSS) - মোবাইল ও ডেক্সটোপ ফ্রেন্ডলি ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #050505; --card: #141414; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Roboto', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
    .navbar { background: rgba(0,0,0,0.9); padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; border-bottom: 2px solid var(--main); }
    .logo { color: var(--main); font-size: 24px; font-weight: bold; text-decoration: none; letter-spacing: 1px; }
    .container { max-width: 1300px; margin: auto; padding: 15px; }
    
    /* Buttons */
    .btn { background: var(--main); color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; font-weight: bold; display: inline-block; transition: 0.3s; }
    .btn:hover { background: #b20710; transform: scale(1.05); }
    .btn-download { background: #00a8e1; margin-top: 15px; width: 100%; text-align: center; font-size: 18px; }

    /* Movie Grid */
    .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; margin-top: 20px; }
    @media (max-width: 600px) { .movie-grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; } }
    
    .card { background: var(--card); border-radius: 8px; overflow: hidden; position: relative; border: 1px solid #222; transition: 0.3s; text-decoration: none; color: white; }
    .card:hover { border-color: var(--main); }
    .card img { width: 100%; height: 270px; object-fit: cover; }
    @media (max-width: 600px) { .card img { height: 170px; } }
    .card-info { padding: 10px; font-size: 13px; text-align: center; }

    /* Details Page */
    .details-box { display: flex; flex-wrap: wrap; gap: 30px; margin-top: 20px; background: #111; padding: 20px; border-radius: 10px; }
    .details-img { flex: 1; min-width: 250px; }
    .details-img img { width: 100%; border-radius: 10px; border: 2px solid #333; }
    .details-content { flex: 2; min-width: 300px; }
    
    /* Ads */
    .ad-container { text-align: center; margin: 15px 0; min-height: 50px; clear: both; }

    /* Player */
    .video-container { width: 100%; background: #000; border-radius: 10px; overflow: hidden; margin-top: 20px; border: 1px solid var(--main); }
    video { width: 100%; aspect-ratio: 16/9; }

    /* Admin Panel */
    .admin-card { background: #181818; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid var(--main); }
    input, select, textarea { width: 100%; padding: 12px; margin: 10px 0; background: #222; border: 1px solid #444; color: white; border-radius: 5px; }
    .progress { display: none; background: #333; border-radius: 20px; height: 25px; margin: 10px 0; }
    .progress-bar { width: 0%; height: 100%; background: var(--main); border-radius: 20px; text-align: center; font-size: 12px; line-height: 25px; }
</style>
"""

# --- HTML টেম্পলেটসমূহ ---

# হোমপেজ
HOME_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/admin" class="btn">ADMIN</a></nav>
<div class="ad-container">{{ ads.social_bar|safe }}</div>
<div class="container">
    <div class="ad-container">{{ ads.banner|safe }}</div>
    <div class="movie-grid">
        {% for m in movies %}
        <a href="/movie/{{ m._id }}" class="card">
            <img src="{{ m.poster }}" loading="lazy">
            <div class="card-info"><b>{{ m.title }}</b><br><small>{{ m.year }}</small></div>
        </a>
        {% endfor %}
    </div>
    <div class="ad-container">{{ ads.native|safe }}</div>
</div>
{{ ads.popunder|safe }}
"""

# মুভি ডিটেইলস পেজ (প্লেয়ার ও ডাউনলোড বাটন সহ)
DETAILS_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/" class="btn">HOME</a></nav>
<div class="container">
    <div class="ad-container">{{ ads.banner|safe }}</div>
    <div class="details-box">
        <div class="details-img">
            <img src="{{ movie.poster }}">
            <a href="{{ ads.download_redirect_url }}" target="_blank" class="btn btn-download">DOWNLOAD (HIGH QUALITY)</a>
        </div>
        <div class="details-content">
            <h1 style="color:var(--main)">{{ movie.title }} ({{ movie.year }})</h1>
            <p style="margin:10px 0; color:#ccc;">Type: {{ movie.type|upper }} | Quality: BlueRay 1080p</p>
            <div class="video-container">
                <video controls playsinline preload="metadata">
                    <source src="{{ movie.video_url }}" type="video/mp4">
                    Your browser does not support casting or video.
                </video>
            </div>
            <div class="ad-container">{{ ads.native|safe }}</div>
        </div>
    </div>
</div>
{{ ads.popunder|safe }}
"""

# এডমিন প্যানেল
ADMIN_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">ADMIN DASHBOARD</a><a href="/logout" class="btn">LOGOUT</a></nav>
<div class="container">
    <div class="admin-card">
        <h3>1. Ad Management & Settings</h3>
        <form action="/update_ads" method="POST">
            <input type="text" name="download_redirect_url" placeholder="Direct Download Link" value="{{ ads.download_redirect_url }}">
            <textarea name="popunder" placeholder="Paste Popunder Ad Code">{{ ads.popunder }}</textarea>
            <textarea name="banner" placeholder="Paste Banner Ad Code">{{ ads.banner }}</textarea>
            <textarea name="social_bar" placeholder="Paste Social Bar Code">{{ ads.social_bar }}</textarea>
            <textarea name="native" placeholder="Paste Native Ad Code">{{ ads.native }}</textarea>
            <button class="btn">SAVE SETTINGS</button>
        </form>
    </div>

    <div class="admin-card">
        <h3>2. Upload Content</h3>
        <div style="display:flex; gap:10px;">
            <input type="text" id="tmdbQ" placeholder="Search Movie/Show on TMDB...">
            <button onclick="searchTMDB()" class="btn">SEARCH</button>
        </div>
        <div id="res" style="display:flex; overflow-x:auto; gap:10px; padding:10px;"></div>
        
        <form id="uploadForm">
            <input type="text" id="t" name="title" placeholder="Title" required>
            <input type="text" id="y" name="year" placeholder="Year">
            <input type="text" id="p" name="poster" placeholder="Poster URL" required>
            <input type="file" id="v" name="video_file" accept="video/mp4" required>
            <div class="progress" id="pBox"><div class="progress-bar" id="pBar">0%</div></div>
            <button type="button" onclick="upload()" class="btn" style="width:100%;">START UPLOAD</button>
        </form>
    </div>
</div>
<script>
    async function searchTMDB() {
        const q = document.getElementById('tmdbQ').value;
        const res = await fetch(`/api/tmdb?q=${q}`);
        const data = await res.json();
        const div = document.getElementById('res'); div.innerHTML = '';
        data.results.forEach(i => {
            const d = document.createElement('div');
            d.innerHTML = `<img src="https://image.tmdb.org/t/p/w92${i.poster_path}" style="border-radius:5px; cursor:pointer;" onclick="fill('${i.title||i.name}','${(i.release_date||i.first_air_date||'').split('-')[0]}','https://image.tmdb.org/t/p/w500${i.poster_path}')">`;
            div.appendChild(d);
        });
    }
    function fill(t,y,p) { document.getElementById('t').value=t; document.getElementById('y').value=y; document.getElementById('p').value=p; }
    
    function upload() {
        const form = document.getElementById('uploadForm');
        const fd = new FormData(form);
        const xhr = new XMLHttpRequest();
        document.getElementById('pBox').style.display = 'block';
        xhr.upload.onprogress = (e) => {
            let p = Math.round((e.loaded/e.total)*100);
            document.getElementById('pBar').style.width = p+'%';
            document.getElementById('pBar').innerText = p+'%';
        };
        xhr.onload = () => { if(xhr.status===200) { alert("Done!"); location.reload(); } else { alert("Error!"); } };
        xhr.open("POST", "/add_content");
        xhr.send(fd);
    }
</script>
"""

# --- রাউটস ---

@app.route('/')
def index():
    try:
        movies = list(movies_collection.find().sort("_id", -1))
        ads = get_settings()
        return render_template_string(HOME_HTML, movies=movies, ads=ads)
    except: return "Database Error! Refresh Page."

@app.route('/movie/<id>')
def details(id):
    try:
        movie = movies_collection.find_one({"_id": ObjectId(id)})
        ads = get_settings()
        return render_template_string(DETAILS_HTML, movie=movie, ads=ads)
    except: return redirect('/')

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="admin-card" style="max-width:350px; margin:100px auto;"><h2>Admin Login</h2><input type="text" name="u" placeholder="User"><input type="password" name="p" placeholder="Pass"><button class="btn" style="width:100%">LOGIN</button></form></div>""")
    return render_template_string(ADMIN_HTML, ads=get_settings())

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Wrong Credentials"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/update_ads', methods=['POST'])
def update_ads():
    if not session.get('auth'): return "Unauthorized", 401
    settings_collection.update_one({"type": "ads"}, {"$set": {
        "popunder": request.form.get('popunder'),
        "banner": request.form.get('banner'),
        "social_bar": request.form.get('social_bar'),
        "native": request.form.get('native'),
        "download_redirect_url": request.form.get('download_redirect_url')
    }})
    return redirect('/admin')

@app.route('/api/tmdb')
def tmdb_api():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "Unauthorized", 401
    try:
        file = request.files.get('video_file')
        if file:
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                file.save(tf.name)
                temp_path = tf.name
            upload = cloudinary.uploader.upload_large(temp_path, resource_type="video", chunk_size=6000000)
            os.remove(temp_path)
            
            movies_collection.insert_one({
                "title": request.form.get('title'),
                "year": request.form.get('year'),
                "poster": request.form.get('poster'),
                "type": "movie",
                "video_url": upload['secure_url']
            })
            return "OK", 200
    except Exception as e:
        return str(e), 500
    return "Error", 400

if __name__ == '__main__':
    # সাইট যেন বন্ধ না হয় (Restart on error handled by Render/Heroku typically, but app.run is standard)
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)), debug=False)
