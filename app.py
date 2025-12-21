import os, requests, threading, time, yt_dlp, certifi
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-key-2025')
MONGO_URI = os.environ.get('MONGO_URI')

admin_col = None
db_connected = False

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        client.admin.command('ping')
        db_connected = True
    except Exception as e: print(f"DB Error: {e}")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, data):
        self.id = str(data['_id'])
        self.username = data.get('username', 'admin')
        self.password = data.get('password', 'admin123')
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
    admin = admin_col.find_one({"username": "admin"})
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

# --- PREMIUM UI ---
UI = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Premium</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder | safe }}{{ admin.ad_socialbar | safe }}{% endif %}
    <style>
        body { background: #0f0c29; background: linear-gradient(135deg, #0f0c29 0%, #302b63 100%); color: #fff; min-height: 100vh; font-family: sans-serif; }
        .glass { background: rgba(255, 255, 255, 0.95); color: #1a1a2e; border-radius: 20px; padding: 25px; box-shadow: 0 15px 35px rgba(0,0,0,0.5); }
        .btn-premium { background: linear-gradient(45deg, #f093fb, #f5576c); border: none; color: white; border-radius: 50px; padding: 10px 30px; font-weight: bold; transition: 0.3s; }
        .btn-premium:hover { transform: scale(1.05); }
        .format-item { background: #f8f9fa; border-radius: 12px; margin-bottom: 10px; padding: 12px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; border: 1px solid #ddd; }
        .navbar { background: rgba(0,0,0,0.3); backdrop-filter: blur(10px); }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top shadow">
        <div class="container"><a class="navbar-brand fw-bold" href="/">🚀 PROTUBE PREMIUM</a>
            {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-light rounded-pill px-3">Dashboard</a>{% endif %}
        </div>
    </nav>
    <div class="container mt-5">
        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-warning text-center">{{m}}</div>{% endfor %}{% endwith %}
        {% if page == 'home' %}
        <div class="text-center py-4"><h1 class="fw-bold mb-3">YouTube Downloader</h1>
            <div class="col-lg-8 mx-auto"><form method="POST" class="input-group rounded-pill overflow-hidden shadow-lg bg-white">
                <input type="text" name="url" class="form-control border-0 p-3" placeholder="লিংক এখানে পেস্ট করুন..." required style="color:#222">
                <button class="btn btn-premium px-5">DOWNLOAD</button></form></div></div>
        {% if video %}{% if video.error %}<div class="alert alert-danger mt-4"><b>Error:</b> Bot detected. Update Cookies in Admin Panel.</div>
        {% else %}<div class="glass mt-5 col-lg-10 mx-auto text-start"><div class="row g-4"><div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow w-100"></div>
        <div class="col-md-7"><h4>{{ video.title }}</h4><div class="mb-3">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
        <div class="formats" style="max-height:300px; overflow-y:auto;">{% for f in video.formats[:8] %}
        <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-item"><b>{{ f.res }} ({{ f.ext | upper }})</b><span class="badge bg-success rounded-pill">{{ f.size }} MB</span></a>{% endfor %}</div></div></div></div>{% endif %}{% endif %}
        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5 glass text-center"><h3>Admin Login</h3><form method="POST">
            <input type="text" name="u" class="form-control mb-3" placeholder="Username" required><input type="password" name="p" class="form-control mb-3" placeholder="Password" required><button class="btn btn-premium w-100">LOGIN</button></form></div>
        {% elif page == 'admin' %}
        <div class="glass mt-4 text-start"><h4>Admin Settings</h4><form method="POST" action="/save_settings"><div class="row">
            <div class="col-md-6 mb-2"><label class="small fw-bold">Popunder</label><textarea name="pop" class="form-control small">{{ admin.ad_popunder }}</textarea></div>
            <div class="col-md-6 mb-2"><label class="small fw-bold">SocialBar</label><textarea name="soc" class="form-control small">{{ admin.ad_socialbar }}</textarea></div>
            <div class="col-md-6 mb-2"><label class="small fw-bold">Native</label><textarea name="nat" class="form-control small">{{ admin.ad_native }}</textarea></div>
            <div class="col-md-6 mb-2"><label class="small fw-bold">Banner</label><textarea name="ban" class="form-control small">{{ admin.ad_banner }}</textarea></div>
            <div class="col-md-8 mb-2"><label class="small fw-bold">DirectLink</label><input type="text" name="d_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
            <div class="col-md-4 mb-2"><label class="small fw-bold">Clicks</label><input type="number" name="d_count" class="form-control" value="{{ admin.ad_direct_count }}"></div></div><hr>
            <label class="fw-bold small text-danger">YouTube Cookies (NETSCAPE FORMAT)</label><textarea name="cookies" class="form-control mb-3" rows="3">{{ admin.yt_cookies }}</textarea>
            <button class="btn btn-premium w-100 py-2">SAVE SETTINGS</button></form><div class="text-center mt-3"><a href="/logout" class="text-danger">Logout</a></div></div>{% endif %}
    </div><script>let c = 0; const m = {{ admin.ad_direct_count if admin else 0 }}, l = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(u) { if (c < m && l !== "") { c++; window.open(l, '_blank'); } else { window.location.href = u; } }</script>
</body></html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = admin_col.find_one({"username": "admin"}) if admin_col else None
    video = None
    if request.method == 'POST': video = fetch_video_data(request.form.get('url'))
    return render_template_string(UI, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = admin_col.find_one({"username": request.form['u']})
        if user and user['password'] == request.form['p']:
            login_user(User(user)); return redirect(url_for('admin'))
        flash("Invalid Credentials! admin / admin123")
    return render_template_string(UI, page='login', admin=None)

@app.route('/admin')
@login_required
def admin(): return render_template_string(UI, page='admin', admin=admin_col.find_one({"username": "admin"}))

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    admin_col.update_one({"username": "admin"}, {"$set": {"ad_popunder": request.form.get('pop'), "ad_socialbar": request.form.get('soc'), "ad_native": request.form.get('nat'), "ad_banner": request.form.get('ban'), "ad_direct_link": request.form.get('d_url'), "ad_direct_count": int(request.form.get('d_count', 0)), "yt_cookies": request.form.get('cookies')}})
    flash("Settings Saved!"); return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    if admin_col is not None and admin_col.count_documents({"username": "admin"}) == 0:
        admin_col.insert_one({"username": "admin", "password": "admin123", "ad_direct_count": 0})
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
