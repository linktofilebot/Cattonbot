import os
import logging
import threading
import asyncio
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import replicate
from dotenv import load_dotenv

# এনভায়রনমেন্ট ভেরিয়েবল লোড
load_dotenv()

# ১. রেন্ডার পোর্টের জন্য Flask সার্ভার সেটিংস
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running online! 🚀", 200

def run_flask():
    # রেন্ডার অটোমেটিক একটা পোর্ট দেয়, সেটা না থাকলে ৮০৮০ ব্যবহার হবে
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ২. কনফিগারেশন সংগ্রহ
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# Replicate এপিআই টোকেন এনভায়রনমেন্টে সেট করা
if REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# লগিং সেটিংস (যাতে সমস্যা হলে কনসোলে দেখা যায়)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ৩. বটের কমান্ড এবং ভিডিও প্রসেসিং লজিক
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম! 🎬\nআমাকে একটি কার্টুন ভিডিও পাঠান। আমি সেটিকে এনিমে ক্যারেক্টারে রূপান্তর করব এবং অটোমেটিক ভয়েস চেঞ্জ করে দেব।"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_video = update.message.video
    if not user_video:
        return

    # ইউজারকে জানানো যে কাজ শুরু হয়েছে
    status_msg = await update.message.reply_text("ভিডিওটি পেয়েছি। এনিমে রূপান্তর এবং ভয়েস চেঞ্জ শুরু হচ্ছে... ⏳")

    try:
        # ভিডিওর ফাইল আইডি থেকে সরাসরি লিঙ্ক তৈরি
        file = await context.bot.get_file(user_video.file_id)
        video_url = file.file_path

        # ধাপ ১: ভিডিও টু এনিমে (Replicate API)
        await status_msg.edit_text("ধাপ ১: ভিডিওর দৃশ্য এনিমে স্টাইলে রূপান্তর করা হচ্ছে... 🎨")
        # lucataco/animate-diff মডেলটি ভিডিওর ফ্রেম ঠিক রেখে এনিমে করে
        anime_output = replicate.run(
            "lucataco/animate-diff:be05cde2",
            input={
                "video": video_url,
                "prompt": "masterpiece, best quality, anime style, high resolution",
                "n_prompt": "bad quality, blurry, low resolution, distorted"
            }
        )

        # ধাপ ২: অটোমেটেড ভয়েস চেঞ্জ (RVC v2)
        await status_msg.edit_text("ধাপ ২: ভয়েস পরিবর্তন এবং ক্যারেক্টার টিউনিং করা হচ্ছে... 🎙️")
        # zsxkib/rvc-v2 মডেলটি অডিও শুনে ভয়েস চেঞ্জ করে
        final_video_output = replicate.run(
            "zsxkib/rvc-v2:4003ec7b",
            input={
                "audio_input": anime_output, # এনিমে ভিডিওর অডিও ইনপুট
                "model_name": "Anime_Multi_Character_Mix", # মাল্টি-ভয়েস এনিমে মডেল
                "index_rate": 0.5,
                "pitch": 0,
                "f0_method": "rmvpe"
            }
        )

        # ধাপ ৩: ফাইনাল রেজাল্ট পাঠানো
        await status_msg.edit_text("সব কাজ সফলভাবে শেষ হয়েছে! এখন ভিডিওটি আপলোড করছি... ✅")
        await update.message.reply_video(
            video=final_video_output,
            caption="আপনার এনিমে ভিডিও তৈরি! ক্যারেক্টার অনুযায়ী ভয়েস অটোমেটিক সেট করা হয়েছে।"
        )
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"দুঃখিত, কাজ করার সময় একটি ভুল হয়েছে। \nবিবরণ: {str(e)}")

# ৪. মেইন ফাংশন (যেটি বট এবং সার্ভার চালু করবে)
if __name__ == '__main__':
    # Flask সার্ভারকে আলাদা থ্রেডে চালু করা (যাতে রেন্ডার পোর্ট ডিটেক্ট করতে পারে)
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # টেলিগ্রাম বট সেটআপ
    if not TELEGRAM_TOKEN:
        print("ভুল: TELEGRAM_TOKEN সেট করা হয়নি!")
    else:
        # অ্যাপ্লিকেশন তৈরি
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # হ্যান্ডলার যোগ করা
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        
        print("বটটি এখন সচল। রেন্ডারে রান করার জন্য প্রস্তুত!")
        application.run_polling()
