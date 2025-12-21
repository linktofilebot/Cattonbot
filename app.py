import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
import replicate
from dotenv import load_dotenv

# এনভায়রনমেন্ট ভেরিয়েবল লোড
load_dotenv()

# রেন্ডার পোর্টের জন্য Flask
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is active and running! 🚀", 200

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# কনফিগারেশন
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("হ্যালো! আমাকে ২০ এমবি-র নিচে একটি কার্টুন ভিডিও পাঠান। আমি সেটিকে এনিমে এবং ভয়েস চেঞ্জ করে দেব।")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    
    # ২০ এমবি চেক (টেলিগ্রাম লিমিট)
    if video.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("❌ ফাইলটি অনেক বড়! দয়া করে ২০ মেগাবাইটের (20MB) ছোট ভিডিও পাঠান।")
        return

    status_msg = await update.message.reply_text("ভিডিও পেয়েছি। প্রসেসিং শুরু হচ্ছে... ⏳")

    try:
        # টেলিগ্রাম থেকে ভিডিওর ডাউনলোড লিঙ্ক বের করা
        file = await context.bot.get_file(video.file_id)
        # সরাসরি ইউআরএল ব্যবহার করছি যাতে রেন্ডারের র‍্যাম কম খরচ হয়
        direct_video_url = file.file_path 

        # ধাপ ১: এনিমে রূপান্তর (Replicate)
        await status_msg.edit_text("ধাপ ১: এনিমে রূপান্তর চলছে... 🎨")
        anime_output = replicate.run(
            "lucataco/animate-diff:be05cde2",
            input={"video": direct_video_url, "prompt": "anime style masterpiece"}
        )

        # ধাপ ২: ভয়েস চেঞ্জ (RVC)
        await status_msg.edit_text("ধাপ ২: ভয়েস পরিবর্তন চলছে... 🎙️")
        final_video = replicate.run(
            "zsxkib/rvc-v2:4003ec7b",
            input={"audio_input": anime_output, "model_name": "Anime_Multi_Character_Mix"}
        )

        await update.message.reply_video(video=final_video, caption="আপনার এনিমে ভিডিও তৈরি! ✅")
        await status_msg.delete()

    except Exception as e:
        error_msg = str(e)
        if "File is too big" in error_msg:
            await update.message.reply_text("❌ ফাইলটি এআই সার্ভারের জন্য অনেক বড় হয়ে গেছে। দয়া করে ছোট বা কম সময়ের ভিডিও দিন।")
        else:
            await update.message.reply_text(f"দুঃখিত, সমস্যা হয়েছে: {error_msg}")

if __name__ == '__main__':
    # Flask সার্ভার চালু
    threading.Thread(target=run_server, daemon=True).start()

    # বট চালু
    if TELEGRAM_TOKEN:
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        print("Bot is running...")
        application.run_polling()
    else:
        print("TELEGRAM_TOKEN missing!")
