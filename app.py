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

# --- অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-yt-2025-key-full')

# --- MongoDB কানেকশন হ্যান্ডলিং ---
MONGO_URI = os.environ.get('MONGO_URI')
admin_col = None
db_connected = False

if MONGO_URI:
    try:
        # মঙ্গোডিবি কানেক্ট করার চেষ্টা
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['yt_downloader_db']
        admin_col = db['admin_settings']
        # কানেকশন চেক করা
        client.admin.command('ping')
        db_connected = True
        print("Connected to MongoDB Atlas Successfully!")
    except Exception as e:
        print(f"MongoDB Error: {e}")
else:
    print("CRITICAL: MONGO_URI is missing in Environment Variables!")

# --- লগইন ম্যানেজার ---
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.password = user_data['password']
        # অ্যাডমিন সেটিংস লোড করা
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
    if user_data:
        return User(user_data)
    return None

# --- ভিডিও ডাউনলোডার লজিক ---
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

    # কুকিজ ফাইল প্রসেসিং
    if admin and admin.get('yt_cookies'):
        with open('temp_cookies.txt', 'w') as f:
            f.write(admin['yt_cookies'])
        ydl_opts['cookiefile'] = 'temp_cookies.txt'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                # ভিডিও এবং অডিও দুটোই আছে এমন ফরম্যাট ফিল্টার
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
                'formats': formats[::-1] # ভালো রেজোলিউশন আগে
            }
        except Exception as e:
            print(f"yt-dlp Error: {e}")
            return None

