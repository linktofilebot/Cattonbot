import os
import requests
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- কনফিগারেশন (Render-এর Environment Variables থেকে আসবে) ---
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

# এডমিন ডিফল্ট এক্সেস
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# --- ডিজাইন এবং স্টাইল (CSS) ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #0b0b0b; --card: #181818; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: white; line-height: 1.6; }
    .navbar { background: #000; padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; border-bottom: 2px solid var(--main); }
    .logo { color: var(--main); font-size: 26px; font-weight: bold; text-decoration: none; }
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    .btn { background: var(--main); color: white; border: none; padding: 10px 22px; border-radius: 4px; cursor: pointer; text-decoration: none; font-weight: bold; transition: 0.3s; display: inline-block; }
    .btn:hover { background: #b2070f; }
    
    /* Movie Grid */
    .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; margin-top: 20px; }
    .card { background: var(--card); border-radius: 8px; overflow: hidden; cursor: pointer; border: 1px solid #222; transition: 0.3s; position: relative; }
    .card:hover { transform: scale(1.05); border-color: var(--main); }
    .card img { width: 100%; height: 260px; object-fit: cover; }
    .card-info { padding: 10px; text-align: center; }
    .badge { position: absolute; top: 10px; right: 10px; background: var(--main); color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }

    /* Admin UI */
    .admin-box { background: var(--card); padding: 30px; border-radius: 10px; border: 1px solid #333; margin-bottom: 30px; }
    input, select { width: 100%; padding: 12px; margin: 8px 0; border-radius: 4px; border: 1px solid #333; background: #222; color: white; }
    
    /* Search Results */
    .search-results { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; margin: 15px 0; }
    .search-item { background: #222; padding: 5px; border-radius: 5px; cursor: pointer; text-align: center; font-size: 11px; transition: 0.2s; }
    .search-item:hover { background: #333; }
    .search-item img { width: 100%; border-radius: 4px; }

    /* Progress Bar */
    .progress-container { width: 100%; background: #333; border-radius: 10px; margin: 15px 0; display: none; height: 30px; overflow: hidden; }
    .progress-bar { width: 0%; height: 100%; background: var(--main); color: white; text-align: center; line-height: 30px; font-weight: bold; transition: 0.2s; }
    
    .player-section { background: #000; padding: 20px; border-radius: 10px; margin-bottom: 30px; display: none; border: 1px solid var(--main); }
    video { width: 100%; max-height: 550px; border-radius: 5px; }
</style>
"""

# --- পাবলিক হোমপেজ টেমপ্লেট ---
HOME_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/admin" class="btn">ADMIN PANEL</a></nav>
<div class="container">
    <div id="playerBox" class="player-section">
        <h2 id="pTitle" style="color:var(--main); margin-bottom:15px;"></h2>
        <video id="vPlayer" controls autoplay src=""></video>
        <div id="trailerBtnDiv" style="margin-top:10px;"></div>
    </div>

    <h2 style="margin-bottom:20px; border-left:4px solid var(--main); padding-left:10px;">Trending Library</h2>
    <div class="movie-grid">
        {% for m in movies %}
        <div class="card" onclick="playMovie('{{ m.video_url }}', '{{ m.title }}', '{{ m.trailer }}')">
            <span class="badge">{{ m.type|upper }}</span>
            <img src="{{ m.poster }}">
            <div class="card-info">
                <p><b>{{ m.title }}</b></p>
                <small>{{ m.year }} {% if m.type == 'tv' %}| S{{ m.season }} E{{ m.episode }}{% endif %}</small>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
<script>
    function playMovie(url, title, trailer) {
        document.getElementById('playerBox').style.display = 'block';
        document.getElementById('vPlayer').src = url;
        document.getElementById('pTitle').innerText = title;
        const trailerDiv = document.getElementById('trailerBtnDiv');
        if(trailer && trailer !== 'None') {
            trailerDiv.innerHTML = `<a href="${trailer}" target="_blank" class="btn" style="background:#444; font-size:12px;">Watch Trailer</a>`;
        } else {
            trailerDiv.innerHTML = '';
        }
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
</script>
"""

# --- এডমিন ড্যাশবোর্ড টেমপ্লেট ---
ADMIN_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">ADMIN PANEL</a><a href="/logout" class="btn" style="background:#444;">LOGOUT</a></nav>
<div class="container">
    <div class="admin-box">
        <h3 style="color:var(--main);">1. Search TMDB (Auto-Fill)</h3>
        <div style="display:flex; gap:10px;">
            <input type="text" id="tmdbQuery" placeholder="Search Movie or TV Series name...">
            <button onclick="searchTMDB()" class="btn" style="height:48px; margin-top:8px;">SEARCH</button>
        </div>
        <div id="searchResults" class="search-results"></div>

        <hr style="border:1px solid #333; margin:25px 0;">

        <h3>2. Upload Content</h3>
        <form id="uploadForm">
            <input type="text" id="fTitle" name="title" placeholder="Title" required>
            <input type="text" id="fYear" name="year" placeholder="Year">
            <input type="text" id="fPoster" name="poster" placeholder="Poster Image URL" required>
            <input type="text" id="fBack" name="backdrop" placeholder="Backdrop URL">
            <input type="text" id="fTrailer" name="trailer" placeholder="Trailer URL (YouTube)">
            
            <select name="type" id="fType" onchange="checkType()">
                <option value="movie">Movie</option>
                <option value="tv">TV Show</option>
            </select>

            <div id="tvFields" style="display:none; gap:10px;">
                <input type="text" name="season" placeholder="Season Number">
                <input type="text" name="episode" placeholder="Episode Number">
            </div>

            <label style="color:#aaa; font-size:12px;">Select MP4 Video File:</label>
            <input type="file" id="fVideo" name="video_file" accept="video/mp4" required>
            
            <div class="progress-container" id="pCont"><div class="progress-bar" id="pBar">0%</div></div>
            <button type="button" onclick="uploadContent()" class="btn" style="width:100%; margin-top:15px; height:50px;">UPLOAD TO CLOUD</button>
        </form>
    </div>

    <h3>Manage Library</h3>
    <table style="width:100%; margin-top:20px; background:var(--card); border-collapse:collapse;">
        <tr style="background:#111; text-align:left;"><th style="padding:15px;">Title</th><th style="padding:15px;">Action</th></tr>
        {% for m in movies %}
        <tr style="border-bottom:1px solid #333;">
            <td style="padding:15px;">{{ m.title }}</td>
            <td style="padding:15px;"><a href="/delete/{{ m._id }}" style="color:red; text-decoration:none; font-weight:bold;">Delete</a></td>
        </tr>
        {% endfor %}
    </table>
</div>

<script>
    function checkType() {
        const type = document.getElementById('fType').value;
        document.getElementById('tvFields').style.display = (type === 'tv') ? 'flex' : 'none';
    }

    async function searchTMDB() {
        const q = document.getElementById('tmdbQuery').value;
        if(!q) return;
        const res = await fetch(`/api/tmdb_proxy?q=${q}`);
        const data = await res.json();
        const div = document.getElementById('searchResults');
        div.innerHTML = '';
        data.results.slice(0, 8).forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.className = 'search-item';
            itemDiv.innerHTML = `<img src="https://image.tmdb.org/t/p/w200${item.poster_path}"><p>${item.title || item.name}</p>`;
            itemDiv.onclick = () => {
                document.getElementById('fTitle').value = item.title || item.name;
                document.getElementById('fYear').value = (item.release_date || item.first_air_date || '').split('-')[0];
                document.getElementById('fPoster').value = `https://image.tmdb.org/t/p/w500${item.poster_path}`;
                document.getElementById('fBack').value = `https://image.tmdb.org/t/p/original${item.backdrop_path}`;
                document.getElementById('fType').value = item.title ? 'movie' : 'tv';
                checkType();
                alert("Details Filled!");
            };
            div.appendChild(itemDiv);
        });
    }

    function uploadContent() {
        const form = document.getElementById('uploadForm');
        const formData = new FormData(form);
        const xhr = new XMLHttpRequest();

        document.getElementById('pCont').style.display = 'block';

        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                document.getElementById('pBar').style.width = percent + '%';
                document.getElementById('pBar').innerText = "Uploading: " + percent + "%";
            }
        };

        xhr.onload = function() {
            if (xhr.status === 200) {
                alert("Upload Successful!");
                window.location.reload();
            } else {
                alert("Error: " + xhr.responseText);
            }
        };

        xhr.open("POST", "/add_content", true);
        xhr.send(formData);
    }
</script>
"""

# --- সার্ভার রাউটস (Backend Logic) ---

@app.route('/')
def index():
    movies = list(movies_collection.find())
    return render_template_string(HOME_HTML, movies=movies)

@app.route('/api/tmdb_proxy')
def tmdb_proxy():
    q = request.args.get('q')
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}"
    return jsonify(requests.get(url).json())

@app.route('/admin')
def admin():
    if session.get('is_admin'):
        movies = list(movies_collection.find())
        return render_template_string(ADMIN_HTML, movies=movies)
    return render_template_string(CSS + """
    <div style="max-width:350px; margin:150px auto; background:var(--card); padding:40px; border-radius:10px; text-align:center; border:1px solid #333;">
        <h2 style="color:var(--main); margin-bottom:25px;">Admin Login</h2>
        <form action="/login" method="POST">
            <input type="text" name="u" placeholder="Admin Name" required>
            <input type="password" name="p" placeholder="Password" required>
            <button type="submit" class="btn" style="width:100%; margin-top:10px;">LOGIN</button>
        </form>
    </div>
    """)

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['is_admin'] = True
        return redirect('/admin')
    return "Invalid Admin Credentials!"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('is_admin'): return "Unauthorized", 401
    
    try:
        video_file = request.files.get('video_file')
        if video_file:
            # Cloudinary আপলোড লজিক
            upload = cloudinary.uploader.upload_large(
                video_file, 
                resource_type="video",
                chunk_size=6000000
            )
            
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
        return "File Missing", 400
    except Exception as e:
        return str(e), 500

@app.route('/delete/<id>')
def delete(id):
    if session.get('is_admin'):
        movies_collection.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
