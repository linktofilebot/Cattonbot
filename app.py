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

# --- App & Database Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-key-2025')

MONGO_URI = os.environ.get('MONGO_URI')
if MONGO_URI:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['yt_downloader_db']
    admin_col = db['admin_settings']
else:
    print("CRITICAL: MONGO_URI is not set!")

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
    user_data = admin_col.find_one({"_id": ObjectId(user_id)})
    return User(user_data) if user_data else None

def fetch_video_data(url):
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

# --- Premium UI Template ---
PREMIUM_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Downloader - Premium Edition</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    
    {% if admin %}
        {{ admin.ad_popunder | safe }}
        {{ admin.ad_socialbar | safe }}
    {% endif %}

    <style>
        :root { --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%); --glass: rgba(255, 255, 255, 0.9); }
        body { font-family: 'Poppins', sans-serif; background: #0f0c29; background: linear-gradient(to right, #24243e, #302b63, #0f0c29); color: #fff; min-height: 100vh; }
        .navbar { background: rgba(0, 0, 0, 0.5); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.1); }
        .glass-card { background: var(--glass); color: #333; border-radius: 20px; border: none; backdrop-filter: blur(10px); box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37); }
        .hero-title { font-weight: 700; background: -webkit-linear-gradient(#fff, #999); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.5rem; }
        .search-box { background: white; border-radius: 50px; padding: 10px; box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        .search-input { border: none; padding: 15px 25px; border-radius: 50px; font-size: 1.1rem; width: 100%; outline: none; }
        .btn-premium { background: var(--primary-gradient); border: none; color: white; border-radius: 50px; padding: 12px 35px; font-weight: 600; transition: 0.3s; }
        .btn-premium:hover { transform: translateY(-3px); box-shadow: 0 10px 20px rgba(0,0,0,0.3); }
        .format-list { max-height: 400px; overflow-y: auto; }
        .format-card { background: #f8f9fa; border-radius: 15px; margin-bottom: 12px; transition: 0.3s; border: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; padding: 15px; text-decoration: none; color: #333; }
        .format-card:hover { background: #fff; border-color: #667eea; transform: scale(1.02); color: #667eea; }
        .admin-sidebar { background: #fff; border-radius: 20px; color: #333; }
        .badge-premium { background: var(--primary-gradient); border-radius: 5px; }
        footer { margin-top: 50px; padding: 20px; border-top: 1px solid rgba(255,255,255,0.1); text-align: center; font-size: 0.9rem; opacity: 0.7; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/"><i class="fab fa-youtube text-danger me-2"></i>PROTUBE <span class="badge bg-danger">PREMIUM</span></a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}
                    <a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-4"><i class="fa fa-tachometer-alt me-1"></i> Dashboard</a>
                {% else %}
                    <a href="/login" class="text-white-50 text-decoration-none small"><i class="fa fa-user-shield me-1"></i> Staff Only</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-5">
        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>

        {% with msgs = get_flashed_messages() %}
            {% for m in msgs %}<div class="alert alert-warning rounded-pill text-center shadow">{{m}}</div>{% endfor %}
        {% endwith %}

        {% if page == 'home' %}
        <div class="text-center py-5">
            <h1 class="hero-title mb-3">Download Your Favorite Videos</h1>
            <p class="text-white-50 mb-5">Fast, Secure, and Unlimited YouTube Downloader</p>
            <div class="col-lg-8 mx-auto search-box">
                <form method="POST" class="d-flex">
                    <input type="text" name="url" class="search-input" placeholder="Paste YouTube link here..." required>
                    <button class="btn btn-premium shadow">ANALYZE</button>
                </form>
            </div>
        </div>

        {% if video %}
        <div class="card glass-card mt-5 col-lg-10 mx-auto p-2">
            <div class="row g-0">
                <div class="col-md-5">
                    <img src="{{ video.thumb }}" class="img-fluid rounded-4 h-100 shadow" style="object-fit: cover; min-height: 250px;">
                </div>
                <div class="col-md-7 p-4">
                    <h4 class="fw-bold mb-2">{{ video.title }}</h4>
                    <div class="mb-3">
                        <span class="badge bg-dark me-2"><i class="fa fa-clock me-1 text-info"></i>{{ video.duration }}</span>
                        <span class="badge bg-dark"><i class="fa fa-eye me-1 text-warning"></i>{{ video.views }} Views</span>
                    </div>
                    <div class="mb-4">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
                    <div class="format-list pe-2">
                        {% for f in video.formats[:8] %}
                        <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-card shadow-sm">
                            <div class="d-flex align-items-center">
                                <div class="icon-box me-3 text-primary"><i class="fa fa-video fa-lg"></i></div>
                                <div><b class="d-block">{{ f.res }}</b><small class="text-muted">{{ f.ext | upper }}</small></div>
                            </div>
                            <span class="badge badge-premium p-2 px-3">{{ f.size }} MB <i class="fa fa-download ms-1"></i></span>
                        </a>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}

        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5">
            <div class="card glass-card p-5 text-center shadow-lg">
                <i class="fa fa-lock fa-3x mb-4 text-primary"></i>
                <h3 class="fw-bold mb-4">Staff Login</h3>
                <form method="POST">
                    <div class="mb-3"><input type="text" name="u" class="form-control rounded-pill p-3" placeholder="Username" required></div>
                    <div class="mb-4"><input type="password" name="p" class="form-control rounded-pill p-3" placeholder="Password" required></div>
                    <button class="btn btn-premium w-100 shadow py-3">LOGIN TO DASHBOARD</button>
                </form>
            </div>
        </div>

        {% elif page == 'admin' %}
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="admin-sidebar p-4 shadow mb-4">
                    <div class="text-center">
                        <img src="https://ui-avatars.com/api/?name=Admin&background=random" class="rounded-circle mb-3" width="80">
                        <h5 class="fw-bold mb-0">System Admin</h5>
                        <p class="small text-muted">Status: <span class="text-success">Online</span></p>
                    </div>
                    <hr>
                    <div class="list-group list-group-flush">
                        <div class="list-group-item border-0 small"><i class="fa fa-database me-2"></i> Database: MongoDB Connected</div>
                        <div class="list-group-item border-0 small"><i class="fa fa-server me-2"></i> Server: Render Cloud</div>
                    </div>
                    <a href="/logout" class="btn btn-danger btn-sm w-100 mt-4 rounded-pill">Logout Session</a>
                </div>
            </div>
            <div class="col-md-8">
                <div class="card glass-card p-4 shadow-lg border-0">
                    <h4 class="fw-bold text-dark mb-4"><i class="fa fa-cog me-2"></i>System & Ads Control</h4>
                    <form method="POST" action="/save_settings">
                        <div class="row g-3">
                            <div class="col-md-6"><label class="fw-bold small mb-1">Popunder Code</label><textarea name="popunder" class="form-control small" rows="3">{{ admin.ad_popunder }}</textarea></div>
                            <div class="col-md-6"><label class="fw-bold small mb-1">Social Bar Code</label><textarea name="socialbar" class="form-control small" rows="3">{{ admin.ad_socialbar }}</textarea></div>
                            <div class="col-md-6"><label class="fw-bold small mb-1">Native Ad Slot</label><textarea name="native" class="form-control small" rows="3">{{ admin.ad_native }}</textarea></div>
                            <div class="col-md-6"><label class="fw-bold small mb-1">Banner Ad Slot</label><textarea name="banner" class="form-control small" rows="3">{{ admin.ad_banner }}</textarea></div>
                            <div class="col-md-8"><label class="fw-bold small mb-1">Direct Link (URL)</label><input type="text" name="direct_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
                            <div class="col-md-4"><label class="fw-bold small mb-1">Show Ads (Count)</label><input type="number" name="direct_count" class="form-control" value="{{ admin.ad_direct_count }}"></div>
                        </div>
                        <hr>
                        <label class="fw-bold small mb-1">Authentication Cookies (Netscape)</label>
                        <textarea name="cookies" class="form-control small mb-3" rows="3">{{ admin.yt_cookies }}</textarea>
                        <button class="btn btn-premium px-5 w-100 shadow">APPLY ALL SETTINGS</button>
                    </form>
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <footer>
        <p>&copy; 2025 ProTube Downloader Premium. Built with Love and Python.</p>
    </footer>

    <script>
        let clickCount = 0;
        const maxAds = {{ admin.ad_direct_count if admin else 0 }};
        const directLink = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(url) {
            if (clickCount < maxAds && directLink !== "") {
                clickCount++;
                window.open(directLink, '_blank');
            } else {
                window.location.href = url;
            }
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
        if not video: flash("Error: Could not retrieve video info.")
    return render_template_string(PREMIUM_HTML, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_data = admin_col.find_one({"username": request.form['u']})
        if user_data and user_data['password'] == request.form['p']:
            login_user(User(user_data))
            return redirect(url_for('admin'))
        flash("Unauthorized: Access Denied.")
    return render_template_string(PREMIUM_HTML, page='login', admin=None)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(PREMIUM_HTML, page='admin', admin=admin_data)

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
    flash("Success: All changes deployed.")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    if admin_col.count_documents({"username": "admin"}) == 0:
        admin_col.insert_one({"username": "admin", "password": "admin123", "ad_direct_count": 0})
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
