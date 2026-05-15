#!/usr/bin/env python3
"""
Скрипт для массового скачивания записей звонков из Sipuni через API.

Использование:
    python sipuni_downloader.py --user YOUR_USER --secret YOUR_SECRET --output ./recordings

Или с интервалом дат:
    python sipuni_downloader.py --user YOUR_USER --secret YOUR_SECRET --from 2024-01-01 --to 2024-01-31 --output ./recordings
"""

import argparse
import csv
import hashlib
import os
import requests
import time
from datetime import datetime
from io import StringIO


def calculate_hash(params, secret):
    """
    Вычисляет контрольную hash-подпись для запроса к API Sipuni.
    
    Порядок полей для hash (согласно документации):
    user + secret + метод + путь + отсортированные параметры
    
    Для export/export-all: user+secret+GET+/api/statistic/export(+all)+param1+param2+...
    Для record: user+secret+GET+/api/statistic/record+id
    """
    # Сортируем параметры по ключам (кроме hash)
    sorted_params = sorted([k for k in params.keys() if k != 'hash'])
    
    # Формируем строку для хеширования
    hash_string = params['user'] + secret + params['method'] + params['path']
    
    for key in sorted_params:
        if key not in ['method', 'path', 'hash']:
            hash_string += str(params[key])
    
    return hashlib.md5(hash_string.encode('utf-8')).hexdigest()


def get_recordings_list(user, secret, from_date=None, to_date=None, anonymous=None):
    """
    Получает список записей звонков в формате CSV.
    
    Args:
        user: номер пользователя в системе Sipuni
        secret: секретный ключ API
        from_date: дата начала периода (YYYY-MM-DD)
        to_date: дата окончания периода (YYYY-MM-DD)
        anonymous: включать ли анонимные звонки (True/False)
    
    Returns:
        Список записей в виде списка словарей
    """
    base_url = "https://sipuni.com/api/statistic/export"
    
    # Параметры запроса
    params = {
        'user': user,
        'method': 'GET',
        'path': '/api/statistic/export',
        'format': 'csv'
    }
    
    if from_date:
        params['from'] = from_date
    if to_date:
        params['to'] = to_date
    if anonymous is not None:
        params['anonymous'] = '1' if anonymous else '0'
    
    # Вычисляем hash
    params['hash'] = calculate_hash(params, secret)
    
    print(f"Запрос списка записей...")
    print(f"URL: {base_url}")
    print(f"Параметры: user={user}, from={from_date}, to={to_date}")
    
    try:
        response = requests.get(base_url, params=params, timeout=300)
        response.raise_for_status()
        
        # Проверяем, что получили CSV
        if 'text/csv' not in response.headers.get('Content-Type', ''):
            print(f"Предупреждение: неожиданный тип контента: {response.headers.get('Content-Type')}")
        
        csv_content = response.text
        
        # Парсим CSV
        reader = csv.DictReader(StringIO(csv_content))
        records = list(reader)
        
        print(f"Получено записей: {len(records)}")
        return records
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении списка записей: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Ответ сервера: {e.response.text}")
        return []


