import requests
import asyncio
from telegram import Bot
from emoji import emojize

# Fungsi untuk mengirim pesan ke grup Telegram
async def send_telegram_message(bot_token, chat_id, message):
    bot = Bot(token=bot_token)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")

# Fungsi untuk mendapatkan semua pasangan kripto di Indodax
def get_all_pairs():
    api_url = 'https://indodax.com/api/pairs'
    response = requests.get(api_url)
    data = response.json()
    return [pair['symbol'] for pair in data]

# Fungsi untuk mendapatkan harga kripto
def get_crypto_price(pair):
    api_url = f'https://indodax.com/api/ticker/{pair.lower()}'
    response = requests.get(api_url)

    if response.status_code == 200:
        data = response.json()
        last_price = float(data.get('ticker', {}).get('last', 0))
        return last_price
    else:
        return None

# Fungsi untuk memonitor kenaikan atau penurunan harga
async def monitor_price_change(bot_token, chat_id, threshold_percent=5):
    all_pairs = get_all_pairs()

    # Inisialisasi harga awal untuk setiap pasangan
    initial_prices = {pair: get_crypto_price(pair) for pair in all_pairs}

    print("Bot is running...")  # Menampilkan status bot berjalan

    while True:
        for pair in all_pairs:
            current_price = get_crypto_price(pair)

            if current_price is not None:
                initial_price = initial_prices.get(pair, current_price)

                # Memastikan initial_price tidak sama dengan 0
                if initial_price != 0:
                    percentage_change = ((current_price - initial_price) / initial_price) * 100
                    change_type = 'naik' if percentage_change > 0 else 'turun'
                    percentage_change = abs(percentage_change)
                    if percentage_change >= threshold_percent:
                        if change_type == 'naik':
                            rocket_emoji = emojize(":rocket:")
                            message = f"<b>{pair.upper()}</b> Harga <b>{change_type}</b> {rocket_emoji} <code>{percentage_change:.2f}%</code> " \
                                      f"(harga sekarang: Rp.{current_price:,.0f})"
                        else:
                            fire_emoji = emojize(":fire:")
                            message = f"<b>{pair.upper()}</b> Harga <b>{change_type}</b> {fire_emoji} <code>{percentage_change:.2f}%</code> " \
                                      f"(harga sekarang: Rp.{current_price:,.0f})"
                        await send_telegram_message(bot_token, chat_id, message)
                        print("Notification sent!")  # Menampilkan status notifikasi terkirim

        await asyncio.sleep(15)  # Periksa setiap 15 detik

if __name__ == '__main__':
    # Masukkan token dan chat ID saat runtime
    bot_token = input("Masukkan Bot Token: ")
    chat_id = input("Masukkan Chat ID: ")

    asyncio.run(monitor_price_change(bot_token, chat_id))
