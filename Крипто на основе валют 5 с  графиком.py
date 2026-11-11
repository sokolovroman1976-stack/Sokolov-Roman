import tkinter as tk
from tkinter import ttk
import requests
import json
import os
import threading
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ================= КОНФИГУРАЦИЯ =================
API_URL_PRICE = "https://api.coingecko.com/api/v3/simple/price"
API_URL_HISTORY = "https://api.coingecko.com/api/v3/coins/{coin_id}/history"
API_URL_MARKET_CHART = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
CB_API_URL = "https://open.er-api.com/v6/latest/USD"
HEADERS = {"Accept": "application/json"}
DATA_FILE = "crypto_history.json"
MAX_RECORDS_PER_COIN = 100   # сколько записей храним на одну монету
MIN_SAVE_INTERVAL = 60       # минимальная пауза между записями, сек

CRYPTO_LIST = [
    ("Bitcoin", "bitcoin"),
    ("Ethereum", "ethereum"),
    ("Tether", "tether"),
    ("BNB", "binancecoin"),
    ("Solana", "solana"),
    ("USDC", "usd-coin"),
    ("XRP", "ripple"),
    ("Dogecoin", "dogecoin"),
    ("Cardano", "cardano"),
]

PERIODS = [
    ("7 дней", 7),
    ("30 дней", 30),
    ("90 дней", 90),
    ("1 год", 365),
]

# Глобальные переменные для виджетов
root = None
label_status = None
crypto_combobox = None
entry_date = None
period_combobox = None
label_coin_name = None
label_price_usd = None
label_price_rub = None
label_change = None
label_coin_date = None
label_suffix_date = None
label_price_date_usd = None
label_price_date_rub = None
label_period_change = None


# ================= РАБОТА С ФАЙЛОМ ИСТОРИИ =================
def load_history():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError):
        return {}


def save_history(history):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError as e:
        if label_status:
            label_status.config(text=f"Ошибка сохранения: {e}", fg="red")


def append_record(coin_id, record):
    """Добавляет запись в историю с ограничением частоты и размера.

    Возвращает True, если запись сохранена, False — если отклонена
    (слишком часто)."""
    history = load_history()
    records = history.setdefault(coin_id, [])

    # Не пишем чаще, чем раз в MIN_SAVE_INTERVAL секунд
    if records:
        last_ts = records[-1].get("timestamp", "")
        try:
            last_dt = datetime.fromisoformat(last_ts)
            if (datetime.now() - last_dt).total_seconds() < MIN_SAVE_INTERVAL:
                return False
        except ValueError:
            pass

    records.append(record)
    history[coin_id] = records[-MAX_RECORDS_PER_COIN:]
    save_history(history)
    return True


# ================= API ЗАПРОСЫ =================
def network_error_message(e):
    """Единое понятное сообщение по типу сетевой ошибки."""
    if isinstance(e, requests.exceptions.HTTPError):
        code = e.response.status_code if e.response is not None else "?"
        if code == 429:
            return "Слишком много запросов к API. Подождите около минуты."
        return f"Ошибка API: HTTP {code}"
    if isinstance(e, requests.exceptions.ConnectionError):
        return "Ошибка: нет соединения с интернетом"
    if isinstance(e, requests.exceptions.Timeout):
        return "Ошибка: таймаут соединения"
    return f"Ошибка сети: {e}"


