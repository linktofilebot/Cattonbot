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

# --- অ্যাপ এবং ডাটাবেস কনফিগারেশন ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-yt-2025-v3')

# MongoDB কানেকশন
MONGO_URI = os.environ.get('MONGO_URI')
admin_col = None
db_status = False

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        client.admin.command('ping')
        db_status = True
        print("Connected to MongoDB Atlas!")
    except Exception as e:
        print(f"MongoDB Error: {e}")
else:
    print("CRITICAL: MONGO_URI is missing in Render Environment Variables!")

# --- লগইন ম্যানেজার ---
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

# --- ইউটিউব ডাউনলোডার লজিক (কুকিজ সাপোর্টসহ) ---
def fetch_video_data(url):
    if admin_col is None: return {"error": "Database not connected"}
    admin = admin_col.find_one({"username": "admin"})
    
    # কুকিজ ফাইল প্রসেসিং (বট সমস্যা সমাধান করতে)
    cookie_path = 'render_cookies.txt'
    if admin and admin.get('yt_cookies'):
        with open(cookie_path, 'w') as f:
            f.write(admin['yt_cookies'])
    else:
        cookie_path = None

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    }
    
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

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
        except Exception as e:
            return {"error": str(e)}

# --- প্রিমিয়াম ইউজার ইন্টারফেস (HTML + CSS + JS) ---
PREMIUM_UI = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Premium - 2025 Edition</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    
    {% if admin %}
        {{ admin.ad_popunder | safe }}
        {{ admin.ad_socialbar | safe }}
    {% endif %}

    <style>
        :root { --main-grad: linear-gradient(135deg, #0f0c29 0%, #302b63 100%); --premium-grad: linear-gradient(45deg, #f093fb 0%, #f5576c 100%); }
        body { font-family: 'Poppins', sans-serif; background: #0f0c29; background: var(--main-grad); color: white; min-height: 100vh; }
        .glass-card { background: rgba(255, 255, 255, 0.95); color: #1a1a2e; border-radius: 25px; padding: 30px; box-shadow: 0 15px 35px rgba(0,0,0,0.5); }
        .navbar { background: rgba(0,0,0,0.3); backdrop-filter: blur(15px); border-bottom: 1px solid rgba(255,255,255,0.1); }
        .btn-premium { background: var(--premium-grad); border: none; color: white; border-radius: 50px; font-weight: 600; padding: 12px 30px; transition: 0.3s; }
        .btn-premium:hover { transform: translateY(-3px); box-shadow: 0 5px 20px rgba(245, 87, 108, 0.4); }
        .format-card { background: #f8f9fa; border-radius: 15px; margin-bottom: 10px; padding: 15px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; border: 1px solid #ddd; transition: 0.3s; }
        .format-card:hover { background: #fff; transform: scale(1.02); color: #f5576c; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="fab fa-youtube text-danger me-2"></i>PROTUBE <span class="badge bg-danger">PREMIUM</span>
            </a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}
                    <a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-4"><i class="fa fa-tachometer-alt"></i> Dashboard</a>
                {% else %}
                    <a href="/login" class="text-white-50 text-decoration-none small"><i class="fa fa-lock"></i> Staff Only</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-5">
        {% if not db_status %}<div class="alert alert-danger text-center rounded-4 shadow">Database not connected! Check MONGO_URI in Render.</div>{% endif %}
        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>
        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-warning text-center rounded-pill">{{m}}</div>{% endfor %}{% endwith %}

        {% if page == 'home' %}
        <div class="text-center py-5">
            <h1 class="fw-bold mb-3" style="font-size: 3.2rem;">Downloader Pro</h1>
            <p class="text-white-50 mb-5">সরাসরি ইউটিউব ভিডিও ডাউনলোড করুন কোনো ঝামেলা ছাড়াই।</p>
            <div class="col-lg-8 mx-auto">
                <form method="POST" class="input-group bg-white rounded-pill overflow-hidden shadow-lg p-1">
                    <input type="text" name="url" class="form-control border-0 px-4 py-3 shadow-none" placeholder="Paste YouTube Link Here..." required style="color:#222;">
                    <button class="btn btn-premium px-5">ANALYZE</button>
                </form>
            </div>
        </div>

        {% if video %}
            {% if video.error %}
                <div class="alert alert-danger col-lg-8 mx-auto rounded-4 mt-4 shadow border-0">
                    <h5 class="fw-bold"><i class="fa fa-robot me-2"></i>Bot Detected!</h5>
                    <p class="small mb-0">ইউটিউব আপনার সার্ভার ব্লক করেছে। সমাধান: অ্যাডমিন প্যানেলে গিয়ে <b>YouTube Cookies</b> দিন।</p>
                    <hr><p class="small mb-0">{{ video.error }}</p>
                </div>
            {% else %}
                <div class="glass-card mt-5 col-lg-10 mx-auto text-start">
                    <div class="row g-4">
                        <div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow w-100 h-100" style="object-fit:cover;"></div>
                        <div class="col-md-7 ps-md-4">
                            <h4 class="fw-bold mb-2">{{ video.title }}</h4>
                            <div class="mb-3">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
                            <div class="formats" style="max-height:350px; overflow-y:auto; padding-right:10px;">
                                {% for f in video.formats[:10] %}
                                <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-card">
                                    <div><i class="fa fa-video text-danger me-2"></i><b>{{ f.res }} ({{ f.ext | upper }})</b></div>
                                    <span class="badge bg-success rounded-pill p-2 px-3">{{ f.size }} MB <i class="fa fa-download ms-1"></i></span>
                                </a>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                </div>
            {% endif %}
        {% endif %}

        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5">
            <div class="glass-card text-center p-5 shadow-lg">
                <i class="fa fa-user-shield fa-3x text-danger mb-4"></i>
                <h4 class="fw-bold mb-4">Admin Access</h4>
                <form method="POST" action="/login">
                    <input type="text" name="u" class="form-control mb-3 rounded-pill p-3 border-0 bg-light" placeholder="Username" required>
                    <input type="password" name="p" class="form-control mb-4 rounded-pill p-3 border-0 bg-light" placeholder="Password" required>
                    <button class="btn btn-premium w-100 py-3 shadow">LOG IN</button>
                </form>
            </div>
        </div>

        {% elif page == 'admin' %}
        <div class="glass-card mt-4 shadow border-0 text-start">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h4 class="fw-bold text-danger m-0"><i class="fa fa-cog me-2"></i>Control Panel</h4>
                <a href="/logout" class="btn btn-sm btn-outline-danger rounded-pill px-3">Logout Session</a>
            </div>
            <hr>
            <form method="POST" action="/save_settings">
                <div class="row">
                    <div class="col-md-6 mb-3"><label class="fw-bold small mb-1">Popunder Script</label><textarea name="pop" class="form-control small" rows="2">{{ admin.ad_popunder }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold small mb-1">Social Bar Script</label><textarea name="soc" class="form-control small" rows="2">{{ admin.ad_socialbar }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold small mb-1">Native Ad Slot</label><textarea name="nat" class="form-control small" rows="2">{{ admin.ad_native }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold small mb-1">Banner Ad Slot</label><textarea name="ban" class="form-control small" rows="2">{{ admin.ad_banner }}</textarea></div>
                    <div class="col-md-8 mb-3"><label class="fw-bold small mb-1">Direct Link Ad URL</label><input type="text" name="d_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
                    <div class="col-md-4 mb-3"><label class="fw-bold small mb-1">Ad Count (Clicks)</label><input type="number" name="d_count" class="form-control" value="{{ admin.ad_direct_count }}"></div>
                </div>
                <hr><label class="fw-bold small mb-1 text-danger">YouTube Cookies (Netscape Format)</label>
                <textarea name="cookies" class="form-control mb-4 small" rows="3" placeholder="Paste your cookies here to fix Bot Error...">{{ admin.yt_cookies }}</textarea>
                <button class="btn btn-premium w-100 py-3 shadow">APPLY CONFIGURATION</button>
            </form>
        </div>
        {% endif %}
    </div>

    <footer class="text-center py-5 text-white-50">
        <small>&copy; 2025 ProTube Premium Downloader. All rights reserved.</small>
    </footer>

    <script>
        let clicks = 0;
        const target = {{ admin.ad_direct_count if admin else 0 }};
        const adLink = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(url) {
            if (clicks < target && adLink !== "") {
                clicks++;
                window.open(adLink, '_blank');
            } else {
                window.location.href = url;
            }
        }
    </script>
</body>
</html>
"""

# --- রাউটস হ্যান্ডলিং ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if admin_col is None: return render_template_string(PREMIUM_UI, page='home', admin=None, db_status=False)
    admin = admin_col.find_one({"username": "admin"})
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
        if not video: flash("Error: Link is invalid or video private!")
    return render_template_string(PREMIUM_UI, page='home', video=video, admin=admin, db_status=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('u')
        p = request.form.get('p')
        user_data = admin_col.find_one({"username": u})
        if user_data and user_data['password'] == p:
            login_user(User(user_data))
            return redirect(url_for('admin'))
        flash("Unauthorized: Invalid Credentials!")
    return render_template_string(PREMIUM_UI, page='login', admin=None, db_status=True)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(PREMIUM_UI, page='admin', admin=admin_data, db_status=True)

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
    flash("Settings Saved and Applied!"); return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    if admin_col is not None:
        if admin_col.count_documents({"username": "admin"}) == 0:
            admin_col.insert_one({"username": "admin", "password": "admin123", "ad_direct_count": 0})
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
