import requests
import asyncio
from telegram import Bot
from emoji import emojize
import json
from datetime import datetime, timedelta
import time
from functools import lru_cache

bot_token = "7165336794:AAFn0S4mbtHGBh4nkZb1zxllJWQtBg6QWG0"
chat_id = "-1001625368792"
config_file = "config.json"
stop_flag_file = "stop_flag.txt"

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

# Fungsi untuk mengatur penanda bahwa bot berhenti
def set_stop_flag():
    with open(stop_flag_file, "w") as f:
        f.write("1")

# Fungsi untuk memeriksa apakah bot berhenti secara normal
def is_stopped_normally():
    try:
        with open(stop_flag_file, "r") as f:
            content = f.read()
            return content.strip() != "1"
    except FileNotFoundError:
        return True

# Fungsi untuk menghapus penanda bot berhenti
def clear_stop_flag():
    try:
        os.remove(stop_flag_file)
    except FileNotFoundError:
        pass

# Fungsi untuk mengirim pesan ke grup Telegram
async def send_telegram_message(message):
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
@lru_cache(maxsize=128)
def get_crypto_data(pair):
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
async def monitor_price_change(threshold_percent=5, interval=5, blacklist_price=15):
    all_pairs = get_all_pairs()
    initial_prices = {}

    print("Initiating Bot...")
    print("Bot is running... Monitoring Price change..")

    while True:
        if is_stopped_normally():
            start_time = time.time()  # Waktu awal permintaan
            for pair in all_pairs:
                await api_limiter()  # Menerapkan pembatasan permintaan
                current_price, volume = get_crypto_data(pair)

                # Skip pair dengan harga di bawah threshold untuk IDR
                if pair.endswith('idr') and current_price is not None and current_price < blacklist_price:
                    continue

                if current_price is not None:
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
                            await send_telegram_message(message)

                    initial_prices[pair] = current_price

            elapsed_time = time.time() - start_time  # Waktu yang dibutuhkan untuk satu iterasi
            if elapsed_time < interval:  # Menunggu sisa waktu interval
                await asyncio.sleep(interval - elapsed_time)
        else:
            print("Bot stopped manually. Exiting...")
            break

# Fungsi untuk memantau volume selama 5 menit
async def monitor_volume(interval=300, threshold_volume=200_000_000):
    all_pairs = get_all_pairs()
    initial_volumes = {}

    print("Bot is running... Monitoring Volume change..")

    while True:
        if is_stopped_normally():
            start_time = time.time()  # Waktu awal pemantauan
            for pair in all_pairs:
                await api_limiter()  # Menerapkan pembatasan permintaan
                _, volume = get_crypto_data(pair)

                if volume is not None:
                    initial_volume = initial_volumes.get(pair, volume)

                    if initial_volume != 0:
                        volume_change = volume - initial_volume

                        if volume_change >= threshold_volume:
                            volume_text = f"IDR {volume:,.0f}"
                            duration = timedelta(seconds=int(time.time() - start_time))
                            message = f"Volume {pair.upper()} naik 🚀 sebesar {volume_change:,.0f} IDR dalam waktu {duration} (Volume sekarang: {volume_text})"
                            await send_telegram_message(message)

                    initial_volumes[pair] = volume

            elapsed_time = time.time() - start_time  # Waktu yang dibutuhkan untuk satu iterasi
            if elapsed_time < interval:  # Menunggu sisa waktu interval
                await asyncio.sleep(interval - elapsed_time)
        else:
            print("Bot stopped manually. Exiting...")
            break

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
async def check_connection():
    indodax_ok = await reconnect_indodax()
    bot_ok = await check_bot_connection()
    if indodax_ok and bot_ok:
        return True
    else:
        return False

async def main():
    try:
        while True:
            config = load_config()
            if not config:
                threshold_percent = float(input("Masukkan persentase perubahan harga yang diinginkan: "))
                interval = float(input("Masukkan waktu interval pemantauan harga (detik): "))
                volume_threshold = float(input("Masukkan ambang batas volume (IDR): "))
                volume_interval = int(input("Masukkan interval waktu pemantauan volume (detik): "))
                config = {
                    "threshold_percent": threshold_percent,
                    "interval": interval,
                    "volume_threshold": volume_threshold,
                    "volume_interval": volume_interval
                }
                save_config(config)
            else:
                threshold_percent = config["threshold_percent"]
                interval = config["interval"]
                volume_threshold = config.get("volume_threshold", None)
                volume_interval = config.get("volume_interval", None)

            connection_ok = await check_connection()
            if connection_ok:
                tasks = [monitor_price_change(threshold_percent, interval)]
                if volume_threshold is not None and volume_interval is not None:
                    tasks.append(monitor_volume(volume_interval, volume_threshold))
                await asyncio.gather(*tasks)
            else:
                print("Connection failed. Retrying...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Rebooting the bot...")
        await main()  # Reboot the bot

if __name__ == '__main__':
    asyncio.run(main())
