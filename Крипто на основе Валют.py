import tkinter as tk
from tkinter import ttk
import requests
import json
import os
import time

# --- НАСТРОЙКИ ---
json_path = 'cripto.json'
CACHE_TTL = 300  # кэшировать курс ЦБ на 5 минут

# Глобальные переменные для кэша курса USD/RUB
usd_rub_rate = None
last_cache_time = 0

# --- ЗАГРУЗКА И ФОРМИРОВАНИЕ СПИСКА МОНЕТ ---
# Сначала самые популярные — в таком порядке они будут в начале списка
top_coins = [
    "Bitcoin", "Ethereum", "Solana", "Cardano", "Ripple",
    "Toncoin", "Dogecoin", "Polkadot", "Litecoin", "Chainlink"
]

cripto = {}

# Загружаем JSON или используем запасной словарь
if os.path.exists(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            cripto = json.load(f)
            if not isinstance(cripto, dict):
                raise ValueError
    except Exception:
        cripto = {
            "Bitcoin": "bitcoin", "Ethereum": "ethereum", "Solana": "solana",
            "Cardano": "cardano", "Ripple": "ripple", "Toncoin": "toncoin",
            "Dogecoin": "dogecoin", "Polkadot": "polkadot", "Litecoin": "litecoin",
            "Chainlink": "chainlink", "Avalanche": "avalanche-2", "Polygon": "polygon",
            "Cosmos": "cosmos", "Near Protocol": "near", "Algorand": "algorand",
            "VeChain": "vechain", "Fantom": "fantom", "Terra Luna Classic": "terra-luna-classic",
            "Monero": "monero", "Zcash": "zcash"
        }
else:
    cripto = {
        "Bitcoin": "bitcoin", "Ethereum": "ethereum", "Solana": "solana",
        "Cardano": "cardano", "Ripple": "ripple", "Toncoin": "toncoin",
        "Dogecoin": "dogecoin", "Polkadot": "polkadot", "Litecoin": "litecoin",
        "Chainlink": "chainlink", "Avalanche": "avalanche-2", "Polygon": "polygon",
        "Cosmos": "cosmos", "Near Protocol": "near", "Algorand": "algorand",
        "VeChain": "vechain", "Fantom": "fantom", "Terra Luna Classic": "terra-luna-classic",
        "Monero": "monero", "Zcash": "zcash"
    }

# Формируем итоговый список: сначала топ-монеты (если они есть в словаре), потом все остальные без сортировки
crypto_names = []
added = set()

# Добавляем топ-монеты, если они есть в cripto
for name in top_coins:
    if name in cripto and name not in added:
        crypto_names.append(name)
        added.add(name)

# Потом добавляем остальные монеты в том порядке, в котором они идут в словаре (без sorted)
for name in cripto.keys():
    if name not in added:
        crypto_names.append(name)
        added.add(name)


def get_usd_rub_rate():
    """Получает курс USD/RUB от ЦБ РФ с простым кэшированием."""
    global usd_rub_rate, last_cache_time
    now = time.time()

    if usd_rub_rate is not None and (now - last_cache_time) < CACHE_TTL:
        return usd_rub_rate

    try:
        resp = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        usd_rub_rate = float(data["Valute"]["USD"]["Value"])
        last_cache_time = now
        return usd_rub_rate
    except Exception as e:
        print(f"Ошибка получения курса ЦБ: {e}")
        return None


def update_label(label_widget, event):
    name = event.widget.get()
    label_widget.config(text=name)


def exchange():
    base_name = base_combobox.get().strip()
    target_currency = target_combobox.get().strip()  # USD или RUB
    amount_str = amount_entry.get().strip()

    if not base_name:
        result_label.config(text="Выберите криптовалюту", fg="red")
        return
    if target_currency not in ("USD", "RUB"):
        result_label.config(text="Выберите валюту: USD или RUB", fg="red")
        return

    try:
        amount = float(amount_str)
        if amount <= 0:
            result_label.config(text="Сумма должна быть больше нуля", fg="red")
            return
    except ValueError:
        result_label.config(text="Введите корректное число (например, 1 или 0.5)", fg="red")
        return

    base_id = cripto.get(base_name)
    if not base_id:
        result_label.config(text="Неверный выбор монеты", fg="red")
        return

    # Получаем курс USD/RUB
    usd_to_rub = get_usd_rub_rate()
    if usd_to_rub is None:
        result_label.config(
            text="Ошибка: не удалось получить курс USD/RUB (нет интернета или сервис ЦБ недоступен)",
            fg="red"
        )
        return

    # Получаем курс криптовалюты к USD (CoinGecko)
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={base_id}&vs_currencies=usd"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        base_rate_usd = data[base_id]['usd']
    except requests.exceptions.Timeout:
        result_label.config(text="Ошибка: превышено время ожидания ответа CoinGecko", fg="red")
        return
    except requests.exceptions.ConnectionError:
        result_label.config(text="Ошибка: нет соединения с интернетом", fg="red")
        return
    except KeyError:
        result_label.config(text="Ошибка: не удалось получить курс монеты", fg="red")
        return
    except Exception as e:
        result_label.config(text=f"Ошибка: {e}", fg="red")
        return

    # Считаем результат
    if target_currency == "USD":
        converted = amount * base_rate_usd
        msg = f"{amount:,.6f} {base_name} = {converted:,.2f} USD"
    else:  # RUB
        converted_usd = amount * base_rate_usd
        converted_rub = converted_usd * usd_to_rub
        msg = (
            f"{amount:,.4f} {base_name}\n"
            f"= {converted_usd:,.2f} USD\n\n"
            f"= {converted_rub:,.2f} RUB\n"
            f"(курс USD/RUB: {usd_to_rub:.2f})"
        )

    result_label.config(text=msg, fg="darkblue")
# --- Управление кнопками после конвертации ---
def show_history_buttons():
    # Если кнопки уже есть — ничего не делаем
    if btn_save_history.winfo_ismapped() and btn_show_history.winfo_ismapped():
        return
    btn_save_history.pack(side="left", padx=5, pady=5)
    btn_show_history.pack(side="left", padx=5, pady=5)

# --- Цена на конкретную дату (отдельное окно с результатом) ---
def get_price_on_date():
    date_str = entry_date.get().strip()
    selected = target_combobox.get()
    if " | " not in selected:
        label_status.config(text="Сначала выберите монету", fg="orange")
        return
    if not date_str:
        label_status.config(text="Введите дату в формате ДД-ММ-ГГГГ", fg="orange")
        return

    coin_name, coin_id = selected.split(" | ")
    url = API_URL_HISTORY.format(coin_id=coin_id)
    params = {"date": date_str}



# --- Показать историю в отдельном окне ---
def show_history():
    selected = crypto_combobox.get()
    if " | " not in selected:
        return
    _, coin_id = selected.split(" | ")

    history = load_history()
    records = history.get(coin_id, [])

    if not records:
        label_status.config(text="Нет сохранённых данных для этой монеты", fg="orange")
        return



# --- Управление кнопками после конвертации ---
def show_history_buttons():
    # Если кнопки уже есть — ничего не делаем
    if btn_save_history.winfo_ismapped() and btn_show_history.winfo_ismapped():
        return
    btn_save_history.pack(side="left", padx=5, pady=5)
    btn_show_history.pack(side="left", padx=5, pady=5)

# --- ИНТЕРФЕЙС ---
root = tk.Tk()
root.title('Конвертер: Крипта → USD / RUB')
root.geometry('400x600')

# 1. Криптовалюта
tk.Label(root, text='Криптовалюта').pack(pady=(20, 5))
base_combobox = ttk.Combobox(root, values=crypto_names, state='readonly')
base_combobox.pack()
base_combobox.set(crypto_names[0])
base_combobox.bind('<<ComboboxSelected>>', lambda e: update_label(base_label, e))

base_label = ttk.Label(root, font=('Arial', 10, 'bold'))
base_label.pack()
# Инициализация текста метки
update_label(base_label, type('Event', (object,), {'widget': base_combobox})())

# 2. Сумма (сразу после криптовалюты)
ttk.Label(root, text='Количество монет').pack(pady=(15, 5))
amount_entry = ttk.Entry(root)
amount_entry.pack()
amount_entry.insert(0, "1")

# 3. В валюту
tk.Label(root, text='В валюту').pack(pady=(15, 5))
target_combobox = ttk.Combobox(root, values=["USD", "RUB"], state='readonly')
target_combobox.pack()
target_combobox.set("USD")

btn = tk.Button(root, text='Конвертировать', command=exchange, bg="#dddddd")
btn.pack(pady=20)

result_label = tk.Label(
    root,
    text="Нажмите «Конвертировать»\n\n Курс USD/RUB берётся от ЦБ РФ",
    font=('Arial', 9, 'bold'),
    justify='center',
    wraplength=380,
    height=5
)
result_label.pack(pady=10)

# Кнопки «Сохранить в историю» и «Показать историю» (скрыты по умолчанию)
history_frame = tk.Frame(root)
history_frame.pack(pady=5)
btn_save_history = ttk.Button(history_frame, text="Сохранить в историю", command=lambda: None)
btn_show_history = ttk.Button(history_frame, text="Показать историю", command=show_history)
# Кнопку «Сохранить» заменим на реальную логику при вызове
btn_save_history.config(command=lambda: save_current_from_labels())

def save_current_from_labels():
    selected = crypto_combobox.get()
    if " | " not in selected:
        label_status.config(text="Сначала обновите курс", fg="orange")
        return
    coin_name, coin_id = selected.split(" | ")
    # Берём цену из метки (она уже отформатирована, но нам нужно число)
    price_text = label_price.cget("text")
    # Убираем «Цена: » и « USD», конвертируем
    try:
        price_val = float(price_text.replace("Цена: ", "").replace(" USD", "").replace(",", ""))
        change_text = label_change.cget("text")
        change_val = float(change_text.replace("Изменение за 24 ч: ", "").replace("%", ""))
        add_to_history(coin_name, coin_id, price_val, change_val)
    except ValueError:
        label_status.config(text="Не удалось извлечь цену для сохранения", fg="red")

# Блок: цена на дату
ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)
ttk.Label(root, text="Цена на конкретную дату").pack(anchor="w", padx=10)

ttk.Label(root, text="Дата (ДД-ММ-ГГГГ):").pack(anchor="w", padx=10)
entry_date = ttk.Entry(root, width=20)
entry_date.pack(anchor="w", padx=10, pady=2)
ttk.Button(root, text="Получить цену на дату", command=get_price_on_date).pack(pady=5)

# Статус
label_status = tk.Label(root, font=("Arial", 9), justify="center", fg="gray")
label_status.pack(side="bottom", pady=5)
root.mainloop()
