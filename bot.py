import asyncio
import urllib.parse
import json
import os
import time
import requests
import http.server
import socketserver
import threading
from hydrogram import Client, idle
from hydrogram.raw.functions.messages import RequestWebView

# --- الإصلاح الجذري لمشكلة الـ Event Loop في إصدارات بايثون الحديثة ---
try:
    loop = asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ================= بيانات القناة والحساب =================
CHANNEL_ID = "@jjjjjjjjjjaaaaaaallll"
API_ID = 33670321
API_HASH = "57841d6b1cc44b5d5d50810f731e189d"
SESSION_STRING = "BAIBxLEAB4PDwWxasshbJuqmlqrt-iM8eNdGiVSMnXzqEc-88naUCuJGQqSUYrLCkZ2CqPVdbw3vqnGNbfOPED5ES71gCt6T9_nrYv_lSBquCdV2yC8ktMNNXuP-XFOpBCLpHThfi6AjSiL3tlMDdNG3htbwUoIIGVrfhdvZN3Ngf5-jK5XsaUHSnsZz82q781CKpR0CEz5yZVTReXSHYXNLCpUY1Gy0V2rBSYwnWd-MRREeaUsGvxpz53NoYoW0vNYa9W3y7zghdZECND5fo53Hko0FYk1Lne24G5jj-mFOmnFb4aYB2jVIBwB1vprd3WpxsP2T3kCFsAgN3mTiA7zHCUdrxwAAAAG5s0U8AA"

# ================= روابط وسيرفر اللعبة =================
AUTH_URL = "https://api.tgmrkt.io/api/v1/auth"
GIVEAWAYS_URL = "https://api.tgmrkt.io/api/v1/giveaways?count=20&cursor=&type=Free&isActive=true&ordering=EndingTimeWithBadge"
WEBAPP_URL = "https://cdn.tgmrkt.io/"
FILE_NAME = "seen_giveaways.txt"

CURRENT_TOKEN = None

# الآن بايثون سيتعرف على الـ loop بدون مشاكل
app = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)

# --- استخراج رابط الـ WebApp وتوليد initData ---
async def get_telegram_init_data():
    bot_peer = await app.resolve_peer("mrkt")
    web_view = await app.invoke(
        RequestWebView(
            peer=bot_peer,
            bot=bot_peer,
            platform="android",
            from_bot_menu=False,
            url=WEBAPP_URL
        )
    )
    full_url = web_view.url
    init_data = full_url.split('#tgWebAppData=')[1].split('&tgWebAppVersion=')[0]
    return urllib.parse.unquote(init_data)

# --- طلب التوكن من سيرفر اللعبة ---
async def refresh_token():
    global CURRENT_TOKEN
    try:
        print("🔄 جاري تحديث التوكن عبر الحساب...")
        init_data = await get_telegram_init_data()
        payload = {
            "appId": None,
            "data": init_data,
            "photo": None
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            "Origin": "https://cdn.tgmrkt.io",
            "Referer": "https://cdn.tgmrkt.io/"
        }
        res = await asyncio.to_thread(requests.post, AUTH_URL, json=payload, headers=headers)
        if res.status_code == 200:
            token = res.cookies.get("access_token")
            if not token:
                try:
                    data = res.json()
                    token = data.get("token") or data.get("accessToken") or data.get("access_token") or data.get("data", {}).get("token")
                except:
                    pass
            
            if token:
                CURRENT_TOKEN = token
                print("✅ تم تجديد التوكن بنجاح ويعمل الآن.")
                return True
            else:
                print(f"⚠️ استجابة غير متوقعة عند التوثيق: {res.text}")
        else:
            print(f"❌ فشل السيرفر في التوثيق: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ استثناء أثناء تجديد التوكن: {e}")
    return False

# --- معالجة الجيفاواي وحفظ المعرفات ---
def get_seen_giveaways():
    if not os.path.exists(FILE_NAME):
        return []
    with open(FILE_NAME, "r") as f:
        return f.read().splitlines()

def save_giveaway(giveaway_id):
    with open(FILE_NAME, "a") as f:
        f.write(f"{giveaway_id}\n")