def download_recording(user, secret, record_id, output_dir, filename_format=None):
    """
    Скачивает конкретную запись звонка.
    
    Args:
        user: номер пользователя в системе Sipuni
        secret: секретный ключ API
        record_id: ID записи для скачивания
        output_dir: директория для сохранения файлов
        filename_format: формат имени файла (по умолчанию: {id}.mp3)
    
    Returns:
        Путь к сохраненному файлу или None в случае ошибки
    """
    base_url = "https://sipuni.com/api/statistic/record"
    
    # Параметры запроса
    params = {
        'user': user,
        'id': record_id,
        'method': 'GET',
        'path': '/api/statistic/record'
    }
    
    # Вычисляем hash
    params['hash'] = calculate_hash(params, secret)
    
    try:
        response = requests.get(base_url, params=params, timeout=60, stream=True)
        response.raise_for_status()
        
        # Определяем расширение файла из Content-Type или используем mp3 по умолчанию
        content_type = response.headers.get('Content-Type', '')
        if 'wav' in content_type:
            ext = '.wav'
        elif 'ogg' in content_type:
            ext = '.ogg'
        else:
            ext = '.mp3'
        
        # Формируем имя файла
        if filename_format:
            filename = filename_format.format(id=record_id) + ext
        else:
            filename = f"{record_id}{ext}"
        
        filepath = os.path.join(output_dir, filename)
        
        # Сохраняем файл
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return filepath
        
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при скачивании записи {record_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Ответ сервера: {e.response.text[:200]}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Массовое скачивание записей звонков из Sipuni',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --user 012345 --secret mysecret --output ./recordings
  %(prog)s --user 012345 --secret mysecret --from 2024-01-01 --to 2024-01-31 --output ./recordings
  %(prog)s --user 012345 --secret mysecret --output ./recordings --delay 0.5
        """
    )
    
    parser.add_argument('--user', required=True, help='Номер пользователя в системе Sipuni')
    parser.add_argument('--secret', required=True, help='Секретный ключ API')
    parser.add_argument('--output', required=True, help='Директория для сохранения записей')
    parser.add_argument('--from', dest='from_date', help='Дата начала периода (YYYY-MM-DD)')
    parser.add_argument('--to', dest='to_date', help='Дата окончания периода (YYYY-MM-DD)')
    parser.add_argument('--anonymous', action='store_true', help='Включать анонимные звонки')
    parser.add_argument('--delay', type=float, default=0.3, help='Задержка между запросами в секундах (по умолчанию 0.3)')
    parser.add_argument('--filename-format', help='Формат имени файла, например: recording_{id}')
    parser.add_argument('--skip-existing', action='store_true', help='Пропускать уже скачанные файлы')
    
    args = parser.parse_args()
    
    # Создаем директорию для вывода
    os.makedirs(args.output, exist_ok=True)
    
    print("=" * 60)
    print("Sipuni Downloader - Массовое скачивание записей звонков")
    print("=" * 60)
    print()
    
    # Получаем список записей
    records = get_recordings_list(
        user=args.user,
        secret=args.secret,
        from_date=args.from_date,
        to_date=args.to_date,
        anonymous=args.anonymous
    )
    
    if not records:
        print("Нет записей для скачивания.")
        return
    
    # Проверяем наличие поля с ID записи
    # В CSV Sipuni поле может называться по-разному, пробуем несколько вариантов
    id_field = None
    possible_id_fields = ['id', 'record_id', 'recording_id', 'ID', 'Id']
    
    for field in possible_id_fields:
        if records and field in records[0]:
            id_field = field
            break
    
    if not id_field:
        print("Не найдено поле с ID записи в CSV. Доступные поля:")
        if records:
            print(list(records[0].keys()))
        return
    
    print(f"\nПоле ID: {id_field}")
    print(f"Начинаю скачивание {len(records)} записей...")
    print()
    
    # Скачиваем записи
    success_count = 0
    error_count = 0
    skip_count = 0
    
    for i, record in enumerate(records, 1):
        record_id = record.get(id_field)
        
        if not record_id:
            print(f"[{i}/{len(records)}] Пропущено: нет ID в записи")
            skip_count += 1
            continue
        
        # Проверяем, существует ли уже файл
        if args.skip_existing:
            # Пробуем разные расширения
            existing = False
            for ext in ['.mp3', '.wav', '.ogg']:
                if args.filename_format:
                    filename = args.filename_format.format(id=record_id) + ext
                else:
                    filename = f"{record_id}{ext}"
                if os.path.exists(os.path.join(args.output, filename)):
                    existing = True
                    break
            
            if existing:
                print(f"[{i}/{len(records)}] Пропущено: {record_id} (уже существует)")
                skip_count += 1
                continue
        
        print(f"[{i}/{len(records)}] Скачивание записи {record_id}...", end=" ")
        
        filepath = download_recording(
            user=args.user,
            secret=args.secret,
            record_id=record_id,
            output_dir=args.output,
            filename_format=args.filename_format
        )
        
        if filepath:
            print(f"OK ({os.path.basename(filepath)})")
            success_count += 1
        else:
            print("ОШИБКА")
            error_count += 1
        
        # Задержка между запросами
        if i < len(records):
            time.sleep(args.delay)
    
    # Итоги
    print()
    print("=" * 60)
    print("Результаты:")
    print(f"  Успешно скачано: {success_count}")
    print(f"  Ошибок: {error_count}")
    print(f"  Пропущено: {skip_count}")
    print(f"  Всего обработано: {len(records)}")
    print(f"  Файлы сохранены в: {os.path.abspath(args.output)}")
    print("=" * 60)


if __name__ == '__main__':
    main()
