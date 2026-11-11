import tkinter as tk
from tkinter import ttk
import requests
import json
import os
import time
from datetime import datetime

# --- НАСТРОЙКИ ---
json_path = 'cripto.json'
history_file = 'crypto_history.json'
CACHE_TTL = 300  # кэшировать курс ЦБ на 5 минут

# Глобальные переменные для кэша курса USD/RUB
usd_rub_rate = None
last_cache_time = 0

# --- ЗАГРУЗКА И ФОРМИРОВАНИЕ СПИСКА МОНЕТ ---
top_coins = [
    "Bitcoin", "Ethereum", "Solana", "Cardano", "Ripple",
    "Toncoin", "Dogecoin", "Polkadot", "Litecoin", "Chainlink"
]

cripto = {}

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

crypto_names = []
added = set()

for name in top_coins:
    if name in cripto and name not in added:
        crypto_names.append(name)
        added.add(name)

for name in cripto.keys():
    if name not in added:
        crypto_names.append(name)
        added.add(name)


# --- РАБОТА С ИСТОРИЕЙ ---
def load_history():
    if not os.path.exists(history_file):
        return {}
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_history(history):
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError as e:
        label_status.config(text=f"Ошибка сохранения истории: {e}", fg="red")


def add_to_history(coin_name, coin_id, price_usd, change_24h):
    history = load_history()
    record = {
        "name": coin_name,
        "id": coin_id,
        "price_usd": price_usd,
        "change_24h": change_24h,
        "timestamp": datetime.now().isoformat(),
        "type": "current",
    }
    if coin_id not in history:
        history[coin_id] = []
    history[coin_id].append(record)
    save_history(history)
    label_status.config(text="Статус: запись добавлена в историю", fg="green")


# --- КУРС USD/RUB ОТ ЦБ ---
def get_usd_rub_rate():
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


# --- КОНВЕРТАЦИЯ ---
def exchange():
    base_name = base_combobox.get().strip()
    target_currency = target_combobox.get().strip()  # USD или RUB
    amount_str = amount_entry.get().strip()

    if not base_name:
        result_label.config(text="Выберите криптовалюту", fg="red")
        clear_history_buttons()
        return
    if target_currency not in ("USD", "RUB"):
        result_label.config(text="Выберите валюту: USD или RUB", fg="red")
        clear_history_buttons()
        return

    try:
        amount = float(amount_str)
        if amount <= 0:
            result_label.config(text="Сумма должна быть больше нуля", fg="red")
            clear_history_buttons()
            return
    except ValueError:
        result_label.config(text="Введите корректное число (например, 1 или 0.5)", fg="red")
        clear_history_buttons()
        return

    base_id = cripto.get(base_name)
    if not base_id:
        result_label.config(text="Неверный выбор монеты", fg="red")
        clear_history_buttons()
        return

    usd_to_rub = get_usd_rub_rate()
    if usd_to_rub is None:
        result_label.config(
            text="Ошибка: не удалось получить курс USD/RUB (нет интернета или сервис ЦБ недоступен)",
            fg="red"
        )
        clear_history_buttons()
        return

    # Получаем курс криптовалюты к USD (CoinGecko)
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={base_id}&vs_currencies=usd&include_24hr_change=true"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        base_rate_usd = data[base_id]['usd']
        change_24h = data[base_id].get('usd_24h_change', 0.0)
    except requests.exceptions.Timeout:
        result_label.config(text="Ошибка: превышено время ожидания ответа CoinGecko", fg="red")
        clear_history_buttons()
        return
    except requests.exceptions.ConnectionError:
        result_label.config(text="Ошибка: нет соединения с интернетом", fg="red")
        clear_history_buttons()
        return
    except KeyError:
        result_label.config(text="Ошибка: не удалось получить курс монеты", fg="red")
        clear_history_buttons()
        return
    except Exception as e:
        result_label.config(text=f"Ошибка: {e}", fg="red")
        clear_history_buttons()
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

    # Сохраняем в историю автоматически
    add_to_history(base_name, base_id, base_rate_usd, change_24h)

    # Показываем кнопки
    show_history_buttons()


