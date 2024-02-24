import requests
import asyncio
from telegram import Bot
import json
import time
from async_lru import alru_cache
from aiolimiter import AsyncLimiter

config_file = "config.json"

# Fungsi untuk membaca konfigurasi dari file
def load_config():
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        return None

# Fungsi untuk menyimpan konfigurasi ke file
def save_config(config):
    with open(config_file, "w") as f:
        json.dump(config, f)

# Fungsi untuk mengirim pesan ke grup Telegram
async def send_telegram_message(message, bot_token, chat_id):
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    print("Sending Notification")

# Fungsi untuk mendapatkan semua pasangan kripto di Indodax
def get_all_pairs():
    api_url = 'https://indodax.com/api/pairs'
    response = requests.get(api_url)
    data = response.json()
    return [pair['symbol'] for pair in data]

# Fungsi untuk mendapatkan harga kripto dan volume
@alru_cache(maxsize=128)
async def get_crypto_data(pair):
    api_url = f'https://indodax.com/api/ticker/{pair.lower()}'
    response = requests.get(api_url)

    if response.status_code == 200:
        data = response.json()
        last_price = float(data.get('ticker', {}).get('last', 0))
        volume = float(data.get('ticker', {}).get('vol_idr', 0))
        return last_price, volume
    else:
        return None, None

# Inisialisasi rate limiter dengan batas 120 permintaan per menit
rate_limiter = AsyncLimiter(120, 60)

# Fungsi untuk membatasi permintaan ke API Indodax dengan rate limiter
async def api_limiter():
    async with rate_limiter:
        await asyncio.sleep(1)  # Menunggu 1 detik sebagai tindakan pencegahan

# Fungsi untuk memonitor kenaikan atau penurunan harga
async def monitor_price_change(bot_token, chat_id, threshold_percent=5, threshold_price_idr=25, interval=5, volume_threshold=300_000_000):
    all_pairs = get_all_pairs()
    initial_prices = {}
    initial_volumes = {}

    print("Initiating Bot...")
    print("Bot is running... Monitoring Price changes..")

    while True:
        start_time = time.time()  # Waktu awal permintaan
        for pair in all_pairs:
            await api_limiter()  # Menerapkan pembatasan permintaan
            current_price, volume = await get_crypto_data(pair)

            # Skip pair dengan volume di bawah threshold
            if volume is not None and volume < volume_threshold:
                continue

            # Skip pair dengan harga di bawah threshold untuk IDR atau tidak ada harga saat ini
            if pair.endswith('idr') and (current_price is None or current_price < threshold_price_idr):
                continue

            if current_price is not None and initial_prices.get(pair) is not None:
                initial_price = initial_prices[pair]
                initial_volume = initial_volumes[pair]

                percentage_change = ((current_price - initial_price) / initial_price) * 100
                change_type = '+' if percentage_change > 0 else '-'
                percentage_change = abs(percentage_change)
                volume_change = volume - initial_volume
                volume_change_text = f" (Volume naik Rp. {volume_change:,.0f})" if volume_change > 0 else ""

                if percentage_change >= threshold_percent:
                    chart_link = f'<a href="https://indodax.com/chart/{pair.upper()}">{pair.upper()}</a>'
                    if pair.endswith('usdt'):
                        price_text = f"USD ${current_price:.8f}" if current_price >= 0.01 else f"USD ${current_price:.8e}"
                    else:
                        price_text = f"Rp.{current_price:,.0f}"
                    volume_text = f"Rp.{volume:,.2f}"
                    emoji = "🚀" if change_type == '+' else "🔻"
                    message = f"{emoji} {chart_link} Harga {change_type} <code>{percentage_change:.2f}%</code> " \
                              f"(harga sekarang: {price_text}) Volume {volume_text}{volume_change_text}"
                    await send_telegram_message(message, bot_token, chat_id)

            initial_prices[pair] = current_price
            initial_volumes[pair] = volume

        elapsed_time = time.time() - start_time  # Waktu yang dibutuhkan untuk satu iterasi
        if elapsed_time < interval:  # Menunggu sisa waktu interval
            await asyncio.sleep(interval - elapsed_time)

# Fungsi untuk melakukan koneksi ulang ke API Indodax
async def reconnect_indodax():
    print("Checking connection to Indodax API...")
    while True:
        try:
            response = requests.get("https://indodax.com/api/pairs")
            if response.status_code == 200:
                print("Indodax API > OK")
                return True
            else:
                print("Indodax API > Fail")
        except Exception as e:
            print(f"Error checking connection to Indodax API: {str(e)}")
        await asyncio.sleep(10)  # Delay 10 detik sebelum mencoba kembali

# Fungsi untuk mengecek koneksi bot
async def check_bot_connection():
    print("Checking connection to Telegram Bot...")
    while True:
        try:
            response = requests.get("https://api.telegram.org")
            if response.status_code == 200:
                print("Telegram Bot > OK")
                return True
            else:
                print("Telegram Bot > Fail")
        except Exception as e:
            print(f"Error checking bot connection: {str(e)}")
        await asyncio.sleep(10)  # Delay 10 detik sebelum mencoba kembali

# Fungsi untuk mengecek koneksi secara keseluruhan
async def check_connection(bot_token, chat_id):
    indodax_ok = await reconnect_indodax()
    bot_ok = await check_bot_connection()
    if indodax_ok and bot_ok:
        return True
    else:
        return False

async def main():
    try:
        config = load_config()
        if not config:
            bot_token = input("Masukkan Bot Token: ")
            chat_id = input("Masukkan Chat ID: ")
            threshold_percent = float(input("Masukkan persentase perubahan harga yang diinginkan: "))
            interval = float(input("Masukkan waktu interval pemantauan harga (detik): "))
            
            config = {
                "bot_token": bot_token,
                "chat_id": chat_id,
                "threshold_percent": threshold_percent,
                "interval": interval
            }
            save_config(config)
        else:
            bot_token = config["bot_token"]
            chat_id = config["chat_id"]
            threshold_percent = config["threshold_percent"]
            interval = config["interval"]

        while True:
            connection_ok = await check_connection(bot_token, chat_id)
            if connection_ok:
                await monitor_price_change(bot_token, chat_id, threshold_percent, threshold_price_idr=25, interval=interval)
            else:
                print("Connection failed. Retrying...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Rebooting the bot...")
        await main()  # Reboot the bot

if __name__ == '__main__':
    asyncio.run(main())
                        
