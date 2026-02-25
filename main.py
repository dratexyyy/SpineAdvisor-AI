import customtkinter as ctk
import google.generativeai as genai
from PIL import Image
from tkinter import filedialog, messagebox
import threading
import json
import os
import re
from datetime import datetime

# Проверка наличия matplotlib для графиков
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    # Настройка шрифтов для кириллицы в графиках (зависит от ОС, но попробуем стандарт)
    plt.rcParams['font.family'] = 'DejaVu Sans' 
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ─── КОНФИГУРАЦИЯ ──────────────────────────────────────────────────
API_KEY = "YOUR-GEMINI-AI API KEY" # Замените на свой ключ, если этот не работает
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-3-flash-preview") # Используем актуальную модель

PROFILE_FILE = "profile.json"
HISTORY_FILE = "history.json"

# Цветовая схема
COLOR_BG           = "#1a1a2e"
COLOR_SIDEBAR      = "#16213e"
COLOR_CARD         = "#21253a"
COLOR_ACCENT       = "#00b4d8"
COLOR_ACCENT_HOVER = "#0096c7"
COLOR_TEXT_MAIN    = "#ffffff"
COLOR_TEXT_SUB     = "#b0bec5"
COLOR_INPUT        = "#2b304a"
COLOR_DANGER       = "#ef5350"
COLOR_SUCCESS      = "#4caf50"
COLOR_WARNING      = "#ff9800"

