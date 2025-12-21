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

# --- অ্যাপ সেটআপ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-key-2025')

# --- ডাটাবেস কানেকশন হ্যান্ডলিং ---
MONGO_URI = os.environ.get('MONGO_URI')

# গ্লোবাল ভেরিয়েবল ডিফাইন করা যাতে NameError না আসে
db = None
admin_col = None

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        # কানেকশন চেক করার জন্য একটি টেস্ট
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"MongoDB Connection Error: {e}")
        admin_col = None
else:
    print("CRITICAL ERROR: MONGO_URI environment variable is missing!")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

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
    if admin_col is None: return None
    user_data = admin_col.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None

def fetch_video_data(url):
    if admin_col is None: return None
    admin = admin_col.find_one({"username": "admin"})
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
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
                'duration': time.strftime('%M:%S', time.gmtime(info.get('duration') or 0)),
                'views': "{:,}".format(info.get('view_count', 0)),
                'formats': formats[::-1]
            }
        except: return None

# --- ডিজাইন টেমপ্লেট ---
PREMIUM_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Downloader - Premium</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder | safe }}{{ admin.ad_socialbar | safe }}{% endif %}
    <style>
        body { background: #0f0c29; background: linear-gradient(to right, #24243e, #302b63, #0f0c29); color: #fff; min-height: 100vh; font-family: sans-serif; }
        .glass-card { background: rgba(255, 255, 255, 0.9); color: #333; border-radius: 20px; border: none; padding: 20px; }
        .btn-premium { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; color: white; border-radius: 50px; padding: 10px 30px; }
        .format-card { background: #f8f9fa; border-radius: 12px; margin-bottom: 10px; padding: 15px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; border: 1px solid #eee; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">🚀 PROTUBE PREMIUM</a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-3">Dashboard</a>{% endif %}
            </div>
        </div>
    </nav>
    <div class="container mt-5">
        {% if not db_connected %}
            <div class="alert alert-danger text-center">
                <h4>Database Connection Error!</h4>
                <p>Please check if you have added <b>MONGO_URI</b> in Render Environment Variables.</p>
            </div>
        {% endif %}
        
        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-warning text-center">{{m}}</div>{% endfor %}{% endwith %}

        {% if page == 'home' %}
        <div class="text-center py-4">
            <h1 class="fw-bold mb-3">YouTube Video Downloader</h1>
            <div class="col-lg-8 mx-auto mt-4">
                <form method="POST" class="input-group">
                    <input type="text" name="url" class="form-control p-3 rounded-start-pill" placeholder="Paste link here..." required>
                    <button class="btn btn-premium rounded-end-pill px-4">ANALYZE</button>
                </form>
            </div>
        </div>
        {% if video %}
        <div class="glass-card mt-5 col-lg-10 mx-auto shadow-lg">
            <div class="row g-0">
                <div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-3 shadow w-100"></div>
                <div class="col-md-7 ps-md-4 mt-3 mt-md-0">
                    <h4 class="fw-bold">{{ video.title }}</h4>
                    <div class="mb-3">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
                    {% for f in video.formats[:7] %}
                    <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-card">
                        <b>{{ f.res }} ({{ f.ext | upper }})</b>
                        <span class="badge bg-primary rounded-pill">{{ f.size }} MB</span>
                    </a>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}
        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5 glass-card text-center">
            <h3 class="fw-bold mb-4">Admin Login</h3>
            <form method="POST">
                <input type="text" name="u" class="form-control mb-3" placeholder="Username" required>
                <input type="password" name="p" class="form-control mb-3" placeholder="Password" required>
                <button class="btn btn-premium w-100">LOGIN</button>
            </form>
        </div>
        {% elif page == 'admin' %}
        <div class="glass-card mt-4 shadow border-0">
            <h4 class="fw-bold text-danger mb-4">Admin Settings</h4>
            <form method="POST" action="/save_settings">
                <div class="row">
                    <div class="col-md-6 mb-3"><label class="fw-bold">Popunder Ad:</label><textarea name="popunder" class="form-control" rows="3">{{ admin.ad_popunder }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold">Social Bar Ad:</label><textarea name="socialbar" class="form-control" rows="3">{{ admin.ad_socialbar }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold">Native Ad:</label><textarea name="native" class="form-control" rows="3">{{ admin.ad_native }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold">Banner Ad:</label><textarea name="banner" class="form-control" rows="3">{{ admin.ad_banner }}</textarea></div>
                    <div class="col-md-8 mb-3"><label class="fw-bold">Direct Link URL:</label><input type="text" name="direct_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
                    <div class="col-md-4 mb-3"><label class="fw-bold">Direct Link Count:</label><input type="number" name="direct_count" class="form-control" value="{{ admin.ad_direct_count }}"></div>
                </div>
                <hr>
                <label class="fw-bold">YouTube Cookies (Netscape Format)</label>
                <textarea name="cookies" class="form-control mb-3" rows="3">{{ admin.yt_cookies }}</textarea>
                <button class="btn btn-premium w-100 py-3 shadow">SAVE ALL SETTINGS</button>
            </form>
            <a href="/logout" class="btn btn-link text-danger mt-3">Logout</a>
        </div>
        {% endif %}
    </div>
    <script>
        let clickCount = 0;
        const maxAds = {{ admin.ad_direct_count if admin else 0 }};
        const directLink = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(url) {
            if (clickCount < maxAds && directLink !== "") {
                clickCount++; window.open(directLink, '_blank');
            } else { window.location.href = url; }
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if admin_col is None:
        return render_template_string(PREMIUM_HTML, page='home', db_connected=False, admin=None)
    
    admin = admin_col.find_one({"username": "admin"})
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
        if not video: flash("Video not found or link error!")
    return render_template_string(PREMIUM_HTML, page='home', video=video, admin=admin, db_connected=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if admin_col is None: return "Database not connected!"
    if request.method == 'POST':
        user_data = admin_col.find_one({"username": request.form['u']})
        if user_data and user_data['password'] == request.form['p']:
            login_user(User(user_data))
            return redirect(url_for('admin'))
        flash("Invalid login!")
    return render_template_string(PREMIUM_HTML, page='login', admin=None, db_connected=True)

@app.route('/admin')
@login_required
def admin():
    if admin_col is None: return "Database error!"
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(PREMIUM_HTML, page='admin', admin=admin_data, db_connected=True)

@app.route('/save_settings', methods=['POST'])
@login_required
def save_settings():
    if admin_col is None: return "Error!"
    admin_col.update_one({"username": "admin"}, {"$set": {
        "ad_popunder": request.form.get('popunder'),
        "ad_socialbar": request.form.get('socialbar'),
        "ad_native": request.form.get('native'),
        "ad_banner": request.form.get('banner'),
        "ad_direct_link": request.form.get('direct_url'),
        "ad_direct_count": int(request.form.get('direct_count', 0)),
        "yt_cookies": request.form.get('cookies')
    }})
    flash("Settings updated!")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    if admin_col is not None:
        if admin_col.count_documents({"username": "admin"}) == 0:
            admin_col.insert_one({"username": "admin", "password": "admin123", "ad_direct_count": 0})
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
