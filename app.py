import os
import requests
import tempfile
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_premium_2026_pro")

# --- কনফিগারেশন (নিজেদের ডিটেইলস বসাবেন) ---
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "your_tmdb_key")

cloudinary.config( 
  cloud_name = os.environ.get("CLOUDINARY_NAME", "your_cloud_name"), 
  api_key = "885392694246946", 
  api_secret = "a7y3o299JJqLfxmj9rLMK3hNbcg" 
)

# MongoDB কানেকশন
client = MongoClient(MONGO_URI)
db = client['moviebox_pro_v4']
movies_col = db['movies']
categories_col = db['categories']
ott_col = db['ott_platforms']
settings_col = db['settings']

# এডমিন ক্রেডেনশিয়াল
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "12345")

# ডিফল্ট সেটিংস ফাংশন
def get_site_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {
            "type": "config", "popunder": "", "banner": "", "social_bar": "", "native": "",
            "download_url": "https://download.com", "ad_link": "https://ads.com", "ad_click_limit": 2
        }
        settings_col.insert_one(conf)
    return conf

# --- ডিজাইন (CSS) ---
CSS = """
<style>
    :root { --main: #e50914; --bg: #0b0b0b; --card: #181818; --text: #eee; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: var(--text); }
    .navbar { background: #000; padding: 15px 5%; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { color: var(--main); font-size: 26px; font-weight: bold; text-decoration: none; }
    .container { max-width: 1300px; margin: auto; padding: 20px; }
    .btn { background: var(--main); color: #fff; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; text-decoration: none; font-weight: bold; display: inline-block; transition: 0.3s; }
    .btn:hover { opacity: 0.8; transform: scale(1.05); }
    
    /* Category Header */
    .cat-header { border-left: 4px solid var(--main); padding-left: 10px; margin: 30px 0 15px; font-size: 22px; display: flex; justify-content: space-between; align-items: center; }
    
    /* Movie Grid */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 15px; }
    @media (max-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); } }
    .card { background: var(--card); border-radius: 8px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; position: relative; transition: 0.3s; }
    .card:hover { border-color: var(--main); }
    .card img { width: 100%; height: 250px; object-fit: cover; }
    @media (max-width: 600px) { .card img { height: 160px; } }
    .ott-badge { position: absolute; top: 5px; left: 5px; width: 30px; height: 30px; border-radius: 5px; background: rgba(0,0,0,0.7); padding: 2px; }
    .ott-badge img { width: 100%; height: 100%; object-fit: contain; }

    /* Admin Panel Styling */
    .admin-box { background: #1a1a1a; padding: 20px; border-radius: 10px; margin-bottom: 25px; border: 1px solid #333; }
    input, select, textarea { width: 100%; padding: 12px; margin: 8px 0; background: #222; border: 1px solid #444; color: #fff; border-radius: 5px; }
    .flex-admin { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 800px) { .flex-admin { grid-template-columns: 1fr; } }
    .table-list { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .table-list th, .table-list td { border: 1px solid #333; padding: 10px; text-align: left; }
</style>
"""

# --- টেম্পলেটসমূহ ---

# হোমপেজ (ক্যাটাগরি অনুযায়ী সাজানো)
HOME_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/admin" class="btn">ADMIN</a></nav>
{{ s.social_bar|safe }}
<div class="container">
    {% for cat in categories %}
    <div class="cat-header">{{ cat.name }}</div>
    <div class="grid">
        {% for m in movies if m.category_id == cat._id|string %}
        <a href="/movie/{{ m._id }}" class="card">
            {% if m.ott_logo %}<div class="ott-badge"><img src="{{ m.ott_logo }}"></div>{% endif %}
            <img src="{{ m.poster }}">
            <div style="padding:8px; text-align:center; font-size:13px;"><b>{{ m.title }}</b></div>
        </a>
        {% endfor %}
    </div>
    {% endfor %}
</div>
{{ s.popunder|safe }}
"""

# ডিটেইলস পেজ (মাল্টি-অ্যাড সিস্টেম সহ)
DETAIL_HTML = CSS + """
<nav class="navbar"><a href="/" class="logo">MOVIEBOX PRO</a><a href="/" class="btn">HOME</a></nav>
<div class="container">
    <div style="display:flex; flex-wrap:wrap; gap:30px; margin-top:20px;">
        <div style="flex:1; min-width:300px;">
            <img src="{{ m.poster }}" style="width:100%; border-radius:10px; border:2px solid var(--main);">
            <button onclick="handleDL()" class="btn" style="width:100%; margin-top:15px; background:#0066ff; height:50px; font-size:18px;">DOWNLOAD NOW</button>
            <p id="st" style="text-align:center; margin-top:10px; color:#aaa;"></p>
        </div>
        <div style="flex:2; min-width:300px;">
            <h1 style="color:var(--main)">{{ m.title }} ({{ m.year }})</h1>
            <div style="margin:20px 0; background:#000; border-radius:10px; overflow:hidden; border:1px solid #333;">
                <video controls playsinline><source src="{{ m.video_url }}" type="video/mp4"></video>
            </div>
            <div class="ad-slot">{{ s.native|safe }}</div>
        </div>
    </div>
