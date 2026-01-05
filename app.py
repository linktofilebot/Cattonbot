import os
import requests
import tempfile
import threading
import time
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
import telebot

# --- ১. অ্যাপ কনফিগারেশন ও সেটিংস ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_ultra_premium_master_2026")

# ডাটাবেস ও ক্লাউড সেটিংস (আপনার দেওয়া ডাটা)
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8589295170:AAHSsqlS6Zp_c-xsIAqZOv6zNiU2m_U6cro") # Render Environment Variable-এ দিবেন

cloudinary.config( 
  cloud_name = "dck0nrnt2", 
  api_key = "885392694246946", 
  api_secret = "a7y3o299JJqLfxmj9rLMK3hNbcg" 
)

# টেলিগ্রাম বট (Error Handle সহ)
bot = None
if ":" in BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# MongoDB কানেকশন ও কালেকশনস
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

# এডমিন ক্রেডেনশিয়াল
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# সাইট সেটিংস লোড ফাংশন
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", "site_name": "MOVIEBOX PRO",
            "ad_link": "https://ad-link.com", "ad_click_limit": 2,
            "notice_text": "Welcome to MovieBox Pro!", "notice_color": "#00ff00",
            "popunder": "", "native_ad": "", "banner_ad": "", "socialbar_ad": ""
        }
        settings_col.insert_one(conf)
    return conf

