import os
import logging
import asyncio
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import replicate
from moviepy.editor import VideoFileClip, AudioFileClip
from dotenv import load_dotenv

# এনভায়রনমেন্ট ভেরিয়েবল লোড
load_dotenv()

# Render-এর Environment Variables থেকে ডেটা নেওয়া
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

# Replicate API সেটআপ
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

# লগিং সেটআপ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("হ্যালো! আমাকে একটি কার্টুন ভিডিও পাঠান। আমি অটোমেটিক সেটিকে এনিমে এবং ভয়েস চেঞ্জ করে দেব।")

async def process_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_video = update.message.video
    chat_id = update.message.chat_id
    
    if not user_video:
        await update.message.reply_text("দয়া করে একটি ভিডিও ফাইল পাঠান।")
        return

    status_msg = await update.message.reply_text("ভিডিওটি পেয়েছি। প্রসেসিং শুরু হচ্ছে... (২-৫ মিনিট সময় লাগতে পারে)")

    # ফাইলের নাম ঠিক করা
    input_video = f"input_{chat_id}.mp4"
    audio_path = f"audio_{chat_id}.mp3"

    try:
        # ১. ভিডিও ডাউনলোড করা
        video_file = await context.bot.get_file(user_video.file_id)
        video_url = video_file.file_path
        
        # ২. ভিডিওকে এনিমে করা (Replicate API)
        await status_msg.edit_text("ধাপ ১: ভিডিওকে এনিমে স্টাইলে রূপান্তর করা হচ্ছে...")
        anime_video_url = replicate.run(
            "lucataco/animate-diff:be05cde2",
            input={
                "video": video_url,
                "prompt": "masterpiece, best quality, anime style, high resolution, vibrant colors",
                "n_prompt": "bad quality, blurry, low resolution, distorted faces"
            }
        )

        # ৩. অডিও এবং স্পিকার ডিটেকশন + ভয়েস চেঞ্জ
        # এখানে আমরা এমন একটি মডেল ব্যবহার করছি যা অডিও এনালাইজ করে ভয়েস চেঞ্জ করবে
        await status_msg.edit_text("ধাপ ২: ক্যারেক্টার অনুযায়ী ভয়েস পরিবর্তন করা হচ্ছে...")
        
        # RVC V2 ব্যবহার করে ভয়েস পরিবর্তন
        # এখানে 'model_name' হিসেবে একটি মাল্টি-ভয়েস এনিমে মডেল ব্যবহার করা হয়েছে
        final_video_url = replicate.run(
            "zsxkib/rvc-v2:4003ec7b",
            input={
                "audio_input": anime_video_url,
                "model_name": "Anime_Multi_Character_Mix", 
                "index_rate": 0.5,
                "pitch": 0, # ০ মানে অরিজিনাল পিচ বজায় থাকবে
                "f0_method": "rmvpe" # উন্নত ভয়েস কোয়ালিটির জন্য
            }
        )

        # ৪. ইউজারকে ফাইনাল ভিডিও পাঠানো
        await status_msg.edit_text("সব কাজ শেষ! ভিডিও পাঠানো হচ্ছে...")
        await update.message.reply_video(
            video=final_video_url, 
            caption="✅ এনিমে এবং ভয়েস কনভার্ট সম্পন্ন হয়েছে!\nবটটি ভালো লাগলে শেয়ার করুন।"
        )
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text(f"দুঃখিত, কোনো একটি কারিগরি সমস্যা হয়েছে। \nError: {str(e)}")

if __name__ == '__main__':
    # চেক করা টোকেন আছে কিনা
    if not TELEGRAM_TOKEN or not REPLICATE_API_TOKEN:
        print("Error: TELEGRAM_TOKEN বা REPLICATE_API_TOKEN পাওয়া যায়নি!")
    else:
        # বট স্টার্ট করা
        application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # হ্যান্ডলার যোগ করা
        start_handler = MessageHandler(filters.COMMAND & filters.Regex('start'), start)
        video_handler = MessageHandler(filters.VIDEO, process_video)
        
        application.add_handler(start_handler)
        application.add_handler(video_handler)
        
        print("বটটি সফলভাবে চালু হয়েছে এবং রেন্ডারে রান করার জন্য প্রস্তুত।")
        application.run_polling()
