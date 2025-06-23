# clip_cutter.spec
import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Основной скрипт
main_script = 'gui.py'

# Текущая директория проекта
current_dir = os.getcwd()

# Путь к папке assets
assets_dir = os.path.join(current_dir, 'assets')

# Собираем данные из assets
data_files = []
for root, dirs, files in os.walk(assets_dir):
    for file in files:
        full_path = os.path.join(root, file)
        data_files.append((full_path, 'assets'))

# Конфигурация сборки
a = Analysis(
    [main_script],
    pathex=[current_dir],  # Указываем путь к корню проекта
    binaries=[],
    datas=data_files,
    hiddenimports=['viral_clip_cutter'],  # Добавляем модуль в hiddenimports
    hookconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ViralClipCutter',
    debug=False,
    console=True,  # Для отладки оставьте console=True
)