# --- প্রিমিয়াম ডিজাইন (HTML UI) ---
UI_TEMPLATE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Premium - Best YT Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    
    <!-- Ads Injection (Popunder & Social Bar) -->
    {% if admin %}
        {{ admin.ad_popunder | safe }}
        {{ admin.ad_socialbar | safe }}
    {% endif %}

    <style>
        body { font-family: 'Poppins', sans-serif; background: #0f0c29; background: linear-gradient(135deg, #0f0c29 0%, #302b63 100%); color: #fff; min-height: 100vh; }
        .glass { background: rgba(255, 255, 255, 0.95); color: #1a1a2e; border-radius: 25px; padding: 30px; box-shadow: 0 15px 35px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); }
        .btn-premium { background: linear-gradient(45deg, #f093fb 0%, #f5576c 100%); border: none; color: white; border-radius: 50px; font-weight: 600; padding: 12px 30px; transition: 0.3s; }
        .btn-premium:hover { transform: scale(1.05); box-shadow: 0 5px 20px rgba(245, 87, 108, 0.4); }
        .format-card { background: #f8f9fa; border-radius: 15px; margin-bottom: 12px; padding: 15px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; border: 1px solid #ddd; transition: 0.3s; }
        .format-card:hover { background: #fff; transform: translateY(-3px); border-color: #f5576c; color: #f5576c; }
        .navbar { background: rgba(0,0,0,0.4); backdrop-filter: blur(15px); border-bottom: 1px solid rgba(255,255,255,0.1); }
        .premium-badge { background: #ff0000; color: white; font-size: 10px; padding: 2px 8px; border-radius: 5px; vertical-align: middle; }
        footer { opacity: 0.6; font-size: 13px; text-align: center; margin-top: 50px; padding-bottom: 20px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/">
                <i class="fab fa-youtube text-danger me-2"></i>PROTUBE <span class="premium-badge">PREMIUM</span>
            </a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}
                    <a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-4"><i class="fa fa-tachometer-alt"></i></a>
                {% else %}
                    <a href="/login" class="text-white-50 text-decoration-none small"><i class="fa fa-lock"></i> Login</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container mt-5">
        {% if not db_connected %}
            <div class="alert alert-danger text-center shadow border-0 rounded-4">
                <i class="fa fa-exclamation-triangle me-2"></i> <b>Database Error:</b> Please set up MONGO_URI in Render Settings.
            </div>
        {% endif %}

        <div class="text-center mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>

        {% with msgs = get_flashed_messages() %}
            {% for m in msgs %}<div class="alert alert-warning text-center rounded-pill shadow-sm border-0">{{m}}</div>{% endfor %}
        {% endwith %}

        {% if page == 'home' %}
        <div class="text-center py-5">
            <h1 class="fw-bold mb-3" style="font-size: 3rem;">Premium Downloader</h1>
            <p class="text-white-50 mb-5">সরাসরি ইউটিউব ভিডিও ডাউনলোড করুন কোনো ঝামেলা ছাড়াই।</p>
            <div class="col-lg-8 mx-auto">
                <form method="POST" class="input-group shadow-lg rounded-pill overflow-hidden bg-white">
                    <input type="text" name="url" class="form-control border-0 p-3 px-4 shadow-none" placeholder="Paste YouTube Video Link..." required style="color: #333;">
                    <button class="btn btn-premium px-5">DOWNLOAD</button>
                </form>
            </div>
        </div>

        {% if video %}
        <div class="glass mt-5 col-lg-10 mx-auto">
            <div class="row g-4">
                <div class="col-md-5">
                    <img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow w-100 h-100" style="object-fit: cover; min-height: 250px;">
                </div>
                <div class="col-md-7 ps-md-4 text-start">
                    <h3 class="fw-bold mb-2">{{ video.title }}</h3>
                    <div class="mb-3">
                        <span class="badge bg-dark me-2 p-2 px-3"><i class="fa fa-clock text-info me-1"></i>{{ video.duration }}</span>
                        <span class="badge bg-dark p-2 px-3"><i class="fa fa-eye text-warning me-1"></i>{{ video.views }}</span>
                    </div>
                    
                    <!-- Native Ad Spot -->
                    <div class="mb-4">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>

                    <div class="formats-list" style="max-height: 350px; overflow-y: auto; padding-right: 10px;">
                        {% for f in video.formats[:10] %}
                        <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-card">
                            <div><i class="fa-video text-danger me-2"></i> <b>{{ f.res }} ({{ f.ext | upper }})</b></div>
                            <span class="badge bg-success rounded-pill p-2">{{ f.size }} MB <i class="fa-download ms-1"></i></span>
                        </a>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}

        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5">
            <div class="glass text-center p-5 shadow-lg">
                <i class="fa fa-user-shield fa-3x text-danger mb-4"></i>
                <h3 class="fw-bold mb-4">Admin Portal</h3>
                <form method="POST">
                    <input type="text" name="u" class="form-control mb-3 rounded-pill p-3 border-0 bg-light" placeholder="Username" required>
                    <input type="password" name="p" class="form-control mb-4 rounded-pill p-3 border-0 bg-light" placeholder="Password" required>
                    <button class="btn btn-premium w-100 py-3 shadow">ACCESS DASHBOARD</button>
                </form>
            </div>
        </div>

        {% elif page == 'admin' %}
        <div class="glass mt-4 shadow border-0">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h4 class="fw-bold text-danger m-0"><i class="fa fa-cogs me-2"></i>Admin Management</h4>
                <a href="/logout" class="btn btn-sm btn-outline-danger rounded-pill px-3">Logout</a>
            </div>
            <hr>
            <form method="POST" action="/save_settings">
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="fw-bold small mb-1">Popunder Ad Script</label>
                        <textarea name="popunder" class="form-control" rows="3" placeholder="Paste Popunder Code">{{ admin.ad_popunder }}</textarea>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="fw-bold small mb-1">Social Bar Ad Script</label>
                        <textarea name="socialbar" class="form-control" rows="3" placeholder="Paste Social Bar Code">{{ admin.ad_socialbar }}</textarea>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="fw-bold small mb-1">Native Ad Script (inside card)</label>
                        <textarea name="native" class="form-control" rows="3" placeholder="Paste Native Ad Code">{{ admin.ad_native }}</textarea>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="fw-bold small mb-1">Banner Ad Script (top/bottom)</label>
                        <textarea name="banner" class="form-control" rows="3" placeholder="Paste Banner Ad Code">{{ admin.ad_banner }}</textarea>
                    </div>
                    <div class="col-md-8 mb-3">
                        <label class="fw-bold small mb-1">Direct Link Ad URL</label>
                        <input type="text" name="direct_url" class="form-control" value="{{ admin.ad_direct_link }}" placeholder="https://adsterra.com/...">
                    </div>
                    <div class="col-md-4 mb-3">
                        <label class="fw-bold small mb-1">Direct Link Clicks</label>
                        <input type="number" name="direct_count" class="form-control" value="{{ admin.ad_direct_count }}">
                    </div>
                </div>
                <hr>
                <label class="fw-bold small mb-1">YouTube Auth Cookies (Netscape Format)</label>
                <textarea name="cookies" class="form-control mb-4" rows="4" placeholder="Paste cookies here to prevent IP blocking">{{ admin.yt_cookies }}</textarea>
                
                <button class="btn btn-premium w-100 py-3 shadow">SAVE ALL CONFIGURATIONS</button>
            </form>
        </div>
        {% endif %}
    </div>

    <footer>
        <p>&copy; 2025 ProTube Premium Downloader. All Rights Reserved.</p>
    </footer>

    <script>
        let currentClicks = 0;
        const targetClicks = {{ admin.ad_direct_count if admin else 0 }};
        const directAdLink = "{{ admin.ad_direct_link if admin else '' }}";

        function handleDownload(videoUrl) {
            if (currentClicks < targetClicks && directAdLink !== "") {
                currentClicks++;
                window.open(directAdLink, '_blank');
            } else {
                window.location.href = videoUrl;
            }
        }
    </script>
</body>
</html>
"""

# --- রাউটস এবং ভিউ লজিক ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if admin_col is None:
        return render_template_string(UI_TEMPLATE, page='home', admin=None, db_connected=False)
    
    admin = admin_col.find_one({"username": "admin"})
    video_data = None
    if request.method == 'POST':
        video_data = fetch_video_data(request.form.get('url'))
        if not video_data:
            flash("Error: Link is invalid or video unavailable!")
    
    return render_template_string(UI_TEMPLATE, page='home', video=video_data, admin=admin, db_connected=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if db_connected is False: return "Database connection missing!"
    if request.method == 'POST':
        user_data = admin_col.find_one({"username": request.form['u']})
        if user_data and user_data['password'] == request.form['p']:
            login_user(User(user_data))
            return redirect(url_for('admin'))
        flash("Invalid Credentials! Please try again.")
    return render_template_string(UI_TEMPLATE, page='login', admin=None, db_connected=True)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(UI_TEMPLATE, page='admin', admin=admin_data, db_connected=True)

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
    flash("Success: All settings updated and live!")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- সার্ভার রান ---
if __name__ == '__main__':
    # প্রথমবার রান হলে ডিফল্ট অ্যাডমিন তৈরি
    if admin_col is not None:
        if admin_col.count_documents({"username": "admin"}) == 0:
            admin_col.insert_one({"username": "admin", "password": "admin123", "ad_direct_count": 0})
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