# Цвета для шкалы боли (от зеленого к красному)
PAIN_COLORS = {
    1: "#4caf50", 2: "#66bb6a", 3: "#8bc34a",
    4: "#cddc39", 5: "#ffeb3b", 6: "#ffc107",
    7: "#ff9800", 8: "#ff5722", 9: "#f44336", 10: "#b71c1c"
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ───────────────────────────────────────
def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def calculate_bmi(height_cm, weight_kg):
    try:
        h_m = float(height_cm) / 100
        w = float(weight_kg)
        bmi = w / (h_m ** 2)
        return round(bmi, 1)
    except (ValueError, ZeroDivisionError, TypeError):
        return None

# ─── ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ ─────────────────────────────────────
class SpineApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Spine Advisor — AI Анализ Спины")
        self.geometry("1200x860")
        self.configure(fg_color=COLOR_BG)
        
        # Состояние приложения
        self.image_path    = None
        self.profile       = load_json(PROFILE_FILE, {})
        self.history       = load_json(HISTORY_FILE, [])
        self.current_frame = None
        self.pain_level    = 0
        self.last_data     = None
        self.canvas_widget = None
        
        self.build_layout()
        self.select_frame("analysis")

    def build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR (Левая панель) ===
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(self.sidebar, text="🦴 Spine Advisor",
            font=ctk.CTkFont(family="Roboto", size=22, weight="bold"), text_color=COLOR_ACCENT
        ).grid(row=0, column=0, padx=20, pady=(30, 30))

        self.btn_analysis = self.create_nav_button("🔍  Анализ",           1, "analysis")
        self.btn_dynamics = self.create_nav_button("📈  Динамика",         2, "dynamics")
        self.btn_history  = self.create_nav_button("🗂  История",          3, "history")
        self.btn_profile  = self.create_nav_button("👤  Профиль",          4, "profile")

        version_info = ctk.CTkLabel(self.sidebar, text="v3.1.0 RU\nAI Powered",
            text_color="gray50", font=("Arial", 11))
        version_info.grid(row=7, column=0, padx=20, pady=20)

        # === ОСНОВНОЙ КОНТЕЙНЕР ===
        self.main_container = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Создание экранов
        self.frame_analysis = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frame_dynamics = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frame_history  = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.frame_profile  = ctk.CTkFrame(self.main_container, fg_color="transparent")

        self.build_analysis_screen(self.frame_analysis)
        self.build_dynamics_screen(self.frame_dynamics)
        self.build_history_screen(self.frame_history)
        self.build_profile_screen(self.frame_profile)

    def create_nav_button(self, text, row, name):
        btn = ctk.CTkButton(self.sidebar, text=text,
            fg_color="transparent", text_color=COLOR_TEXT_SUB,
            hover_color=COLOR_CARD, anchor="w", height=50,
            font=ctk.CTkFont(size=15),
            command=lambda: self.select_frame(name)
        )
        btn.grid(row=row, column=0, sticky="ew", padx=10, pady=4)
        return btn

    def select_frame(self, name):
        # Сброс подсветки кнопок
        for btn in [self.btn_analysis, self.btn_dynamics, self.btn_history, self.btn_profile]:
            btn.configure(fg_color="transparent", text_color=COLOR_TEXT_SUB)
        
        if self.current_frame:
            self.current_frame.grid_forget()
            
        mapping = {
            "analysis": (self.frame_analysis, self.btn_analysis),
            "dynamics": (self.frame_dynamics, self.btn_dynamics),
            "history":  (self.frame_history,  self.btn_history),
            "profile":  (self.frame_profile,  self.btn_profile),
        }
        
        frame, btn = mapping[name]
        btn.configure(fg_color=COLOR_CARD, text_color=COLOR_ACCENT)
        
        self.current_frame = frame
        self.current_frame.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)
        
        # Обновление данных при переключении
        if name == "history":
            self.refresh_history_list()
        if name == "dynamics":
            self.refresh_dynamics()

    # ─── ЭКРАН 1: АНАЛИЗ ───────────────────────────────────────────
    def build_analysis_screen(self, parent):
        ctk.CTkLabel(parent, text="AI Диагностика",
            font=("Roboto", 28, "bold"), text_color="white"
        ).pack(anchor="w", pady=(0, 15))

        # Карточка ввода
        input_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15)
        input_card.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(input_card, text="Опишите симптомы:",
            font=("Roboto", 14, "bold"), text_color="white"
        ).pack(anchor="w", padx=20, pady=(18, 5))

        self.symptom_input = ctk.CTkTextbox(input_card, height=70,
            fg_color=COLOR_INPUT, text_color="white", font=("Roboto", 13))
        self.symptom_input.pack(fill="x", padx=20, pady=(0, 12))
        self.symptom_input.insert("0.0", "Например: тянущая боль в пояснице справа, усиливается при сидении...")
        # Удаление подсказки при клике можно реализовать через bind FocusIn (оставим пока так)

        # Выбор боли
        pain_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        pain_frame.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(pain_frame, text="Уровень боли:",
            font=("Roboto", 13, "bold"), text_color=COLOR_TEXT_SUB
        ).pack(side="left", padx=(0, 12))
        
        self.pain_buttons = {}
        for i in range(1, 11):
            btn = ctk.CTkButton(pain_frame, text=str(i), width=38, height=38,
                fg_color=COLOR_INPUT, hover_color=PAIN_COLORS[i],
                text_color="white", font=("Roboto", 12, "bold"),
                corner_radius=8, command=lambda v=i: self.set_pain(v))
            btn.pack(side="left", padx=2)
            self.pain_buttons[i] = btn
            
        self.pain_selected_label = ctk.CTkLabel(pain_frame, text="",
            text_color=COLOR_TEXT_SUB, font=("Roboto", 12))
        self.pain_selected_label.pack(side="left", padx=(10, 0))

        # Кнопки действий
        action_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=(0, 18))
        
        self.upload_btn = ctk.CTkButton(action_frame, text="📷 МРТ / Снимок",
            command=self.upload_image, fg_color="#37474f", hover_color="#455a64", width=160, height=40)
        self.upload_btn.pack(side="left", padx=(0, 10))
        
        self.image_label = ctk.CTkLabel(action_frame, text="Файл не выбран", text_color="gray")
        self.image_label.pack(side="left")
        
        self.analyze_btn = ctk.CTkButton(action_frame, text="🔍 Запустить Анализ",
            command=self.analyze, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            font=("Roboto", 14, "bold"), height=40, width=190)
        self.analyze_btn.pack(side="right")
        
        # Прогресс бар (скрыт по умолчанию)
        self.progress_bar = ctk.CTkProgressBar(input_card, height=3, progress_color=COLOR_ACCENT)
        self.progress_bar.set(0)

        # Карточка результата
        result_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15)
        result_card.pack(fill="both", expand=True)
        
        res_header = ctk.CTkFrame(result_card, fg_color="transparent")
        res_header.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(res_header, text="Заключение ИИ:",
            font=("Roboto", 16, "bold"), text_color=COLOR_ACCENT).pack(side="left")
            
        self.pdf_btn = ctk.CTkButton(res_header, text="💾 Сохранить Отчет",
            command=self.export_report, fg_color="#37474f", hover_color="#455a64",
            height=32, width=150, font=("Roboto", 12))
        self.pdf_btn.pack(side="right")
        
        self.result_box = ctk.CTkTextbox(result_card, font=("Consolas", 13),
            fg_color="#1a1c29", text_color="#e0e0e0", wrap="word")
        self.result_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.result_box.insert("0.0", "Здесь появится результат анализа...\nЗаполните симптомы или загрузите МРТ.")
        self.result_box.configure(state="disabled")

    def set_pain(self, value):
        self.pain_level = value
        for i, btn in self.pain_buttons.items():
            btn.configure(fg_color=PAIN_COLORS[i] if i <= value else COLOR_INPUT)
            
        labels = {1:"Нет боли", 2:"Очень слабая", 3:"Слабая", 4:"Умеренная",
                  5:"Средняя", 6:"Заметная", 7:"Сильная", 8:"Очень сильная",
                  9:"Нестерпимая", 10:"Максимальная"}
        self.pain_selected_label.configure(
            text=f"— {labels.get(value, '')}", text_color=PAIN_COLORS[value])

    # ─── ЭКРАН 2: ДИНАМИКА ─────────────────────────────────────────
    def build_dynamics_screen(self, parent):
        ctk.CTkLabel(parent, text="Динамика лечения",
            font=("Roboto", 28, "bold"), text_color="white"
        ).pack(anchor="w", pady=(0, 15))

        # Статистика
        stats_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15)
        stats_card.pack(fill="x", pady=(0, 15))
        self.stats_row = ctk.CTkFrame(stats_card, fg_color="transparent")
        self.stats_row.pack(fill="x", padx=20, pady=15)

        self.stat_visits  = self._make_stat(self.stats_row, "Всего приемов",   "--",    COLOR_ACCENT)
        self.stat_angle   = self._make_stat(self.stats_row, "Угол (текущий)",  "--",    COLOR_WARNING)
        self.stat_angle_d = self._make_stat(self.stats_row, "Изм. угла",       "--",    COLOR_SUCCESS)
        self.stat_pain    = self._make_stat(self.stats_row, "Боль (текущая)",  "--/10", COLOR_DANGER)
        self.stat_pain_d  = self._make_stat(self.stats_row, "Изм. боли",       "--",    COLOR_SUCCESS)

        # График
        self.chart_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15)
        self.chart_card.pack(fill="both", expand=True)
        self.chart_placeholder = ctk.CTkLabel(self.chart_card,
            text="Проведите минимум 2 анализа, чтобы увидеть график динамики",
            font=("Roboto", 16), text_color="gray")
        self.chart_placeholder.pack(expand=True)

    def _make_stat(self, parent, label, value, color):
        frame = ctk.CTkFrame(parent, fg_color=COLOR_INPUT, corner_radius=10)
        frame.pack(side="left", expand=True, fill="x", padx=8)
        ctk.CTkLabel(frame, text=label, font=("Roboto", 11), text_color=COLOR_TEXT_SUB).pack(pady=(10,2))
        val_label = ctk.CTkLabel(frame, text=value, font=("Roboto", 22, "bold"), text_color=color)
        val_label.pack(pady=(0, 10))
        return val_label

    def refresh_dynamics(self):
        h = self.history
        self.stat_visits.configure(text=str(len(h)))
        if not h:
            return
            
        last = h[-1]
        last_angle = last.get("angle")
        last_pain  = last.get("pain_level")
        
        self.stat_angle.configure(text=f"{last_angle}°" if last_angle is not None else "--")
        self.stat_pain.configure(text=f"{last_pain}/10" if isinstance(last_pain, int) else "--/10")
        
        if len(h) >= 2:
            prev = h[-2]
            prev_angle = prev.get("angle")
            prev_pain  = prev.get("pain_level")
            
            # Сравнение угла
            if last_angle is not None and prev_angle is not None:
                diff = round(float(last_angle) - float(prev_angle), 1)
                sign = "▼" if diff < 0 else ("▲" if diff > 0 else "=")
                # Если угол уменьшился - это хорошо (зеленый)
                color = COLOR_SUCCESS if diff <= 0 else COLOR_DANGER 
                self.stat_angle_d.configure(text=f"{sign} {abs(diff)}°", text_color=color)
                
            # Сравнение боли
            if isinstance(last_pain, int) and isinstance(prev_pain, int):
                diff_p = last_pain - prev_pain
                sign = "▼" if diff_p < 0 else ("▲" if diff_p > 0 else "=")
                color = COLOR_SUCCESS if diff_p <= 0 else COLOR_DANGER
                self.stat_pain_d.configure(text=f"{sign} {abs(diff_p)}", text_color=color)
                
        self.draw_chart()

    def draw_chart(self):
        if not MATPLOTLIB_OK:
            self.chart_placeholder.configure(text="Библиотека matplotlib не установлена")
            return
            
        dates, angles, pains = [], [], []
        for r in self.history:
            try:
                dt = datetime.strptime(r["date"], "%d.%m.%Y %H:%M")
                
                a = r.get("angle")
                p = r.get("pain_level")
                
                # Добавляем точку только если есть угол или боль
                if a is not None or (p is not None and isinstance(p, int)):
                    dates.append(dt)
                    angles.append(float(a) if a is not None else float("nan"))
                    pains.append(float(p) if isinstance(p, int) else float("nan"))
            except Exception:
                continue
                
        if len(dates) < 2:
            return
            
        self.chart_placeholder.pack_forget()
        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()
            
        # Построение графиков
        fig = Figure(figsize=(9, 4.5), facecolor="#21253a")
        fig.subplots_adjust(hspace=0.5, left=0.1, right=0.95, top=0.9, bottom=0.15)

        # График 1: Угол
        ax1 = fig.add_subplot(2, 1, 1)
        ax1.set_facecolor("#1a1c29")
        ax1.plot(dates, angles, color="#00b4d8", linewidth=2.5, marker="o", markersize=6)
        ax1.fill_between(dates, angles, alpha=0.15, color="#00b4d8")
        ax1.set_ylabel("Угол (°)", color="white", fontsize=9)
        ax1.tick_params(colors="#b0bec5", labelsize=8)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax1.grid(color="#2b304a", linestyle="--", alpha=0.5)
        ax1.set_title("Динамика искривления", color="white", fontsize=11, pad=5)
        for spine in ax1.spines.values(): spine.set_edgecolor("#2b304a")

        # График 2: Боль
        ax2 = fig.add_subplot(2, 1, 2)
        ax2.set_facecolor("#1a1c29")
        ax2.plot(dates, pains, color="#ff5722", linewidth=2.5, marker="s", markersize=6)
        ax2.fill_between(dates, pains, alpha=0.15, color="#ff5722")
        ax2.set_ylabel("Боль (1-10)", color="white", fontsize=9)
        ax2.set_ylim(0, 10.5)
        ax2.tick_params(colors="#b0bec5", labelsize=8)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax2.grid(color="#2b304a", linestyle="--", alpha=0.5)
        ax2.set_title("Уровень боли", color="white", fontsize=11, pad=5)
        for spine in ax2.spines.values(): spine.set_edgecolor("#2b304a")

        self.canvas_widget = FigureCanvasTkAgg(fig, master=self.chart_card)
        self.canvas_widget.draw()
        self.canvas_widget.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=15)

    # ─── ЭКРАН 3: ИСТОРИЯ ──────────────────────────────────────────
    def build_history_screen(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(header, text="История Анализов",
            font=("Roboto", 28, "bold"), text_color="white").pack(side="left")
            
        ctk.CTkButton(header, text="🗑 Очистить все", command=self.clear_history,
            fg_color=COLOR_DANGER, hover_color="#c62828", height=36, width=150).pack(side="right")
            
        list_card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15)
        list_card.pack(fill="both", expand=True)
        
        self.history_scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh_history_list(self):
        for w in self.history_scroll.winfo_children():
            w.destroy()
            
        if not self.history:
            ctk.CTkLabel(self.history_scroll,
                text="История пуста. Проведите первый анализ!",
                text_color="gray", font=("Roboto", 14)).pack(pady=40)
            return
            
        for record in reversed(self.history):
            self.create_history_card(self.history_scroll, record)

    def create_history_card(self, parent, record):
        card = ctk.CTkFrame(parent, fg_color=COLOR_INPUT, corner_radius=10)
        card.pack(fill="x", padx=5, pady=5)
        
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(10, 5))
        
        risk = record.get("risk", "--")
        risk_color = {"низкий": COLOR_SUCCESS, "средний": COLOR_WARNING, "высокий": COLOR_DANGER}.get(risk, "white")
        
        # Дата
        ctk.CTkLabel(top, text=f"{record.get('date','--')}",
            font=("Roboto", 13, "bold"), text_color="white").pack(side="left")
            
        # Показатели
        metrics = []
        if isinstance(record.get('pain_level'), int): metrics.append(f"Боль: {record['pain_level']}/10")
        if record.get('angle') is not None: metrics.append(f"Угол: {record['angle']}°")
        
        ctk.CTkLabel(top, text=" | ".join(metrics),
            font=("Roboto", 12), text_color=COLOR_TEXT_SUB).pack(side="left", padx=15)
            
        ctk.CTkLabel(top, text=f"Риск: {risk.upper()}",
            font=("Roboto", 12, "bold"), text_color=risk_color).pack(side="right")

        # Динамика
        dyn = record.get("dynamics", "")
        if dyn and dyn != "pervichnyy_osmotr":
            dyn_map = {"uluchshenie": "Улучшение", "uhudshenie": "Ухудшение", "bez_izmeneniy": "Без изменений"}
            dyn_colors = {"uluchshenie": COLOR_SUCCESS, "uhudshenie": COLOR_DANGER, "bez_izmeneniy": COLOR_WARNING}
            
            d_text = dyn_map.get(dyn, dyn)
            d_color = dyn_colors.get(dyn, "white")
            
            ctk.CTkLabel(card, text=f"Динамика: {d_text}",
                font=("Roboto", 11, "bold"), text_color=d_color).pack(anchor="w", padx=15)

        # Комментарий
        comment = record.get("comment", "")
        if comment:
            ctk.CTkLabel(card, text=f"{comment}",
                font=("Roboto", 12), text_color="#90caf9",
                wraplength=700, justify="left").pack(anchor="w", padx=15, pady=(0, 10))

    def clear_history(self):
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить всю историю анализов?"):
            self.history = []
            save_json(HISTORY_FILE, self.history)
            self.refresh_history_list()

    # ─── ЭКРАН 4: ПРОФИЛЬ ──────────────────────────────────────────
    def build_profile_screen(self, parent):
        ctk.CTkLabel(parent, text="Медицинский Профиль",
            font=("Roboto", 28, "bold"), text_color="white").pack(anchor="w", pady=(0, 20))
            
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=15)
        card.pack(fill="both", expand=True)
        
        input_grid = ctk.CTkFrame(card, fg_color="transparent")
        input_grid.pack(fill="x", padx=30, pady=30)
        
        fields = [
            ("ФИО Пациента:", "name", 0, 0),
            ("Возраст:", "age", 0, 1),
            ("Рост (см):", "height", 1, 0),
            ("Вес (кг):", "weight", 1, 1),
            ("Диагноз:", "diagnosis", 2, 0),
        ]
        
        self.profile_entries = {}
        for label, key, r, c in fields:
            ff = ctk.CTkFrame(input_grid, fg_color="transparent")
            colspan = 2 if key == "diagnosis" else 1
            ff.grid(row=r, column=c, padx=15, pady=10, sticky="ew", columnspan=colspan)
            
            ctk.CTkLabel(ff, text=label, text_color=COLOR_TEXT_SUB, font=("Roboto", 14)).pack(anchor="w", pady=(0,5))
            entry = ctk.CTkEntry(ff, height=40, border_width=0, fg_color=COLOR_INPUT, text_color="white")
            entry.pack(fill="x")
            
            if key in self.profile:
                entry.insert(0, self.profile[key])
            self.profile_entries[key] = entry
            
            input_grid.grid_columnconfigure(c, weight=1)
            
        # Поле анамнеза
        hf = ctk.CTkFrame(card, fg_color="transparent")
        hf.pack(fill="both", expand=True, padx=45, pady=(0, 20))
        ctk.CTkLabel(hf, text="Анамнез / Хронические заболевания:", text_color=COLOR_TEXT_SUB, font=("Roboto", 14)).pack(anchor="w", pady=(0,5))
        
        self.history_box = ctk.CTkTextbox(hf, height=130, fg_color=COLOR_INPUT, text_color="white", corner_radius=10)
        self.history_box.pack(fill="both", expand=True)
        if "history" in self.profile:
            self.history_box.insert("0.0", self.profile["history"])
            
        # Кнопка сохранения
        ctk.CTkButton(card, text="💾 Сохранить Изменения", command=self.save_profile_data,
            height=48, fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            font=("Roboto", 15, "bold")).pack(pady=(0,10), padx=45, fill="x")
            
        self.profile_status = ctk.CTkLabel(card, text="", text_color=COLOR_SUCCESS, font=("Roboto", 14))
        self.profile_status.pack(pady=(0, 20))

    def save_profile_data(self):
        data = {key: entry.get() for key, entry in self.profile_entries.items()}
        data["history"] = self.history_box.get("0.0", "end").strip()
        
        # Расчет BMI для отображения статуса
        bmi = calculate_bmi(data.get("height"), data.get("weight"))
        bmi_msg = f" (ИМТ: {bmi})" if bmi else ""
        
        self.profile = data
        save_json(PROFILE_FILE, data)
        self.profile_status.configure(text=f"Профиль успешно обновлен{bmi_msg}")
        self.after(3000, lambda: self.profile_status.configure(text=""))

    # ─── ЛОГИКА АНАЛИЗА ────────────────────────────────────────────
    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.image_path = path
            filename = os.path.basename(path)
            self.image_label.configure(text=f"📄 {filename}", text_color=COLOR_SUCCESS)

    def analyze(self):
        symptoms = self.symptom_input.get("0.0", "end").strip()
        # Игнорируем плейсхолдер
        if "Например:" in symptoms: symptoms = ""
        
        if not symptoms and not self.image_path:
            self.show_result_text("⚠️ Пожалуйста, опишите симптомы или загрузите снимок МРТ.")
            return
            
        self.analyze_btn.configure(state="disabled", text="Обработка...")
        self.progress_bar.pack(fill="x", padx=20, pady=(0,5))
        self.progress_bar.start()
        
        self.show_result_text("⏳ Анализ данных нейросетью, пожалуйста подождите...")
        threading.Thread(target=self.run_analysis, args=(symptoms,), daemon=True).start()

    def build_profile_context(self):
        p = self.profile
        lines = []
        if p.get("name"):      lines.append(f"Имя: {p['name']}")
        if p.get("age"):       lines.append(f"Возраст: {p['age']} лет")
        if p.get("height"):    lines.append(f"Рост: {p['height']} см")
        if p.get("weight"):    lines.append(f"Вес: {p['weight']} кг")
        
        bmi = calculate_bmi(p.get("height"), p.get("weight"))
        if bmi: lines.append(f"Индекс массы тела (ИМТ): {bmi}")
        
        if p.get("diagnosis"): lines.append(f"Диагноз: {p['diagnosis']}")
        if p.get("history"):   lines.append(f"История болезни: {p['history']}")
        return "\n".join(lines)

    def get_previous_analysis_context(self):
        if not self.history:
            return ""
        last = self.history[-1]
        lines = ["\nПредыдущий анализ (для оценки динамики):"]
        lines.append(f"  Дата: {last.get('date','--')}")
        if last.get("angle") is not None:
            lines.append(f"  Угол искривления: {last['angle']}")
        if isinstance(last.get("pain_level"), int):
            lines.append(f"  Уровень боли: {last['pain_level']}/10")
        lines.append("Сравни с текущими показателями и укажи динамику.")
        return "\n".join(lines)

    def run_analysis(self, symptoms):
        try:
            profile_ctx   = self.build_profile_context()
            profile_block = f"\nДанные пациента:\n{profile_ctx}\n" if profile_ctx else ""
            pain_block    = f"\nУровень боли пациента: {self.pain_level}/10\n" if self.pain_level else ""
            prev_block    = self.get_previous_analysis_context()

            prompt = f"""Ты опытный врач-вертебролог и рентгенолог.
{profile_block}{pain_block}{prev_block}
Текущие жалобы/симптомы: {symptoms}

Твоя задача: Проанализировать данные и снимок (если есть).
Верни ответ СТРОГО в формате JSON. Никакого текста до или после JSON.
Все значения в JSON должны быть на русском языке.

Формат JSON:
{{
  "ugol_iskrivleniya": <число или null, если по фото/тексту невозможно определить>,
  "zona_davleniya": "<поясничный отдел / грудной отдел / шейный отдел / null>",
  "rekomenduemaya_zhostkost": "<мягкий / средний / жесткий / не требуется>",
  "stepen_riska": "<низкий / средний / высокий>",
  "srochno_k_vrachu": <true или false>,
  "uprazhneniya": ["название упражнения 1", "название упражнения 2"],
  "kommentariy": "<подробное описание проблемы для пациента (на русском)>",
  "dinamika": "<uluchshenie / uhudshenie / bez_izmeneniy / pervichnyy_osmotr>",
  "dinamika_kommentariy": "<сравнение с прошлым визитом, если есть данные>",
  "preduprezhdenie": "Важное напоминание о необходимости очного осмотра."
}}"""

            if self.image_path:
                image = Image.open(self.image_path)
                response = model.generate_content([prompt, image])
            else:
                response = model.generate_content(prompt)

            # Безопасное обновление UI из потока
            self.after(0, lambda: self.process_result(response.text, symptoms))

        except Exception as e:
            self.after(0, lambda: self.show_result_text(f"Ошибка соединения или API: {str(e)}"))

    def process_result(self, raw_text, symptoms):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.analyze_btn.configure(state="normal", text="🔍 Запустить Анализ")
        
        try:
            clean  = re.sub(r"```json|```", "", raw_text).strip()
            data   = json.loads(clean)
            self.last_data = raw_text # Сохраняем оригинал для экспорта
            
            # Сохранение в историю
            record = {
                "date":             datetime.now().strftime("%d.%m.%Y %H:%M"),
                "symptoms":         symptoms,
                "pain_level":       self.pain_level if self.pain_level else "--",
                "risk":             data.get("stepen_riska", "неизвестно"),
                "angle":            data.get("ugol_iskrivleniya"),
                "stiffness":        data.get("rekomenduemaya_zhostkost"),
                "zone":             data.get("zona_davleniya"),
                "urgent":           data.get("srochno_k_vrachu", False),
                "exercises":        data.get("uprazhneniya", []),
                "comment":          data.get("kommentariy", ""),
                "dynamics":         data.get("dinamika", "pervichnyy_osmotr"),
                "dynamics_comment": data.get("dinamika_kommentariy", ""),
            }
            self.history.append(record)
            save_json(HISTORY_FILE, self.history)
            
            self.display_analysis_result(data)
            
        except json.JSONDecodeError:
            self.show_result_text(f"Ошибка чтения ответа от ИИ (не JSON):\n{raw_text}")
        except Exception as e:
            self.show_result_text(f"Ошибка обработки: {str(e)}")

    def display_analysis_result(self, data):
        self.result_box.configure(state="normal")
        self.result_box.delete("0.0", "end")
        
        lines = []
        
        # Динамика
        dyn = data.get("dinamika", "pervichnyy_osmotr")
        if dyn != "pervichnyy_osmotr":
            dyn_map = {"uluchshenie": "ПОЛОЖИТЕЛЬНАЯ (Улучшение)", 
                       "uhudshenie": "ОТРИЦАТЕЛЬНАЯ (Ухудшение)", 
                       "bez_izmeneniy": "БЕЗ ИЗМЕНЕНИЙ"}
            lines.append("📊 ДИНАМИКА:")
            lines.append(f"   {dyn_map.get(dyn, dyn)}")
            if data.get("dinamika_kommentariy"):
                lines.append(f"   {data.get('dinamika_kommentariy')}")
            lines.append("-" * 40)

        # Основные данные
        angle = data.get('ugol_iskrivleniya')
        angle_str = f"{angle}°" if angle is not None else "Не определен"
        
        lines.append(f"📐 Угол искривления:  {angle_str}")
        lines.append(f"📍 Зона проблемы:     {data.get('zona_davleniya', '—')}")
        lines.append(f"⚙️ Корсет/Жесткость:  {data.get('rekomenduemaya_zhostkost', '—')}")
        lines.append(f"⚠️ Степень риска:     {data.get('stepen_riska', '—')}")
        
        urgent = data.get('srochno_k_vrachu')
        urg_str = "🚨 ДА, НУЖЕН ВРАЧ!" if urgent else "Нет, плановый осмотр"
        lines.append(f"🚑 Срочно к врачу:    {urg_str}")
        
        if self.pain_level:
            lines.append(f"⚡ Уровень боли:      {self.pain_level}/10")

        lines.append("\n" + "─"*30 + "\n")
        
        lines.append("🏃 Рекомендуемые упражнения:")
        for ex in data.get("uprazhneniya", []):
            lines.append(f"   • {ex}")
            
        lines.append("\n💬 Заключение ИИ:")
        lines.append(data.get('kommentariy', ''))
        
        lines.append(f"\nℹ️ ВАЖНО: {data.get('preduprezhdenie', '')}")

        self.result_box.insert("0.0", "\n".join(lines))
        self.result_box.configure(state="disabled")

    def show_result_text(self, text):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.analyze_btn.configure(state="normal", text="🔍 Запустить Анализ")
        self.result_box.configure(state="normal")
        self.result_box.delete("0.0", "end")
        self.result_box.insert("0.0", text)
        self.result_box.configure(state="disabled")

    # ─── ЭКСПОРТ ОТЧЕТА ────────────────────────────────────────────
    def export_report(self):
        if not self.last_data:
            messagebox.showwarning("Нет данных", "Сначала проведите анализ.")
            return
            
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML файл", "*.html")],
            title="Сохранить заключение"
        )
        if not path: return
        
        try:
            clean = re.sub(r"```json|```", "", self.last_data).strip()
            data  = json.loads(clean)
        except:
            return

        p = self.profile
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        # Подготовка данных для HTML
        pain_str = f"{self.pain_level}/10" if self.pain_level else "Не указан"
        urgent_css = "color:red;font-weight:bold" if data.get("srochno_k_vrachu") else "color:green"
        urgent_txt = "ТРЕБУЕТСЯ ОСМОТР ВРАЧА" if data.get("srochno_k_vrachu") else "Плановый режим"
        
        ex_html = "".join(f"<li>{ex}</li>" for ex in data.get("uprazhneniya", []))
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Медицинское заключение - Spine Advisor</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 40px auto; color: #333; line-height: 1.6; }}
                .header {{ border-bottom: 3px solid #00b4d8; padding-bottom: 20px; margin-bottom: 30px; }}
                .header h1 {{ margin: 0; color: #16213e; }}
                .meta {{ color: #666; font-size: 0.9em; margin-top: 5px; }}
                .section {{ background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .section h2 {{ margin-top: 0; color: #00b4d8; font-size: 1.2em; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
                .field {{ margin-bottom: 5px; }}
                .label {{ font-weight: bold; color: #555; }}
                .alert {{ background: #fff3e0; border-left: 5px solid #ff9800; padding: 15px; margin: 20px 0; }}
                .footer {{ text-align: center; font-size: 0.8em; color: #aaa; margin-top: 50px; border-top: 1px solid #eee; padding-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Spine Advisor: Заключение ИИ</h1>
                <div class="meta">Дата анализа: {date_str}</div>
            </div>

            <div class="section">
                <h2>Данные пациента</h2>
                <div class="grid">
                    <div class="field"><span class="label">ФИО:</span> {p.get('name','—')}</div>
                    <div class="field"><span class="label">Возраст:</span> {p.get('age','—')}</div>
                    <div class="field"><span class="label">Рост/Вес:</span> {p.get('height','—')} см / {p.get('weight','—')} кг</div>
                </div>
            </div>

            <div class="section">
                <h2>Результаты диагностики</h2>
                <div class="grid">
                    <div class="field"><span class="label">Угол искривления:</span> {data.get('ugol_iskrivleniya','—')}</div>
                    <div class="field"><span class="label">Зона давления:</span> {data.get('zona_davleniya','—')}</div>
                    <div class="field"><span class="label">Степень риска:</span> {data.get('stepen_riska','—')}</div>
                    <div class="field"><span class="label">Уровень боли:</span> {pain_str}</div>
                </div>
                <br>
                <div class="field"><span class="label">Статус:</span> <span style="{urgent_css}">{urgent_txt}</span></div>
            </div>

            <div class="section">
                <h2>Рекомендации и Упражнения</h2>
                <p>{data.get('kommentariy','')}</p>
                <ul>{ex_html}</ul>
            </div>

            <div class="alert">
                <strong>ВАЖНО:</strong> {data.get('preduprezhdenie','Данный отчет сформирован искусственным интеллектом и не является официальным медицинским диагнозом. Обратитесь к врачу.')}
            </div>

            <div class="footer">
                Сгенерировано в приложении Spine Advisor v3.1
            </div>
        </body>
        </html>
        """

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
            
        # Автооткрытие в браузере (где можно сохранить в PDF через Ctrl+P)
        import webbrowser
        webbrowser.open(path)
        messagebox.showinfo("Готово", "Отчет сохранен!\nОн открыт в браузере.\nНажмите Ctrl+P, чтобы сохранить как PDF.")

if __name__ == "__main__":
    app = SpineApp()
    app.mainloop()