# --- УПРАВЛЕНИЕ КНОПКАМИ ИСТОРИИ ---
def clear_history_buttons():
    btn_save_history.pack_forget()
    btn_show_history.pack_forget()


def show_history_buttons():
    if btn_save_history.winfo_ismapped() and btn_show_history.winfo_ismapped():
        return
    btn_save_history.pack(side="left", padx=5, pady=5)
    btn_show_history.pack(side="left", padx=5, pady=5)


def save_current_from_labels():
    label_status.config(text="Запись уже сохранена автоматически при конвертации", fg="orange")


# --- ЦЕНА НА ДАТУ (В ТОМ ЖЕ ОКНЕ) ---
API_URL_HISTORY = "https://api.coingecko.com/api/v3/coins/{coin_id}/history"


def get_price_on_date():
    date_str = entry_date.get().strip()
    selected_name = base_combobox.get()

    if not selected_name:
        label_status.config(text="Сначала выберите монету", fg="orange")
        price_on_date_label.config(text="", fg="black")
        return

    if not date_str:
        label_status.config(text="Введите дату в формате ДД-ММ-ГГГГ", fg="orange")
        price_on_date_label.config(text="", fg="black")
        return

    coin_id = cripto.get(selected_name)
    if not coin_id:
        label_status.config(text="Неверная монета", fg="red")
        price_on_date_label.config(text="", fg="black")
        return

    url = API_URL_HISTORY.format(coin_id=coin_id)
    params = {"date": date_str}

    # Блокируем кнопку и показываем «Загрузка»
    btn_date.config(state="disabled")
    price_on_date_label.config(text="Загрузка...", fg="gray")
    label_status.config(text="Запрос к API CoinGecko...", fg="blue")

    def fetch_and_show():
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            market_data = data.get("market_data", {})
            current_price = market_data.get("current_price", {})
            price_usd = current_price.get("usd")

            if price_usd is not None:
                price_on_date_label.config(
                    text=f"Цена {selected_name} на {date_str}: {price_usd:,.2f} USD",
                    fg="#005500"
                )
                label_status.config(text=f"Статус: цена на {date_str} получена", fg="green")
            else:
                price_on_date_label.config(
                    text="Нет данных о цене на эту дату",
                    fg="orange"
                )
                label_status.config(text="Статус: нет исторических данных", fg="orange")
        except requests.exceptions.HTTPError as e:
            price_on_date_label.config(text=f"Ошибка API: {e.response.status_code}", fg="red")
            label_status.config(text="Ошибка API", fg="red")
        except requests.exceptions.RequestException:
            price_on_date_label.config(text="Ошибка сети", fg="red")
            label_status.config(text="Ошибка сети", fg="red")
        except Exception:
            price_on_date_label.config(text="Внутренняя ошибка", fg="red")
            label_status.config(text="Внутренняя ошибка", fg="red")
        finally:
            btn_date.config(state="normal")

    root.after(0, fetch_and_show)


