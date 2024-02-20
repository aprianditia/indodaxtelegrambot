import requests
import asyncio
from telegram import Bot
from emoji import emojize

bot_token = "7165336794:AAFn0S4mbtHGBh4nkZb1zxllJWQtBg6QWG0"
chat_id = "-1001625368792"

# Fungsi untuk mengirim pesan ke grup Telegram
async def send_telegram_message(message):
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
async def monitor_price_change(threshold_percent=5, interval=5):
    all_pairs = get_all_pairs()
    initial_prices = {}

    print("Bot is running...")  

    while True:
        for pair in all_pairs:
            current_price = get_crypto_price(pair)

            if current_price is not None:
                initial_price = initial_prices.get(pair, current_price)

                if initial_price != 0:
                    percentage_change = ((current_price - initial_price) / initial_price) * 100
                    change_type = 'naik' if percentage_change > 0 else 'turun'
                    percentage_change = abs(percentage_change)
                    if percentage_change >= threshold_percent:
                        chart_link = f'<a href="https://indodax.com/chart/{pair.upper()}">{pair.upper()}</a>'
                        if pair.endswith('usdt'):
                            price_text = f"USD ${current_price:,.2f}"
                        else:
                            price_text = f"Rp.{current_price:,.0f}"
                        if change_type == 'naik':
                            rocket_emoji = emojize(":rocket:")
                            message = f"{chart_link} Harga {change_type} {rocket_emoji} <code>{percentage_change:.2f}%</code> " \
                                      f"(harga sekarang: {price_text})"
                        else:
                            fire_emoji = emojize(":fire:")
                            message = f"{chart_link} Harga {change_type} {fire_emoji} <code>{percentage_change:.2f}%</code> " \
                                      f"(harga sekarang: {price_text})"
                        await send_telegram_message(message)
                        print("Notification sent!")  

                initial_prices[pair] = current_price

        await asyncio.sleep(interval)

# Fungsi untuk memonitor kenaikan volume
async def monitor_volume_increase(threshold_volume=3000, interval=30):
    print("Monitoring volume...")

    while True:
        try:
            api_url = 'https://indodax.com/api/tickers'
            response = requests.get(api_url)
            data = response.json()

            for pair_data in data.values():
                volume = float(pair_data.get('vol_idr', 0))
                pair = pair_data.get('pair')

                if volume >= threshold_volume:
                    message = f"Volume untuk pasangan {pair} telah naik secara drastis menjadi {volume} IDR dalam 5 menit terakhir!"
                    await send_telegram_message(message)
                    print("Volume notification sent!")

            await asyncio.sleep(interval)
        except Exception as e:
            print(f"An error occurred while monitoring volume: {str(e)}")

# Fungsi untuk melakukan koneksi ulang
async def reconnect():
    print("Connection lost. Reconnecting...")
    while True:
        try:
            await asyncio.sleep(10)  # Delay 10 detik sebelum mencoba kembali
            response = requests.get("https://indodax.com/api/pairs")
            if response.status_code == 200:
                print("Reconnected successfully!")
                return True
        except Exception as e:
            print(f"Reconnection failed: {str(e)}")
            continue

async def main():
    while True:
        try:
            task1 = asyncio.create_task(monitor_price_change())
            task2 = asyncio.create_task(monitor_volume_increase())
            await asyncio.gather(task1, task2)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            await reconnect()

if __name__ == '__main__':
    asyncio.run(main())
