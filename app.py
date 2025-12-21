import os, requests, threading, time, yt_dlp, certifi
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId

# --- APP CONFIG ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-key-2025-final')
MONGO_URI = os.environ.get('MONGO_URI')

# Admin Settings
ADM_U = os.environ.get('ADMIN_USER', 'admin')
ADM_P = os.environ.get('ADMIN_PASS', 'admin123')

admin_col = None
db_status = False

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        client.admin.command('ping')
        db_status = True
    except Exception as e: print(f"DB Error: {e}")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, data):
        self.id = str(data['_id'])
        self.username = data.get('username', ADM_U)
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
    u_data = admin_col.find_one({"_id": ObjectId(user_id)})
    return User(u_data) if u_data else None

def get_video(url):
    if admin_col is None: return {"error": "Database Disconnected"}
    adm = admin_col.find_one({"username": ADM_U})
    c_file = 'cookies.txt'
    if adm and adm.get('yt_cookies'):
        with open(c_file, 'w') as f: f.write(adm['yt_cookies'])
    else: c_file = None
    opts = {
        'format': 'best', 'quiet': True, 'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    }
    if c_file: opts['cookiefile'] = c_file
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = [{'ext': f.get('ext'), 'res': f.get('resolution') or f.get('format_note'), 'url': f.get('url'), 'size': round(f.get('filesize', 0)/(1024*1024),2) if f.get('filesize') else "N/A"} for f in info.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') != 'none']
            return {'title': info.get('title'), 'thumb': info.get('thumbnail'), 'formats': formats[::-1]}
        except Exception as e: return {"error": str(e)}

# --- PREMIUM UI ---
UI = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Premium</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder|safe if admin.ad_popunder }}{{ admin.ad_socialbar|safe if admin.ad_socialbar }}{% endif %}
    <style>
        body { background: #0b0e14; color: #fff; font-family: sans-serif; min-height: 100vh; }
        .glass { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(15px); border-radius: 20px; padding: 25px; border: 1px solid rgba(255, 255, 255, 0.1); }
        .btn-p { background: linear-gradient(90deg, #ff0050, #ff0081); border: none; color: #fff; border-radius: 50px; padding: 12px 30px; font-weight: 600; }
        .f-item { background: rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 10px; padding: 15px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #fff; border: 1px solid rgba(255,255,255,0.1); }
        .f-item:hover { border-color: #ff0050; transform: translateX(5px); transition: 0.3s; }
        .navbar { background: rgba(0,0,0,0.5); backdrop-filter: blur(10px); }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top shadow"><div class="container"><a class="navbar-brand fw-bold" href="/">🚀 PRO<span style="color:#ff0050">TUBE</span></a>
    {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-3">Dashboard</a>{% else %}<a href="/login" class="text-white-50 small text-decoration-none">Staff</a>{% endif %}</div></nav>
    <div class="container mt-5">
        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner|safe if admin.ad_banner }}{% endif %}</div>
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-info text-center rounded-pill">{{m}}</div>{% endfor %}{% endwith %}
        {% if page == 'home' %}
        <div class="text-center py-5"><h1 class="fw-bold display-4">High-Speed Downloader</h1><div class="col-lg-8 mx-auto mt-4 glass">
            <form method="POST" class="d-flex gap-2"><input type="text" name="url" class="form-control bg-transparent text-white rounded-pill border-secondary p-3 shadow-none" placeholder="Paste Video Link..." required><button class="btn btn-p px-4">Analyze</button></form></div></div>
        {% if video %}{% if video.error %}<div class="alert alert-danger glass border-0 mt-4 text-center"><b>Bot Error!</b> অ্যাডমিন প্যানেলে কুকিজ আপডেট করুন।</div>
        {% else %}<div class="glass mt-5 col-lg-11 mx-auto shadow-lg"><div class="row g-4"><div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow w-100"></div>
        <div class="col-md-7"><h3>{{ video.title }}</h3><div class="mb-3">{% if admin %}{{ admin.ad_native|safe if admin.ad_native }}{% endif %}</div>
        <div style="max-height:350px; overflow-y:auto; padding-right:10px;">{% for f in video.formats[:10] %}
        <a href="javascript:void(0)" onclick="hDl('{{ f.url }}')" class="f-item"><span><i class="fa fa-play text-danger me-2"></i><b>{{ f.res }}</b> ({{f.ext|upper}})</span><span class="badge bg-danger rounded-pill">{{ f.size }} MB</span></a>{% endfor %}</div></div></div></div>{% endif %}{% endif %}
        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5 glass text-center"><h2>Login</h2><form method="POST" action="/login">
            <input type="text" name="u" class="form-control bg-dark text-white mb-3" placeholder="User" required><input type="password" name="p" class="form-control bg-dark text-white mb-4" placeholder="Pass" required><button class="btn btn-p w-100 shadow">Login</button></form></div>
        {% elif page == 'admin' %}
        <div class="glass mt-4"><h3>Admin Control</h3><form method="POST" action="/save_settings"><div class="row g-3">
            <div class="col-md-6"><label class="small fw-bold">Popunder Code</label><textarea name="pop" class="form-control bg-dark text-white">{{ admin.ad_popunder }}</textarea></div>
            <div class="col-md-6"><label class="small fw-bold">SocialBar Code</label><textarea name="soc" class="form-control bg-dark text-white">{{ admin.ad_socialbar }}</textarea></div>
            <div class="col-md-6"><label class="small fw-bold">Native Ad Code</label><textarea name="nat" class="form-control bg-dark text-white">{{ admin.ad_native }}</textarea></div>
            <div class="col-md-6"><label class="small fw-bold">Banner Ad Code</label><textarea name="ban" class="form-control bg-dark text-white">{{ admin.ad_banner }}</textarea></div>
            <div class="col-md-8"><label class="small fw-bold">Direct Link URL</label><input type="text" name="d_url" class="form-control bg-dark text-white" value="{{ admin.ad_direct_link }}"></div>
            <div class="col-md-4"><label class="small fw-bold">Clicks Count</label><input type="number" name="d_count" class="form-control bg-dark text-white" value="{{ admin.ad_direct_count }}"></div>
            <div class="col-12"><label class="small text-danger fw-bold">YouTube Netscape Cookies</label><textarea name="cookies" class="form-control bg-dark text-white" rows="5">{{ admin.yt_cookies }}</textarea></div>
            </div><button class="btn btn-p w-100 mt-4 shadow py-2">Save All Settings</button></form><div class="text-center mt-3"><a href="/logout" class="text-danger small">Logout</a></div></div>{% endif %}
    </div><script>let c=0; const m={{ admin.ad_direct_count if admin and admin.ad_direct_count else 0 }}, l="{{ admin.ad_direct_link if admin and admin.ad_direct_link else '' }}";
    function hDl(u){if(c<m && l!==""){c++; window.open(l,'_blank');}else{window.location.href=u;}}</script>
</body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = admin_col.find_one({"username": ADM_U}) if admin_col is not None else None
    video = None
    if request.method == 'POST': video = get_video(request.form.get('url'))
    return render_template_string(UI, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('u'), request.form.get('p')
        if u == ADM_U and p == ADM_P:
            user_data = admin_col.find_one({"username": ADM_U})
            login_user(User(user_data)); return redirect(url_for('admin'))
        flash("Invalid Credentials!")
    return render_template_string(UI, page='login', admin=None)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": ADM_U})
    return render_template_string(UI, page='admin', admin=admin_data)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    admin_col.update_one({"username": ADM_U}, {"$set": {"ad_popunder": request.form.get('pop'), "ad_socialbar": request.form.get('soc'), "ad_native": request.form.get('nat'), "ad_banner": request.form.get('ban'), "ad_direct_link": request.form.get('d_url'), "ad_direct_count": int(request.form.get('d_count', 0)), "yt_cookies": request.form.get('cookies')}})
    flash("Settings Saved!"); return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    if admin_col is not None and admin_col.count_documents({"username": ADM_U}) == 0:
        admin_col.insert_one({"username": ADM_U, "password": ADM_P, "ad_direct_count": 0})
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
