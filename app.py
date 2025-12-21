import os, requests, threading, time, yt_dlp, certifi
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-key-2025-nextgen')
MONGO_URI = os.environ.get('MONGO_URI')

# অ্যাডমিন ক্রেডেনশিয়াল এনভায়রনমেন্ট থেকে (ডিফল্ট: admin / admin123)
ENV_USER = os.environ.get('ADMIN_USER', 'admin')
ENV_PASS = os.environ.get('ADMIN_PASS', 'admin123')

admin_col = None
db_connected = False

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        client.admin.command('ping')
        db_connected = True
        print("Connected to MongoDB!")
    except Exception as e: print(f"DB Error: {e}")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, data):
        self.id = str(data['_id'])
        self.username = data.get('username', ENV_USER)
        self.password = data.get('password', ENV_PASS)
        self.yt_cookies = data.get('yt_cookies', '')
        self.ad_popunder = data.get('ad_popunder', '')
        self.ad_socialbar = data.get('ad_socialbar', '')
        self.ad_native = data.get('ad_native', '')
        self.ad_banner = data.get('ad_banner', '')
        self.ad_direct_link = data.get('ad_direct_link', '')
        self.ad_direct_count = data.get('ad_direct_count', 0)

@login_manager.user_loader
def load_user(user_id):
    if admin_col is None: return None
    user_data = admin_col.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None

