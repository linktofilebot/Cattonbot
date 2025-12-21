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

# --- ডাটাবেস মডেল (অ্যাডমিন টেবিল) ---
class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    yt_cookies = db.Column(db.Text, nullable=True) # আইপি ব্লক এড়ানোর জন্য

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --- ভিডিও ডাউনলোডার লজিক (উন্নত) ---
def fetch_video_data(url):
    admin = AdminUser.query.filter_by(username='admin').first()
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    # কুকিজ ফাইল তৈরি করা (যদি থাকে)
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
                'duration': time.strftime('%H:%M:%S', time.gmtime(info.get('duration'))),
                'views': info.get('view_count'),
                'formats': formats[::-1]
            }
        except Exception as e:
            print(f"Error: {e}")
            return None

# --- স্লিপ মোড প্রতিরোধের লজিক (Keep-Alive) ---
def keep_web_alive():
    while True:
        try:
            url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/"
            requests.get(url)
            print("Keep-Alive: Ping successful")
        except:
            pass
        time.sleep(300) # প্রতি ৫ মিনিট পর পর

# --- সব ডিজাইন এক সাথে (HTML UI) ---
MAIN_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Premium YT Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --primary: #FF0000; --secondary: #212121; }
        body { background: #f8f9fa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar { background: white; border-bottom: 2px solid var(--primary); }
        .hero-section { background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.05); padding: 50px 20px; margin-top: 30px; }
        .search-box { border: 2px solid #ddd; border-radius: 50px; padding: 15px 30px; font-size: 1.1rem; transition: 0.3s; }
        .search-box:focus { border-color: var(--primary); box-shadow: none; }
        .btn-download { background: var(--primary); color: white; border-radius: 50px; padding: 15px 40px; font-weight: bold; border: none; }
        .btn-download:hover { background: #cc0000; color: white; }
        .video-card { border: none; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; background: white; }
        .format-item { background: #f1f3f5; border-radius: 12px; margin-bottom: 10px; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; text-decoration: none; color: #333; transition: 0.2s; }
        .format-item:hover { background: #e9ecef; transform: scale(1.02); }
        .admin-sidebar { background: white; border-radius: 20px; padding: 20px; box-shadow: 0 5px 20px rgba(0,0,0,0.05); }
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
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-info mt-3 rounded-pill text-center shadow-sm">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% if page == 'home' %}
        <div class="hero-section text-center">
            <h1 class="fw-bold text-dark mb-3">সহজেই ইউটিউব ভিডিও ডাউনলোড করুন</h1>
            <p class="text-muted mb-5">কোনো অ্যাড নেই, হাই-কোয়ালিটি ভিডিও সরাসরি আপনার গ্যালারিতে।</p>
            <form method="POST" class="col-lg-8 mx-auto">
                <div class="position-relative">
                    <input type="text" name="url" class="form-control search-box" placeholder="ভিডিওর লিংক এখানে পেস্ট করুন..." required>
                    <button class="btn btn-download position-absolute end-0 top-0 mt-1 me-1 shadow">Analyze</button>
                </div>
            </form>
        </div>

        {% if video %}
        <div class="video-card mt-5 col-lg-10 mx-auto">
            <div class="row g-0">
                <div class="col-md-5">
                    <img src="{{ video.thumb }}" class="img-fluid h-100" style="object-fit: cover;">
                </div>
                <div class="col-md-7 p-4">
                    <h4 class="fw-bold mb-3">{{ video.title }}</h4>
                    <div class="mb-4">
                        <span class="badge bg-light text-dark border p-2 px-3 me-2"><i class="fa-clock me-1"></i> {{ video.duration }}</span>
                        <span class="badge bg-light text-dark border p-2 px-3"><i class="fa-eye me-1"></i> {{ video.views }} Views</span>
                    </div>
                    <div class="formats-list">
                        {% for f in video.formats[:7] %}
                        <a href="{{ f.url }}" target="_blank" class="format-item shadow-sm">
                            <div>
                                <i class="fa-video me-2 text-danger"></i>
                                <strong>{{ f.res }}</strong> <span class="text-muted small">({{ f.ext | upper }})</span>
                            </div>
                            <span class="badge bg-success rounded-pill">{{ f.size }} MB <i class="fa-download ms-1"></i></span>
                        </a>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        {% endif %}

        {% elif page == 'login' %}
        <div class="col-md-4 mx-auto mt-5">
            <div class="hero-section text-center p-5 shadow">
                <i class="fa-lock-open fa-3x text-danger mb-4"></i>
                <h3 class="fw-bold mb-4">অ্যাডমিন প্যানেল</h3>
                <form method="POST">
                    <input type="text" name="u" class="form-control mb-3 rounded-pill p-3" placeholder="Username" required>
                    <input type="password" name="p" class="form-control mb-4 rounded-pill p-3" placeholder="Password" required>
                    <button class="btn btn-download w-100 py-3 shadow">Login</button>
                </form>
            </div>
        </div>

        {% elif page == 'admin' %}
        <div class="row mt-5">
            <div class="col-md-4">
                <div class="admin-sidebar text-center mb-4">
                    <img src="https://ui-avatars.com/api/?name=Admin&background=random" class="rounded-circle mb-3" width="80">
                    <h5 class="fw-bold">অ্যাডমিন ড্যাশবোর্ড</h5>
                    <p class="small text-muted">সার্ভার স্ট্যাটাস: <span class="text-success fw-bold">Active</span></p>
                    <hr>
                    <a href="/logout" class="btn btn-outline-danger w-100 rounded-pill">Logout</a>
                </div>
            </div>
            <div class="col-md-8">
                <div class="hero-section p-4 shadow border-0 mt-0">
                    <h5 class="fw-bold mb-4"><i class="fa-cookie-bite me-2 text-warning"></i>YouTube Cookies (আইপি ব্লক সমাধান)</h5>
                    <form method="POST" action="/save_cookies">
                        <textarea name="cookies" class="form-control mb-3" rows="10" placeholder="Paste Netscape format cookies here...">{{ current_user.yt_cookies or '' }}</textarea>
                        <button class="btn btn-download px-5 shadow">Save Settings</button>
                    </form>
                    <div class="mt-4 alert alert-warning small">
                        <strong>কিভাবে করবেন?</strong> ব্রাউজারে 'Get cookies.txt' এক্সটেনশন ব্যবহার করে ইউটিউবের কুকিজ কপি করে এখানে পেস্ট করুন। এতে ইউটিউব আপনার সার্ভার ব্লক করতে পারবে না।
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
    </div>

    <footer class="text-center py-5 text-muted mt-5">
        <p>&copy; 2025 YouTube Downloader Pro | All Rights Reserved</p>
    </footer>
</body>
</html>
"""

# --- রাউটস এবং লজিক ---

@app.route('/', methods=['GET', 'POST'])
def index():
    video = None
    if request.method == 'POST':
        video = fetch_video_data(request.form.get('url'))
        if not video:
            flash("দুঃখিত! ভিডিওর তথ্য পাওয়া যায়নি। সঠিক ইউটিউব লিংক ব্যবহার করুন।")
    return render_template_string(MAIN_HTML, page='home', video=video)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        admin = AdminUser.query.filter_by(username=request.form['u']).first()
        if admin and admin.password == request.form['p']:
            login_user(admin)
            return redirect(url_for('admin'))
        flash("ভুল ইউজার বা পাসওয়ার্ড!")
    return render_template_string(MAIN_HTML, page='login')

@app.route('/admin')
@login_required
def admin():
    return render_template_string(MAIN_HTML, page='admin')

@app.route('/save_cookies', methods=['POST'])
@login_required
def save_cookies():
    current_user.yt_cookies = request.form.get('cookies')
    db.session.commit()
    flash("সেটিংস সফলভাবে আপডেট হয়েছে!")
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # ডিফল্ট অ্যাডমিন একাউন্ট (যদি না থাকে)
        if not AdminUser.query.filter_by(username='admin').first():
            db.session.add(AdminUser(username='admin', password='admin123'))
            db.session.commit()
    
    # Keep-Alive থ্রেড চালু
    threading.Thread(target=keep_web_alive, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