# --- ২. প্রিমিয়াম রেসপন্সিভ CSS ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    .nav { background: rgba(0,0,0,0.96); padding: 15px; display: flex; justify-content: center; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { 
        font-size: clamp(22px, 6vw, 30px); font-weight: bold; text-decoration: none; text-transform: uppercase; 
        background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000);
        background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
        animation: rainbow 5s linear infinite; letter-spacing: 2px;
    }
    @keyframes rainbow { to { background-position: 400% center; } }
    .back-btn { position: absolute; left: 15px; color: #fff; font-size: 22px; cursor: pointer; text-decoration: none; }
    .container { max-width: 1400px; margin: auto; padding: 15px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 25px; padding: 5px 20px; border: 1px solid #333; width: 100%; max-width: 550px; margin: 0 auto 15px; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 10px; font-size: 15px; }
    .ott-slider { display: flex; gap: 15px; overflow-x: auto; padding: 10px 0 20px; scrollbar-width: none; }
    .ott-circle { flex: 0 0 auto; text-align: center; width: 75px; text-decoration: none; }
    .ott-circle img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 2px solid #333; }
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 22px; } }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; display: block; position: relative; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card-title { padding: 10px; text-align: center; font-size: 13px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
    video { width: 100%; border-radius: 12px; background: #000; aspect-ratio: 16/9; }
    .btn-main { background: var(--main); color: #fff; border: none; padding: 14px 25px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; text-decoration: none; }
    .drw { position: fixed; top: 0; right: -100%; width: 300px; height: 100%; background: #0a0a0a; border-left: 1px solid #333; transition: 0.4s; z-index: 2000; padding-top: 50px; overflow-y: auto; }
    .drw.active { right: 0; }
    .drw span, .drw a { padding: 18px 25px; display: block; color: #fff; text-decoration: none; border-bottom: 1px solid #222; cursor: pointer; font-weight: bold; }
    .sec-box { display: none; background: #111; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #222; }
    input, select, textarea { width: 100%; padding: 14px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }
    .progress-container { width: 100%; background: #222; border-radius: 10px; margin: 15px 0; display: none; overflow: hidden; }
    .progress-bar { width: 0%; height: 20px; background: var(--main); text-align: center; font-size: 12px; color: #fff; }
</style>
"""

# --- ৩. ফ্রন্টএন্ড রাউটস ও টেম্পলেটস ---

@app.route('/')
def index():
    query = request.args.get('q')
    cats, otts = list(categories_col.find()), list(ott_col.find())
    if query:
        movies = list(movies_col.find({"$or": [{"title": {"$regex": query, "$options": "i"}}, {"ott": {"$regex": query, "$options": "i"}}]}).sort("_id", -1))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(HOME_HTML, categories=cats, movies=movies, otts=otts, query=query, s=get_config())

HOME_HTML = CSS + """
{{ s.popunder|safe }}
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    <div style="color:{{ s.notice_color }}; text-align:center; margin-bottom:15px; font-weight:bold;">{{ s.notice_text }}</div>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies, web series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#888;"><i class="fas fa-search"></i></button>
    </form>
    <div class="ott-slider">
        {% for o in otts %}<a href="/?q={{ o.name }}" class="ott-circle"><img src="{{ o.logo }}"><span>{{ o.name }}</span></a>{% endfor %}
    </div>
    <div class="cat-title">Latest Content</div>
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
    <video id="vBox" controls poster="{{ m.backdrop }}" style="width:100%; border-radius:12px;">
        <source src="{{ m.video_url if m.type == 'movie' else (eps[0].video_url if eps else '') }}" type="video/mp4">
    </video>
    {% if eps %}
    <div class="cat-title">Select Episode</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap:10px;">
        {% for e in eps %}<div onclick="document.getElementById('vBox').src='{{ e.video_url }}'; document.getElementById('vBox').play()" style="background:#222; padding:10px; text-align:center; cursor:pointer; border-radius:5px; font-size:12px;">S{{ e.season }} E{{ e.episode }}</div>{% endfor %}
    </div>
    {% endif %}
    <h1>{{ m.title }}</h1>
    <button onclick="window.open('{{ s.ad_link }}'); window.location.href=document.getElementById('vBox').src" class="btn-main" style="margin-top:20px;">📥 DOWNLOAD NOW</button>
</div>
"""

# --- ৪. অ্যাডমিন প্যানেল (সার্চ ফিচার সহ) ---

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin Login</h2><input type="password" name="p" required><button class="btn-main">LOGIN</button></form></div>""")
    
    movies = list(movies_col.find().sort("_id", -1))
    counts = {"movies": movies_col.count_documents({"type": "movie"}), "series": movies_col.count_documents({"type": "series"})}
    return render_template_string(ADMIN_HTML, movies=movies, counts=counts, s=get_config(), otts=list(ott_col.find()), categories=list(categories_col.find()), languages=list(languages_col.find()))

ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:32px; position:absolute; right:20px;" onclick="document.getElementById('drw').classList.toggle('active')">☰</div></nav>
<div class="drw" id="drw">
    <a href="/">👁️ View Site</a>
    <span onclick="openSec('upBox')">📤 Upload Content</span>
    <span onclick="openSec('epBox')">🎞️ Add Episode</span>
    <span onclick="openSec('manageBox')">🎬 Bulk Action / Search</span>
    <span onclick="openSec('epManageBox')">📂 Manage Episodes</span>
    <span onclick="openSec('ottBox')">📺 OTT Platforms</span>
    <span onclick="openSec('catBox')">📂 Categories</span>
    <span onclick="openSec('langBox')">🌐 Languages</span>
    <span onclick="openSec('setBox')">⚙️ Settings</span>
    <a href="/logout" style="color:red;">🔴 Logout</a>
</div>

<div class="container">
    <div id="upBox" class="sec-box" style="display:block;">
        <h3>Upload / TMDB Search</h3>
        <div style="display:flex; gap:10px;"><input type="text" id="tmdbQ" placeholder="Movie Name..."><button onclick="tmdbSearch()" class="btn-main" style="width:100px;">Search</button></div>
        <div id="tmdbRes" style="display:flex; gap:10px; overflow-x:auto; margin-top:10px;"></div>
        <form action="/add_content" method="POST" enctype="multipart/form-data">
            <input type="text" name="title" id="t" placeholder="Title" required>
            <input type="text" name="poster" id="p" placeholder="Poster URL">
            <input type="text" name="backdrop" id="b" placeholder="Backdrop URL">
            <select name="type"><option value="movie">Movie</option><option value="series">Web Series</option></select>
            <input type="file" name="video_file">
            <button class="btn-main">SAVE CONTENT</button>
        </form>
    </div>

    <!-- বাল্ক একশন ও লাইভ সার্চ -->
    <div id="manageBox" class="sec-box">
        <h3>🎬 Bulk Action / Search</h3>
        <input type="text" id="bulkSch" placeholder="🔍 Search content title..." onkeyup="filterBulk()" style="border:1px solid var(--main);">
        <div id="bulkList" style="max-height:450px; overflow-y:auto; margin-top:10px;">
            {% for m in movies %}
            <div class="b-item" style="padding:10px; border-bottom:1px solid #222; display:flex; justify-content:space-between;">
                <span>{{ m.title }}</span><a href="/del_movie/{{ m._id }}" style="color:red; text-decoration:none;" onclick="return confirm('Delete?')">Delete</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ইপিসোড ম্যানেজমেন্ট ও সার্চ -->
    <div id="epManageBox" class="sec-box">
        <h3>📂 Manage Episodes</h3>
        <input type="text" id="epSch" placeholder="🔍 Find series..." onkeyup="filterEp()" style="border:1px solid var(--main); margin-bottom:10px;">
        <select id="sSel" onchange="loadEps(this.value)">
            <option value="">Select Series</option>
            {% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
        </select>
        <div id="epList" style="margin-top:15px;"></div>
    </div>
    
    <div id="epBox" class="sec-box">
        <h3>🎞️ Add Episode</h3>
        <form action="/add_episode" method="POST" enctype="multipart/form-data">
            <select name="series_id">{% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}</select>
            <input type="number" name="season" placeholder="Season" required>
            <input type="number" name="episode" placeholder="Episode" required>
            <input type="file" name="video_file" required>
            <button class="btn-main">UPLOAD EPISODE</button>
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
    async function tmdbSearch(){
        let q = document.getElementById('tmdbQ').value;
        let r = await fetch('/api/tmdb?q='+q);
        let d = await r.json();
        let res = document.getElementById('tmdbRes'); res.innerHTML = '';
        d.results.slice(0,5).forEach(i => {
            let img = document.createElement('img'); img.src = "https://image.tmdb.org/t/p/w92"+i.poster_path; img.style.height="80px"; img.style.cursor="pointer";
            img.onclick = () => { document.getElementById('t').value = i.title || i.name; document.getElementById('p').value = "https://image.tmdb.org/t/p/w500"+i.poster_path; document.getElementById('b').value = "https://image.tmdb.org/t/p/original"+i.backdrop_path; };
            res.appendChild(img);
        });
    }
    async function loadEps(sid){
        if(!sid) return;
        let r = await fetch('/api/episodes/'+sid);
        let data = await r.json();
        let div = document.getElementById('epList'); div.innerHTML = '';
        data.forEach(e => { div.innerHTML += `<div style="padding:10px; border-bottom:1px solid #222;">S${e.season} E${e.episode} <a href="/del_ep/${e._id}" style="color:red; float:right;">X</a></div>`; });
    }
</script>
"""

# --- ৫. এপিআই রাউটস ও লজিক ---

@app.route('/api/tmdb')
def tmdb_api():
    q = request.args.get('q')
    res = requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}")
    return jsonify(res.json())

@app.route('/api/episodes/<sid>')
def get_eps_api(sid):
    eps = list(episodes_col.find({"series_id": sid}).sort([("season", 1), ("episode", 1)]))
    for e in eps: e['_id'] = str(e['_id'])
    return jsonify(eps)

@app.route('/login', methods=['POST'])
def login():
    if request.form['p'] == ADMIN_PASS: session['auth'] = True
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

@app.route('/add_content', methods=['POST'])
def add_content():
    if not session.get('auth'): return "No", 401
    file, v_url = request.files.get('video_file'), ""
    if file:
        up = cloudinary.uploader.upload_large(file, resource_type="video")
        v_url = up['secure_url']
    movies_col.insert_one({"title": request.form.get('title'), "poster": request.form.get('poster'), "backdrop": request.form.get('backdrop'), "type": request.form.get('type'), "video_url": v_url, "likes": 0, "year": datetime.now().year})
    return redirect('/admin')

@app.route('/add_episode', methods=['POST'])
def add_episode():
    if not session.get('auth'): return "No", 401
    file = request.files.get('video_file')
    if file:
        up = cloudinary.uploader.upload_large(file, resource_type="video")
        episodes_col.insert_one({"series_id": request.form.get('series_id'), "season": int(request.form.get('season')), "episode": int(request.form.get('episode')), "video_url": up['secure_url']})
    return redirect('/admin')

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'): movies_col.delete_one({"_id": ObjectId(id)}); episodes_col.delete_many({"series_id": id})
    return redirect('/admin')

@app.route('/del_ep/<id>')
def del_ep(id):
    if session.get('auth'): episodes_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

# --- ৬. টেলিগ্রাম বট লজিক (১০০% কাজের) ---

user_data = {}

if bot:
    @bot.message_handler(commands=['start'])
    def bot_start(message):
        bot.reply_to(message, "🎬 স্বাগতম! মুভি আপলোড করতে /upload দিন।")

    @bot.message_handler(commands=['upload'])
    def bot_up_init(message):
        bot.reply_to(message, "📽️ মুভির নাম (Title) পাঠান:")
        user_data[message.chat.id] = {'step': 'title'}

    @bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('step') == 'title')
    def bot_get_title(message):
        user_data[message.chat.id]['title'] = message.text
        user_data[message.chat.id]['step'] = 'video'
        bot.reply_to(message, f"মুভি: {message.text}\nএখন ভিডিও ফাইলটি (Video/File) পাঠান।")

    @bot.message_handler(content_types=['video', 'document'])
    def bot_get_video(message):
        cid = message.chat.id
        if user_data.get(cid, {}).get('step') == 'video':
            msg = bot.reply_to(message, "⏳ ক্লাউডিনারিতে আপলোড হচ্ছে... দয়া করে অপেক্ষা করুন।")
            try:
                # ফাইল আইডি থেকে ডাউনলোড লিঙ্ক তৈরি (টেলিগ্রাম সার্ভার ব্যবহার করে)
                file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
                file_info = bot.get_file(file_id)
                file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
                
                # রেন্ডার সার্ভারের র‍্যাম না বাঁচিয়ে সরাসরি ক্লাউডিনারি আপলোড
                up = cloudinary.uploader.upload_large(file_url, resource_type="video")
                
                movies_col.insert_one({
                    "title": user_data[cid]['title'], "year": datetime.now().year, "type": "movie",
                    "poster": "https://via.placeholder.com/500x750", "video_url": up['secure_url'], "likes": 0
                })
                bot.edit_message_text(f"✅ সফল! {user_data[cid]['title']} অ্যাড হয়েছে।", cid, msg.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ এরর: {e}", cid, msg.message_id)
            user_data[cid] = {}

def run_bot():
    if bot:
        print("Bot Started...")
        while True:
            try:
                bot.polling(none_stop=True, interval=3, timeout=20)
            except:
                time.sleep(5)

if __name__ == '__main__':
    # বটকে আলাদা থ্রেডে চালু করা
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
