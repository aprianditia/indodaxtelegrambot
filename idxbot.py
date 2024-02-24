import requests
import asyncio
from telegram import Bot
from emoji import emojize
import json
import time
from datetime import timedelta
from async_lru import alru_cache

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

# Semaphore untuk membatasi jumlah permintaan ke API
api_semaphore = asyncio.Semaphore(180)

# Fungsi untuk membatasi permintaan ke API Indodax
async def api_limiter():
    async with api_semaphore:
        await asyncio.sleep(1)

# Fungsi untuk memonitor kenaikan atau penurunan harga
async def monitor_price_change(bot_token, chat_id, threshold_percent=5, threshold_price_idr=25, threshold_volume_idr=400_000_000, interval=15):
    all_pairs = get_all_pairs()
    initial_prices = {}

    print("Initiating Bot...")
    print("Bot is running... Monitoring Price change..")

    while True:
        start_time = time.time()  # Waktu awal permintaan
        for pair in all_pairs:
            await api_limiter()  # Menerapkan pembatasan permintaan
            current_price, volume = await get_crypto_data(pair)

            if current_price is None or volume is None:
                continue

            if current_price < threshold_price_idr or volume < threshold_volume_idr:
                continue

            initial_price = initial_prices.get(pair, current_price)

            if initial_price != 0:
                percentage_change = ((current_price - initial_price) / initial_price) * 100
                change_type = 'naik' if percentage_change > 0 else 'turun'
                percentage_change = abs(percentage_change)
                if percentage_change >= threshold_percent:
                    chart_link = f'<a href="https://indodax.com/chart/{pair.upper()}">{pair.upper()}</a>'
                    if pair.endswith('usdt'):
                        price_text = f"USD ${current_price:.8f}" if current_price >= 0.01 else f"USD ${current_price:.8e}"
                    else:
                        price_text = f"Rp.{current_price:,.0f}"
                    volume_text = f"IDR {volume:,.0f}"
                    if change_type == 'naik':
                        emoji = emojize(":rocket:")
                        message = f"{chart_link} Harga {change_type} {emoji} <code>+{percentage_change:.2f}%</code> " \
                                  f"(harga sekarang: {price_text}) Volume {volume_text}"
                    else:
                        emoji = emojize(":fire:")
                        message = f"{chart_link} Harga {change_type} {emoji} <code>-{percentage_change:.2f}%</code> " \
                                  f"(harga sekarang: {price_text}) Volume {volume_text}"
                    await send_telegram_message(message, bot_token, chat_id)

            initial_prices[pair] = current_price

        elapsed_time = time.time() - start_time  # Waktu yang dibutuhkan untuk satu iterasi
        if elapsed_time < interval:  # Menunggu sisa waktu interval
            await asyncio.sleep(interval - elapsed_time)

# Fungsi untuk memantau volume selama 5 menit
async def monitor_volume(bot_token, chat_id, interval=300, threshold_volume=200_000_000):
    all_pairs = get_all_pairs()
    initial_volumes = {}

    print("Bot is running... Monitoring Volume change..")

    while True:
        start_time = time.time()  # Waktu awal pemantauan
        for pair in all_pairs:
            await api_limiter()  # Menerapkan pembatasan permintaan
            _, volume = await get_crypto_data(pair)

            if volume is not None:
                initial_volume = initial_volumes.get(pair, volume)

                if initial_volume != 0:
                    volume_change = volume - initial_volume

                    if volume_change >= threshold_volume:
                        volume_text = f"IDR {volume:,.0f}"
                        duration = timedelta(seconds=int(time.time() - start_time))
                        message = f"Volume {pair.upper()} naik 🚀 sebesar {volume_change:,.0f} IDR dalam waktu {duration} (Volume sekarang: {volume_text})"
                        await send_telegram_message(message, bot_token, chat_id)

                initial_volumes[pair] = volume

        elapsed_time = time.time() - start_time  # Waktu yang dibutuhkan untuk satu iterasi
        if elapsed_time < interval:  # Menunggu sisa waktu interval
            await asyncio.sleep(interval - elapsed_time)

# Fungsi untuk melakukan koneksi ulang ke API Indodax
async def reconnect_indodax():
    print("Checking connection to Indodax API...")
    while True:
        try:
            start_time = time.time()
            await api_limiter()  # Menerapkan pembatasan permintaan
            response = requests.get("https://indodax.com/api/pairs")
            latency = time.time() - start_time
            if response.status_code == 200:
                print(f"Indodax API > OK ({latency} seconds)")
                return True
            else:
                print(f"Indodax API > Fail ({latency} seconds)")
        except Exception as e:
            print(f"Error checking connection to Indodax API: {str(e)}")
        await asyncio.sleep(10)  # Delay 10 detik sebelum mencoba kembali

# Fungsi untuk mengecek koneksi bot
async def check_bot_connection():
    print("Checking connection to Telegram Bot...")
    while True:
        try:
            start_time = time.time()
            await api_limiter()  # Menerapkan pembatasan permintaan
            response = requests.get("https://api.telegram.org")
            latency = time.time() - start_time
            if response.status_code == 200:
                print(f"Telegram Bot > OK ({latency} seconds)")
                return True
            else:
                print(f"Telegram Bot > Fail ({latency} seconds)")
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
            volume_threshold = float(input("Masukkan ambang batas volume (IDR): "))
            volume_interval = int(input("Masukkan interval waktu pemantauan volume (detik): "))

            config = {
                "bot_token": bot_token,
                "chat_id": chat_id,
                "threshold_percent": threshold_percent,
                "interval": interval,
                "volume_threshold": volume_threshold,
                "volume_interval": volume_interval
            }
            save_config(config)
        else:
            bot_token = config["bot_token"]
            chat_id = config["chat_id"]
            threshold_percent = config["threshold_percent"]
            interval = config["interval"]
            volume_threshold = config.get("volume_threshold", None)
            volume_interval = config.get("volume_interval", None)

        while True:
            connection_ok = await check_connection(bot_token, chat_id)
            if connection_ok:
                tasks = [monitor_price_change(bot_token, chat_id, threshold_percent, threshold_price_idr=25, threshold_volume_idr=volume_threshold, interval=interval)]
                if volume_threshold is not None and volume_interval is not None:
                    tasks.append(monitor_volume(bot_token, chat_id, volume_interval, volume_threshold))
                await asyncio.gather(*tasks)
            else:
                print("Connection failed. Retrying...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Rebooting the bot...")
        await main()  # Reboot the bot

if __name__ == '__main__':
    asyncio.run(main())