# --- ПОКАЗАТЬ ИСТОРИЮ ---
def show_history():
    selected_name = base_combobox.get()
    if not selected_name:
        label_status.config(text="Сначала выберите монету", fg="orange")
        return

    coin_id = cripto.get(selected_name)
    if not coin_id:
        label_status.config(text="Неверная монета", fg="red")
        return

    history = load_history()
    records = history.get(coin_id, [])

    if not records:
        label_status.config(text="Нет сохранённых данных для этой монеты", fg="orange")
        return

    # Окно истории: в заголовок добавляем название монеты
    hist_win = tk.Toplevel(root)
    hist_win.title(f"История запросов: {selected_name}")
    hist_win.geometry("650x450")

    tree = ttk.Treeview(hist_win, columns=("name", "time", "price", "change", "type"), show="headings", height=17)

    # Добавляем колонку с названием монеты
    tree.heading("name", text="Монета")
    tree.heading("time", text="Время/Дата")
    tree.heading("price", text="Цена (USD)")
    tree.heading("change", text="Изменение 24ч (%)")
    tree.heading("type", text="Тип")

    tree.column("name", width=120, anchor="w")
    tree.column("time", width=160)
    tree.column("price", width=120, anchor="e")
    tree.column("change", width=130, anchor="e")
    tree.column("type", width=80, anchor="center")

    for r in records:
        time_str = r["timestamp"][:19]
        typ = r.get("type", "unknown")
        # В каждую строку явно пишем название монеты
        tree.insert(
            "", "end",
            values=(selected_name, time_str, f"{r['price_usd']:,.2f}", f"{r.get('change_24h', 0):.2f}", typ)
        )

    tree.pack(fill="both", expand=True, padx=10, pady=10)

    ttk.Button(hist_win, text="Закрыть", command=hist_win.destroy).pack(pady=5)



# --- ИНТЕРФЕЙС ---
root = tk.Tk()
root.title('Конвертер: Крипта → USD / RUB')
root.geometry('400x650')

# 1. Криптовалюта
tk.Label(root, text='Криптовалюта').pack(pady=(20, 5))
base_combobox = ttk.Combobox(root, values=crypto_names, state='readonly')
base_combobox.pack()
base_combobox.set(crypto_names[0])

base_label = ttk.Label(root, font=('Arial', 10, 'bold'))
base_label.pack()


def update_label(event):
    name = event.widget.get()
    base_label.config(text=name)


base_combobox.bind('<<ComboboxSelected>>', update_label)
base_label.config(text=base_combobox.get())

# 2. Сумма
ttk.Label(root, text='Количество монет').pack(pady=(15, 5))
amount_entry = ttk.Entry(root)
amount_entry.pack()
amount_entry.insert(0, "1")

# 3. В валюту
ttk.Label(root, text='В валюту').pack(pady=(15, 5))
target_combobox = ttk.Combobox(root, values=["USD", "RUB"], state='readonly')
target_combobox.pack()
target_combobox.set("USD")

# Кнопка конвертации
btn = tk.Button(root, text='Конвертировать', command=exchange, bg="#dddddd")
btn.pack(pady=20)

# Результат
result_label = tk.Label(
    root,
    text="Нажмите «Конвертировать»\n\nКурс USD/RUB берётся от ЦБ РФ",
    font=('Arial', 9, 'bold'),
    justify='center',
    wraplength=380,
    height=5
)
result_label.pack(pady=10)

# Блок кнопок истории (по умолчанию скрыты)
history_frame = tk.Frame(root)
history_frame.pack(pady=5)

btn_save_history = ttk.Button(history_frame, text="Сохранить в историю", command=save_current_from_labels)
btn_show_history = ttk.Button(history_frame, text="Показать историю", command=show_history)

# Статусная строка
label_status = tk.Label(root, font=("Arial", 9), justify="center", fg="gray")
label_status.pack(side="bottom", pady=5)

# Разделитель и блок «Цена на дату»
ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)
ttk.Label(root, text="Цена на конкретную дату (не ранее 01-01-2026)" ).pack(anchor="w", padx=10)

ttk.Label(root, text="Формат (ДД-ММ-ГГГГ):").pack(anchor="w", padx=10)
entry_date = ttk.Entry(root, width=20)
entry_date.pack(anchor="w", padx=10, pady=2)

# Кнопка «Получить цену на дату»
btn_date = ttk.Button(root, text="Показать стоимость на эту дату", command=get_price_on_date)
btn_date.pack(pady=5)

# Метка для вывода цены на дату (прямо в главном окне)
price_on_date_label = tk.Label(
    root,
    text="",
    font=("Arial", 10, "bold"),
    fg="black",
    justify="center"
)
price_on_date_label.pack(pady=(0, 15))

root.mainloop()

