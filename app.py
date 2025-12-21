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

# --- অ্যাপ এবং ডাটাবেস সেটআপ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'yt-pro-permanent-2025'

# আপনার MongoDB Link এখানে দিন (অথবা Render Environment Variable এ MONGO_URI নামে দিন)
MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://freelancermaruf1735:6XaThbuVG2zOUWm4@cluster0.ywwppvf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['yt_downloader_db']
admin_col = db['admin_settings']

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- ইউজার মডেল (MongoDB এর জন্য) ---
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.password = user_data['password']
        self.yt_cookies = user_data.get('yt_cookies', '')
        self.ad_popunder = user_data.get('ad_popunder', '')
        self.ad_socialbar = user_data.get('ad_socialbar', '')
        self.ad_native = user_data.get('ad_native', '')
        self.ad_banner = user_data.get('ad_banner', '')
        self.ad_direct_link = user_data.get('ad_direct_link', '')
        self.ad_direct_count = user_data.get('ad_direct_count', 0)

@login_manager.user_loader
def load_user(user_id):
    user_data = admin_col.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None

# --- ভিডিও ডাউনলোডার লজিক ---
def fetch_video_data(url):
    admin = admin_col.find_one({"username": "admin"})
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    if admin and admin.get('yt_cookies'):
        with open('temp_cookies.txt', 'w') as f:
            f.write(admin['yt_cookies'])
        ydl_opts['cookiefile'] = 'temp_cookies.txt'

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
            return {
                'title': info.get('title'),
                'thumb': info.get('thumbnail'),
                'duration': time.strftime('%H:%M:%S', time.gmtime(info.get('duration') or 0)),
                'views': info.get('view_count', 0),
                'formats': formats[::-1]
            }
        except: return None

# --- ডিজাইন এবং ইউজার ইন্টারফেস ---
MAIN_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium YT Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder | safe }}{{ admin.ad_socialbar | safe }}{% endif %}
    <style>
        :root { --primary: #FF0000; }
        body { background: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
        .navbar { background: white; border-bottom: 2px solid var(--primary); }
        .hero-section { background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.05); padding: 50px 20px; margin-top: 30px; }
        .btn-download { background: var(--primary); color: white; border-radius: 50px; padding: 12px 30px; font-weight: bold; border: none; }
        .format-item { background: #f1f3f5; border-radius: 12px; margin-bottom: 10px; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; transition: 0.3s; }
        .format-item:hover { transform: scale(1.02); background: #e9ecef; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg sticky-top shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold text-dark" href="/">🚀 YT DOWNLOADER</a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-outline-dark rounded-pill px-3">Dashboard</a>{% endif %}
            </div>
        </div>
    </nav>
    <div class="container">
        <div class="text-center mt-3">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>
        {% if page == 'home' %}
        <div class="hero-section text-center">
            <h2 class="fw-bold mb-4">ইউটিউব ভিডিও ডাউনলোড করুন</h2>
            <form method="POST" class="col-lg-8 mx-auto">
                <div class="input-group mb-3">
                    <input type="text" name="url" class="form-control rounded-pill-start p-3" placeholder="লিংক এখানে পেস্ট করুন..." required>
                    <button class="btn btn-download rounded-pill-end">Analyze</button>
                </div>
            </form>
        </div>
        {% if video %}
        <div class="card mt-5 col-lg-10 mx-auto shadow-lg border-0 rounded-4 overflow-hidden">
            <div class="row g-0">
                <div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid h-100" style="object-fit: cover;"></div>
                <div class="col-md-7 p-4">
                    <h4 class="fw-bold">{{ video.title }}</h4>
                    <div class="my-3">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
                    <div class="formats-list">
                        {% for f in video.formats[:7] %}
                        <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-item shadow-sm">
                            <div><i class="fa-video text-danger me-2"></i><strong>{{ f.res }}</strong></div>
                            <span class="badge bg-success rounded-pill">{{ f.size }} MB <i class="fa-download ms-1"></i></span>
                        </a>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5 hero-section text-center">
            <h3 class="fw-bold mb-4">Admin Login</h3>
            <form method="POST">
                <input type="text" name="u" class="form-control mb-3" placeholder="Username" required>
                <input type="password" name="p" class="form-control mb-3" placeholder="Password" required>
                <button class="btn btn-download w-100">Login</button>
            </form>
        </div>
        {% elif page == 'admin' %}
        <div class="hero-section p-4 mt-4 shadow border-0">
            <h4 class="fw-bold mb-4 text-danger"><i class="fa-tools me-2"></i>Admin & Ad Management</h4>
            <form method="POST" action="/save_settings">
                <div class="row">
                    <div class="col-md-6 mb-3"><label class="fw-bold">Popunder Ad:</label><textarea name="popunder" class="form-control" rows="3">{{ admin.ad_popunder }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold">Social Bar Ad:</label><textarea name="socialbar" class="form-control" rows="3">{{ admin.ad_socialbar }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold">Native Ad:</label><textarea name="native" class="form-control" rows="3">{{ admin.ad_native }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold">Banner Ad:</label><textarea name="banner" class="form-control" rows="3">{{ admin.ad_banner }}</textarea></div>
                    <div class="col-md-8 mb-3"><label class="fw-bold">Direct Link URL:</label><input type="text" name="direct_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
                    <div class="col-md-4 mb-3"><label class="fw-bold">Direct Link Count:</label><input type="number" name="direct_count" class="form-control" value="{{ admin.ad_direct_count }}"></div>
                </div>
                <hr><h5 class="fw-bold mt-3">YouTube Cookies</h5>
                <textarea name="cookies" class="form-control mb-3" rows="4">{{ admin.yt_cookies }}</textarea>
                <button class="btn btn-download px-5 shadow">Save All Settings</button>
            </form>
        </div>
        {% endif %}
    </div>
    <script>
        let clickCount = 0;
        const maxAds = {{ admin.ad_direct_count if admin else 0 }};
        const directLink = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(url) {
            if (clickCount < maxAds && directLink !== "") { clickCount++; window.open(directLink, '_blank'); }
            else { window.location.href = url; }
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = admin_col.find_one({"username": "admin"})
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
        if not video: flash("Error fetching video data!")
    return render_template_string(MAIN_HTML, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_data = admin_col.find_one({"username": request.form['u']})
        if user_data and user_data['password'] == request.form['p']:
            user_obj = User(user_data)
            login_user(user_obj)
            return redirect(url_for('admin'))
        flash("Invalid login!")
    return render_template_string(MAIN_HTML, page='login', admin=None)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(MAIN_HTML, page='admin', admin=admin_data)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    admin_col.update_one({"username": "admin"}, {"$set": {
        "ad_popunder": request.form.get('popunder'),
        "ad_socialbar": request.form.get('socialbar'),
        "ad_native": request.form.get('native'),
        "ad_banner": request.form.get('banner'),
        "ad_direct_link": request.form.get('direct_url'),
        "ad_direct_count": int(request.form.get('direct_count', 0)),
        "yt_cookies": request.form.get('cookies')
    }})
    flash("Settings Saved!")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    # প্রথমবার রান হলে ডিফল্ট অ্যাডমিন তৈরি করা
    if admin_col.count_documents({"username": "admin"}) == 0:
        admin_col.insert_one({"username": "admin", "password": "admin123", "ad_direct_count": 0})
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