</div>
<script>
    let clicks = 0; const limit = {{ s.ad_click_limit }};
    function handleDL() {
        if(clicks < limit) { clicks++; document.getElementById('st').innerText = `Unlocking: ${clicks}/${limit}`; window.open("{{ s.ad_link }}", "_blank"); }
        else { window.location.href = "{{ s.download_url }}"; }
    }
</script>
"""

# এডমিন প্যানেল (ক্যাটাগরি ও OTT ম্যানেজমেন্ট সহ)
ADMIN_HTML = CSS + """
<nav class="navbar"><a href="/admin" class="logo">ADMIN PANEL</a><a href="/logout" class="btn" style="background:#444;">LOGOUT</a></nav>
<div class="container">
    <div class="flex-admin">
        <!-- ক্যাটাগরি ম্যানেজমেন্ট -->
        <div class="admin-box">
            <h3>Manage Categories</h3>
            <form action="/add_category" method="POST" style="display:flex; gap:5px;">
                <input type="text" name="name" placeholder="Category Name" required>
                <input type="number" name="order" placeholder="Serial" style="width:80px;" required>
                <button class="btn">ADD</button>
            </form>
            <table class="table-list">
                <tr><th>Name</th><th>Serial</th><th>Action</th></tr>
                {% for c in categories %}
                <tr><td>{{ c.name }}</td><td>{{ c.order }}</td><td><a href="/del_category/{{ c._id }}" style="color:red;">Del</a></td></tr>
                {% endfor %}
            </table>
        </div>

        <!-- OTT ম্যানেজমেন্ট -->
        <div class="admin-box">
            <h3>Manage OTT Platforms</h3>
            <form action="/add_ott" method="POST">
                <input type="text" name="name" placeholder="OTT Name (e.g. Netflix)" required>
                <input type="text" name="logo" placeholder="Logo URL" required>
                <input type="number" name="order" placeholder="Serial" required>
                <button class="btn" style="width:100%;">ADD OTT</button>
            </form>
            <table class="table-list">
                <tr><th>Icon</th><th>Name</th><th>Action</th></tr>
                {% for o in otts %}
                <tr><td><img src="{{ o.logo }}" width="30"></td><td>{{ o.name }}</td><td><a href="/del_ott/{{ o._id }}" style="color:red;">Del</a></td></tr>
                {% endfor %}
            </table>
        </div>
    </div>

    <!-- মুভি আপলোড -->
    <div class="admin-box">
        <h3>Upload Content</h3>
        <div style="display:flex; gap:10px; margin-bottom:15px;">
            <input type="text" id="tmdbQ" placeholder="Search TMDB...">
            <button onclick="find()" class="btn">SEARCH</button>
        </div>
        <div id="res" style="display:flex; gap:10px; overflow-x:auto; margin-bottom:15px;"></div>
        <form id="uForm">
            <div class="flex-admin">
                <div>
                    <input type="text" name="title" id="ft" placeholder="Title" required>
                    <input type="text" name="year" id="fy" placeholder="Year">
                    <input type="text" name="poster" id="fp" placeholder="Poster URL">
                </div>
                <div>
                    <select name="category_id">
                        <option value="">Select Category</option>
                        {% for c in categories %}<option value="{{ c._id }}">{{ c.name }}</option>{% endfor %}
                    </select>
                    <select name="ott_id">
                        <option value="">Select OTT (Optional)</option>
                        {% for o in otts %}<option value="{{ o._id }}">{{ o.name }}</option>{% endfor %}
                    </select>
                    <input type="file" name="video_file" accept="video/mp4" required>
                </div>
            </div>
            <button type="button" onclick="up()" class="btn" style="width:100%; background:green;">UPLOAD NOW</button>
        </form>
    </div>

    <!-- অ্যাড সেটিংস -->
    <div class="admin-box">
        <h3>Global Settings (Ads & Links)</h3>
        <form action="/update_settings" method="POST">
            <div class="flex-admin">
                <input type="text" name="download_url" value="{{ s.download_url }}" placeholder="Final Download Link">
                <input type="text" name="ad_link" value="{{ s.ad_link }}" placeholder="Ad Redirect Link">
                <input type="number" name="ad_click_limit" value="{{ s.ad_click_limit }}" placeholder="Ad Click Count">
            </div>
            <textarea name="popunder" placeholder="Popunder Script">{{ s.popunder }}</textarea>
            <textarea name="banner" placeholder="Banner Script">{{ s.banner }}</textarea>
            <textarea name="social_bar" placeholder="Social Bar Script">{{ s.social_bar }}</textarea>
            <textarea name="native" placeholder="Native Script">{{ s.native }}</textarea>
            <button class="btn" style="width:100%;">SAVE ALL SETTINGS</button>
        </form>
    </div>
