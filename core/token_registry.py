import os
import json
import time
import requests

from binance.spot import Spot
from pybit.unified_trading import HTTP
import okx.Account as AccountAPI


class TokenRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tokens = []
            cls._instance._load_from_file()
        return cls._instance

    def add_token_full(self, token_data: dict):
        """Жёсткая дедупликация по полному ключу:
           token + exchange + mode + network + contract_address
           Это позволяет хранить разные сети и адреса одного токена"""
        
        key = (
            token_data.get("token", ""),
            token_data.get("exchange", ""),
            token_data.get("mode", ""),
            token_data.get("network", ""),
            token_data.get("contract_address", "")
        )

        for existing in self.tokens:
            existing_key = (
                existing.get("token", ""),
                existing.get("exchange", ""),
                existing.get("mode", ""),
                existing.get("network", ""),
                existing.get("contract_address", "")
            )
            if existing_key == key:
                existing.update(token_data)   # обновляем данные, если запись уже есть
                self._save_to_file()
                return

        # Если такой комбинации нет — добавляем новую строку
        self.tokens.append(token_data)
        self._save_to_file()

    def get_all_tokens(self):
        """Возвращает все записи для глобального реестра"""
        return self.tokens

    def _load_from_file(self):
        path = "data/token_registry.json"
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.tokens = json.load(f)
            except Exception:
                self.tokens = []
        else:
            self.tokens = []

    def _save_to_file(self):
        os.makedirs("data", exist_ok=True)
        with open("data/token_registry.json", 'w', encoding='utf-8') as f:
            json.dump(self.tokens, f, ensure_ascii=False, indent=2)

    # ====================== COINGECKO ======================
    def import_top_coins_from_coingecko(self, max_pages=20):
        """Этап 1 — Импорт топ-5000 токенов с CoinGecko"""
        base_url = "https://api.coingecko.com/api/v3/coins/markets"
        headers = {"accept": "application/json"}
        total_added = 0

        for page in range(1, max_pages + 1):
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 250,
                "page": page,
                "price_change_percentage": "24h"
            }
            try:
                resp = requests.get(base_url, params=params, headers=headers, timeout=15)

                if resp.status_code == 429:
                    print(f"[CoinGecko] 429 Rate Limit на странице {page}. Ждём 60 секунд...")
                    time.sleep(60)
                    continue

                if resp.status_code != 200:
                    print(f"[CoinGecko] Страница {page} ошибка {resp.status_code}")
                    break

                coins = resp.json()
                page_added = 0

                for coin in coins:
                    token_data = {
                        "token": coin["symbol"].upper(),
                        "exchange": "CoinGecko",
                        "mode": "Spot",
                        "network": "",
                        "contract_address": "",
                        "source": "CoinGecko API",
                        "name": coin.get("name"),
                        "market_cap_rank": coin.get("market_cap_rank"),
                        "current_price": coin.get("current_price"),
                        "market_cap": coin.get("market_cap"),
                        "price_change_24h": coin.get("price_change_percentage_24h"),
                        "coingecko_id": coin.get("id"),
                        "last_updated": coin.get("last_updated")
                    }
                    self.add_token_full(token_data)
                    page_added += 1
                    total_added += 1

                print(f"[CoinGecko] Страница {page}/20 — добавлено/обновлено {page_added} токенов")
                time.sleep(2.0)

            except Exception as e:
                print(f"[CoinGecko] Ошибка на странице {page}: {e}")
                time.sleep(5)
                continue

        self._save_to_file()
        return len(self.tokens)

    def enrich_contract_addresses(self):
        """Этап 2 CoinGecko — Обогащение адресами контрактов"""
        updated = 0
        base_url = "https://api.coingecko.com/api/v3/coins"

        for entry in self.tokens:
            if entry.get("source") != "CoinGecko API" or not entry.get("coingecko_id"):
                continue
            if entry.get("contract_address"):
                continue

            try:
                url = f"{base_url}/{entry['coingecko_id']}"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                platforms = data.get("platforms", {}) or data.get("detail_platforms", {})

                for network, address in platforms.items():
                    if address and str(address).strip():
                        new_entry = entry.copy()
                        new_entry["network"] = network
                        new_entry["contract_address"] = address
                        new_entry["source"] = "CoinGecko API (enriched)"
                        self.add_token_full(new_entry)
                        updated += 1

                time.sleep(1.3)

            except Exception as e:
                print(f"[Enrich CoinGecko] Ошибка для {entry.get('token')}: {e}")

        self._save_to_file()
        return updated

    # ====================== SPOT С БИРЖ ======================
    def enrich_spot_from_exchanges(self, binance=True, bybit=True, okx=True, master_password: str = None):
        """Главный метод — обогащение Spot-токенами и адресами контрактов с бирж"""
        from core.contract_fetcher import ContractFetcher

        if not master_password:
            print("[TokenRegistry] Ошибка: мастер-пароль не передан")
            return 0

        fetcher = ContractFetcher()
        total = fetcher.enrich_spot_from_exchanges(
            binance=binance, 
            bybit=bybit, 
            okx=okx, 
            master_password=master_password
        )

        self._save_to_file()
        return total

    # ====================== СБРОС ======================
    def clear_registry(self):
        """Полный сброс реестра"""
        self.tokens = []
        self._save_to_file()


# Глобальный экземпляр
token_registry = TokenRegistry()