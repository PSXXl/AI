#!/usr/bin/env python3
"""
Скрипт для скачивания аудиозаписей звонков из Sipuni API.

Процесс:
1. Получение secret ключа
2. Скачивание CSV файла со статистикой звонков
3. Извлечение ID аудиофайлов из CSV
4. Скачивание аудиофайлов по ID

Требуется:
- USER_ID: ID пользователя в Sipuni
- API_KEY: Ключ интеграции (API ключ)
"""

import requests
import csv
import os
from datetime import datetime, timedelta
from io import StringIO
import argparse

# ==================== НАСТРОЙКИ ====================
# Замените на ваши данные
USER_ID = "ВАШ_USER_ID"
API_KEY = "ВАШ_API_KEY"

# Базовый URL API Sipuni
BASE_URL = "https://api.sipuni.com/api"

# Папка для сохранения аудиофайлов
DOWNLOAD_DIR = "./sipuni_recordings"
# ===================================================


def get_secret_key(user_id, api_key):
    """
    Получение secret ключа для доступа к API.
    
    Args:
        user_id: ID пользователя
        api_key: API ключ
        
    Returns:
        str: Secret ключ или None при ошибке
    """
    url = f"{BASE_URL}/secret"
    headers = {
        "User-Id": user_id,
        "Api-Key": api_key
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success"):
            secret = data.get("data", {}).get("secret")
            print(f"✓ Secret ключ получен успешно")
            return secret
        else:
            print(f"✗ Ошибка при получении secret: {data}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Ошибка запроса: {e}")
        return None


def download_statistics_csv(secret_key, date_from, date_to):
    """
    Скачивание CSV файла со статистикой звонков.
    
    Args:
        secret_key: Secret ключ
        date_from: Дата начала периода (YYYY-MM-DD)
        date_to: Дата окончания периода (YYYY-MM-DD)
        
    Returns:
        list: Список записей из CSV или None при ошибке
    """
    url = f"{BASE_URL}/statistics"
    params = {
        "secret": secret_key,
        "dateFrom": date_from,
        "dateTo": date_to
    }
    
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        
        # Парсим CSV
        csv_content = response.text
        reader = csv.DictReader(StringIO(csv_content))
        records = list(reader)
        
        print(f"✓ Загружено {len(records)} записей из CSV")
        return records
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Ошибка при загрузке CSV: {e}")
        return None


def extract_recording_ids(statistics_records):
    """
    Извлечение ID аудиофайлов из записей статистики.
    
    Args:
        statistics_records: Список записей статистики
        
    Returns:
        list: Уникальные ID аудиофайлов
    """
    recording_ids = set()
    
    for record in statistics_records:
        # Поле с ID записи может называться по-разному
        # Проверяем несколько возможных вариантов
        id_field = None
        for field in ["recording_id", "recordId", "audio_id", "id"]:
            if field in record and record[field]:
                id_field = field
                break
        
        if id_field:
            recording_ids.add(record[id_field])
    
    recording_ids_list = list(recording_ids)
    print(f"✓ Найдено {len(recording_ids_list)} уникальных ID аудиофайлов")
    
    return recording_ids_list


def download_recording(secret_key, recording_id, download_dir):
    """
    Скачивание одного аудиофайла.
    
    Args:
        secret_key: Secret ключ
        recording_id: ID аудиофайла
        download_dir: Папка для сохранения
        
    Returns:
        bool: True если успешно, False иначе
    """
    url = f"{BASE_URL}/recording/{recording_id}"
    params = {
        "secret": secret_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=60, stream=True)
        response.raise_for_status()
        
        # Создаем папку если не существует
        os.makedirs(download_dir, exist_ok=True)
        
        # Определяем имя файла
        filename = f"{recording_id}.mp3"
        filepath = os.path.join(download_dir, filename)
        
        # Сохраняем файл
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"  ✓ Скачан файл: {filename}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Ошибка при скачивании {recording_id}: {e}")
        return False


