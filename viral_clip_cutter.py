import os
import sys
import subprocess
import argparse
import json
import cv2
import numpy as np
from datetime import datetime
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
import re
import requests
from urllib.parse import urlparse, parse_qs
import signal
import threading
import time

# Добавляем поддержку для распознавания речи (если установлено)
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

# Добавляем поддержку для загрузки видео из YouTube (если установлено)
try:
    from yt_dlp import YoutubeDL
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

class TimeoutError(Exception):
    """Исключение, вызываемое при превышении времени ожидания."""
    pass

def timeout_handler(signum, frame):
    """Обработчик сигнала для таймаута."""
    raise TimeoutError("Превышено время ожидания выполнения команды")

class ProcessWithTimeout:
    """Класс для запуска процесса с таймаутом."""
    def __init__(self, cmd, timeout=300, verbose=False):
        self.cmd = cmd
        self.timeout = timeout
        self.verbose = verbose
        self.process = None
        self.stdout_data = None
        self.stderr_data = None
        self.returncode = None
        self.timed_out = False
        
    def run(self):
        """Запускает процесс с таймаутом."""
        def target():
            self.process = subprocess.Popen(
                self.cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            self.stdout_data, self.stderr_data = self.process.communicate()
            self.returncode = self.process.returncode
            
        thread = threading.Thread(target=target)
        thread.start()
        
        thread.join(self.timeout)
        if thread.is_alive():
            if self.verbose:
                print(f"Превышено время ожидания ({self.timeout} сек) для команды: {' '.join(self.cmd)}")
            
            # Завершаем процесс
            if self.process:
                try:
                    self.process.terminate()
                    time.sleep(1)
                    if self.process.poll() is None:
                        self.process.kill()
                except:
                    pass
                
            thread.join()
            self.timed_out = True
            self.returncode = -1
            self.stdout_data = b""
            self.stderr_data = b"Timeout exceeded"
            
        return self.returncode, self.stdout_data, self.stderr_data, self.timed_out

class ViralClipCutter:
    def __init__(self, args):
        """Инициализация с параметрами командной строки"""
        self.input_file = args.input
        self.output_dir = args.output
        self.scene_threshold = args.threshold
        self.min_duration = args.min_duration
        self.max_duration = args.max_duration
        self.format = args.format
        self.add_title = args.title
        self.workers = args.workers
        self.verbose = args.verbose
        self.equal_parts = args.equal_parts
        self.part_duration = args.part_duration
        self.add_subtitles = args.subtitles
        self.template = args.template
        self.smart_reframe = args.smart_reframe  # Инициализация атрибута
        self.add_music = args.music
        self.music_file = args.music_file
        self.preview = args.preview
        self.viral_boost = args.viral_boost
        self.auto_fallback = args.auto_fallback
        self.command_timeout = args.command_timeout
        
        # Создаем выходную директорию, если она не существует
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Настройка логирования
        self.log_file = os.path.join(self.output_dir, "clipcutter_log.txt")
        
        # Инициализация временной директории для рабочих файлов
        self.temp_dir = tempfile.mkdtemp()
        
        # Шаблоны для разных платформ
        self.templates = {
            "tiktok": {
                "overlay": "assets/templates/tiktok_overlay.png",
                "font": "assets/fonts/tiktok_font.ttf",
                "text_position": "bottom"
            },
            "instagram": {
                "overlay": "assets/templates/instagram_overlay.png",
                "font": "assets/fonts/instagram_font.ttf",
                "text_position": "top"
            },
            "youtube": {
                "overlay": "assets/templates/youtube_overlay.png",
                "font": "assets/fonts/youtube_font.ttf",
                "text_position": "bottom"
            },
            "none": None
        }
        
        # Музыкальные треки
        self.music_tracks = {
            "energetic": "assets/music/energetic.mp3",
            "emotional": "assets/music/emotional.mp3",
            "funny": "assets/music/funny.mp3",
            "dramatic": "assets/music/dramatic.mp3",
            "none": None
        }
        
    def __del__(self):
        """Деструктор для очистки временных файлов"""
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
        
    def log(self, message):
        """Логирование сообщений"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        if self.verbose:
            print(log_message)
            
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    
    def run_command_with_timeout(self, cmd, timeout=None):
        """Запускает команду с таймаутом и возвращает результат."""
        if timeout is None:
            timeout = self.command_timeout
            
        self.log(f"Выполнение команды с таймаутом {timeout} сек: {' '.join(cmd)}")
        
        process = ProcessWithTimeout(cmd, timeout=timeout, verbose=self.verbose)
        returncode, stdout_data, stderr_data, timed_out = process.run()
        
        stdout_text = stdout_data.decode('utf-8', errors='ignore')
        stderr_text = stderr_data.decode('utf-8', errors='ignore')
        
        if timed_out:
            self.log(f"ОШИБКА: Превышено время ожидания ({timeout} сек) для команды")
            return returncode, stdout_text, stderr_text, True
            
        return returncode, stdout_text, stderr_text, False
    
    def download_from_url(self, url):
        """Загрузка видео по URL (YouTube, Reddit и др.)"""
        if not YTDLP_AVAILABLE:
            self.log("Ошибка: для загрузки видео по URL требуется установить yt-dlp (pip install yt-dlp)")
            return None
            
        self.log(f"Загрузка видео с URL: {url}")
        
        # Определяем тип URL
        if "youtube.com" in url or "youtu.be" in url:
            source_type = "youtube"
        elif "reddit.com" in url:
            source_type = "reddit"
        else:
            source_type = "generic"
            
        # Настройки для yt-dlp
        ydl_opts = {
            'format': 'best[ext=mp4]',
            'outtmpl': os.path.join(self.temp_dir, 'downloaded_video.%(ext)s'),
            'quiet': not self.verbose,
        }
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
                self.log(f"Видео успешно загружено: {downloaded_file}")
                return downloaded_file
        except Exception as e:
            self.log(f"Ошибка при загрузке видео: {str(e)}")
            return None
    
    def get_video_info(self, video_file=None):
        """Получение информации о видео (длительность, разрешение и т.д.)"""
        if video_file is None:
            video_file = self.input_file
            
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd, timeout=60)
        
        if timed_out:
            self.log("Превышено время ожидания при получении информации о видео")
            return None
            
        if returncode != 0:
            self.log(f"Ошибка при получении информации о видео")
            return None
            
        try:
            info = json.loads(stdout_text)
            return info
        except json.JSONDecodeError:
            self.log("Ошибка при парсинге информации о видео")
            return None
    
    def detect_scenes(self):
        """Определяет смены сцен с помощью FFmpeg и возвращает список временных меток."""
        self.log(f"Анализ сцен с порогом {self.scene_threshold}...")
        
        cmd = [
            "ffmpeg", "-i", self.input_file, "-filter_complex",
            f"select='gt(scene,{self.scene_threshold})',metadata=print", "-an", "-f", "null", "-"
        ]
        
        self.log(f"Выполнение команды: {' '.join(cmd)}")
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log("Превышено время ожидания при анализе сцен")
            return []
            
        if returncode != 0:
            self.log(f"Ошибка при анализе сцен")
            return []
            
        lines = stderr_text.splitlines()
        times = []
        
        for line in lines:
            if "pts_time:" in line:
                parts = line.split("pts_time:")
                if len(parts) > 1:
                    try:
                        times.append(float(parts[1].strip()))
                    except ValueError:
                        pass
        
        self.log(f"Найдено {len(times)} смен сцен")
        return times
    
    def detect_interesting_moments(self):
        """Расширенное определение интересных моментов на основе аудио и видео анализа"""
        self.log("Анализ интересных моментов в видео...")
        
        # Сначала получаем обычные смены сцен
        scene_times = self.detect_scenes()
        
        if self.viral_boost and len(scene_times) > 0:
            # Анализ аудио для определения громких моментов
            audio_peaks = self.detect_audio_peaks()
            
            # Анализ движения для определения активных сцен
            motion_peaks = self.detect_motion_peaks()
            
            # Объединяем все маркеры
            all_markers = set(scene_times)
            all_markers.update(audio_peaks)
            all_markers.update(motion_peaks)
            
            # Сортируем все маркеры
            sorted_markers = sorted(list(all_markers))
            self.log(f"Найдено {len(sorted_markers)} интересных моментов (сцены + аудио + движение)")
            
            return sorted_markers
        else:
            return scene_times
    
    def detect_audio_peaks(self):
        """Определение пиков громкости в аудиодорожке"""
        self.log("Анализ аудио для определения пиков громкости...")
        
        # Извлекаем аудио во временный файл
        audio_file = os.path.join(self.temp_dir, "audio.wav")
        cmd = [
            "ffmpeg", "-y", "-i", self.input_file, "-vn", "-acodec", "pcm_s16le", 
            "-ar", "44100", "-ac", "1", audio_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out or returncode != 0 or not os.path.exists(audio_file):
            self.log("Не удалось извлечь аудио")
            return []
        
        # Анализируем громкость с помощью FFmpeg
        cmd = [
            "ffmpeg", "-i", audio_file, "-af", 
            "volumedetect", "-f", "null", "-"
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log("Превышено время ожидания при анализе громкости")
            return []
        
        # Более сложный анализ с использованием сегментации
        cmd = [
            "ffmpeg", "-i", audio_file, "-af", 
            "silencedetect=noise=-30dB:d=0.5", "-f", "null", "-"
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log("Превышено время ожидания при анализе тишины")
            return []
        
        # Извлекаем моменты окончания тишины (начало громких частей)
        peaks = []
        for line in stderr_text.splitlines():
            if "silence_end" in line:
                match = re.search(r"silence_end: (\d+\.?\d*)", line)
                if match:
                    peaks.append(float(match.group(1)))
        
        self.log(f"Найдено {len(peaks)} аудио пиков")
        return peaks
    
    def detect_motion_peaks(self):
        """Определение моментов с интенсивным движением"""
        self.log("Анализ видео для определения интенсивного движения...")
        
        # Извлекаем кадры с низким разрешением для быстрого анализа
        frames_dir = os.path.join(self.temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Извлекаем кадры с частотой 1 кадр в секунду
        cmd = [
            "ffmpeg", "-i", self.input_file, "-vf", "fps=1,scale=320:-1", 
            "-q:v", "3", os.path.join(frames_dir, "frame_%04d.jpg")
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log("Превышено время ожидания при извлечении кадров")
            return []
        
        # Анализируем движение между кадрами
        frame_files = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.endswith('.jpg')])
        
        if len(frame_files) < 2:
            self.log("Недостаточно кадров для анализа движения")
            return []
        
        motion_scores = []
        prev_frame = cv2.imread(frame_files[0], cv2.IMREAD_GRAYSCALE)
        
        for i in range(1, len(frame_files)):
            curr_frame = cv2.imread(frame_files[i], cv2.IMREAD_GRAYSCALE)
            if curr_frame is None:
                continue
                
            # Вычисляем разницу между кадрами
            frame_diff = cv2.absdiff(curr_frame, prev_frame)
            motion_score = np.sum(frame_diff) / (frame_diff.shape[0] * frame_diff.shape[1])
            motion_scores.append((i, motion_score))
            
            prev_frame = curr_frame
        
        # Находим пики движения (верхние 20%)
        if motion_scores:
            motion_scores.sort(key=lambda x: x[1], reverse=True)
            top_motion = motion_scores[:max(1, len(motion_scores) // 5)]
            motion_peaks = sorted([score[0] for score in top_motion])  # Секунды от начала видео
            
            self.log(f"Найдено {len(motion_peaks)} пиков движения")
            return motion_peaks
        
        return []
    
    def filter_scenes(self, times):
        """Фильтрует сцены по длительности и другим критериям"""
        if not times:
            return []
            
        # Добавляем начало видео и получаем длительность
        video_info = self.get_video_info()
        if not video_info:
            return []
            
        try:
            duration = float(video_info["format"]["duration"])
            self.log(f"Общая длительность видео: {duration} секунд")
        except (KeyError, ValueError):
            self.log("Не удалось определить длительность видео")
            return []
            
        # Добавляем начало и конец видео
        times = [0.0] + times
        times.append(duration)
        
        # Фильтруем сцены по длительности
        filtered_scenes = []
        
        for i in range(len(times) - 1):
            start = times[i]
            end = times[i + 1]
            scene_duration = end - start
            
            if self.min_duration <= scene_duration <= self.max_duration:
                filtered_scenes.append((start, end))
                
        self.log(f"После фильтрации осталось {len(filtered_scenes)} сцен")
        return filtered_scenes
    
    def create_equal_parts(self):
        """Создает список временных отрезков равной длительности"""
        video_info = self.get_video_info()
        if not video_info:
            return []
            
        try:
            duration = float(video_info["format"]["duration"])
            self.log(f"Общая длительность видео: {duration} секунд")
        except (KeyError, ValueError):
            self.log("Не удалось определить длительность видео")
            return []
        
        parts = []
        start_time = 0.0
        
        while start_time < duration:
            end_time = min(start_time + self.part_duration, duration)
            if end_time - start_time >= self.min_duration:
                parts.append((start_time, end_time))
            start_time = end_time
        
        self.log(f"Создано {len(parts)} равных частей по {self.part_duration} секунд")
        return parts
    
    def generate_subtitles(self, input_file):
        """Генерирует субтитры для видео с помощью распознавания речи"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.log("Ошибка: для генерации субтитров требуется установить SpeechRecognition (pip install SpeechRecognition)")
            return None
            
        self.log("Генерация субтитров...")
        
        # Извлекаем аудио во временный файл
        audio_file = os.path.join(self.temp_dir, "audio_for_subs.wav")
        cmd = [
            "ffmpeg", "-y", "-i", input_file, "-vn", "-acodec", "pcm_s16le", 
            "-ar", "16000", "-ac", "1", audio_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out or returncode != 0 or not os.path.exists(audio_file):
            self.log("Не удалось извлечь аудио для субтитров")
            return None
        
        # Разделяем аудио на сегменты для лучшего распознавания
        segments_dir = os.path.join(self.temp_dir, "audio_segments")
        os.makedirs(segments_dir, exist_ok=True)
        
        # Получаем длительность аудио
        audio_info = self.get_video_info(audio_file)
        if not audio_info:
            return None
            
        try:
            duration = float(audio_info["format"]["duration"])
        except (KeyError, ValueError):
            self.log("Не удалось определить длительность аудио")
            return None
        
        # Разделяем на сегменты по 10 секунд
        segment_length = 10
        subtitles = []
        
        recognizer = sr.Recognizer()
        
        for i in range(0, int(duration), segment_length):
            segment_file = os.path.join(segments_dir, f"segment_{i}.wav")
            end_time = min(i + segment_length, duration)
            
            # Вырезаем сегмент
            cmd = [
                "ffmpeg", "-y", "-i", audio_file, "-ss", str(i), 
                "-t", str(end_time - i), segment_file
            ]
            
            returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd, timeout=60)
            
            if timed_out or returncode != 0 or not os.path.exists(segment_file):
                continue
                
            # Распознаем речь
            try:
                with sr.AudioFile(segment_file) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data, language="ru-RU")
                    
                    if text:
                        # Формат SRT: номер, время начала --> время конца, текст
                        start_time_str = self.format_srt_time(i)
                        end_time_str = self.format_srt_time(end_time)
                        
                        subtitles.append(f"{len(subtitles) + 1}")
                        subtitles.append(f"{start_time_str} --> {end_time_str}")
                        subtitles.append(text)
                        subtitles.append("")  # Пустая строка между субтитрами
            except Exception as e:
                self.log(f"Ошибка при распознавании речи: {str(e)}")
        
        if subtitles:
            srt_file = os.path.join(self.temp_dir, "subtitles.srt")
            with open(srt_file, "w", encoding="utf-8") as f:
                f.write("\n".join(subtitles))
            
            self.log(f"Субтитры сгенерированы и сохранены в {srt_file}")
            return srt_file
        
        return None
    
    def format_srt_time(self, seconds):
        """Форматирует время для SRT субтитров"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
    
    def add_title_to_video(self, input_file, output_file, title_text):
        """Добавляет заголовок к видео"""
        cmd = [
            "ffmpeg", "-y", "-i", input_file, "-vf",
            f"drawtext=text='{title_text}':fontcolor=white:fontsize=30:box=1:boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=30",
            "-c:a", "copy", output_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log(f"Превышено время ожидания при добавлении заголовка")
            # Если не удалось добавить заголовок, просто копируем файл
            shutil.copy(input_file, output_file)
    
    def apply_template(self, input_file, output_file, template_name):
        """Применяет шаблон оформления к видео"""
        if template_name == "none" or template_name not in self.templates:
            # Просто копируем файл без изменений
            shutil.copy(input_file, output_file)
            return
            
        template = self.templates[template_name]
        
        # Проверяем наличие файлов шаблона
        template_dir = "assets/templates"
        if not os.path.exists(template_dir):
            os.makedirs(template_dir, exist_ok=True)
            
        # Если файла шаблона нет, создаем заглушку
        overlay_file = template["overlay"]
        if not os.path.exists(overlay_file):
            # Создаем простую заглушку для оверлея
            self.create_template_placeholder(template_name)
            
        # Применяем шаблон с помощью FFmpeg
        cmd = [
            "ffmpeg", "-y", "-i", input_file, "-i", overlay_file,
            "-filter_complex", "[0:v][1:v]overlay=0:0", "-c:a", "copy", output_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log(f"Превышено время ожидания при применении шаблона")
            # Если не удалось применить шаблон, просто копируем файл
            shutil.copy(input_file, output_file)
    
    def create_template_placeholder(self, template_name):
        """Создает заглушку для шаблона, если файл не существует"""
        template = self.templates[template_name]
        overlay_file = template["overlay"]
        
        # Создаем директорию, если не существует
        os.makedirs(os.path.dirname(overlay_file), exist_ok=True)
        
        # Создаем простое изображение с текстом
        img = np.zeros((1080, 1920, 4), dtype=np.uint8)  # RGBA
        img[:, :, 3] = 128  # Полупрозрачность
        
        # Добавляем текст
        cv2.putText(img, f"{template_name.upper()} TEMPLATE", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255, 255), 2)
        
        # Сохраняем изображение
        cv2.imwrite(overlay_file, img)
    
    def smart_reframe_video(self, input_file, output_file, target_format):
        """Интеллектуальное изменение соотношения сторон с фокусом на объектах"""
        if not self.smart_reframe:  # Используем self.smart_reframe
            # Используем стандартное изменение формата
            self.format_for_social(input_file, output_file)
            return
            
        self.log("Применение интеллектуального рефрейминга...")
        
        # Определяем целевое соотношение сторон
        if target_format == "vertical":
            target_ratio = 9/16  # Вертикальный формат (9:16)
            target_width = 1080
            target_height = 1920
        elif target_format == "square":
            target_ratio = 1  # Квадратный формат (1:1)
            target_width = 1080
            target_height = 1080
        else:
            # Оригинальный формат
            shutil.copy(input_file, output_file)
            return
        
        # Получаем информацию о видео
        video_info = self.get_video_info(input_file)
        if not video_info:
            # Если не удалось получить информацию, используем стандартное изменение формата
            self.format_for_social(input_file, output_file)
            return
            
        # Извлекаем разрешение
        try:
            for stream in video_info["streams"]:
                if stream["codec_type"] == "video":
                    width = int(stream["width"])
                    height = int(stream["height"])
                    break
            else:
                raise KeyError("Video stream not found")
        except (KeyError, ValueError):
            self.log("Не удалось определить разрешение видео")
            self.format_for_social(input_file, output_file)
            return
        
        # Определяем области интереса в видео
        roi = self.detect_roi(input_file, width, height)
        
        if roi:
            # Используем обнаруженную область интереса для кадрирования
            x, y, w, h = roi
            
            # Вычисляем параметры кадрирования с учетом целевого соотношения сторон
            crop_ratio = w / h
            
            if crop_ratio > target_ratio:
                # Если область шире, чем нужно, уменьшаем ширину
                new_w = int(h * target_ratio)
                x_offset = x + (w - new_w) // 2
                crop_params = f"{new_w}:{h}:{x_offset}:{y}"
            else:
                # Если область выше, чем нужно, уменьшаем высоту
                new_h = int(w / target_ratio)
                y_offset = y + (h - new_h) // 2
                crop_params = f"{w}:{new_h}:{x}:{y_offset}"
            
            # Применяем кадрирование и масштабирование
            cmd = [
                "ffmpeg", "-y", "-i", input_file, "-vf",
                f"crop={crop_params},scale={target_width}:{target_height}",
                "-c:a", "copy", output_file
            ]
        else:
            # Если не удалось определить область интереса, используем стандартное изменение формата
            self.format_for_social(input_file, output_file)
            return
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log(f"Превышено время ожидания при применении интеллектуального рефрейминга")
            # Если не удалось применить рефрейминг, используем стандартное изменение формата
            self.format_for_social(input_file, output_file)
    
    def detect_roi(self, video_file, width, height):
        """Определяет область интереса (Region of Interest) в видео"""
        self.log("Определение области интереса в видео...")
        
        # Извлекаем кадры для анализа
        frames_dir = os.path.join(self.temp_dir, "roi_frames")
        os.makedirs(frames_dir, exist_ok=True)
        
        # Извлекаем 10 кадров равномерно распределенных по видео
        cmd = [
            "ffmpeg", "-i", video_file, "-vf", "select='not(mod(n,floor(n_frames/10)))',scale=640:-1", 
            "-vsync", "0", os.path.join(frames_dir, "frame_%03d.jpg")
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd, timeout=60)
        
        if timed_out:
            self.log("Превышено время ожидания при извлечении кадров для ROI")
            return None
        
        frame_files = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.endswith('.jpg')])
        
        if not frame_files:
            self.log("Не удалось извлечь кадры для анализа ROI")
            return None
        
        # Загружаем каскады для обнаружения лиц
        try:
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        except:
            self.log("Не удалось загрузить каскады для обнаружения лиц")
            face_cascade = None
        
        # Анализируем кадры для определения областей интереса
        roi_areas = []
        
        for frame_file in frame_files:
            frame = cv2.imread(frame_file)
            if frame is None:
                continue
                
            # Масштабируем для ускорения обработки
            scale_factor = 640 / frame.shape[1]
            frame_small = cv2.resize(frame, (640, int(frame.shape[0] * scale_factor)))
            
            # Обнаружение лиц
            if face_cascade:
                gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                
                for (x, y, w, h) in faces:
                    # Масштабируем обратно к оригинальному размеру
                    x_orig = int(x / scale_factor)
                    y_orig = int(y / scale_factor)
                    w_orig = int(w / scale_factor)
                    h_orig = int(h / scale_factor)
                    
                    # Добавляем отступы вокруг лица
                    padding = 0.5  # 50% от размера лица
                    x_pad = max(0, int(x_orig - w_orig * padding))
                    y_pad = max(0, int(y_orig - h_orig * padding))
                    w_pad = min(width - x_pad, int(w_orig * (1 + 2 * padding)))
                    h_pad = min(height - y_pad, int(h_orig * (1 + 2 * padding)))
                    
                    roi_areas.append((x_pad, y_pad, w_pad, h_pad))
            
            # Если лица не обнаружены, используем анализ движения
            if not roi_areas:
                # Здесь можно добавить анализ движения или другие методы
                pass
        
        if roi_areas:
            # Объединяем все найденные области интереса
            x_min = min(area[0] for area in roi_areas)
            y_min = min(area[1] for area in roi_areas)
            x_max = max(area[0] + area[2] for area in roi_areas)
            y_max = max(area[1] + area[3] for area in roi_areas)
            
            # Проверяем, что область не слишком маленькая
            if (x_max - x_min) < width * 0.3 or (y_max - y_min) < height * 0.3:
                # Если область слишком маленькая, расширяем ее
                center_x = (x_min + x_max) // 2
                center_y = (y_min + y_max) // 2
                
                new_width = max((x_max - x_min), int(width * 0.6))
                new_height = max((y_max - y_min), int(height * 0.6))
                
                x_min = max(0, center_x - new_width // 2)
                y_min = max(0, center_y - new_height // 2)
                x_max = min(width, x_min + new_width)
                y_max = min(height, y_min + new_height)
            
            return (x_min, y_min, x_max - x_min, y_max - y_min)
        
        # Если не удалось определить область интереса, используем центр кадра
        center_x = width // 2
        center_y = height // 2
        
        if width > height:
            # Горизонтальное видео
            crop_height = height
            crop_width = int(crop_height * 9/16) if self.format == "vertical" else crop_height
            
            return (center_x - crop_width // 2, 0, crop_width, crop_height)
        else:
            # Вертикальное видео
            return (0, 0, width, height)
    
    def format_for_social(self, input_file, output_file):
        """Форматирует видео для социальных сетей (вертикальный формат)"""
        if self.format == "vertical":
            # Вертикальный формат (9:16) для TikTok, Reels, Shorts
            cmd = [
                "ffmpeg", "-y", "-i", input_file, "-vf",
                "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:a", "copy", output_file
            ]
        elif self.format == "square":
            # Квадратный формат (1:1)
            cmd = [
                "ffmpeg", "-y", "-i", input_file, "-vf",
                "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:a", "copy", output_file
            ]
        else:
            # Оригинальный формат
            shutil.copy(input_file, output_file)
            return
            
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log(f"Превышено время ожидания при форматировании видео")
            # Если не удалось отформатировать, просто копируем файл
            shutil.copy(input_file, output_file)
    
    def add_music_to_video(self, input_file, output_file, music_type=None):
        """Добавляет фоновую музыку к видео"""
        if not self.add_music:
            # Просто копируем файл без изменений
            shutil.copy(input_file, output_file)
            return
            
        # Определяем музыкальный файл
        music_file = None
        if self.music_file and os.path.exists(self.music_file):
            music_file = self.music_file
        elif music_type in self.music_tracks and self.music_tracks[music_type]:
            music_file = self.music_tracks[music_type]
            
            # Проверяем наличие файла
            if not os.path.exists(music_file):
                # Создаем директорию, если не существует
                os.makedirs(os.path.dirname(music_file), exist_ok=True)
                
                # Скачиваем заглушку для музыки
                self.log(f"Музыкальный файл {music_file} не найден, создаем заглушку")
                self.create_music_placeholder(music_type)
        
        if not music_file or not os.path.exists(music_file):
            self.log("Музыкальный файл не найден")
            shutil.copy(input_file, output_file)
            return
            
        # Получаем длительность видео
        video_info = self.get_video_info(input_file)
        if not video_info:
            shutil.copy(input_file, output_file)
            return
            
        try:
            video_duration = float(video_info["format"]["duration"])
        except (KeyError, ValueError):
            self.log("Не удалось определить длительность видео")
            shutil.copy(input_file, output_file)
            return
            
        # Добавляем музыку с помощью FFmpeg
        cmd = [
            "ffmpeg", "-y", "-i", input_file, "-i", music_file, 
            "-filter_complex", 
            f"[1:a]volume=0.3,atrim=0:{video_duration},aloop=loop=-1:size=0,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a1]; [0:a][a1]amix=inputs=2:duration=first[a]", 
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", output_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
        
        if timed_out:
            self.log(f"Превышено время ожидания при добавлении музыки")
            # Если не удалось добавить музыку, просто копируем файл
            shutil.copy(input_file, output_file)
    
    def create_music_placeholder(self, music_type):
        """Создает заглушку для музыкального файла"""
        music_file = self.music_tracks[music_type]
        
        # Создаем директорию, если не существует
        os.makedirs(os.path.dirname(music_file), exist_ok=True)
        
        # Генерируем тишину с помощью FFmpeg
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
            "-t", "10", music_file
        ]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd, timeout=30)
        
        if timed_out:
            self.log(f"Превышено время ожидания при создании заглушки для музыки")
    
    def preview_clip(self, clip_file):
        """Предварительный просмотр клипа"""
        if not self.preview:  # Используем self.preview
            return
            
        self.log(f"Предпросмотр клипа: {clip_file}")
        
        # Используем FFplay для просмотра
        cmd = ["ffplay", "-autoexit", "-window_title", f"Preview: {os.path.basename(clip_file)}", clip_file]
        
        returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd, timeout=60)
        
        if timed_out:
            self.log(f"Превышено время ожидания при предпросмотре клипа")
    
    def process_scene(self, scene_data):
        """Обрабатывает одну сцену (для параллельной обработки)"""
        index, (start, end) = scene_data
        self.log(f"Обработка части {index+1}: {start:.2f} - {end:.2f} (длительность: {end-start:.2f}с)")
        
        # Временные файлы
        temp_dir = tempfile.mkdtemp()
        temp_cut = os.path.join(temp_dir, "temp_cut.mp4")
        temp_with_title = os.path.join(temp_dir, "temp_with_title.mp4")
        temp_with_subs = os.path.join(temp_dir, "temp_with_subs.mp4")
        temp_with_template = os.path.join(temp_dir, "temp_with_template.mp4")
        temp_with_music = os.path.join(temp_dir, "temp_with_music.mp4")
        
        try:
            # Шаг 1: Вырезаем сцену
            cmd = [
                "ffmpeg", "-y", "-ss", str(start), "-i", self.input_file,
                "-t", str(end - start), "-c", "copy", temp_cut
            ]
            
            returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
            
            if timed_out or returncode != 0 or not os.path.exists(temp_cut):
                self.log(f"Ошибка при вырезании части {index+1}: превышено время ожидания или ошибка FFmpeg")
                return False
                
            current_file = temp_cut
            
            # Шаг 2: Добавляем заголовок, если нужно
            if self.add_title:
                title_text = f"Клип {index+1}"
                self.add_title_to_video(current_file, temp_with_title, title_text)
                if os.path.exists(temp_with_title):
                    current_file = temp_with_title
            
            # Шаг 3: Добавляем субтитры, если нужно
            if self.add_subtitles:
                srt_file = self.generate_subtitles(current_file)
                if srt_file:
                    cmd = [
                        "ffmpeg", "-y", "-i", current_file, "-vf",
                        f"subtitles={srt_file}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3'",
                        "-c:a", "copy", temp_with_subs
                    ]
                    
                    returncode, stdout_text, stderr_text, timed_out = self.run_command_with_timeout(cmd)
                    
                    if not timed_out and returncode == 0 and os.path.exists(temp_with_subs):
                        current_file = temp_with_subs
            
            # Шаг 4: Применяем шаблон, если нужно
            if self.template != "none":
                self.apply_template(current_file, temp_with_template, self.template)
                if os.path.exists(temp_with_template):
                    current_file = temp_with_template
            
            # Шаг 5: Добавляем музыку, если нужно
            if self.add_music:
                self.add_music_to_video(current_file, temp_with_music)
                if os.path.exists(temp_with_music):
                    current_file = temp_with_music
            
            # Шаг 6: Форматируем для соцсетей с интеллектуальным рефреймингом
            output_file = os.path.join(self.output_dir, f"clip_{index+1:03}.mp4")
            if self.smart_reframe:
                self.smart_reframe_video(current_file, output_file, self.format)
            else:
                self.format_for_social(current_file, output_file)
            
            # Проверяем, что выходной файл создан
            if not os.path.exists(output_file):
                self.log(f"Ошибка: выходной файл {output_file} не был создан")
                return False
                
            # Шаг 7: Предпросмотр, если нужно
            if self.preview:
                self.preview_clip(output_file)
            
            self.log(f"Часть {index+1} успешно обработана и сохранена как {output_file}")
            return True
        except Exception as e:
            self.log(f"Ошибка при обработке части {index+1}: {str(e)}")
            return False
        finally:
            # Удаляем временные файлы
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def run(self):
        """Основной метод для запуска процесса нарезки"""
        self.log(f"Начало обработки видео: {self.input_file}")
        
        # Проверяем, является ли вход URL
        if self.input_file.startswith(("http://", "https://")):
            downloaded_file = self.download_from_url(self.input_file)
            if downloaded_file:
                self.input_file = downloaded_file
            else:
                self.log("Не удалось загрузить видео по URL")
                return False
        
        # Определяем части для обработки
        parts = []
        
        if self.equal_parts:
            # Режим равных частей
            parts = self.create_equal_parts()
            self.log(f"Используется режим равных частей: {len(parts)} частей по {self.part_duration} секунд")
        else:
            # Режим обнаружения сцен или интересных моментов
            if self.viral_boost:
                scene_times = self.detect_interesting_moments()
            else:
                scene_times = self.detect_scenes()
            
            if scene_times:
                parts = self.filter_scenes(scene_times)
                self.log(f"Используется режим обнаружения сцен: найдено {len(parts)} частей")
            elif self.auto_fallback:
                # Автоматический переход к режиму равных частей, если не удалось определить сцены
                self.log("Не удалось определить сцены. Автоматический переход к режиму равных частей.")
                parts = self.create_equal_parts()
                self.log(f"Используется режим равных частей: {len(parts)} частей по {self.part_duration} секунд")
            else:
                self.log("Не удалось определить сцены. Проверьте входной файл и параметры.")
                return False
        
        if not parts:
            self.log("Не найдено подходящих частей для обработки.")
            return False
        
        self.log(f"Начинаем обработку {len(parts)} частей...")
        
        # Ограничиваем количество частей для обработки, если их слишком много
        max_parts = 100  # Максимальное количество частей для обработки
        if len(parts) > max_parts:
            self.log(f"Внимание: найдено слишком много частей ({len(parts)}). Ограничиваем до {max_parts} частей.")
            parts = parts[:max_parts]
        
        # Обрабатываем части параллельно
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            results = list(executor.map(self.process_scene, enumerate(parts)))
        
        # Подсчитываем успешно обработанные части
        success_count = sum(1 for r in results if r)
        
        self.log(f"Обработка завершена. Успешно обработано {success_count} из {len(parts)} частей.")
        return success_count > 0

# Пример использования
if __name__ == "__main__":
    # Пример аргументов для тестирования
    class Args:
        input = "input.mp4"
        output = "clips"
        threshold = 0.4
        min_duration = 3.0
        max_duration = 60.0
        format = "original"
        title = False
        workers = 2
        verbose = True
        equal_parts = False
        part_duration = 15.0
        subtitles = False
        template = "none"
        smart_reframe = True  # Пример: включен интеллектуальный рефрейминг
        add_music = False
        music_file = None
        preview = True  # Пример: включен предпросмотр
        viral_boost = False
        auto_fallback = True
        command_timeout = 300

    args = Args()
    cutter = ViralClipCutter(args)
    cutter.run()