</div>
<script>
    async function find(){
        let q = document.getElementById('tmdbQ').value;
        let r = await fetch(`/api/tmdb?q=${q}`);
        let d = await r.json();
        let div = document.getElementById('res'); div.innerHTML = '';
        d.results.slice(0,6).forEach(i => {
            let img = document.createElement('img');
            img.src = "https://image.tmdb.org/t/p/w92"+i.poster_path;
            img.style.cursor="pointer"; img.style.borderRadius="5px";
            img.onclick = () => {
                document.getElementById('ft').value = i.title || i.name;
                document.getElementById('fy').value = (i.release_date || i.first_air_date || '').split('-')[0];
                document.getElementById('fp').value = "https://image.tmdb.org/t/p/w500"+i.poster_path;
            };
            div.appendChild(img);
        });
    }
    function up(){
        let fd = new FormData(document.getElementById('uForm'));
        let xhr = new XMLHttpRequest();
        xhr.open("POST", "/add_content");
        xhr.onload = () => { if(xhr.status==200){alert("Success!"); location.reload();} else {alert("Error!");} };
        xhr.send(fd);
    }
</script>
"""

# --- রাউটস (সহজ এবং কার্যকরী) ---

@app.route('/')
def index():
    categories = list(categories_col.find().sort("order", 1))
    movies = list(movies_col.find())
    return render_template_string(HOME_HTML, categories=categories, movies=movies, s=get_site_config())

@app.route('/movie/<id>')
def movie_page(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    return render_template_string(DETAIL_HTML, m=m, s=get_site_config())

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="admin-box" style="max-width:350px; margin:100px auto;"><h2>Admin</h2><input type="text" name="u" placeholder="User"><input type="password" name="p" placeholder="Pass"><button class="btn">LOGIN</button></form></div>""")
    return render_template_string(ADMIN_HTML, 
        categories=list(categories_col.find().sort("order", 1)),
        otts=list(ott_col.find().sort("order", 1)),
        s=get_site_config()
    )

# --- ক্যাটাগরি ও OTT লজিক ---
@app.route('/add_category', methods=['POST'])
def add_cat():
    if session.get('auth'):
        categories_col.insert_one({"name": request.form.get('name'), "order": int(request.form.get('order', 0))})
    return redirect('/admin')

@app.route('/del_category/<id>')
def del_cat(id):
    if session.get('auth'): categories_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

@app.route('/add_ott', methods=['POST'])
def add_ott():
    if session.get('auth'):
        ott_col.insert_one({"name": request.form.get('name'), "logo": request.form.get('logo'), "order": int(request.form.get('order', 0))})
    return redirect('/admin')

@app.route('/del_ott/<id>')
def del_ott(id):
    if session.get('auth'): ott_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

# --- কন্টেন্ট ও সেটিংস ---
@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not session.get('auth'): return "No", 401
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
    if not session.get('auth'): return "No", 401
    file = request.files.get('video_file')
    if file:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            file.save(tf.name)
            up = cloudinary.uploader.upload_large(tf.name, resource_type="video", chunk_size=6000000)
        os.remove(tf.name)
        
        # OTT লোগো ফেচ করা
        ott_logo = ""
        ott_id = request.form.get('ott_id')
        if ott_id:
            ott_data = ott_col.find_one({"_id": ObjectId(ott_id)})
            if ott_data: ott_logo = ott_data['logo']

        movies_col.insert_one({
            "title": request.form.get('title'),
            "year": request.form.get('year'),
            "poster": request.form.get('poster'),
            "category_id": request.form.get('category_id'),
            "ott_id": ott_id,
            "ott_logo": ott_logo,
            "video_url": up['secure_url']
        })
        return "OK"
    return "Err", 400

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

@app.route('/api/tmdb')
def tmdb():
    q = request.args.get('q')
    return jsonify(requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={q}").json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
