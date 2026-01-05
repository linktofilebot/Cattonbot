import os
from flask import Flask, render_template_string, request, redirect, url_for, session
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)

# --- রেন্ডার এনভায়রনমেন্ট ভেরিয়েবল থেকে কনফিগারেশন ---
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_123")
MONGO_URI = os.environ.get("MONGO_URI")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# MongoDB কানেকশন চেক
if MONGO_URI:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_db']
    movies_collection = db['movies']
else:
    print("Error: MONGO_URI missing! Please add it in Render Environment Variables.")

# --- প্রিমিয়াম ডার্ক থিম ডিজাইন (CSS) ---
CSS = """
<style>
    :root { --main-color: #e50914; --bg-color: #0b0b0b; --card-bg: #181818; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg-color); color: white; }
    .navbar { background: rgba(0,0,0,0.9); padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; border-bottom: 2px solid var(--main-color); }
    .logo { color: var(--main-color); font-size: 26px; font-weight: bold; text-decoration: none; letter-spacing: 1px; }
    .container { max-width: 1300px; margin: auto; padding: 20px; }
    .btn { background: var(--main-color); color: white; border: none; padding: 10px 22px; border-radius: 4px; cursor: pointer; text-decoration: none; font-weight: bold; transition: 0.3s; }
    .btn:hover { background: #b2070f; }
    .player-box { background: #000; padding: 10px; border-radius: 8px; margin-bottom: 30px; display: none; text-align: center; border: 1px solid #333; }
    video { width: 100%; max-height: 550px; border-radius: 5px; box-shadow: 0 0 20px rgba(0,0,0,0.5); }
    .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 25px; margin-top: 20px; }
    .card { background: var(--card-bg); border-radius: 8px; overflow: hidden; transition: 0.4s; cursor: pointer; border: 1px solid #222; }
    .card:hover { transform: scale(1.06); border-color: var(--main-color); }
    .card img { width: 100%; height: 270px; object-fit: cover; }
    .card-title { padding: 12px; text-align: center; font-size: 15px; font-weight: 500; }
    input { width: 100%; padding: 14px; margin: 10px 0; border-radius: 4px; border: 1px solid #333; background: #222; color: white; }
    table { width: 100%; border-collapse: collapse; background: var(--card-bg); margin-top: 20px; border-radius: 8px; overflow: hidden; }
    th, td { padding: 15px; border-bottom: 1px solid #333; text-align: left; }
</style>
"""

# --- পাবলিক হোমপেজ টেমপ্লেট ---
HOME_HTML = CSS + """
<div class="navbar">
    <a href="/" class="logo">MOVIEBOX PRO</a>
    <a href="/admin" class="btn">ADMIN</a>
</div>
<div class="container">
    <div id="pBox" class="player-box">
        <h2 id="pTitle" style="margin-bottom:10px; color:var(--main-color);"></h2>
        <video id="pMain" controls autoplay src=""></video>
    </div>

    <h2 style="margin-bottom:20px;">Trending Movies</h2>
    <div class="movie-grid">
        {% for m in movies %}
        <div class="card" onclick="playM('{{ m.video_url }}', '{{ m.title }}')">
            <img src="{{ m.poster }}">
            <div class="card-title">{{ m.title }}</div>
        </div>
        {% endfor %}
    </div>
</div>
<script>
    function playM(url, title) {
        document.getElementById('pBox').style.display = 'block';
        document.getElementById('pMain').src = url;
        document.getElementById('pTitle').innerText = title;
        window.scrollTo({top: 0, behavior: 'smooth'});
    }
</script>
"""

# --- এডমিন প্যানেল টেমপ্লেট ---
ADMIN_HTML = CSS + """
<div class="navbar">
    <a href="/" class="logo">ADMIN PANEL</a>
    <a href="/logout" class="btn" style="background:#444;">LOGOUT</a>
</div>
<div class="container">
    <div style="background:var(--card-bg); padding:30px; border-radius:10px; max-width:600px; margin:auto;">
        <h3>Add New Movie</h3>
        <form action="/add" method="POST">
            <input type="text" name="t" placeholder="Movie Title" required>
            <input type="text" name="p" placeholder="Poster URL (Cloud Link)" required>
            <input type="text" name="v" placeholder="Video URL (Direct mp4 Link)" required>
            <button type="submit" class="btn" style="width:100%; margin-top:10px;">UPLOAD MOVIE</button>
        </form>
    </div>

    <h3 style="margin-top:40px;">Manage Movies ({{ movies|length }})</h3>
    <table>
        <tr style="background:#111;"><th>Movie Name</th><th>Action</th></tr>
        {% for m in movies %}
        <tr>
            <td>{{ m.title }}</td>
            <td><a href="/del/{{ m._id }}" style="color:#ff4444; font-weight:bold; text-decoration:none;">Delete</a></td>
        </tr>
        {% endfor %}
    </table>
</div>
"""

# --- Routes (লজিক) ---

@app.route('/')
def index():
    m_data = list(movies_collection.find()) if MONGO_URI else []
    return render_template_string(HOME_HTML, movies=m_data)

@app.route('/admin')
def admin():
    if session.get('auth'):
        m_data = list(movies_collection.find())
        return render_template_string(ADMIN_HTML, movies=m_data)
    return render_template_string(CSS + """
    <div style="max-width:350px; margin:150px auto; background:var(--card-bg); padding:30px; border-radius:10px; text-align:center;">
        <h2 style="color:var(--main-color); margin-bottom:20px;">Admin Login</h2>
        <form action="/login" method="POST">
            <input type="text" name="u" placeholder="Username" required>
            <input type="password" name="p" placeholder="Password" required>
            <button type="submit" class="btn" style="width:100%;">LOGIN</button>
        </form>
    </div>
    """)

@app.route('/login', methods=['POST'])
def login():
    if request.form['u'] == ADMIN_USER and request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Login Failed! Check Render Variables."

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/add', methods=['POST'])
def add():
    if session.get('auth'):
        movies_collection.insert_one({
            "title": request.form['t'],
            "poster": request.form['p'],
            "video_url": request.form['v']
        })
    return redirect('/admin')

@app.route('/del/<id>')
def delete(id):
    if session.get('auth'):
        movies_collection.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
