import os
import requests
import tempfile
import threading
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
import telebot

# --- অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_ultra_2026_master")

# --- ডাটাবেস ও ক্লাউড সেটিংস ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "7dc544d9253bccc3cfecc1c677f69819")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN") # রেন্ডারে ভেরিয়েবল দিন

cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME", "dck0nrnt2"), 
  api_key = os.environ.get("CLOUDINARY_API_KEY", "885392694246946"), 
  api_secret = os.environ.get("CLOUDINARY_API_SECRET", "a7y3o299JJqLfxmj9rLMK3hNbcg") 
)

bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB কানেকশন
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col = db['movies']
    episodes_col = db['episodes']
    categories_col = db['categories']
    languages_col = db['languages']
    ott_col = db['ott_platforms']
    settings_col = db['settings']
    comments_col = db['comments']
except Exception as e:
    print(f"Database Connection Error: {e}")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {"type": "config", "site_name": "MOVIEBOX PRO", "ad_link": "https://ad-link.com", "ad_click_limit": 2, "notice_text": "Welcome to MovieBox Pro!", "notice_color": "#00ff00", "popunder": "", "native_ad": "", "banner_ad": "", "socialbar_ad": ""}
        settings_col.insert_one(conf)
    return conf

# --- প্রিমিয়াম CSS ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    .nav { background: rgba(0,0,0,0.96); padding: 15px; display: flex; justify-content: center; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { 
        font-size: clamp(22px, 6vw, 30px); font-weight: bold; text-decoration: none; text-transform: uppercase; 
        background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: rainbow 5s linear infinite; letter-spacing: 2px;
    }
    @keyframes rainbow { to { background-position: 400% center; } }
    .container { max-width: 1400px; margin: auto; padding: 15px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 25px; padding: 5px 20px; border: 1px solid #333; width: 100%; max-width: 550px; margin: 0 auto 15px; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 10px; font-size: 15px; }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; display: block; position: relative; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card-title { padding: 10px; text-align: center; font-size: 13px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }
    .btn-main { background: var(--main); color: #fff; border: none; padding: 14px 25px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; text-decoration: none; }
    .sec-box { display: none; background: #111; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #222; }
    input, select, textarea { width: 100%; padding: 14px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }
    .drw { position: fixed; top: 0; right: -100%; width: 300px; height: 100%; background: #0a0a0a; border-left: 1px solid #333; transition: 0.4s; z-index: 2000; padding-top: 50px; overflow-y: auto; }
    .drw.active { right: 0; }
    .drw span, .drw a { padding: 15px 25px; display: block; color: #fff; text-decoration: none; border-bottom: 1px solid #222; cursor: pointer; font-weight: bold; }
</style>
"""

# --- ফ্রন্টএন্ড রাউটস ---

@app.route('/')
def index():
    query = request.args.get('q')
    s = get_config()
    otts = list(ott_col.find())
    cats = list(categories_col.find())
    if query:
        movies = list(movies_col.find({"$or": [{"title": {"$regex": query, "$options": "i"}}, {"ott": {"$regex": query, "$options": "i"}}]}).sort("_id", -1))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(HOME_HTML, s=s, movies=movies, otts=otts, cats=cats, query=query)

HOME_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies, web series..." value="{{ query or '' }}">
    </form>
    <div class="cat-title">Latest Updates</div>
    <div class="grid">
        {% for m in movies %}
        <a href="/content/{{ m._id }}" class="card">
            <img src="{{ m.poster }}">
            <div class="card-title">{{ m.title }}</div>
        </a>
        {% endfor %}
    </div>
</div>
"""

@app.route('/content/<id>')
def content_detail(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    if not m: return redirect('/')
    eps = list(episodes_col.find({"series_id": id}).sort([("season", 1), ("episode", 1)]))
    s = get_config()
    return render_template_string(DETAIL_HTML, m=m, eps=eps, s=s)

DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    <video id="p" controls poster="{{ m.backdrop }}">
        <source src="{{ m.video_url if m.type == 'movie' else (eps[0].video_url if eps else '') }}" type="video/mp4">
    </video>
    {% if m.type == 'series' and eps %}
    <div class="cat-title">Episodes</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap:10px;">
        {% for e in eps %}
        <div onclick="document.getElementById('p').src='{{ e.video_url }}'; document.getElementById('p').play()" style="background:#222; padding:10px; text-align:center; cursor:pointer; border-radius:5px; font-size:12px;">S{{ e.season }} E{{ e.episode }}</div>
        {% endfor %}
    </div>
    {% endif %}
    <h1 style="margin-top:20px;">{{ m.title }}</h1>
    <button onclick="window.open('{{ s.ad_link }}'); window.location.href=document.getElementById('p').src" class="btn-main" style="margin-top:20px;">📥 DOWNLOAD NOW</button>
</div>
"""

# --- এডমিন রাউটস ---

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin Login</h2><input type="password" name="p" placeholder="Password"><button class="btn-main">LOGIN</button></form></div>""")
    
    counts = {"movies": movies_col.count_documents({"type": "movie"}), "series": movies_col.count_documents({"type": "series"}), "episodes": episodes_col.count_documents({})}
    movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(ADMIN_HTML, movies=movies, counts=counts, s=get_config())

ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:30px; position:absolute; right:20px;" onclick="document.getElementById('drw').classList.toggle('active')">☰</div></nav>
<div class="drw" id="drw">
    <a href="/">👁️ View Site</a>
    <span onclick="openSec('upBox')">📤 Upload Content</span>
    <span onclick="openSec('epBox')">🎞️ Add Episode</span>
    <span onclick="openSec('manageBox')">🎬 Bulk Action / Search</span>
    <span onclick="openSec('epManageBox')">📂 Manage Episodes</span>
    <span onclick="openSec('setBox')">⚙️ Settings</span>
    <a href="/logout" style="color:red;">🔴 Logout</a>
</div>
<div class="container">
    <!-- স্ট্যাটাস কার্ড -->
    <div style="display:flex; gap:10px; margin-bottom:20px;">
        <div style="background:#111; padding:15px; flex:1; text-align:center; border-radius:10px;"><b>{{ counts.movies }}</b><br>Movies</div>
        <div style="background:#111; padding:15px; flex:1; text-align:center; border-radius:10px;"><b>{{ counts.series }}</b><br>Series</div>
    </div>

    <!-- কন্টেন্ট আপলোড -->
    <div id="upBox" class="sec-box">
        <h3>📤 Upload Movie/Series</h3>
        <form action="/add_content" method="POST" enctype="multipart/form-data">
            <input type="text" name="title" placeholder="Title" required>
            <input type="text" name="poster" placeholder="Poster URL">
            <input type="text" name="backdrop" placeholder="Backdrop URL">
            <select name="type"><option value="movie">Movie</option><option value="series">Web Series</option></select>
            <input type="file" name="video_file" accept="video/mp4">
            <button class="btn-main">SAVE CONTENT</button>
        </form>
    </div>

    <!-- ইপিসোড অ্যাড -->
    <div id="epBox" class="sec-box">
        <h3>🎞️ Add Episode</h3>
        <form action="/add_episode" method="POST" enctype="multipart/form-data">
            <select name="series_id">
                {% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
            </select>
            <input type="number" name="season" placeholder="Season" required>
            <input type="number" name="episode" placeholder="Episode" required>
            <input type="file" name="video_file" accept="video/mp4">
            <button class="btn-main">UPLOAD EPISODE</button>
        </form>
    </div>

    <!-- বাল্ক একশন ও সার্চ -->
    <div id="manageBox" class="sec-box" style="display:block;">
        <h3>🎬 Bulk Action / Edit Search</h3>
        <input type="text" id="bulkSch" placeholder="🔍 Search movie/series name..." onkeyup="filterBulk()" style="border:1px solid var(--main);">
        <div id="bulkList" style="max-height:450px; overflow-y:auto; margin-top:10px; border:1px solid #222;">
            {% for m in movies %}
            <div class="b-item" style="padding:12px; border-bottom:1px solid #222; display:flex; justify-content:space-between; align-items:center;">
                <span>{{ m.title }} <small>({{ m.type }})</small></span>
                <div>
                    <a href="/del_movie/{{ m._id }}" style="color:red; margin-left:10px;" onclick="return confirm('Delete?')">Delete</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ইপিসোড ম্যানেজমেন্ট -->
    <div id="epManageBox" class="sec-box">
        <h3>📂 Manage Episodes</h3>
        <input type="text" id="epSch" placeholder="🔍 Find series name..." onkeyup="filterEp()" style="border:1px solid var(--main);">
        <select id="sSel" onchange="loadEps(this.value)" style="margin-top:10px;">
            <option value="">-- Select Series to See Episodes --</option>
            {% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
        </select>
        <div id="epList" style="margin-top:15px;"></div>
    </div>

    <!-- সেটিংস -->
    <div id="setBox" class="sec-box">
        <h3>⚙️ Site Settings</h3>
        <form action="/update_settings" method="POST">
            <label>Site Name</label><input type="text" name="site_name" value="{{ s.site_name }}">
            <label>Ad Link</label><input type="text" name="ad_link" value="{{ s.ad_link }}">
            <button class="btn-main">SAVE SETTINGS</button>
        </form>
    </div>
</div>
<script>
    function openSec(id){ document.querySelectorAll('.sec-box').forEach(s=>s.style.display='none'); document.getElementById(id).style.display='block'; document.getElementById('drw').classList.remove('active'); }
    function filterBulk(){
        let q = document.getElementById('bulkSch').value.toLowerCase();
        document.querySelectorAll('.b-item').forEach(i => i.style.display = i.innerText.toLowerCase().includes(q) ? 'flex' : 'none');
    }
    function filterEp(){
        let q = document.getElementById('epSch').value.toLowerCase();
        let sel = document.getElementById('sSel');
        for(let i=0; i<sel.options.length; i++) sel.options[i].style.display = sel.options[i].text.toLowerCase().includes(q) ? 'block' : 'none';
    }
    async function loadEps(sid){
        if(!sid) return;
        let r = await fetch('/api/episodes/'+sid);
        let data = await r.json();
        let div = document.getElementById('epList'); div.innerHTML = '';
        if(data.length == 0) div.innerHTML = 'No episodes found.';
        data.forEach(e => {
            div.innerHTML += `<div style="padding:10px; border-bottom:1px solid #222; display:flex; justify-content:space-between;">
                <span>Season ${e.season} - Episode ${e.episode}</span>
                <a href="/del_ep/${e._id}" style="color:red;" onclick="return confirm('Delete?')">Delete</a>
            </div>`;
        });
    }
</script>
"""

# --- এপিআই এবং একশনস ---

@app.route('/login', methods=['POST'])
def admin_login():
    if request.form['p'] == ADMIN_PASS:
        session['auth'] = True
        return redirect('/admin')
    return "Fail"

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "Unauthorized", 401
    file, v_url = request.files.get('video_file'), ""
    if file:
        up = cloudinary.uploader.upload_large(file, resource_type="video")
        v_url = up['secure_url']
    movies_col.insert_one({
        "title": request.form.get('title'), "poster": request.form.get('poster'),
        "backdrop": request.form.get('backdrop'), "type": request.form.get('type'),
        "video_url": v_url, "likes": 0, "language": "Hindi/English"
    })
    return redirect('/admin')

@app.route('/add_episode', methods=['POST'])
def add_episode():
    if not session.get('auth'): return "Unauthorized", 401
    file, v_url = request.files.get('video_file'), ""
    if file:
        up = cloudinary.uploader.upload_large(file, resource_type="video")
        v_url = up['secure_url']
    episodes_col.insert_one({
        "series_id": request.form.get('series_id'),
        "season": int(request.form.get('season')),
        "episode": int(request.form.get('episode')),
        "video_url": v_url
    })
    return redirect('/admin')

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'):
        movies_col.delete_one({"_id": ObjectId(id)})
        episodes_col.delete_many({"series_id": id})
    return redirect('/admin')

@app.route('/del_ep/<id>')
def del_ep(id):
    if session.get('auth'): episodes_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/api/episodes/<sid>')
def get_eps_api(sid):
    eps = list(episodes_col.find({"series_id": sid}).sort([("season", 1), ("episode", 1)]))
    for e in eps: e['_id'] = str(e['_id'])
    return jsonify(eps)

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {
            "site_name": request.form.get('site_name'),
            "ad_link": request.form.get('ad_link')
        }})
    return redirect('/admin')

# --- টেলিগ্রাম বট (URL সিস্টেম) ---

user_data = {}

@bot.message_handler(commands=['upload'])
def start_up(message):
    bot.reply_to(message, "📽️ মুভি বা সিরিজের নাম (Title) পাঠান:")
    user_data[message.chat.id] = {'step': 'title'}

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('step') == 'title')
def get_title(message):
    user_data[message.chat.id]['title'] = message.text
    user_data[message.chat.id]['step'] = 'url'
    bot.reply_to(message, "🔗 এবার ভিডিও ডাউনলোড লিঙ্ক (Direct URL) দিন:")

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('step') == 'url')
def get_url(message):
    if message.text.startswith("http"):
        cid = message.chat.id
        movies_col.insert_one({
            "title": user_data[cid]['title'],
            "year": datetime.now().year,
            "poster": "https://via.placeholder.com/500x750?text=No+Poster",
            "backdrop": "https://via.placeholder.com/1280x720?text=No+Backdrop",
            "type": "movie",
            "language": "Bangla/Hindi",
            "video_url": message.text,
            "likes": 0
        })
        bot.send_message(cid, f"✅ সফলভাবে অ্যাড হয়েছে: {user_data[cid]['title']}")
        user_data[cid] = {}
    else:
        bot.reply_to(message, "❌ ভুল লিঙ্ক! দয়া করে সঠিক লিঙ্ক পাঠান।")

def run_bot():
    if BOT_TOKEN != "YOUR_BOT_TOKEN":
        print("Bot Started...")
        bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
