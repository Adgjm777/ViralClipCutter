import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import os
import viral_clip_cutter  # Импорт модуля

from viral_clip_cutter import ViralClipCutter  # Импорт класса

class ClipCutterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Viral Clip Cutter by Vitalii Moskalev")
        self.root.geometry("800x600")
        
        # Создаем основные элементы интерфейса
        self.create_widgets()
        
    def create_widgets(self):
        # Заголовок с автором
        title_frame = ttk.Frame(self.root)
        title_frame.pack(padx=10, pady=10, fill="x")
        
        ttk.Label(title_frame, text="Viral Clip Cutter", font=("Arial", 16, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(title_frame, text="Создано: Vitalii Moskalev", font=("Arial", 12)).grid(row=1, column=0, sticky="w", padx=5)
        
        # Фрейм для контактов
        contact_frame = ttk.Frame(self.root)
        contact_frame.pack(padx=10, pady=5, fill="x")
        
        ttk.Label(contact_frame, text="Telegram: @adgjm90", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(contact_frame, text="Email: moskalevvitalii@gmail.com", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky="w", padx=5)
        
        # Фрейм для входных данных
        input_frame = ttk.LabelFrame(self.root, text="Входные данные")
        input_frame.pack(padx=10, pady=10, fill="x")
        
        # Поле ввода пути к файлу/URL
        ttk.Label(input_frame, text="Входной файл/URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.input_entry = ttk.Entry(input_frame, width=50)
        self.input_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(input_frame, text="Обзор", command=self.browse_input).grid(row=0, column=2, padx=5, pady=5)
        
        # Поле выбора выходной директории
        ttk.Label(input_frame, text="Выходная директория:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.output_entry = ttk.Entry(input_frame, width=50)
        self.output_entry.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(input_frame, text="Обзор", command=self.browse_output).grid(row=1, column=2, padx=5, pady=5)
        
        # Параметры нарезки
        params_frame = ttk.LabelFrame(self.root, text="Параметры нарезки")
        params_frame.pack(padx=10, pady=10, fill="x")
        
        # Порог сцен
        ttk.Label(params_frame, text="Порог сцен:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.threshold_var = tk.DoubleVar(value=0.4)
        ttk.Spinbox(params_frame, from_=0.1, to=0.9, increment=0.1, 
                   textvariable=self.threshold_var).grid(row=0, column=1, padx=5, pady=5)
        
        # Минимальная длительность
        ttk.Label(params_frame, text="Мин. длительность (сек):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.min_duration_var = tk.DoubleVar(value=3.0)
        ttk.Spinbox(params_frame, from_=1.0, to=60.0, increment=1.0, 
                   textvariable=self.min_duration_var).grid(row=1, column=1, padx=5, pady=5)
        
        # Максимальная длительность
        ttk.Label(params_frame, text="Макс. длительность (сек):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.max_duration_var = tk.DoubleVar(value=60.0)
        ttk.Spinbox(params_frame, from_=5.0, to=300.0, increment=5.0, 
                   textvariable=self.max_duration_var).grid(row=2, column=1, padx=5, pady=5)
        
        # Формат вывода
        ttk.Label(params_frame, text="Формат:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.format_var = tk.StringVar(value="original")
        format_combo = ttk.Combobox(params_frame, textvariable=self.format_var, 
                                   values=["original", "vertical", "square"])
        format_combo.grid(row=3, column=1, padx=5, pady=5)
        
        # Дополнительные опции
        options_frame = ttk.LabelFrame(self.root, text="Дополнительные опции")
        options_frame.pack(padx=10, pady=10, fill="x")
        
        # Чекбоксы
        self.title_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Добавить заголовок", variable=self.title_var).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.subtitles_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Добавить субтитры", variable=self.subtitles_var).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        self.template_var = tk.StringVar(value="none")
        ttk.Label(options_frame, text="Шаблон:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        template_combo = ttk.Combobox(options_frame, textvariable=self.template_var, 
                                     values=["none", "tiktok", "instagram", "youtube"])
        template_combo.grid(row=1, column=1, padx=5, pady=5)
        
        self.music_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Добавить музыку", variable=self.music_var).grid(row=2, column=0, sticky="w", padx=5, pady=5)
        
        self.viral_boost_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Вирусный буст", variable=self.viral_boost_var).grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        self.preview_var = tk.BooleanVar(value=False)  # Добавлен чекбокс для preview
        ttk.Checkbutton(options_frame, text="Предпросмотр", variable=self.preview_var).grid(row=3, column=0, sticky="w", padx=5, pady=5)
        
        # Кнопки
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.pack(padx=10, pady=10, fill="x")
        
        ttk.Button(buttons_frame, text="Запустить", command=self.run_cutter).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(buttons_frame, text="Отмена", command=self.root.quit).grid(row=0, column=1, padx=5, pady=5)
        
        # Поле для вывода логов
        log_frame = ttk.LabelFrame(self.root, text="Лог")
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(padx=5, pady=5, fill="both", expand=True)
        
    def browse_input(self):
        path = filedialog.askopenfilename(title="Выберите входной файл", 
                                         filetypes=[("Видео файлы", "*.mp4 *.avi *.mov"), 
                                                    ("Все файлы", "*.*")])
        if path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, path)
            
    def browse_output(self):
        path = filedialog.askdirectory(title="Выберите выходную директорию")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)
            
    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def run_cutter(self):
        # Собираем параметры
        input_path = self.input_entry.get()
        output_dir = self.output_entry.get()
        
        if not input_path:
            messagebox.showerror("Ошибка", "Укажите входной файл/URL")
            return
            
        if not output_dir:
            messagebox.showerror("Ошибка", "Укажите выходную директорию")
            return
            
        # Создаем аргументы для ViralClipCutter
        args = type('', (), {})()  # Пустой объект для имитации argparse.Namespace
        args.input = input_path
        args.output = output_dir
        args.threshold = self.threshold_var.get()
        args.min_duration = self.min_duration_var.get()
        args.max_duration = self.max_duration_var.get()
        args.format = self.format_var.get()
        args.title = self.title_var.get()
        args.subtitles = self.subtitles_var.get()
        args.template = self.template_var.get()
        args.music = self.music_var.get()
        args.viral_boost = self.viral_boost_var.get()
        args.workers = 2  # По умолчанию 2 потока
        args.verbose = True  # Включаем подробный вывод для лога
        args.equal_parts = False  # По умолчанию режим обнаружения сцен
        args.part_duration = 15.0
        args.auto_fallback = True
        args.command_timeout = 300
        args.music_file = None  # Укажите путь к музыкальному файлу, если нужно
        args.preview = self.preview_var.get()  # Используем значение из чекбокса
        args.smart_reframe = self.viral_boost_var.get()  # Пример: связываем viral_boost с smart_reframe
        
        # Запускаем обработку
        self.log("Начало обработки...")
        try:
            cutter = ViralClipCutter(args)
            print(f"smart_reframe: {cutter.smart_reframe}")  # Для отладки
            success = cutter.run()
            if success:
                self.log("Обработка завершена успешно!")
                messagebox.showinfo("Успех", "Клипы успешно созданы!")
            else:
                self.log("Обработка завершена с ошибками.")
                messagebox.showwarning("Внимание", "Не все клипы были созданы.")
        except Exception as e:
            self.log(f"Ошибка: {str(e)}")
            messagebox.showerror("Ошибка", f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ClipCutterGUI(root)
    root.mainloop()