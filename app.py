import os
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)

# --- কনফিগারেশন (Render Environment Variables থেকে আসবে) ---
app.secret_key = os.environ.get("SECRET_KEY", "movie_secret_99")
MONGO_URI = os.environ.get("MONGO_URI")

# Cloudinary কনফিগারেশন (আপনার দেওয়া কি-গুলো এখানে সেট করা হয়েছে)
cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME"), 
  api_key = "885392694246946", 
  api_secret = "a7y3o299JJqLfxmj9rLMK3hNbcg" 
)

# MongoDB কানেকশন
if MONGO_URI:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_db']
    movies_collection = db['movies']
else:
    print("WARNING: MONGO_URI missing!")

# এডমিন ডিফল্ট এক্সেস
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# --- প্রিমিয়াম ডার্ক থিম ডিজাইন (CSS) ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #0b0b0b; --card: #181818; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: white; line-height: 1.6; }
    .navbar { background: #000; padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; border-bottom: 2px solid var(--main); }
    .logo { color: var(--main); font-size: 26px; font-weight: bold; text-decoration: none; text-transform: uppercase; }
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    .btn { background: var(--main); color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; text-decoration: none; font-weight: bold; transition: 0.3s; }
    .btn:hover { background: #b2070f; opacity: 0.9; }
    .player-section { background: #000; padding: 15px; border-radius: 10px; margin-bottom: 30px; display: none; text-align: center; border: 1px solid #333; }
    video { width: 100%; max-height: 500px; border-radius: 5px; box-shadow: 0 0 20px rgba(229, 9, 20, 0.2); }
    .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; margin-top: 20px; }
    .card { background: var(--card); border-radius: 8px; overflow: hidden; transition: 0.4s; cursor: pointer; border: 1px solid #222; }
    .card:hover { transform: translateY(-5px); border-color: var(--main); }
    .card img { width: 100%; height: 260px; object-fit: cover; }
    .card-info { padding: 12px; text-align: center; font-size: 15px; }
    input[type=text], input[type=password], input[type=file] { width: 100%; padding: 12px; margin: 10px 0; border-radius: 4px; border: 1px solid #333; background: #222; color: white; }
    .admin-box { background: var(--card); padding: 30px; border-radius: 10px; max-width: 600px; margin: auto; border: 1px solid #333; }
    .loader { display: none; color: #ffcc00; font-weight: bold; margin: 10px 0; padding: 10px; border: 1px dashed #ffcc00; }
    table { width: 100%; margin-top: 30px; border-collapse: collapse; background: var(--card); }
    th, td { padding: 15px; border-bottom: 1px solid #333; text-align: left; }
</style>
"""

# --- পাবলিক হোমপেজ টেমপ্লেট ---
HOME_HTML = CSS + """
<nav class="navbar">
    <a href="/" class="logo">MOVIEBOX CLOUD</a>
    <a href="/admin" class="btn">ADMIN PANEL</a>
</nav>
<div class="container">
    <div id="videoBox" class="player-section">
        <h2 id="videoTitle" style="margin-bottom:15px; color:var(--main);"></h2>
        <video id="mainPlayer" controls autoplay src=""></video>
    </div>

    <h2 style="margin-bottom:20px; border-left: 4px solid var(--main); padding-left: 10px;">Trending Movies</h2>
    <div class="movie-grid">
        {% for movie in movies %}
        <div class="card" onclick="playMovie('{{ movie.video_url }}', '{{ movie.title }}')">
            <img src="{{ movie.poster }}" alt="Poster">
            <div class="card-info">{{ movie.title }}</div>
        </div>
        {% endfor %}
    </div>
</div>
<script>
    function playMovie(url, title) {
        document.getElementById('videoBox').style.display = 'block';
        document.getElementById('mainPlayer').src = url;
        document.getElementById('videoTitle').innerText = title;
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
</script>
"""

# --- এডমিন ড্যাশবোর্ড টেমপ্লেট ---
ADMIN_HTML = CSS + """
<nav class="navbar">
    <a href="/" class="logo">ADMIN CONTROL</a>
    <a href="/logout" class="btn" style="background:#444;">LOGOUT</a>
</nav>
<div class="container">
    <div class="admin-box">
        <h3 style="margin-bottom:20px; color:var(--main);">Upload New Movie</h3>
        <form action="/add" method="POST" enctype="multipart/form-data" onsubmit="document.getElementById('loader').style.display='block'">
            <input type="text" name="title" placeholder="Movie Name" required>
            <input type="text" name="poster" placeholder="Poster URL (e.g. https://image.jpg)" required>
            <label style="font-size:13px; color:#aaa;">Select MP4 Video File:</label>
            <input type="file" name="video_file" accept="video/mp4" required>
            <div id="loader" class="loader">Uploading to Cloudinary... Do not refresh!</div>
            <button type="submit" class="btn" style="width:100%; margin-top:10px;">UPLOAD & SAVE</button>
        </form>
    </div>

    <h3 style="margin-top:50px;">Library Management</h3>
    <table>
        <tr style="background:#111;"><th>Movie Title</th><th>Action</th></tr>
        {% for movie in movies %}
        <tr>
            <td>{{ movie.title }}</td>
            <td><a href="/delete/{{ movie._id }}" style="color:#ff4444; font-weight:bold; text-decoration:none;">Delete</a></td>
        </tr>
        {% endfor %}
    </table>
</div>
"""

# --- লজিক / রাউটস ---

@app.route('/')
def index():
    movies = list(movies_collection.find())
    return render_template_string(HOME_HTML, movies=movies)

@app.route('/admin')
def admin():
    if session.get('logged_in'):
        movies = list(movies_collection.find())
        return render_template_string(ADMIN_HTML, movies=movies)
    return render_template_string(CSS + """
    <div style="max-width:350px; margin:150px auto; background:var(--card); padding:40px; border-radius:10px; text-align:center; border:1px solid #333;">
        <h2 style="color:var(--main); margin-bottom:25px;">Admin Login</h2>
        <form action="/login" method="POST">
            <input type="text" name="user" placeholder="Username" required>
            <input type="password" name="pass" placeholder="Password" required>
            <button type="submit" class="btn" style="width:100%; margin-top:10px;">LOGIN</button>
        </form>
    </div>
    """)

@app.route('/login', methods=['POST'])
def login():
    if request.form['user'] == ADMIN_USER and request.form['pass'] == ADMIN_PASS:
        session['logged_in'] = True
        return redirect('/admin')
    return "Invalid Access!"

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/add', methods=['POST'])
def add():
    if session.get('logged_in'):
        title = request.form['title']
        poster = request.form['poster']
        file = request.files['video_file']
        
        if file:
            # Cloudinary Large File Upload
            upload_result = cloudinary.uploader.upload_large(file, resource_type="video")
            video_url = upload_result['secure_url']
            
            # MongoDB সেভ
            movies_collection.insert_one({
                "title": title,
                "poster": poster,
                "video_url": video_url
            })
    return redirect('/admin')

@app.route('/delete/<id>')
def delete(id):
    if session.get('logged_in'):
        movies_collection.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
