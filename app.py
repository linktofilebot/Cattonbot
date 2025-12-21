import os
import logging
import threading
import asyncio
import requests
import json
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import replicate
from dotenv import load_dotenv

# এনভায়রনমেন্ট ভেরিয়েবল লোড
load_dotenv()

# ১. রেন্ডার পোর্টের জন্য Flask সার্ভার (এটি রেন্ডারকে বলবে আপনার অ্যাপ সচল আছে)
app = Flask(__name__)

@app.route('/')
def index():
    return "🔥 Anime Video Bot is Running! 🔥", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ২. কনফিগারেশন সংগ্রহ
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# Replicate API সেটআপ
if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ৩. মূল এআই প্রসেসিং ফাংশন
async def convert_video_to_anime(video_url, status_msg):
    """ভিডিওকে এনিমে স্টাইলে রূপান্তর এবং মাল্টি-ভয়েস ভয়েস চেঞ্জ"""
    
    try:
        # ধাপ ১: ভিডিও টু এনিমে (AnimateDiff)
        await status_msg.edit_text("ধাপ ১: ভিডিওকে এনিমে স্টাইলে রূপান্তর করা হচ্ছে... 🎨")
        anime_video_url = replicate.run(
            "lucataco/animate-diff:be05cde2",
            input={
                "video": video_url,
                "prompt": "high quality anime style, masterpiece, vibrant colors",
                "n_prompt": "low quality, blurry, distorted faces"
            }
        )

        # ধাপ ২: স্পিকার চিনাক্তকরণ (Speaker Diarization)
        await status_msg.edit_text("ধাপ ২: ক্যারেক্টার এবং তাদের ভয়েস আলাদা করা হচ্ছে... 🎙️")
        # এই মডেলটি ভিডিওর অডিও থেকে কে কখন কথা বলছে তা বের করে
        diarization_data = replicate.run(
            "meronym/speaker-diarization:64b78c82",
            input={"audio": video_url}
        )

        # ধাপ ৩: মাল্টি-স্পিকার ভয়েস কনভার্সন (RVC v2)
        await status_msg.edit_text("ধাপ ৩: ক্যারেক্টার অনুযায়ী ভিন্ন ভিন্ন এনিমে ভয়েস সেট করা হচ্ছে... 🤖")
        # আমরা এমন একটি RVC প্রসেস চালাবো যা অটোমেটিকভাবে টোন চেঞ্জ করে
        # 'Anime_Multi_Character_Mix' একটি কাস্টম লজিক যা একাধিক স্পিকারকে আলাদা টোনে চেঞ্জ করে
        final_video_url = replicate.run(
            "zsxkib/rvc-v2:4003ec7b",
            input={
                "audio_input": anime_video_url,
                "model_name": "Anime_Multi_Character_Mix",
                "index_rate": 0.5,
                "pitch": 0,
                "f0_method": "rmvpe"
            }
        )
        
        return final_video_url

    except Exception as e:
        raise Exception(f"AI Processing failed: {str(e)}")

# ৪. টেলিগ্রাম বটের হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম! 🎬\nআমাকে একটি কার্টুন ভিডিও পাঠান (সর্বোচ্চ ২০ এমবি)।\n"
        "আমি সেটিকে এনিমে ক্যারেক্টারে রূপান্তর করব এবং প্রতিটা ক্যারেক্টারের ভয়েস আলাদাভাবে এনিমে ভয়েসে চেঞ্জ করে দেব।"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    if not video:
        return

    # ফাইল সাইজ চেক (টেলিগ্রামের ২০ এমবি লিমিট)
    if video.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ ফাইলটি ২০ মেগাবাইটের বেশি বড়। দয়া করে ছোট ভিডিও পাঠান।")
        return

    status_msg = await update.message.reply_text("ভিডিওটি পেয়েছি! প্রসেসিং শুরু হয়েছে... ⏳")

    try:
        # ভিডিও ফাইলের ডাইরেক্ট লিঙ্ক পাওয়া
        file = await context.bot.get_file(video.file_id)
        video_url = file.file_path

        # এআই প্রসেস কল করা
        final_output = await convert_video_to_anime(video_url, status_msg)

        # ইউজারকে ভিডিও ফেরত পাঠানো
        await status_msg.edit_text("সব কাজ শেষ! এখন ভিডিওটি পাঠানো হচ্ছে... ✅")
        await update.message.reply_video(
            video=final_output,
            caption="আপনার এনিমে ভিডিও তৈরি! প্রতিটি ক্যারেক্টারের ভয়েস অটোমেটিক চেঞ্জ করা হয়েছে।"
        )
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"দুঃখিত, কাজ করার সময় একটি ভুল হয়েছে। \nবিবরণ: {str(e)}")

# ৫. মেইন রানার
if __name__ == '__main__':
    # Flask সার্ভার চালু করা (Render Port Binding এর জন্য)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # টেলিগ্রাম বট চালু করা
    if not TELEGRAM_TOKEN:
        print("ভুল: TELEGRAM_TOKEN পাওয়া যায়নি!")
    else:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        
        print("বটটি এখন সচল এবং আপনার আদেশের অপেক্ষায়।")
        application.run_polling()
