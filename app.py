import os
import logging
import threading
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import replicate
from dotenv import load_dotenv

# এনভায়রনমেন্ট ভেরিয়েবল লোড করা
load_dotenv()

# ১. রেন্ডারের পোর্টের জন্য Flask সার্ভার (এটি রেন্ডারকে বলবে আপনার অ্যাপ সচল আছে)
server = Flask(__name__)

@server.route('/')
def health_check():
    return "Bot is running and healthy!", 200

def run_flask():
    # Render অটোমেটিক PORT এনভায়রনমেন্ট ভেরিয়েবল দেয়, না থাকলে ৮০৮০ ব্যবহার হবে
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

# ২. কনফিগারেশন (Render Environment Variables থেকে আসবে)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# লগিং সেটআপ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ৩. বটের কাজ শুরু
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("হ্যালো! আমাকে একটি কার্টুন ভিডিও পাঠান। আমি অটোমেটিক সেটিকে এনিমে ভিডিও এবং ভিন্ন ভিন্ন ভয়েসে রূপান্তর করে দেব।")

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_video = update.message.video
    if not user_video:
        return

    status_msg = await update.message.reply_text("ভিডিও পেয়েছি! কাজ শুরু হচ্ছে... এতে কিছুক্ষণ সময় লাগবে।")

    try:
        # ভিডিও ফাইলের লিঙ্ক বের করা
        video_file = await context.bot.get_file(user_video.file_id)
        video_url = video_file.file_path

        # ধাপ ১: ভিডিও টু এনিমে (Replicate)
        await status_msg.edit_text("ধাপ ১: ভিডিওর দৃশ্যগুলোকে এনিমে স্টাইলে রূপান্তর করা হচ্ছে...")
        anime_video_output = replicate.run(
            "lucataco/animate-diff:be05cde2",
            input={
                "video": video_url,
                "prompt": "masterpiece, best quality, anime style, high resolution",
                "n_prompt": "low quality, blurry, distorted"
            }
        )

        # ধাপ ২: অটোমেটেড ভয়েস চেঞ্জ (RVC)
        # এখানে 'Anime_Multi_Character_Mix' মডেলটি ব্যবহার করা হয়েছে যা ক্যারেক্টার অনুযায়ী ভয়েস মডুলেট করে
        await status_msg.edit_text("ধাপ ২: প্রতিটি ক্যারেক্টারের ভয়েস আলাদা করা এবং পরিবর্তন করা হচ্ছে...")
        final_video_output = replicate.run(
            "zsxkib/rvc-v2:4003ec7b",
            input={
                "audio_input": anime_video_output,
                "model_name": "Anime_Multi_Character_Mix",
                "index_rate": 0.5,
                "pitch": 0,
                "f0_method": "rmvpe"
            }
        )

        # ৪. ইউজারকে ফাইনাল ভিডিও পাঠানো
        await status_msg.edit_text("সব কাজ শেষ! এখন ভিডিওটি আপলোড করছি...")
        await update.message.reply_video(
            video=final_video_output, 
            caption="✅ আপনার এনিমে ভিডিও ক্যারেক্টার ভয়েস সহ তৈরি!"
        )
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"দুঃখিত, কোনো একটি সমস্যা হয়েছে। \nError: {str(e)}")

# ৫. মেইন ফাংশন যা সব কিছু একসাথে চালু করবে
if __name__ == '__main__':
    # আলাদা থ্রেডে Flask সার্ভার চালু করা যেন Render পোর্ট ডিটেক্ট করতে পারে
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # টেলিগ্রাম বট সেটআপ
    if not TELEGRAM_TOKEN:
        print("ভুল: TELEGRAM_TOKEN পাওয়া যায়নি!")
    else:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # হ্যান্ডলার যোগ করা
        application.add_handler(MessageHandler(filters.COMMAND & filters.Regex('start'), start))
        application.add_handler(MessageHandler(filters.VIDEO, process_video))
        
        print("বটটি এখন সচল এবং রেন্ডারে রান করার জন্য সম্পূর্ণ প্রস্তুত।")
        application.run_polling()
