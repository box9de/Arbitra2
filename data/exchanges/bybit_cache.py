import os
import json

def load_bybit_markets():
    """Точная оригинальная функция из Arbitra1 — загружает кэш рынков Bybit (spot + futures)."""
    cache_file = "data/exchanges/bybit_markets_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # Если кэша нет — возвращаем пустой словарь (как было в оригинале)
    return {}