def format_message(gw):
    gw_id = str(gw.get('id', ''))
    clean_gw_id = gw_id.replace('-', '')
    
    channels = gw.get("chanels", [])
    is_boost = gw.get("isChanelBoostRequired", False)
    is_trader = gw.get("isForActiveTraders", False)
    is_premium = gw.get("isForPremium", False)
    
    preview_gift = gw.get("previewGift", {})
    gift_name = preview_gift.get("name", "Unknown")
    prize_link = f"https://t.me/nft/{gift_name}" if gift_name != "Unknown" else "No prize specified"
    
    reqs = []
    if channels:
        for ch in channels:
            reqs.append(f"• @{ch}")
            
    if is_boost:
        reqs.append("• Boost the channel")
    if is_premium:
        reqs.append("• Be a premium user")
    if is_trader:
        reqs.append("• Active trader volume")
        
    req_text = "\n".join(reqs) if reqs else "• No specific requirements"
    
    return (
        f"🎉 **New Exclusive Giveaway!** 🔥\n\n"
        f"🎁 **Prize:** {prize_link}\n"
        f"🤖 **Bot:** @mrkt\n\n"
        f"📋 **Requirements:**\n{req_text}\n\n"
        f"🚀 **Join Now:**\n"
        f"https://t.me/mrkt/app?startapp=6091548061and768giveaway{clean_gw_id}"
    )

# --- المراقبة التلقائية ---
async def check_giveaways_loop():
    global CURRENT_TOKEN
    while True:
        try:
            if not CURRENT_TOKEN:
                await refresh_token()
                await asyncio.sleep(5)
                continue

            headers = {
                "Authorization": f"Bearer {CURRENT_TOKEN}",
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://cdn.tgmrkt.io",
                "Referer": "https://cdn.tgmrkt.io/",
                "sec-ch-ua": '"Chromium";v="139", "Not A(Brand";v="99"',
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"Android"'
            }
            
            cookies = {
                "access_token": CURRENT_TOKEN
            }
            
            res = await asyncio.to_thread(requests.get, GIVEAWAYS_URL, headers=headers, cookies=cookies)
            if res.status_code == 200:
                try:
                    data = res.json()
                    items = data.get('items', []) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        seen = get_seen_giveaways()
                        for gw in items:
                            gw_id = str(gw.get('id', ''))
                            if gw_id and gw_id not in seen:
                                msg = format_message(gw)
                                await app.send_message(CHANNEL_ID, msg, disable_web_page_preview=True)
                                save_giveaway(gw_id)
                                print(f"✅ تم إرسال جيفاواي جديد للقناة: {gw_id}")
                except json.JSONDecodeError:
                    print("⚠️ استجابة السيرفر ليست بصيغة JSON صحيحة.")
            elif res.status_code in [401, 403]:
                print(f"⚠️ التوكن غير مصرح به، جاري التجديد...")
                CURRENT_TOKEN = None
            else:
                print(f"⚠️ حالة السيرفر: {res.status_code}")
        except Exception as e:
            print(f"حدث خطأ أثناء فحص السيرفر: {e}")
        await asyncio.sleep(60)

# --- سيرفر Koyeb الوهمي ---
def run_server():
    try:
        port = int(os.environ.get("PORT", 8000))
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", port), handler) as httpd:
            print(f"🌐 Web server is running on port {port} for Koyeb health checks")
            httpd.serve_forever()
    except Exception as e:
        print(f"Server error: {e}")

# ================= نقطة البداية =================
async def main():
    print("🚀 جاري تشغيل النظام على السيرفر...")
    await app.start()
    
    try:
        await app.send_message(CHANNEL_ID, "🚀 الحساب يعمل الآن على Koyeb لجمع الجوائز ونشرها 24/7!")
        print("✅ تم ربط الحساب بالقناة بنجاح.")
    except Exception as e:
        print(f"⚠️ خطأ: تأكد أن حسابك لديه صلاحية النشر في القناة. التفاصيل: {e}")

    asyncio.create_task(check_giveaways_loop())
    await idle()
    await app.stop()

if __name__ == '__main__':
    # تشغيل خادم الويب الوهمي لتجاوز فحص Koyeb
    threading.Thread(target=run_server, daemon=True).start()
    
    # تشغيل الدالة الرئيسية باستخدام الـ loop الذي تم إنشاؤه في البداية
    loop.run_until_complete(main())
