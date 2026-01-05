import os
import threading
from flask import Flask, render_template_string, request, redirect, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import telebot
from datetime import datetime

# --- কনফিগারেশন ---
app = Flask(__name__)
app.secret_key = "moviebox_unlimited_2026"

MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "") # রেন্ডারে আপনার টোকেন দিন

# MongoDB কানেকশন
client = MongoClient(MONGO_URI)
db = client['moviebox_v5_db']
movies_col = db['movies']

bot = None
if ":" in BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# --- ডিজাইন এবং ফ্রন্টএন্ড আগের মতোই থাকবে ---
# (আপনার রেইনবো লোগো এবং প্রিমিয়াম সিএসএস এখানে বসাবেন)

@app.route('/')
def index():
    movies = list(movies_col.find().sort("_id", -1))
    return render_template_string("<h1>MovieBox Pro V5</h1><ul>{% for m in movies %}<li>{{ m.title }}</li>{% endfor %}</ul>", movies=movies)

# --- ৪ জিবি মুভি হ্যান্ডেল করার জন্য বট সিস্টেম ---
user_data = {}

if bot:
    @bot.message_handler(commands=['upload'])
    def bot_upload_start(message):
        bot.reply_to(message, "🎬 ৪ জিবি মুভি অ্যাড করার সিস্টেম...\nপ্রথমে মুভির নাম (Title) পাঠান:")
        user_data[message.chat.id] = {'step': 'title'}

    @bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('step') == 'title')
    def bot_get_title(message):
        user_data[message.chat.id]['title'] = message.text
        user_data[message.chat.id]['step'] = 'link'
        bot.reply_to(message, f"মুভি: {message.text}\nএখন মুভির **Direct Download Link** পাঠান।\n(টেলিগ্রাম লিঙ্ক জেনারেটর বট থেকে পাওয়া লিঙ্কটি এখানে দিন)")

    @bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('step') == 'link')
    def bot_get_link(message):
        cid = message.chat.id
        link = message.text
        if link.startswith("http"):
            # ৪ জিবি ভিডিও লিঙ্ক সরাসরি MongoDB-তে সেভ হবে
            movies_col.insert_one({
                "title": user_data[cid]['title'],
                "video_url": link, # সরাসরি লিঙ্ক সেভ হচ্ছে
                "poster": "https://via.placeholder.com/500x750",
                "type": "movie",
                "year": datetime.now().year,
                "likes": 0
            })
            bot.send_message(cid, f"✅ সফলভাবে ৪ জিবি মুভি অ্যাড হয়েছে!\nমুভি: {user_data[cid]['title']}")
            user_data[cid] = {}
        else:
            bot.reply_to(message, "❌ ভুল লিঙ্ক! দয়া করে একটি সঠিক URL দিন।")

def run_bot():
    if bot: bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
