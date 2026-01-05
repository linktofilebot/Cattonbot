import os
import requests
import tempfile
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- কনফিগারেশন ---
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_2026_super_secret")
MONGO_URI = os.environ.get("MONGO_URI")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

# Cloudinary কনফিগারেশন
cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME"), 
  api_key = "885392694246946", 
  api_secret = "a7y3o299JJqLfxmj9rLMK3hNbcg" 
)

# MongoDB কানেকশন
client = MongoClient(MONGO_URI)
db = client['moviebox_db']
movies_collection = db['movies']

# এডমিন ডিফল্ট
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# --- ডিজাইন (CSS) ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #0b0b0b; --card: #181818; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: white; line-height: 1.6; }
    .navbar { background: #000; padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; border-bottom: 2px solid var(--main); }
    .logo { color: var(--main); font-size: 26px; font-weight: bold; text-decoration: none; }
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    .btn { background: var(--main); color: white; border: none; padding: 10px 22px; border-radius: 4px; cursor: pointer; text-decoration: none; font-weight: bold; transition: 0.3s; display: inline-block; }
    .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; margin-top: 20px; }
    .card { background: var(--card); border-radius: 8px; overflow: hidden; cursor: pointer; border: 1px solid #222; transition: 0.3s; position: relative; }
    .card:hover { transform: scale(1.05); border-color: var(--main); }
    .card img { width: 100%; height: 260px; object-fit: cover; }
    .card-info { padding: 10px; text-align: center; }
    .admin-box { background: var(--card); padding: 30px; border-radius: 10px; border: 1px solid #333; margin-bottom: 30px; }
    input, select { width: 100%; padding: 12px; margin: 8px 0; border-radius: 4px; border: 1px solid #333; background: #222; color: white; }
    .progress-container { width: 100%; background: #333; border-radius: 10px; margin: 15px 0; display: none; height: 30px; overflow: hidden; }
    .progress-bar { width: 0%; height: 100%; background: var(--main); color: white; text-align: center; line-height: 30px; font-weight: bold; }
    .search-results { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; margin: 15px 0; }
    .search-item { background: #222; padding: 5px; border-radius: 5px; cursor: pointer; text-align: center; font-size: 11px; }
    .search-item img { width: 100%; border-radius: 4px; }
    .player-section { background: #000; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: none; border: 1px solid var(--main); }
    video { width: 100%; max-height: 550px; border-radius: 5px; }
</style>
"""

# --- পাবলিক হোমপেজ ---
HOME_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/admin" class="btn">ADMIN PANEL</a></nav>
<div class="container">
    <div id="playerBox" class="player-section">
        <h2 id="pTitle" style="color:var(--main); margin-bottom:15px;"></h2>
        <video id="vPlayer" controls autoplay src=""></video>
    </div>
    <div class="movie-grid">
        {% for m in movies %}
        <div class="card" onclick="playMovie('{{ m.video_url }}', '{{ m.title }}')">
            <img src="{{ m.poster }}">
            <div class="card-info">
                <p><b>{{ m.title }}</b></p>
                <small>{{ m.year }} | {{ m.type|upper }}</small>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
<script>
    function playMovie(url, title) {
        document.getElementById('playerBox').style.display = 'block';
        document.getElementById('vPlayer').src = url;
        document.getElementById('pTitle').innerText = title;
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
</script>
"""

# --- এডমিন ড্যাশবোর্ড ---
ADMIN_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">ADMIN PANEL</a><a href="/logout" class="btn" style="background:#444;">LOGOUT</a></nav>
<div class="container">
    <div class="admin-box">
        <h3>1. Search TMDB (Auto-Fill)</h3>
        <div style="display:flex; gap:10px;">
            <input type="text" id="tmdbQuery" placeholder="Search Movie or TV Show...">
            <button onclick="searchTMDB()" class="btn" style="height:48px; margin-top:8px;">SEARCH</button>
        </div>
        <div id="searchResults" class="search-results"></div>
        <hr style="border:1px solid #333; margin:25px 0;">
        <h3>2. Upload Content</h3>
        <form id="uploadForm">
            <input type="text" id="fTitle" name="title" placeholder="Title" required>
            <input type="text" id="fYear" name="year" placeholder="Year">
            <input type="text" id="fPoster" name="poster" placeholder="Poster URL" required>
            <input type="text" id="fBack" name="backdrop" placeholder="Backdrop URL">
            <input type="text" id="fTrailer" name="trailer" placeholder="Trailer URL">
            <select name="type" id="fType" onchange="checkType()">
                <option value="movie">Movie</option>
                <option value="tv">TV Show</option>
            </select>
            <div id="tvFields" style="display:none; gap:10px;">
                <input type="text" name="season" placeholder="Season">
                <input type="text" name="episode" placeholder="Episode">
            </div>
            <input type="file" id="fVideo" name="video_file" accept="video/mp4" required>
            <div class="progress-container" id="pCont"><div class="progress-bar" id="pBar">0%</div></div>
            <button type="button" onclick="startUpload()" class="btn" style="width:100%;">UPLOAD NOW</button>
        </form>
    </div>
</div>
<script>
    function checkType() { document.getElementById('tvFields').style.display = (document.getElementById('fType').value === 'tv') ? 'flex' : 'none'; }
    async function searchTMDB() {
        const q = document.getElementById('tmdbQuery').value;
        const res = await fetch(`/api/tmdb?q=${q}`);
        const data = await res.json();
        const div = document.getElementById('searchResults');
        div.innerHTML = '';
        data.results.slice(0, 8).forEach(item => {
            const d = document.createElement('div');
            d.className = 'search-item';
            d.innerHTML = `<img src="https://image.tmdb.org/t/p/w200${item.poster_path}"><p>${item.title || item.name}</p>`;
            d.onclick = () => {
                document.getElementById('fTitle').value = item.title || item.name;
                document.getElementById('fYear').value = (item.release_date || item.first_air_date || '').split('-')[0];
                document.getElementById('fPoster').value = `https://image.tmdb.org/t/p/w500${item.poster_path}`;
                document.getElementById('fBack').value = `https://image.tmdb.org/t/p/original${item.backdrop_path}`;
                document.getElementById('fType').value = item.title ? 'movie' : 'tv';
                checkType();
            };
            div.appendChild(d);
        });
    }
    function startUpload() {
        const form = document.getElementById('uploadForm');
        const formData = new FormData(form);
        const xhr = new XMLHttpRequest();
        document.getElementById('pCont').style.display = 'block';
        xhr.upload.onprogress = (e) => {
            const p = Math.round((e.loaded / e.total) * 100);
            document.getElementById('pBar').style.width = p + '%';
            document.getElementById('pBar').innerText = p + '%';
        };
        xhr.onload = () => { if(xhr.status === 200) { alert("Done!"); window.location.reload(); } else { alert("Error: " + xhr.responseText); } };
        xhr.open("POST", "/add_content", true);
        xhr.send(formData);
    }
</script>
"""

# --- রাউটস ---

@app.route('/')
def index():
    movies = list(movies_collection.find())
    return render_template_string(HOME_HTML, movies=movies)

@app.route('/api/tmdb')
def tmdb_api():
    q = request.args.get('q')
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}"
    return jsonify(requests.get(url).json())

@app.route('/admin')
def admin():
    if session.get('auth'): return render_template_string(ADMIN_HTML)
    return render_template_string(CSS + """
    <div style="max-width:350px; margin:150px auto; background:var(--card); padding:30px; border-radius:10px; text-align:center;">
        <form action="/login" method="POST"><input type="text" name="u" placeholder="Admin"><input type="password" name="p" placeholder="Pass"><button class="btn" style="width:100%;">LOGIN</button></form>
    </div>
    """)

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
    if not session.get('auth'): return "Unauthorized", 401
    try:
        file = request.files.get('video_file')
        if file:
            # এটিই সমাধান: ফাইলকে টেম্পোরারি সেভ করা
            with tempfile.NamedTemporaryFile(delete=False) as tf:
                file.save(tf.name)
                temp_path = tf.name
            
            # আপলোড করা
            upload = cloudinary.uploader.upload_large(temp_path, resource_type="video", chunk_size=6000000)
            os.remove(temp_path) # কাজ শেষ হলে ফাইল ডিলিট করা
            
            movies_collection.insert_one({
                "title": request.form.get('title'),
                "year": request.form.get('year'),
                "poster": request.form.get('poster'),
                "backdrop": request.form.get('backdrop'),
                "trailer": request.form.get('trailer'),
                "type": request.form.get('type'),
                "season": request.form.get('season'),
                "episode": request.form.get('episode'),
                "video_url": upload['secure_url']
            })
            return "OK", 200
    except Exception as e:
        return str(e), 500
    return "No file", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