def parse_date(date_string):
    """
    Парсинг даты из строки.
    
    Args:
        date_string: Строка с датой в формате YYYY-MM-DD или относительное значение (например, "7d")
        
    Returns:
        datetime: Объект даты
    """
    if not date_string:
        return None
    
    # Проверка на относительный формат (например, "7d" - 7 дней назад)
    if date_string.endswith('d'):
        try:
            days = int(date_string[:-1])
            return datetime.now() - timedelta(days=days)
        except ValueError:
            pass
    
    # Попытка парсинга в формате YYYY-MM-DD
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        pass
    
    # Попытка парсинга в формате DD.MM.YYYY
    try:
        return datetime.strptime(date_string, "%d.%m.%Y")
    except ValueError:
        pass
    
    raise ValueError(f"Неверный формат даты: {date_string}. Используйте YYYY-MM-DD или относительный формат (например, 7d)")


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(
        description="Скачивание аудиозаписей звонков из Sipuni API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --from 2024-01-01 --to 2024-01-31
  %(prog)s --from 7d                    # За последние 7 дней
  %(prog)s --from 30d --to 2024-01-31   # С 30 дней назад до указанной даты
  %(prog)s                              # Использовать настройки по умолчанию (7 дней)
        """
    )
    
    parser.add_argument(
        "--from", 
        dest="date_from", 
        type=str, 
        help="Дата начала периода (YYYY-MM-DD) или относительный формат (например, 7d - 7 дней назад)"
    )
    
    parser.add_argument(
        "--to", 
        dest="date_to", 
        type=str, 
        help="Дата окончания периода (YYYY-MM-DD). По умолчанию - сегодня"
    )
    
    parser.add_argument(
        "--days", 
        type=int, 
        help="Количество дней для выгрузки (альтернатива --from). По умолчанию 7"
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        default=DOWNLOAD_DIR,
        help=f"Папка для сохранения файлов. По умолчанию: {DOWNLOAD_DIR}"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Sipuni Audio Downloader")
    print("=" * 50)
    
    # Проверка настроек
    if USER_ID == "ВАШ_USER_ID" or API_KEY == "ВАШ_API_KEY":
        print("\n⚠️  ВНИМАНИЕ: Необходимо указать USER_ID и API_KEY в настройках скрипта!")
        return
    
    # Определение папки для загрузок
    download_dir = args.output
    
    # Создание папки если не существует
    os.makedirs(download_dir, exist_ok=True)
    
    # Шаг 1: Получение secret ключа
    print("\n[1/4] Получение secret ключа...")
    secret = get_secret_key(USER_ID, API_KEY)
    
    if not secret:
        print("\n✗ Не удалось получить secret ключ. Проверьте USER_ID и API_KEY.")
        return
    
    # Шаг 2: Определение дат
    print("\n[2/4] Определение периода выгрузки...")
    
    try:
        # Определение даты окончания
        if args.date_to:
            date_to = parse_date(args.date_to)
        else:
            date_to = datetime.now()
        
        # Определение даты начала
        if args.date_from:
            date_from = parse_date(args.date_from)
        elif args.days:
            date_from = datetime.now() - timedelta(days=args.days)
        else:
            # По умолчанию 7 дней
            date_from = datetime.now() - timedelta(days=7)
        
        # Проверка корректности периода
        if date_from > date_to:
            print("\n✗ Ошибка: Дата начала не может быть больше даты окончания!")
            print(f"  Дата начала: {date_from.strftime('%Y-%m-%d')}")
            print(f"  Дата окончания: {date_to.strftime('%Y-%m-%d')}")
            return
            
    except ValueError as e:
        print(f"\n✗ Ошибка: {e}")
        return
    
    date_from_str = date_from.strftime("%Y-%m-%d")
    date_to_str = date_to.strftime("%Y-%m-%d")
    
    print(f"✓ Период: {date_from_str} - {date_to_str}")
    
    # Шаг 3: Скачивание CSV
    print(f"\n[3/4] Загрузка статистики за указанный период...")
    statistics = download_statistics_csv(secret, date_from_str, date_to_str)
    
    if not statistics:
        print("\n✗ Не удалось загрузить статистику.")
        return
    
    # Шаг 4: Извлечение ID аудиофайлов
    print("\n[4/4] Извлечение ID аудиофайлов...")
    recording_ids = extract_recording_ids(statistics)
    
    if not recording_ids:
        print("\n⚠️  Аудиофайлы не найдены за указанный период.")
        return
    
    # Шаг 5: Скачивание аудиофайлов
    print(f"\n[5/5] Скачивание {len(recording_ids)} аудиофайлов...")
    print(f"Папка сохранения: {os.path.abspath(download_dir)}\n")
    
    success_count = 0
    error_count = 0
    
    for i, rec_id in enumerate(recording_ids, 1):
        print(f"[{i}/{len(recording_ids)}] ", end="")
        if download_recording(secret, rec_id, download_dir):
            success_count += 1
        else:
            error_count += 1
    
    # Итоги
    print("\n" + "=" * 50)
    print("ЗАВЕРШЕНО")
    print(f"Успешно скачано: {success_count}")
    print(f"Ошибок: {error_count}")
    print(f"Файлы сохранены в: {os.path.abspath(download_dir)}")
    print("=" * 50)


if __name__ == "__main__":
    main()
