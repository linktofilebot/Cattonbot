import os
import requests
import threading
import time
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import yt_dlp

# --- অ্যাপ সেটআপ ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ultimate-yt-downloader-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- ডাটাবেস মডেল ---
class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    yt_cookies = db.Column(db.Text, nullable=True)
    ad_popunder = db.Column(db.Text, nullable=True)
    ad_socialbar = db.Column(db.Text, nullable=True)
    ad_native = db.Column(db.Text, nullable=True)
    ad_banner = db.Column(db.Text, nullable=True)
    ad_direct_link = db.Column(db.String(500), nullable=True)
    ad_direct_count = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --- ভিডিও ডাউনলোডার লজিক ---
def fetch_video_data(url):
    admin = AdminUser.query.filter_by(username='admin').first()
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    if admin and admin.yt_cookies:
        with open('temp_cookies.txt', 'w') as f:
            f.write(admin.yt_cookies)
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
        except:
            return None

def keep_web_alive():
    while True:
        try:
            render_url = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
            url = f"https://{render_url}/" if render_url else "http://localhost:5000/"
            requests.get(url, timeout=10)
        except: pass
        time.sleep(300)

# --- সম্পূর্ণ ডিজাইন এবং অ্যাড সিস্টেম ---
MAIN_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium YT Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    
    {% if admin %}
    {{ admin.ad_popunder | safe if admin.ad_popunder }}
    {{ admin.ad_socialbar | safe if admin.ad_socialbar }}
    {% endif %}

    <style>
        :root { --primary: #FF0000; --secondary: #212121; }
        body { background: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
        .navbar { background: white; border-bottom: 2px solid var(--primary); }
        .hero-section { background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.05); padding: 50px 20px; margin-top: 30px; }
        .search-box { border: 2px solid #ddd; border-radius: 50px; padding: 15px 30px; font-size: 1.1rem; }
        .btn-download { background: var(--primary); color: white; border-radius: 50px; padding: 15px 40px; font-weight: bold; border: none; }
        .video-card { border: none; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; background: white; }
        .format-item { background: #f1f3f5; border-radius: 12px; margin-bottom: 10px; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; }
        .format-item:hover { transform: scale(1.01); background: #e9ecef; }
        .ad-container { text-align: center; margin: 20px 0; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg sticky-top shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold text-dark" href="/"><i class="fa-play-circle fab text-danger me-2"></i>YT DOWNLOADER</a>
            <div class="ms-auto">
                {% if current_user.is_authenticated %}
                    <a href="/admin" class="btn btn-outline-dark btn-sm rounded-pill px-3">Dashboard</a>
                    <a href="/logout" class="btn btn-danger btn-sm rounded-pill px-3 ms-2">Logout</a>
                {% else %}
                    <a href="/login" class="text-muted text-decoration-none small">Admin Login</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="container">
        <div class="ad-container">{% if admin %}{{ admin.ad_banner | safe if admin.ad_banner }}{% endif %}</div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}{% for message in messages %}
                <div class="alert alert-info mt-3 text-center shadow-sm">{{ message }}</div>
            {% endfor %}{% endif %}
        {% endwith %}

        {% if page == 'home' %}
        <div class="hero-section text-center">
            <h1 class="fw-bold text-dark mb-3">ইউটিউব ভিডিও ডাউনলোড করুন</h1>
            <p class="text-muted mb-5">সরাসরি হাই-কোয়ালিটি ভিডিও ডাউনলোড।</p>
            <form method="POST" class="col-lg-8 mx-auto">
                <div class="position-relative">
                    <input type="text" name="url" class="form-control search-box" placeholder="লিংক এখানে পেস্ট করুন..." required>
                    <button class="btn btn-download position-absolute end-0 top-0 mt-1 me-1">Analyze</button>
                </div>
            </form>
        </div>

        {% if video %}
        <div class="video-card mt-5 col-lg-10 mx-auto">
            <div class="row g-0">
                <div class="col-md-5"><img src="{{ video.thumb }}" class="img-fluid h-100" style="object-fit: cover;"></div>
                <div class="col-md-7 p-4">
                    <h4 class="fw-bold mb-3">{{ video.title }}</h4>
                    <div class="mb-3">{% if admin %}{{ admin.ad_native | safe if admin.ad_native }}{% endif %}</div>
                    <div class="formats-list">
                        {% for f in video.formats[:7] %}
                        <a href="javascript:void(0)" onclick="handleDownload('{{ f.url }}')" class="format-item shadow-sm">
                            <div><i class="fa-video me-2 text-danger"></i><strong>{{ f.res }}</strong></div>
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
            <h3 class="fw-bold mb-4">অ্যাডমিন লগইন</h3>
            <form method="POST">
                <input type="text" name="u" class="form-control mb-3 p-3 rounded-pill" placeholder="Username" required>
                <input type="password" name="p" class="form-control mb-4 p-3 rounded-pill" placeholder="Password" required>
                <button class="btn btn-download w-100 py-3">Login</button>
            </form>
        </div>

        {% elif page == 'admin' %}
        <div class="row mt-4">
            <div class="col-md-12">
                <div class="hero-section p-4 shadow border-0">
                    <h4 class="fw-bold mb-4 text-danger"><i class="fa-tools me-2"></i>Ad Management System</h4>
                    <form method="POST" action="/save_ads">
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label class="fw-bold">Popunder Ad Code:</label>
                                <textarea name="popunder" class="form-control" rows="4">{{ admin.ad_popunder or '' }}</textarea>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="fw-bold">Social Bar Ad Code:</label>
                                <textarea name="socialbar" class="form-control" rows="4">{{ admin.ad_socialbar or '' }}</textarea>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="fw-bold">Native Ad Code:</label>
                                <textarea name="native" class="form-control" rows="4">{{ admin.ad_native or '' }}</textarea>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label class="fw-bold">Banner Ad Code:</label>
                                <textarea name="banner" class="form-control" rows="4">{{ admin.ad_banner or '' }}</textarea>
                            </div>
                            <div class="col-md-8 mb-3">
                                <label class="fw-bold">Direct Link URL:</label>
                                <input type="text" name="direct_url" class="form-control" value="{{ admin.ad_direct_link or '' }}">
                            </div>
                            <div class="col-md-4 mb-3">
                                <label class="fw-bold">Direct Link Count:</label>
                                <input type="number" name="direct_count" class="form-control" value="{{ admin.ad_direct_count or 0 }}">
                            </div>
                        </div>
                        <hr>
                        <h5 class="fw-bold mt-4">YouTube Cookies</h5>
                        <textarea name="cookies" class="form-control mb-3" rows="5">{{ admin.yt_cookies or '' }}</textarea>
                        <button class="btn btn-download px-5 shadow">Save All Settings</button>
                    </form>
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <script>
        let clickCount = 0;
        const maxAds = {% if admin %}{{ admin.ad_direct_count or 0 }}{% else %}0{% endif %};
        const directLink = "{% if admin %}{{ admin.ad_direct_link or '' }}{% endif %}";

        function handleDownload(videoUrl) {
            if (clickCount < maxAds && directLink !== "") {
                clickCount++;
                window.open(directLink, '_blank');
            } else {
                window.location.href = videoUrl;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    admin = AdminUser.query.filter_by(username='admin').first()
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
        if not video: flash("Error fetching video data!")
    return render_template_string(MAIN_HTML, page='home', video=video, admin=admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    admin = AdminUser.query.filter_by(username='admin').first()
    if request.method == 'POST':
        target = AdminUser.query.filter_by(username=request.form['u']).first()
        if target and target.password == request.form['p']:
            login_user(target)
            return redirect(url_for('admin'))
        flash("Invalid login!")
    return render_template_string(MAIN_HTML, page='login', admin=admin)

@app.route('/admin')
@login_required
def admin():
    return render_template_string(MAIN_HTML, page='admin', admin=current_user)

@app.route('/save_ads', methods=['POST'])
@login_required
def save_ads():
    current_user.ad_popunder = request.form.get('popunder')
    current_user.ad_socialbar = request.form.get('socialbar')
    current_user.ad_native = request.form.get('native')
    current_user.ad_banner = request.form.get('banner')
    current_user.ad_direct_link = request.form.get('direct_url')
    current_user.ad_direct_count = int(request.form.get('direct_count', 0))
    current_user.yt_cookies = request.form.get('cookies')
    db.session.commit()
    flash("Settings updated!")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    logout_user(); return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not AdminUser.query.filter_by(username='admin').first():
            db.session.add(AdminUser(username='admin', password='admin123'))
            db.session.commit()
    threading.Thread(target=keep_web_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