def fetch_video_data(url):
    if admin_col is None: return {"error": "DB Not Connected"}
    admin = admin_col.find_one({"username": ENV_USER})
    cookie_path = 'cookies.txt'
    if admin and admin.get('yt_cookies'):
        with open(cookie_path, 'w') as f: f.write(admin['yt_cookies'])
    else: cookie_path = None

    ydl_opts = {
        'format': 'best', 'quiet': True, 'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    }
    if cookie_path: ydl_opts['cookiefile'] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    formats.append({'ext': f.get('ext'), 'res': f.get('resolution') or f.get('format_note'), 'url': f.get('url'), 'size': round(f.get('filesize', 0)/(1024*1024),2) if f.get('filesize') else "N/A"})
            return {'title': info.get('title'), 'thumb': info.get('thumbnail'), 'duration': time.strftime('%M:%S', time.gmtime(info.get('duration') or 0)), 'views': "{:,}".format(info.get('view_count', 0)), 'formats': formats[::-1]}
        except Exception as e: return {"error": str(e)}

# --- UI DESIGN (Premium Gradient & Glassmorphism) ---
UI = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Premium - NextGen Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder | safe }}{{ admin.ad_socialbar | safe }}{% endif %}
    <style>
        :root { --primary: #ff0050; --bg: #0b0e14; }
        body { background: var(--bg); color: #fff; font-family: 'Poppins', sans-serif; min-height: 100vh; overflow-x: hidden; }
        .bg-animate { background: linear-gradient(-45deg, #0b0e14, #1a1a2e, #240b36); background-size: 400% 400%; animation: grad 15s ease infinite; }
        @keyframes grad { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
        .navbar { background: rgba(0,0,0,0.6); backdrop-filter: blur(15px); border-bottom: 1px solid rgba(255,255,255,0.1); }
        .glass-card { background: rgba(255, 255, 255, 0.08); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; padding: 30px; box-shadow: 0 25px 50px rgba(0,0,0,0.5); }
        .btn-premium { background: linear-gradient(90deg, #ff0050, #ff0081); border: none; color: white; border-radius: 50px; padding: 12px 35px; font-weight: 600; text-transform: uppercase; transition: 0.3s; }
        .btn-premium:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(255, 0, 80, 0.4); }
        .format-item { background: rgba(255,255,255,0.05); border-radius: 15px; margin-bottom: 12px; padding: 18px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #fff; border: 1px solid rgba(255,255,255,0.1); transition: 0.3s; }
        .format-item:hover { background: rgba(255,255,255,0.15); border-color: var(--primary); transform: translateX(10px); }
        .admin-input { background: rgba(0,0,0,0.3) !important; border: 1px solid rgba(255,255,255,0.1) !important; color: #fff !important; }
    </style>
</head>
<body class="bg-animate">
    <nav class="navbar navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold fs-3" href="/">🚀 PRO<span style="color:var(--primary)">TUBE</span> <span class="badge bg-danger fs-6">PREMIUM</span></a>
            {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-4">Dashboard</a>{% endif %}
        </div>
    </nav>
    <div class="container mt-5">
        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-info border-0 rounded-pill text-center shadow">{{m}}</div>{% endfor %}{% endwith %}
        {% if page == 'home' %}
        <div class="text-center py-5">
            <h1 class="fw-bold display-3 mb-4">Best YouTube Downloader</h1>
            <p class="lead text-white-50 mb-5">ডাউনলোড করুন আনলিমিটেড ভিডিও হাই-স্পিডে।</p>
            <div class="col-lg-8 mx-auto glass-card">
                <form method="POST" class="d-flex gap-2">
                    <input type="text" name="url" class="form-control admin-input rounded-pill p-3" placeholder="Paste link here..." required>
                    <button class="btn btn-premium px-5">Analyze</button>
                </form>
            </div>
        </div>
        {% if video %}{% if video.error %}<div class="alert alert-danger glass-card border-0 mt-4 text-center">Bot Detected! অ্যাডমিন প্যানেলে কুকিজ দিন।</div>
        {% else %}<div class="glass-card mt-5 col-lg-11 mx-auto"><div class="row g-5"><div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow-lg w-100"></div>
        <div class="col-md-7"><h3>{{ video.title }}</h3><div class="mb-3">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
        <div class="formats" style="max-height:400px; overflow-y:auto;">{% for f in video.formats[:10] %}
        <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-item"><span><i class="fa fa-play text-danger me-2"></i><b>{{ f.res }}</b> ({{ f.ext | upper }})</span>
        <span class="badge rounded-pill" style="background:var(--primary)">{{ f.size }} MB <i class="fa fa-download ms-1"></i></span></a>{% endfor %}</div></div></div></div>{% endif %}{% endif %}
        {% elif page == 'login' %}
        <div class="col-md-5 mx-auto mt-5 glass-card text-center">
            <h2 class="fw-bold mb-4">Admin Login</h2>
            <form method="POST"><input type="text" name="u" class="form-control admin-input mb-3 p-3" placeholder="Username" required>
                <input type="password" name="p" class="form-control admin-input mb-4 p-3" placeholder="Password" required><button class="btn btn-premium w-100 py-3">Login</button></form>
        </div>
        {% elif page == 'admin' %}
        <div class="glass-card mt-4"><div class="d-flex justify-content-between mb-5"><h3>Admin Control</h3><a href="/logout" class="btn btn-sm btn-outline-danger px-4 rounded-pill">Logout</a></div>
            <form method="POST" action="/save_settings"><div class="row g-4">
                <div class="col-md-6"><label class="small fw-bold mb-2">Popunder Ad</label><textarea name="pop" class="form-control admin-input" rows="3">{{ admin.ad_popunder }}</textarea></div>
                <div class="col-md-6"><label class="small fw-bold mb-2">Social Bar Ad</label><textarea name="soc" class="form-control admin-input" rows="3">{{ admin.ad_socialbar }}</textarea></div>
                <div class="col-md-6"><label class="small fw-bold mb-2">Native Ad</label><textarea name="nat" class="form-control admin-input" rows="3">{{ admin.ad_native }}</textarea></div>
                <div class="col-md-6"><label class="small fw-bold mb-2">Banner Ad</label><textarea name="ban" class="form-control admin-input" rows="3">{{ admin.ad_banner }}</textarea></div>
                <div class="col-md-8"><label class="small fw-bold mb-2">Direct Link URL</label><input type="text" name="d_url" class="form-control admin-input" value="{{ admin.ad_direct_link }}"></div>
                <div class="col-md-4"><label class="small fw-bold mb-2">Click Count</label><input type="number" name="d_count" class="form-control admin-input" value="{{ admin.ad_direct_count }}"></div>
                <div class="col-12"><label class="fw-bold mb-2 text-danger">YouTube Cookies (Netscape Format)</label><textarea name="cookies" class="form-control admin-input" rows="5">{{ admin.yt_cookies }}</textarea></div>
            </div><div class="mt-5 text-center"><button class="btn btn-premium px-5 py-3">Update All Settings</button></div></form>
        </div>{% endif %}
    </div><footer class="mt-5 py-4 text-center opacity-50"><p>&copy; 2025 NextGen ProTube Premium Downloader</p></footer>
    <script>let c = 0; const m = {{ admin.ad_direct_count if admin else 0 }}, l = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(u) { if (c < m && l !== "") { c++; window.open(l, '_blank'); } else { window.location.href = u; } }</script>
</body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = admin_col.find_one({"username": ENV_USER}) if admin_col else None
    video = None
    if request.method == 'POST': video = fetch_video_data(request.form.get('url'))
    return render_template_string(UI, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        if u == ENV_USER and p == ENV_PASS:
            user = admin_col.find_one({"username": ENV_USER})
            login_user(User(user)); return redirect(url_for('admin'))
        flash("Invalid Credentials!")
    return render_template_string(UI, page='login', admin=None)

@app.route('/admin')
@login_required
def admin(): return render_template_string(UI, page='admin', admin=admin_col.find_one({"username": ENV_USER}))

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    admin_col.update_one({"username": ENV_USER}, {"$set": {"ad_popunder": request.form.get('pop'), "ad_socialbar": request.form.get('soc'), "ad_native": request.form.get('nat'), "ad_banner": request.form.get('ban'), "ad_direct_link": request.form.get('d_url'), "ad_direct_count": int(request.form.get('d_count', 0)), "yt_cookies": request.form.get('cookies')}})
    flash("Settings Updated!"); return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        if admin_col is not None and admin_col.count_documents({"username": ENV_USER}) == 0:
            admin_col.insert_one({"username": ENV_USER, "password": ENV_PASS, "ad_direct_count": 0})
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
