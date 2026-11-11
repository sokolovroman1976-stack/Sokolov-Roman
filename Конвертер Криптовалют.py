import requests
import tkinter as tk
from tkinter import ttk, messagebox

# Топ монет: название -> id на CoinGecko
COINS = {
    "Bitcoin": "bitcoin",
    "Ethereum": "ethereum",
    "Tether": "tether",
    "BNB": "binancecoin",
    "Solana": "solana",
    "XRP": "ripple",
    "Dogecoin": "dogecoin",
    "Cardano": "cardano",
    "TRON": "tron",
    "Chainlink": "chainlink",
}


def get_price_usd(coin_id):
    """Текущая цена монеты в USD."""
    r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                     params={"ids": coin_id, "vs_currencies": "usd"},
                     timeout=10)
    return r.json()[coin_id]["usd"]


def get_usd_rub():
    """Курс USD/RUB от ЦБ РФ."""
    r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
    return r.json()["Valute"]["USD"]["Value"]


def convert():
    coin = coins_box.get()
    try:
        amount = float(amount_entry.get().replace(",", "."))
    except ValueError:
        messagebox.showerror("Ошибка", "Введите число")
        return

    try:
        price = get_price_usd(COINS[coin])
        result = amount * price
        if currency_box.get() == "RUB":
            result *= get_usd_rub()
        result_label.config(text=f"{amount:g} {coin} = {result:,.2f} {currency_box.get()}")
    except Exception:
        messagebox.showerror("Ошибка", "Нет подключения к интернету")


root = tk.Tk()
root.title("Конвертер: Крипта → USD / RUB")
root.geometry("320x320")

tk.Label(root, text="Криптовалюта").pack(pady=(15, 0))
coins_box = ttk.Combobox(root, values=list(COINS), state="readonly", width=22)
coins_box.set("Bitcoin")
coins_box.pack()

tk.Label(root, text="Количество монет").pack(pady=(10, 0))
amount_entry = ttk.Entry(root, justify="center", width=22)
amount_entry.insert(0, "1")
amount_entry.pack()

tk.Label(root, text="В валюту").pack(pady=(10, 0))
currency_box = ttk.Combobox(root, values=["USD", "RUB"], state="readonly", width=22)
currency_box.set("USD")
currency_box.pack()

ttk.Button(root, text="Конвертировать", command=convert).pack(pady=15)

result_label = tk.Label(root, text="", font=("Arial", 12, "bold"))
result_label.pack()

tk.Label(root, text="Курс USD/RUB берётся от ЦБ РФ", font=("Arial", 8), fg="gray").pack(side="bottom", pady=5)

root.mainloop()
