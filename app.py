import os
import requests
import threading
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pymongo import MongoClient
from bson.objectid import ObjectId
import yt_dlp
import certifi

# --- App Setup ---
app = Flask(__name__)
# Render এ SECRET_KEY না থাকলে এটি ব্যবহার হবে
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-key-2026-v2')

# --- MongoDB Connection ---
MONGO_URI = os.environ.get('MONGO_URI')
admin_col = None
db_status = False

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        # ডাটাবেস এবং কালেকশন নাম আগের কোডগুলোর সাথে মিল রেখে ফিক্স করা হলো
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        client.admin.command('ping')
        db_status = True
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"MongoDB Error: {e}")
else:
    print("CRITICAL: MONGO_URI missing!")

# --- Login Manager ---
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

# --- YouTube Logic (Bot Error Fix) ---
def fetch_video_data(url):
    if admin_col is None: return {"error": "Database not connected"}
    admin = admin_col.find_one({"username": "admin"})
    
    # কুকিজ ফাইল তৈরি (বট সমস্যা সমাধান করতে)
    cookie_file = 'cookies.txt'
    if admin and admin.get('yt_cookies'):
        with open(cookie_file, 'w') as f:
            f.write(admin['yt_cookies'])
    else:
        cookie_file = None

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    }
    
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    formats.append({
                        'ext': f.get('ext'),
                        'res': f.get('resolution') or f.get('format_note'),
                        'url': f.get('url'),
                        'size': round(f.get('filesize', 0) / (1024*1024), 2) if f.get('filesize') else "N/A"
                    })
            return {'title': info.get('title'), 'thumb': info.get('thumbnail'), 'formats': formats[::-1]}
        except Exception as e:
            return {"error": str(e)}

# --- Premium UI (Full Fix) ---
HTML_UI = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium YT Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder | safe }}{{ admin.ad_socialbar | safe }}{% endif %}
    <style>
        body { background: #0f0c29; color: white; font-family: sans-serif; min-height: 100vh; }
        .glass { background: rgba(255, 255, 255, 0.95); color: #222; border-radius: 20px; padding: 30px; }
        .btn-premium { background: linear-gradient(45deg, #f093fb, #f5576c); border: none; color: white; border-radius: 50px; padding: 10px 30px; font-weight: bold; }
        .format-card { background: #f1f3f5; border-radius: 12px; margin-bottom: 10px; padding: 15px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; }
        .navbar { background: rgba(0,0,0,0.5); backdrop-filter: blur(10px); }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/"><i class="fab fa-youtube text-danger me-2"></i>PROTUBE PREMIUM</a>
            <div>
                {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-light rounded-pill px-3">Admin</a>{% else %}
                <a href="/login" class="btn btn-sm btn-outline-light rounded-pill">Login</a>{% endif %}
            </div>
        </div>
    </nav>
    <div class="container mt-5 text-center">
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-warning">{{m}}</div>{% endfor %}{% endwith %}

        {% if page == 'home' %}
        <div class="py-5">
            <h1 class="fw-bold mb-4">YouTube Downloader Pro</h1>
            <div class="col-lg-8 mx-auto">
                <form method="POST" class="input-group rounded-pill overflow-hidden shadow-lg bg-white">
                    <input type="text" name="url" class="form-control border-0 p-3" placeholder="Paste link here..." required style="color:#222">
                    <button class="btn btn-premium px-5">DOWNLOAD</button>
                </form>
            </div>
        </div>
        {% if video %}
            {% if video.error %}
                <div class="alert alert-danger mt-4"><b>YouTube Error:</b> Sign-in/Bot detected. <br> Solution: Admin Panel এ গিয়ে YouTube Cookies দিন।</div>
            {% else %}
                <div class="glass mt-5 col-lg-10 mx-auto text-start">
                    <div class="row g-4">
                        <div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow w-100"></div>
                        <div class="col-md-7 ps-md-4">
                            <h4 class="fw-bold mb-3">{{ video.title }}</h4>
                            <div class="mb-4">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
                            <div class="formats" style="max-height:300px; overflow-y:auto;">
                                {% for f in video.formats[:8] %}
                                <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-card">
                                    <b>{{ f.res }} ({{ f.ext | upper }})</b>
                                    <span class="badge bg-success rounded-pill">{{ f.size }} MB</span>
                                </a>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            {% endif %}
        {% endif %}

        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5 glass text-center">
            <h3 class="fw-bold mb-4">Admin Login</h3>
            <form method="POST" action="/login">
                <input type="text" name="u" class="form-control mb-3" placeholder="Username" required>
                <input type="password" name="p" class="form-control mb-4" placeholder="Password" required>
                <button class="btn btn-premium w-100">LOGIN</button>
            </form>
        </div>

        {% elif page == 'admin' %}
        <div class="glass mt-4 text-start">
            <div class="d-flex justify-content-between mb-4"><h4>Admin Settings</h4><a href="/logout" class="text-danger">Logout</a></div>
            <form method="POST" action="/save_settings">
                <div class="row">
                    <div class="col-md-6 mb-3"><label class="small fw-bold">Popunder</label><textarea name="pop" class="form-control small">{{ admin.ad_popunder }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="small fw-bold">Social Bar</label><textarea name="soc" class="form-control small">{{ admin.ad_socialbar }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="small fw-bold">Native</label><textarea name="nat" class="form-control small">{{ admin.ad_native }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="small fw-bold">Banner</label><textarea name="ban" class="form-control small">{{ admin.ad_banner }}</textarea></div>
                    <div class="col-md-8 mb-3"><label class="small fw-bold">Direct Link URL</label><input type="text" name="d_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
                    <div class="col-md-4 mb-3"><label class="small fw-bold">Click Count</label><input type="number" name="d_count" class="form-control" value="{{ admin.ad_direct_count }}"></div>
                </div>
                <hr>
                <label class="fw-bold text-danger">YouTube Cookies (NETSCAPE FORMAT)</label>
                <textarea name="cookies" class="form-control mb-4" rows="4">{{ admin.yt_cookies }}</textarea>
                <button class="btn btn-premium w-100">SAVE ALL</button>
            </form>
        </div>
        {% endif %}
    </div>
    <script>
        let clicks = 0;
        const max = {{ admin.ad_direct_count if admin else 0 }};
        const adLink = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(url) {
            if (clicks < max && adLink !== "") { clicks++; window.open(adLink, '_blank'); }
            else { window.location.href = url; }
        }
    </script>
</body>
</html>
"""

# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = admin_col.find_one({"username": "admin"}) if admin_col else None
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
    return render_template_string(HTML_UI, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        user_data = admin_col.find_one({"username": u})
        if user_data and user_data['password'] == p:
            login_user(User(user_data))
            return redirect(url_for('admin'))
        flash("Invalid Credentials! admin / admin123")
    return render_template_string(HTML_UI, page='login', admin=None)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(HTML_UI, page='admin', admin=admin_data)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    admin_col.update_one({"username": "admin"}, {"$set": {
        "ad_popunder": request.form.get('pop'),
        "ad_socialbar": request.form.get('soc'),
        "ad_native": request.form.get('nat'),
        "ad_banner": request.form.get('ban'),
        "ad_direct_link": request.form.get('d_url'),
        "ad_direct_count": int(request.form.get('d_count', 0)),
        "yt_cookies": request.form.get('cookies')
    }})
    flash("Settings Saved!"); return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    # ফিক্সড অ্যাডমিন ইউজার তৈরি
    if admin_col is not None:
        if admin_col.count_documents({"username": "admin"}) == 0:
            admin_col.insert_one({"username": "admin", "password": "admin123"})
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
