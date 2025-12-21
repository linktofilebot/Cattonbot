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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'premium-yt-downloader-key-2025')

# --- MongoDB কানেকশন ---
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
        print("MongoDB Connected Successfully!")
    except Exception as e:
        print(f"MongoDB Error: {e}")
else:
    print("CRITICAL: MONGO_URI is missing!")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- ইউজার মডেল ---
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data.get('username')
        self.password = user_data.get('password')
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

# --- ভিডিও ফেচিং লজিক (উন্নত) ---
def fetch_video_data(url):
    if admin_col is None: return None
    admin = admin_col.find_one({"username": "admin"})
    
    # কুকিজ ফাইল প্রসেসিং
    cookie_filename = 'yt_cookies.txt'
    if admin and admin.get('yt_cookies'):
        with open(cookie_filename, 'w') as f:
            f.write(admin['yt_cookies'])
    else:
        # যদি কুকিজ না থাকে তবে ব্ল্যাঙ্ক ফাইল তৈরি করবে না
        cookie_filename = None

    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }

    if cookie_filename and os.path.exists(cookie_filename):
        ydl_opts['cookiefile'] = cookie_filename

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
            print(f"Extraction Error: {str(e)}")
            return {"error": str(e)}

# --- প্রিমিয়াম ডিজাইন (HTML) ---
PREMIUM_UI = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProTube Premium - Best YT Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
    {% if admin %}{{ admin.ad_popunder | safe }}{{ admin.ad_socialbar | safe }}{% endif %}
    <style>
        body { font-family: 'Poppins', sans-serif; background: #0f0c29; background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 100%); color: #fff; min-height: 100vh; }
        .glass-card { background: rgba(255, 255, 255, 0.95); color: #1a1a2e; border-radius: 20px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .btn-premium { background: linear-gradient(45deg, #f093fb 0%, #f5576c 100%); border: none; color: white; border-radius: 50px; font-weight: 600; padding: 12px 30px; }
        .format-item { background: #f8f9fa; border-radius: 12px; margin-bottom: 10px; padding: 15px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; border: 1px solid #ddd; }
        .format-item:hover { background: #fff; transform: scale(1.02); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .navbar { background: rgba(0,0,0,0.3); backdrop-filter: blur(10px); }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/"><i class="fab fa-youtube text-danger me-2"></i>PROTUBE <span class="badge bg-danger">PREMIUM</span></a>
            {% if current_user.is_authenticated %}<a href="/admin" class="btn btn-sm btn-outline-light rounded-pill px-3">Dashboard</a>{% endif %}
        </div>
    </nav>
    <div class="container mt-5 text-center">
        {% if not db_connected %}<div class="alert alert-danger">Database Not Connected! Check MONGO_URI.</div>{% endif %}
        
        <div class="mb-4">{% if admin %}{{ admin.ad_banner | safe }}{% endif %}</div>

        {% with msgs = get_flashed_messages() %}{% for m in msgs %}<div class="alert alert-info rounded-pill">{{m}}</div>{% endfor %}{% endwith %}

        {% if page == 'home' %}
        <div class="py-5">
            <h1 class="fw-bold mb-4">YouTube Downloader Pro</h1>
            <div class="col-lg-8 mx-auto">
                <form method="POST" class="input-group shadow-lg rounded-pill overflow-hidden">
                    <input type="text" name="url" class="form-control border-0 p-3 px-4" placeholder="Paste Video Link..." required>
                    <button class="btn btn-premium px-5">DOWNLOAD</button>
                </form>
            </div>
        </div>
        {% if video %}
            {% if video.error %}
                <div class="alert alert-danger mt-4">Error: {{ video.error }} <br> <b>Solution:</b> Admin Panel এ গিয়ে নতুন YouTube Cookies দিন।</div>
            {% else %}
                <div class="glass-card mt-5 col-lg-10 mx-auto text-start">
                    <div class="row g-4">
                        <div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid rounded-4 shadow w-100"></div>
                        <div class="col-md-7 ps-md-4">
                            <h4 class="fw-bold mb-3">{{ video.title }}</h4>
                            <div class="mb-3">
                                <span class="badge bg-dark me-2">Time: {{ video.duration }}</span>
                                <span class="badge bg-dark">Views: {{ video.views }}</span>
                            </div>
                            <div class="mb-4">{% if admin %}{{ admin.ad_native | safe }}{% endif %}</div>
                            <div class="formats-list" style="max-height:300px; overflow-y:auto;">
                                {% for f in video.formats[:8] %}
                                <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-item">
                                    <div><i class="fa-video text-danger me-2"></i><b>{{ f.res }} ({{ f.ext | upper }})</b></div>
                                    <span class="badge bg-success rounded-pill p-2">{{ f.size }} MB</span>
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
                <h3 class="fw-bold mb-4">Admin Login</h3>
                <form method="POST">
                    <input type="text" name="u" class="form-control mb-3 rounded-pill p-3" placeholder="Username (admin)" required>
                    <input type="password" name="p" class="form-control mb-4 rounded-pill p-3" placeholder="Password" required>
                    <button class="btn btn-premium w-100 py-3 shadow">LOGIN</button>
                </form>
            </div>
        </div>

        {% elif page == 'admin' %}
        <div class="glass-card mt-4 shadow border-0 text-start">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h4 class="fw-bold text-danger m-0">Admin Controls</h4>
                <a href="/logout" class="btn btn-sm btn-outline-danger rounded-pill px-3">Logout</a>
            </div>
            <form method="POST" action="/save_settings">
                <div class="row">
                    <div class="col-md-6 mb-3"><label class="fw-bold small">Popunder</label><textarea name="popunder" class="form-control" rows="2">{{ admin.ad_popunder }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold small">Social Bar</label><textarea name="socialbar" class="form-control" rows="2">{{ admin.ad_socialbar }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold small">Native Ad</label><textarea name="native" class="form-control" rows="2">{{ admin.ad_native }}</textarea></div>
                    <div class="col-md-6 mb-3"><label class="fw-bold small">Banner Ad</label><textarea name="banner" class="form-control" rows="2">{{ admin.ad_banner }}</textarea></div>
                    <div class="col-md-8 mb-3"><label class="fw-bold small">Direct Link Ad</label><input type="text" name="direct_url" class="form-control" value="{{ admin.ad_direct_link }}"></div>
                    <div class="col-md-4 mb-3"><label class="fw-bold small">Click Limit</label><input type="number" name="direct_count" class="form-control" value="{{ admin.ad_direct_count }}"></div>
                </div>
                <hr>
                <label class="fw-bold small text-danger">YouTube Cookies (NETSCAPE FORMAT - BOT সমস্যা সমাধানে অবশ্যই দিন)</label>
                <textarea name="cookies" class="form-control mb-4" rows="5" placeholder="Paste Cookies here...">{{ admin.yt_cookies }}</textarea>
                <button class="btn btn-premium w-100 py-3 shadow">SAVE CONFIGURATION</button>
            </form>
        </div>
        {% endif %}
    </div>
    <script>
        let clicks = 0;
        const maxAds = {{ admin.ad_direct_count if admin else 0 }};
        const adLink = "{{ admin.ad_direct_link if admin else '' }}";
        function handleDownload(url) {
            if (clicks < maxAds && adLink !== "") { clicks++; window.open(adLink, '_blank'); }
            else { window.location.href = url; }
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if admin_col is None: return render_template_string(PREMIUM_UI, page='home', admin=None, db_connected=False)
    admin = admin_col.find_one({"username": "admin"})
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
        if not video: flash("Invalid Link!")
    return render_template_string(PREMIUM_UI, page='home', video=video, admin=admin, db_connected=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_data = admin_col.find_one({"username": request.form['u']})
        # ইউজারনেম এবং পাসওয়ার্ড চেক
        if user_data and user_data['password'] == request.form['p']:
            login_user(User(user_data))
            return redirect(url_for('admin'))
        else:
            flash("Invalid Login! Username: admin, Password: " + ("admin123" if not user_data else "Your Saved Password"))
    return render_template_string(PREMIUM_UI, page='login', admin=None, db_connected=True)

@app.route('/admin')
@login_required
def admin():
    admin_data = admin_col.find_one({"username": "admin"})
    return render_template_string(PREMIUM_UI, page='admin', admin=admin_data, db_connected=True)

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
    flash("Settings Saved!"); return redirect(url_for('admin'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    # ফোর্সেড অ্যাডমিন তৈরি (যদি না থাকে)
    if admin_col is not None:
        if admin_col.count_documents({"username": "admin"}) == 0:
            admin_col.insert_one({"username": "admin", "password": "admin123"})
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
