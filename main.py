import customtkinter as ctk
from datetime import datetime
import calendar
import json
import os
import ctypes

from ib_controller import IBController
from account_panel import AccountPanel
from path_utils import get_bundled_path, get_user_data_path, get_config_path

ctk.set_appearance_mode("dark")

COLOR_BG = "#0f0f0f"
COLOR_CARD_EMPTY = "#1c1c1e"
COLOR_CARD_PROFIT = "#0d2e1a"
COLOR_CARD_LOSS = "#2e0d0d"
COLOR_PROFIT = "#00e676"
COLOR_LOSS = "#ff4f4f"
COLOR_ACCENT = "#3a7bd5"
COLOR_SIDEBAR = "#161618"
COLOR_ROW_BG = "#1e1e22"
COLOR_ROW_BORDER = "#2a2a30"
COLOR_TEXT = "#e8e8e8"
COLOR_SUBTEXT = "#888"
COLOR_DELETE = "#8b0000"

class TradingCalendar(ctk.CTk):
    def __init__(self):
        super().__init__()
        myappid = 'mycompany.tradingcalendar.pro.v2'
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except: pass
        self.title("Trading Journal Pro")
        self.geometry("1500x780")
        self.configure(fg_color=COLOR_BG)
        self.attributes("-alpha", 0.97)
        try: self.iconbitmap(get_bundled_path("app_icon.ico"))
        except: pass
        self.data_file = get_user_data_path("trading_data.json")
        self.trading_data = self.load_data()
        self.view_date = datetime.now()
        self.current_month = self.view_date.month
        self.current_year = self.view_date.year
        self.selected_date = None
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # IB Integration – Controller + Account Panel
        self._ib_controller = IBController(
            root=self,
            on_data_received=self._on_ib_data,
            on_error=self._on_ib_error,
            config_path=get_config_path(),
        )

        self.setup_ui()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.trading_data, f, indent=4, ensure_ascii=False)

    def calc_net(self, gross):
        after_commission = gross - 6
        if after_commission > 0:
            net = after_commission * 0.75
        else:
            net = after_commission
        return round(net, 2)

    def day_total(self, date_id):
        txs = self.trading_data.get(date_id, [])
        if not isinstance(txs, list) or len(txs) == 0: return None
        return round(sum(tx["net"] for tx in txs), 2)

    def month_total(self):
        total = 0
        for day in range(1, 32):
            date_id = f"{day:02d}/{self.current_month:02d}/{self.current_year}"
            t = self.day_total(date_id)
            if t is not None: total += t
        return round(total, 2)

    def setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(20, 0))
        ctk.CTkButton(header, text="<", width=40, height=40, fg_color="#222", hover_color="#333", font=("Arial", 20), corner_radius=10, command=self.prev_month).pack(side="left")
        m_name = calendar.month_name[self.current_month]
        self.title_label = ctk.CTkLabel(header, text=f"{m_name} {self.current_year}", font=("Helvetica Neue", 30, "bold"), text_color=COLOR_TEXT)
        self.title_label.pack(side="left", padx=20)
        ctk.CTkButton(header, text=">", width=40, height=40, fg_color="#222", hover_color="#333", font=("Arial", 20), corner_radius=10, command=self.next_month).pack(side="left")
        
        days_frame = ctk.CTkFrame(self, fg_color="transparent")
        days_frame.grid(row=1, column=0, sticky="ew", padx=30, pady=(12, 4))
        days_heb = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        for i, d in enumerate(days_heb):
            days_frame.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(days_frame, text=d, font=("Helvetica Neue", 13), text_color=COLOR_SUBTEXT).grid(row=0, column=i, pady=4)

        self.cal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cal_frame.grid(row=2, column=0, sticky="nsew", padx=30, pady=4)

        self.footer = ctk.CTkFrame(self, height=48, fg_color="#141416", corner_radius=0)
        self.footer.grid(row=3, column=0, sticky="ew")
        self.footer_label = ctk.CTkLabel(self.footer, text="", font=("Helvetica Neue", 16, "bold"))
        self.footer_label.pack(pady=12)

        self.sidebar = ctk.CTkFrame(self, width=420, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar.grid(row=0, column=1, rowspan=4, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.pack_propagate(False)

        # IB Account Panel – at top of sidebar
        self._account_panel = AccountPanel(self.sidebar, controller=self._ib_controller)
        self._account_panel.pack(fill="x", padx=8, pady=(10, 6))

        # Trade details area (below account panel) – rebuilt on day selection
        self._sidebar_content = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self._sidebar_content.pack(fill="both", expand=True)
        
        ctk.CTkLabel(self._sidebar_content, text="בחר יום\nמהלוח", font=("Helvetica Neue", 15), text_color=COLOR_SUBTEXT, justify="center").pack(expand=True)
        self.draw_calendar()

    def draw_calendar(self):
        for w in self.cal_frame.winfo_children(): w.destroy()
        month_days = calendar.monthcalendar(self.current_year, self.current_month)
        for c in range(7): self.cal_frame.grid_columnconfigure(c, weight=1, uniform="col")
        for r in range(len(month_days)): self.cal_frame.grid_rowconfigure(r, weight=1, uniform="row")

        for r, week in enumerate(month_days):
            for c, day in enumerate(week):
                if day == 0:
                    ctk.CTkFrame(self.cal_frame, fg_color="transparent").grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
                    continue
                date_id = f"{day:02d}/{self.current_month:02d}/{self.current_year}"
                total = self.day_total(date_id)

                if total is None:
                    card_color, amount_text, amount_color = COLOR_CARD_EMPTY, "", COLOR_TEXT
                elif total >= 0:
                    card_color, amount_text, amount_color = COLOR_CARD_PROFIT, f"+{total}$", COLOR_PROFIT
                else:
                    card_color, amount_text, amount_color = COLOR_CARD_LOSS, f"{total}$", COLOR_LOSS

                is_selected = (date_id == self.selected_date)
                border_color = COLOR_ACCENT if is_selected else card_color
                card = ctk.CTkFrame(self.cal_frame, fg_color=card_color, border_width=2 if is_selected else 0, border_color=border_color, corner_radius=12)
                card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
                card.grid_propagate(False)
                card.grid_rowconfigure(0, weight=1)
                card.grid_rowconfigure(1, weight=2)
                card.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(card, text=str(day), font=("Helvetica Neue", 12), text_color=COLOR_SUBTEXT, anchor="nw").grid(row=0, column=0, sticky="nw", padx=8, pady=(6, 0))
                if amount_text: ctk.CTkLabel(card, text=amount_text, font=("Helvetica Neue", 17, "bold"), text_color=amount_color).grid(row=1, column=0, sticky="s", padx=4, pady=(0, 8))
                
                card.bind("<Button-1>", lambda e, d=date_id: self.select_day(d))
                for child in card.winfo_children(): child.bind("<Button-1>", lambda e, d=date_id: self.select_day(d))

        m_name = calendar.month_name[self.current_month]
        self.title_label.configure(text=f"{m_name} {self.current_year}")
        mt = self.month_total()
        color, sign = (COLOR_PROFIT, "+") if mt >= 0 else (COLOR_LOSS, "")
        self.footer_label.configure(text=f"סה״כ חודשי (נטו לאחר מיסים): {sign}{mt}$", text_color=color)

    def prev_month(self):
        if self.current_month == 1: self.current_month, self.current_year = 12, self.current_year - 1
        else: self.current_month -= 1
        self.selected_date = None
        self.clear_sidebar()
        self.draw_calendar()

    def next_month(self):
        if self.current_month == 12: self.current_month, self.current_year = 1, self.current_year + 1
        else: self.current_month += 1
        self.selected_date = None
        self.clear_sidebar()
        self.draw_calendar()

    def clear_sidebar(self):
        for w in self._sidebar_content.winfo_children(): w.destroy()
        ctk.CTkLabel(self._sidebar_content, text="בחר יום\nמהלוח", font=("Helvetica Neue", 15), text_color=COLOR_SUBTEXT, justify="center").pack(expand=True)

    def select_day(self, date_id):
        self.selected_date = str(date_id)
        self.draw_calendar()
        self.open_sidebar(self.selected_date)

    def open_sidebar(self, date_id):
        for w in self._sidebar_content.winfo_children(): w.destroy()
        header = ctk.CTkFrame(self._sidebar_content, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(18, 6))

        try:
            d, m, y = str(date_id).split("/")
            month_heb = ["", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
            date_str = f"{int(d)} ב{month_heb[int(m)]} {y}"
        except Exception:
            date_str = str(date_id)

        ctk.CTkLabel(header, text=date_str, font=("Helvetica Neue", 19, "bold"), text_color=COLOR_TEXT).pack(side="right")
        total = self.day_total(date_id)
        summary_frame = ctk.CTkFrame(self._sidebar_content, fg_color=COLOR_ROW_BG, corner_radius=10)
        summary_frame.pack(fill="x", padx=16, pady=(0, 10))

        if total is None: summary_text, summary_color = "אין עסקאות היום", COLOR_SUBTEXT
        elif total >= 0: summary_text, summary_color = f"רווח יומי נטו: +{total}$", COLOR_PROFIT
        else: summary_text, summary_color = f"הפסד יומי נטו: {total}$", COLOR_LOSS

        ctk.CTkLabel(summary_frame, text=summary_text, font=("Helvetica Neue", 15, "bold"), text_color=summary_color).pack(pady=10)

        list_header = ctk.CTkFrame(self._sidebar_content, fg_color="transparent")
        list_header.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(list_header, text="עסקאות", font=("Helvetica Neue", 13), text_color=COLOR_SUBTEXT).pack(side="right")

        self.tx_list = ctk.CTkScrollableFrame(self._sidebar_content, fg_color="transparent", scrollbar_button_color="#333")
        self.tx_list.pack(fill="both", expand=True, padx=10)
        self.refresh_tx_list(date_id)

        add_frame = ctk.CTkFrame(self._sidebar_content, fg_color=COLOR_ROW_BG, corner_radius=12)
        add_frame.pack(fill="x", padx=16, pady=(8, 16))
        ctk.CTkLabel(add_frame, text="הוסף עסקה חדשה", font=("Helvetica Neue", 13, "bold"), text_color=COLOR_TEXT).pack(pady=(10, 4))
        
        self.t_type = ctk.CTkSegmentedButton(add_frame, values=["Long", "Short"], font=("Helvetica Neue", 13))
        self.t_type.pack(fill="x", padx=12, pady=3)
        self.t_type.set("Long")

        self.entry_price = ctk.CTkEntry(add_frame, placeholder_text="מחיר כניסה", font=("Helvetica Neue", 14), height=36, justify="right")
        self.entry_price.pack(fill="x", padx=12, pady=3)
        self.exit_price = ctk.CTkEntry(add_frame, placeholder_text="מחיר יציאה", font=("Helvetica Neue", 14), height=36, justify="right")
        self.exit_price.pack(fill="x", padx=12, pady=3)
        self.risk_entry = ctk.CTkEntry(add_frame, placeholder_text="מחיר Stop Loss", font=("Helvetica Neue", 14), height=36, justify="right")
        self.risk_entry.pack(fill="x", padx=12, pady=3)
        self.running_total_entry = ctk.CTkEntry(add_frame, placeholder_text="Running Total — סה״כ בחשבון ($)", font=("Helvetica Neue", 14), height=36, justify="right")
        self.running_total_entry.pack(fill="x", padx=12, pady=3)
        self.running_total_entry.bind("<Return>", lambda e: self.add_transaction(date_id))

        ctk.CTkButton(add_frame, text="+ הוסף עסקה", font=("Helvetica Neue", 14, "bold"), height=38, fg_color=COLOR_ACCENT, hover_color="#2a5fa8", corner_radius=8, command=lambda: self.add_transaction(date_id)).pack(fill="x", padx=12, pady=(6, 12))

    def refresh_tx_list(self, date_id):
        for w in self.tx_list.winfo_children(): w.destroy()
        transactions = self.trading_data.get(date_id, [])
        if not isinstance(transactions, list) or len(transactions) == 0:
            ctk.CTkLabel(self.tx_list, text="אין עסקאות עדיין", font=("Helvetica Neue", 13), text_color=COLOR_SUBTEXT).pack(pady=20)
            return

        for i, tx in enumerate(transactions):
            gross, net, entry_p, exit_p, risk, running_total, t_side = tx.get("gross", 0), tx.get("net", 0), tx.get("entry", 0), tx.get("exit", 0), tx.get("risk", 0), tx.get("running_total", 0), tx.get("type", "Long")
            net_color, sign = (COLOR_PROFIT, "+") if net >= 0 else (COLOR_LOSS, "")

            row = ctk.CTkFrame(self.tx_list, fg_color=COLOR_ROW_BG, corner_radius=10)
            row.pack(fill="x", pady=3)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(8, 2))
            ctk.CTkButton(top, text="✕", width=28, height=28, fg_color="transparent", hover_color=COLOR_DELETE, text_color="#888", font=("Arial", 13), corner_radius=6, command=lambda idx=i, d=date_id: self.delete_transaction(d, idx)).pack(side="left")
            ctk.CTkLabel(top, text=f"#{i+1}", font=("Helvetica Neue", 11), text_color=COLOR_SUBTEXT).pack(side="right", padx=(0, 2))
            ctk.CTkLabel(top, text=f"נטו: {sign}{net}$   |   ברוטו: {gross}$   |   {t_side}", font=("Helvetica Neue", 13, "bold"), text_color=net_color).pack(side="right", padx=6)
            
            details = ctk.CTkFrame(row, fg_color="transparent")
            details.pack(fill="x", padx=10, pady=(0, 2))
            ctk.CTkLabel(details, text=f"כניסה: {entry_p}$   יציאה: {exit_p}$   סיכון: {risk}$", font=("Helvetica Neue", 11), text_color=COLOR_SUBTEXT, anchor="e", justify="right").pack(side="right")
            
            bottom = ctk.CTkFrame(row, fg_color="transparent")
            bottom.pack(fill="x", padx=10, pady=(2, 8))
            ctk.CTkLabel(bottom, text=f"סה״כ בחשבון: {running_total}$", font=("Helvetica Neue", 12, "bold"), text_color=COLOR_TEXT, anchor="e", justify="right").pack(side="right")

    def add_transaction(self, date_id):
        try:
            entry_p = float(self.entry_price.get().strip())
            exit_p = float(self.exit_price.get().strip())
            sl_price = float(self.risk_entry.get().strip())
            running_total = float(self.running_total_entry.get().strip())
            t_side = self.t_type.get()
        except:
            for w in (self.entry_price, self.exit_price, self.risk_entry, self.running_total_entry):
                try: 
                    if not w.get().strip(): w.configure(border_color="red")
                except: pass
            return

        diff = (exit_p - entry_p) if t_side == "Long" else (entry_p - exit_p)
        gross = round(diff * 2, 2)
        net = self.calc_net(gross)
        
        risk_dist = abs(entry_p - sl_price)
        risk_usd = round(risk_dist * 2, 2)

        if date_id not in self.trading_data or not isinstance(self.trading_data[date_id], list): self.trading_data[date_id] = []
        self.trading_data[date_id].append({"type": t_side, "entry": entry_p, "exit": exit_p, "risk": risk_usd, "running_total": running_total, "gross": gross, "net": net})
        self.save_data()
        self.draw_calendar()
        self.open_sidebar(date_id)

    def delete_transaction(self, date_id, index):
        txs = self.trading_data.get(date_id, [])
        if isinstance(txs, list) and 0 <= index < len(txs):
            txs.pop(index)
            if len(txs) == 0: del self.trading_data[date_id]
            self.save_data()
            self.draw_calendar()
            self.open_sidebar(date_id)

    # =========================================================================
    # IB Integration Callbacks (called via root.after – main thread safe)
    # =========================================================================

    def _on_ib_data(self, data):
        """Callback: IBController fetched account data successfully."""
        self._account_panel.on_data_received(data)

    def _on_ib_error(self, message):
        """Callback: IBController encountered an error."""
        self._account_panel.on_error(message)

if __name__ == "__main__":
    TradingCalendar().mainloop()