def get_usd_rub_rate():
    """Получает текущий курс USD к RUB."""
    try:
        resp = requests.get(CB_API_URL, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json().get("rates", {}).get("RUB")
    except requests.RequestException:
        return None


def fetch_crypto_data(coin_id):
    """Получает текущие данные о монете."""
    params = {
        "ids": coin_id,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    resp = requests.get(API_URL_PRICE, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_price_on_date(coin_id, date_str):
    """Получает цену монеты на дату в USD и RUB (исторические данные от CoinGecko).

    Возвращает (price_usd, price_rub) — оба могут быть None."""
    resp = requests.get(
        API_URL_HISTORY.format(coin_id=coin_id),
        params={"date": date_str},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    market_data = resp.json().get("market_data") or {}
    current_price = market_data.get("current_price") or {}
    if not isinstance(current_price, dict):
        return None, None
    return current_price.get("usd"), current_price.get("rub")


def fetch_market_chart(coin_id, days):
    """Получает историю цен за период.

    Возвращает список кортежей (datetime, цена USD)."""
    resp = requests.get(
        API_URL_MARKET_CHART.format(coin_id=coin_id),
        params={"vs_currency": "usd", "days": days},
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    prices = resp.json().get("prices", [])
    return [
        (datetime.fromtimestamp(ts_ms / 1000), float(price))
        for ts_ms, price in prices
    ]


def set_status(text, color):
    label_status.config(text=text, fg=color)


def selected_coin():
    """Разбирает выбранный элемент комбобокса.

    Возвращает (имя, id) или (None, None)."""
    selected = crypto_combobox.get()
    if " | " not in selected:
        return None, None
    return selected.split(" | ")


# ================= ЛОГИКА ПРИЛОЖЕНИЯ =================
def update_price_async():
    """Обновляет текущий курс и сохраняет в историю (запросы — в фоне)."""
    coin_name, coin_id = selected_coin()
    if coin_id is None:
        return
    set_status("Статус: загрузка данных...", "blue")

    def worker():
        try:
            data = fetch_crypto_data(coin_id)
            price_usd = data[coin_id]["usd"]
            change_24h = data[coin_id].get("usd_24h_change") or 0.0
            rate_rub = get_usd_rub_rate()
        except requests.RequestException as e:
            msg = network_error_message(e)
            root.after(0, lambda: set_status(msg, "red"))
            return

        def apply():
            label_coin_name.config(text=coin_name)
            label_price_usd.config(text=f"Цена: {price_usd:,.2f} USD")
            label_change.config(text=f"Изменение за 24 ч: {change_24h:+.2f}%")
            # Сбрасываем расчёт периода при обновлении текущего курса
            label_period_change.config(text="", fg="gray")

            if rate_rub is not None:
                price_rub = price_usd * rate_rub
                label_price_rub.config(
                    text=f"{price_rub:,.2f} ₽ (курс: 1 USD = {rate_rub:.2f} ₽)",
                    fg="#005500",
                )
            else:
                label_price_rub.config(text="(Курс USD/RUB не загружен)", fg="orange")

            saved = append_record(coin_id, {
                "name": coin_name,
                "id": coin_id,
                "price_usd": price_usd,
                "change_24h": change_24h,
                "rate_rub": rate_rub,
                "timestamp": datetime.now().isoformat(),
                "type": "current",
            })
            if saved:
                set_status("Статус: данные получены и сохранены", "green")
            else:
                set_status(
                    "Статус: данные получены (в историю не записаны — слишком часто)",
                    "gray",
                )

        root.after(0, apply)

    threading.Thread(target=worker, daemon=True).start()


def get_price_on_date_async():
    """Цена на дату (USD и RUB того же дня), исторический курс и изменение за период."""
    date_str = entry_date.get().strip()
    coin_name, coin_id = selected_coin()

    if not date_str:
        set_status("Введите дату в формате дд-мм-гггг, например 06-11-2025", "orange")
        return
    try:
        date_obj = datetime.strptime(date_str, "%d-%m-%Y").date()
    except ValueError:
        set_status("Некорректная дата. Пример: 06-11-2025", "orange")
        return
    if date_obj > datetime.now().date():
        set_status("Дата не может быть в будущем", "orange")
        return

    if coin_id is None:
        return
    set_status("Статус: загрузка цены на дату...", "blue")

    def worker():
        try:
            # 1. Цена «тогда» (USD и RUB того же дня)
            price_then, rub_then = fetch_price_on_date(coin_id, date_str)
            # 2. Цена «сейчас»
            data_now = fetch_crypto_data(coin_id)
            price_now = data_now[coin_id]["usd"]
        except requests.RequestException as e:
            msg = network_error_message(e)
            root.after(0, lambda: set_status(msg, "red"))
            return

        def apply():
            label_coin_date.config(text=coin_name)
            label_suffix_date.config(text=f" (на {date_str})")

            if price_then is None or price_then <= 0:
                label_price_date_usd.config(text="Нет данных о цене на эту дату", fg="orange")
                label_price_date_rub.config(text="", fg="gray")
                label_period_change.config(text="", fg="gray")
                set_status("API не вернул данные для этой даты", "orange")
                return

            label_price_date_usd.config(
                text=f"Цена на дату: {price_then:,.2f} USD", fg="#005500"
            )

            if rub_then is not None:
                rate_on_date = rub_then / price_then   # исторический курс USD/RUB на дату
                label_price_date_rub.config(
                    text=f"{rub_then:,.2f} ₽ (курс на дату: 1 USD = {rate_on_date:.2f} ₽)",
                    fg="#005500",
                )
                label_status.config(text="Статус: цена на дату получена", fg="green")
            else:
                label_price_date_rub.config(text="(Рубли на дату недоступны)", fg="orange")
                label_status.config(text="Статус: нет рублёвой цены на дату", fg="orange")

            # 3. Изменение от «тогда» к «сейчас» (в USD)
            delta_percent = ((price_now - price_then) / price_then) * 100
            color = "dark blue" if delta_percent >= 0 else "#cc0000"
            sign = "+" if delta_percent >= 0 else ""
            label_period_change.config(
                text=f"Изменение с {date_str}: {sign}{delta_percent:.2f}%",
                fg=color,
                font=("Arial", 11, "bold"),
            )

        root.after(0, apply)

    threading.Thread(target=worker, daemon=True).start()


def show_graph_async():
    """Строит график цены за выбранный период (запрос — в фоне)."""
    coin_name, coin_id = selected_coin()
    if coin_id is None:
        return

    period_label = period_combobox.get()
    days = next((d for name, d in PERIODS if name == period_label), 30)
    set_status("Статус: загрузка данных для графика...", "blue")

    def worker():
        try:
            points = fetch_market_chart(coin_id, days)
            current_data = fetch_crypto_data(coin_id)
            price_now = current_data[coin_id]["usd"]
        except requests.RequestException as e:
            msg = network_error_message(e)
            root.after(0, lambda: set_status(msg, "red"))
            return

        def apply():
            graph_win = tk.Toplevel(root)
            graph_win.title(f"График цены: {coin_name} — {period_label}")
            graph_win.geometry("880x580")
            graph_win.minsize(640, 420)

            if not points:
                ttk.Label(
                    graph_win,
                    text="Нет данных для графика за этот период.",
                    font=("Arial", 11),
                ).pack(expand=True)
                return

            times = [p[0] for p in points]
            values = [p[1] for p in points]

            fig = Figure(figsize=(8.6, 5.4), dpi=100)
            ax = fig.add_subplot(111)
            ax.plot(times, values, color="#0055a4", linewidth=1.8, label="Цена (USD)")
            ax.fill_between(times, values, color="#0055a4", alpha=0.12)

            # Точки сохранённых замеров из истории, попавшие в период
            since = datetime.now() - timedelta(days=days)
            saved_points = []
            for r in load_history().get(coin_id, []):
                try:
                    dt = datetime.fromisoformat(r["timestamp"])
                except (KeyError, ValueError):
                    continue
                if dt >= since:
                    saved_points.append((dt, r["price_usd"]))
            if saved_points:
                ax.scatter(
                    [p[0] for p in saved_points],
                    [p[1] for p in saved_points],
                    color="#cc0000", s=28, zorder=3, label="Ваши замеры",
                )
                ax.legend(loc="upper left", fontsize=9)

            price_first = values[0]
            period_change = ((price_now - price_first) / price_first) * 100 if price_first else 0
            sign = "+" if period_change >= 0 else ""
            ax.set_title(
                f"{coin_name}: цена за {period_label.lower()} | "
                f"сейчас {price_now:,.2f} USD ({sign}{period_change:.2f}% за период)",
                fontsize=11,
            )
            ax.set_ylabel("USD")
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(
                mdates.ConciseDateFormatter(mdates.AutoDateLocator())
            )
            fig.autofmt_xdate()
            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=graph_win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)
            set_status("Статус: график построен", "green")

        root.after(0, apply)

    threading.Thread(target=worker, daemon=True).start()


def show_history():
    """Открывает окно с историей сохранённых записей."""
    _, coin_id = selected_coin()
    if coin_id is None:
        return

    records = load_history().get(coin_id, [])
    if not records:
        set_status("Нет сохранённых данных для этой монеты", "orange")
        return

    hist_win = tk.Toplevel(root)
    hist_win.title(f"История: {crypto_combobox.get()}")
    hist_win.geometry("700x450")
    hist_win.resizable(False, False)

    frame = tk.Frame(hist_win)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    tree = ttk.Treeview(
        frame,
        columns=("time", "price_usd", "price_rub", "change", "type"),
        show="headings",
        height=17,
    )
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.heading("time", text="Время/Дата")
    tree.heading("price_usd", text="Цена (USD)")
    tree.heading("price_rub", text="Цена (RUB)")
    tree.heading("change", text="24ч Изменение (%)")
    tree.heading("type", text="Тип")
    tree.column("time", width=160)
    tree.column("price_usd", width=110, anchor="e")
    tree.column("price_rub", width=130, anchor="e")
    tree.column("change", width=120, anchor="e")
    tree.column("type", width=80, anchor="center")

    for r in reversed(records):  # свежие записи сверху
        time_str = r["timestamp"][:19].replace("T", "  ")
        price_rub_val = "-"
        if r.get("rate_rub"):
            price_rub_val = f"{r['price_usd'] * r['rate_rub']:,.2f}"
        tree.insert("", "end", values=(
            time_str,
            f"{r['price_usd']:,.2f}",
            price_rub_val,
            f"{r.get('change_24h', 0):.2f}",
            r.get("type", "unknown"),
        ))

    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    ttk.Button(hist_win, text="Закрыть", command=hist_win.destroy).pack(pady=5)


# ================= СОЗДАНИЕ ИНТЕРФЕЙСА (GUI) =================
root = tk.Tk()
root.title("Crypto Tracker: Курсы и Динамика")
root.geometry("440x760")
root.resizable(False, False)

# 1. Выбор монеты
ttk.Label(root, text="Выберите монету:").pack(anchor="w", padx=10)
crypto_values = [f"{name} | {cid}" for name, cid in CRYPTO_LIST]
crypto_combobox = ttk.Combobox(root, values=crypto_values, state="readonly")
crypto_combobox.current(0)
crypto_combobox.pack(pady=5, padx=10)

ttk.Separator(root, orient="horizontal").pack(padx=10, pady=10)

# 2. Блок текущего курса
ttk.Label(root, text="Текущий курс (из API)", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
ttk.Button(root, text="Обновить курс и сохранить", command=update_price_async).pack(pady=5)

frame_name = tk.Frame(root)
frame_name.pack(pady=2)
label_prefix = tk.Label(frame_name, text="Монета: ", font=("Arial", 11))
label_coin_name = tk.Label(frame_name, font=("Arial", 11, "bold"))
label_prefix.pack(side=tk.LEFT)
label_coin_name.pack(side=tk.LEFT)

label_price_usd = tk.Label(root, font=("Arial", 12, "bold"), justify="center", fg="#005500")
label_price_usd.pack(pady=2)

label_price_rub = tk.Label(root, font=("Arial", 11), justify="center", fg="#222222")
label_price_rub.pack(pady=1)

label_change = tk.Label(root, font=("Arial", 11), justify="center")
label_change.pack(pady=2)

ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)

# 3. Блок цены на дату
ttk.Label(root, text="Цена монеты на конкретную дату", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
ttk.Label(root, text="Дата (дд-мм-гггг), не позднее сегодняшней:").pack(anchor="w", padx=10)
entry_date = ttk.Entry(root, width=20)
entry_date.pack(anchor="w", padx=10, pady=2)
ttk.Button(root, text="Получить цену на дату", command=get_price_on_date_async).pack(pady=5)

frame_name_date = tk.Frame(root)
frame_name_date.pack(pady=2)
label_prefix_date = tk.Label(frame_name_date, text="Монета: ", font=("Arial", 11))
label_coin_date = tk.Label(frame_name_date, font=("Arial", 11, "bold"))
label_suffix_date = tk.Label(frame_name_date, text="", font=("Arial", 11))
label_prefix_date.pack(side=tk.LEFT)
label_coin_date.pack(side=tk.LEFT)
label_suffix_date.pack(side=tk.LEFT)

label_price_date_usd = tk.Label(root, font=("Arial", 12, "bold"), justify="center", fg="#005500")
label_price_date_usd.pack(pady=2)

label_price_date_rub = tk.Label(root, font=("Arial", 11), justify="center", fg="#222222")
label_price_date_rub.pack(pady=1)

label_period_change = tk.Label(root, font=("Arial", 11, "bold"), justify="center")
label_period_change.pack(pady=4)

ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)

# 4. Блок графика
ttk.Label(root, text="График цены", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
period_combobox = ttk.Combobox(
    root, values=[name for name, _ in PERIODS], state="readonly", width=12
)
period_combobox.current(1)
period_combobox.pack(anchor="w", padx=10, pady=2)
ttk.Button(root, text="Показать график", command=show_graph_async).pack(pady=5)

ttk.Separator(root, orient="horizontal").pack(fill="x", padx=10, pady=10)

# 5. Блок истории сохранённых записей
ttk.Label(root, text="Сохранённая история по монете", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
ttk.Button(root, text="Показать историю записей", command=show_history).pack(pady=5)

# Статусная строка внизу окна
label_status = tk.Label(
    root,
    text="Готов к работе. Выберите монету и нажмите одну из кнопок.",
    font=("Arial", 9),
    fg="gray",
    anchor="w",
    wraplength=420,
    justify="left",
)
label_status.pack(fill="x", side="bottom", padx=10, pady=8)

# Запуск главного цикла приложения
root.mainloop()
