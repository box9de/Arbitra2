# core/contract_fetcher.py
import json
import os
from binance.spot import Spot
from pybit.unified_trading import HTTP
import okx.Account as AccountAPI
import requests   # ← добавь эту строку
import hmac
import hashlib
import time

from core.token_registry import TokenRegistry


class ContractFetcher:
    def __init__(self):
        self.registry = TokenRegistry()
        self.config_dir = "config"
        self.encrypted_file = f"{self.config_dir}/api_keys.enc"
    
    def _load_encrypted_config(self, master_password: str) -> dict:
        """Загружает и расшифровывает api_keys.enc"""
        import os
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64

        config_path = "config/api_keys.enc"   # ← ИСПРАВЛЕНО

        if not os.path.exists(config_path):
            print(f"[DEBUG] Файл {config_path} не найден")
            return {}

        with open(config_path, "rb") as f:
            encrypted_data = f.read()

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'ArbitraSalt2026',
            iterations=600000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        fernet = Fernet(key)

        try:
            decrypted = fernet.decrypt(encrypted_data)
            import json
            config = json.loads(decrypted.decode())
            print(f"[DEBUG] Конфиг успешно расшифрован. Ключи: {list(config.keys())}")
            return config
        except Exception as e:
            print(f"[DEBUG] Ошибка расшифровки: {e}")
            return {}

    def _load_keys(self, master_password: str, exchange: str):
        """Загружает ключи для биржи (учитывает вложенную структуру)"""
        try:
            config = self._load_encrypted_config(master_password)
            ex = exchange.capitalize()  # Binance, Bybit, OKX

            if ex not in config:
                print(f"[DEBUG] {ex} не найден в конфиге")
                return ('', '') if ex != "OKX" else ('', '', '')

            data = config[ex]

            if ex == "OKX":
                return (
                    data.get('api_key', '') or data.get('key', ''),
                    data.get('api_secret', '') or data.get('secret', ''),
                    data.get('passphrase', '') or data.get('pass', '')
                )
            else:
                api_key = data.get('api_key', '') or data.get('key', '')
                api_secret = data.get('api_secret', '') or data.get('secret', '')
                print(f"[DEBUG] {exchange} → Key length: {len(api_key)}")
                print(f"[DEBUG] {exchange} → Secret length: {len(api_secret)}")
                return api_key, api_secret

        except Exception as e:
            print(f"[DEBUG] Ошибка _load_keys для {exchange}: {e}")
            return ('', '') if exchange != "OKX" else ('', '', '')

    # ==================== BINANCE SPOT ====================
    def fetch_binance_spot_deposits(self, master_password: str):
        added = 0
        addresses_fetched = 0

        try:
            print(f"[Binance] Запрашиваем список монет и адресов (signed request)...")
            api_key, api_secret = self._load_keys(master_password, "Binance")

            timestamp = int(time.time() * 1000)
            params = f"timestamp={timestamp}&recvWindow=60000"
            signature = hmac.new(
                api_secret.encode('utf-8') if api_secret else b'',
                params.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            url = f"https://api.binance.com/sapi/v1/capital/config/getall?{params}&signature={signature}"
            headers = {'X-MBX-APIKEY': api_key} if api_key else {}

            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            coins = resp.json()

            for coin in coins:
                base = coin.get('coin')
                if not base:
                    continue

                spot_pairs = [f"{base}USDT", f"{base}USDC", f"{base}BUSD"]
                futures_pairs = []

                for net in coin.get('networkList', []):
                    if not net.get('depositEnable', False):
                        continue
                    network = net.get('network', '')
                    contract = net.get('contractAddress', '') or net.get('address', '')

                    token_data = {
                        "token": base,
                        "exchange": "Binance",
                        "mode": "Spot",
                        "network": network,
                        "contract_address": contract,
                        "source": "Binance Public Coin Info",
                        "spot_pairs": spot_pairs,
                        "futures_pairs": futures_pairs
                    }
                    self.registry.add_token_full(token_data.copy())
                    added += 1
                    if contract:
                        addresses_fetched += 1
                        print(f"  → Binance {base} | {network} | {contract[:12]}...")

            print(f"[Binance Spot] Итого записей: {added} | Успешно получено адресов: {addresses_fetched}")
            return added

        except Exception as e:
            print(f"[Binance Spot] Критическая ошибка: {e}")
            return 0

    # ==================== BYBIT SPOT ====================
    def fetch_bybit_spot_deposits(self, master_password: str):
        """Bybit Spot — signed запрос + максимальная отладка"""
        added = 0
        addresses_fetched = 0

        try:
            print(f"[Bybit] Запрашиваем список монет и адресов (signed request with time sync)...")
            api_key, api_secret = self._load_keys(master_password, "Bybit")

            # Получаем server time
            time_resp = requests.get("https://api.bybit.com/v5/market/time", timeout=10)
            server_time = int(time_resp.json()["result"]["timeSecond"]) * 1000
            timestamp = str(server_time)
            recv_window = "30000"

            param_str = timestamp + api_key + recv_window
            signature = hmac.new(
                api_secret.encode('utf-8'),
                param_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            headers = {
                'X-BAPI-API-KEY': api_key,
                'X-BAPI-SIGN': signature,
                'X-BAPI-TIMESTAMP': timestamp,
                'X-BAPI-RECV-WINDOW': recv_window,
            }

            url = "https://api.bybit.com/v5/asset/coin/query-info"
            resp = requests.get(url, headers=headers, timeout=20)

            print(f"[DEBUG Bybit] Status code: {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            rows = data.get("result", {}).get("rows", [])
            print(f"[DEBUG Bybit] Найдено монет (rows): {len(rows)}")

            if rows:
                print(f"[DEBUG Bybit] Ключи первой монеты: {list(rows[0].keys())}")

            for coin in rows:
                base = coin.get("coin") or coin.get("name")
                if not base:
                    print(f"[DEBUG Bybit] Пропущена монета без имени")
                    continue

                spot_pairs = [f"{base}USDT", f"{base}USDC", f"{base}BUSD"]
                futures_pairs = []

                chains = coin.get("chains", [])
                print(f"[DEBUG Bybit] У {base} найдено chains: {len(chains)}")

                for chain in chains:
                    network = chain.get("chain", "").strip()
                    contract = chain.get("contractAddress", "").strip()

                    # Убрали жёсткий фильтр depositEnable — добавляем всё, что есть
                    token_data = {
                        "token": base,
                        "exchange": "Bybit",
                        "mode": "Spot",
                        "network": network,
                        "contract_address": contract,
                        "source": "Bybit v5 Coin Info",
                        "spot_pairs": spot_pairs,
                        "futures_pairs": futures_pairs
                    }

                    self.registry.add_token_full(token_data.copy())
                    added += 1

                    if contract:
                        addresses_fetched += 1
                        print(f"  → Bybit {base} | {network} | {contract[:12]}...")
                    else:
                        print(f"  → Bybit {base} | {network} | (нет адреса)")

            print(f"[Bybit Spot] Итого записей: {added} | Успешно получено адресов: {addresses_fetched}")
            return added

        except Exception as e:
            print(f"[Bybit Spot] Критическая ошибка: {e}")
            return 0

    # ==================== OKX ====================
    def fetch_okx_spot_deposits(self, master_password: str):
        """OKX Spot — получение монет, адресов контрактов и торговых пар"""
        added = 0
        addresses_fetched = 0

        try:
            print(f"[OKX] Запрашиваем публичный список монет и адресов...")

            # Загружаем ключи
            config = self._load_encrypted_config(master_password)
            okx_data = config.get("OKX", {})
            api_key = okx_data.get("api_key") or okx_data.get("key", "")
            api_secret = okx_data.get("api_secret") or okx_data.get("secret", "")
            passphrase = okx_data.get("passphrase", "")

            if not api_key or not api_secret:
                print("[OKX] Ключи не найдены, используем публичный запрос (без passphrase)")
                # fallback на публичный запрос, если ключей нет
                resp = requests.get("https://www.okx.com/api/v5/asset/currencies", timeout=20)
            else:
                # Signed запрос (как в рабочей версии)
                import time
                import hmac
                import hashlib
                import base64
                from datetime import datetime, timezone

                timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                method = "GET"
                request_path = "/api/v5/asset/currencies"
                pre_hash = timestamp + method + request_path
                signature = base64.b64encode(
                    hmac.new(
                        api_secret.encode('utf-8'),
                        pre_hash.encode('utf-8'),
                        hashlib.sha256
                    ).digest()
                ).decode('utf-8')

                headers = {
                    'OK-ACCESS-KEY': api_key,
                    'OK-ACCESS-SIGN': signature,
                    'OK-ACCESS-TIMESTAMP': timestamp,
                    'OK-ACCESS-PASSPHRASE': passphrase,
                    'Content-Type': 'application/json',
                }
                resp = requests.get("https://www.okx.com/api/v5/asset/currencies", headers=headers, timeout=20)

            resp.raise_for_status()
            data = resp.json()

            for coin in data.get("data", []):
                base = coin.get("ccy")
                if not base:
                    continue

                # Собираем торговые пары
                spot_pairs = [f"{base}USDT", f"{base}USDC", f"{base}BUSD"]
                futures_pairs = []  # пока пусто, можно расширить позже

                # Сеть и адрес
                raw_chain = coin.get("chain", "")
                chain = raw_chain.replace(base, "").replace("-", "").strip() or raw_chain
                contract = coin.get("ctAddr", "") or coin.get("addr", "")

                token_data = {
                    "token": base,
                    "exchange": "OKX",
                    "mode": "Spot",
                    "network": chain,
                    "contract_address": contract,
                    "source": "OKX Public Currencies",
                    "spot_pairs": spot_pairs,
                    "futures_pairs": futures_pairs
                }

                self.registry.add_token_full(token_data.copy())
                added += 1

                if contract:
                    addresses_fetched += 1
                    print(f"  → OKX {base} | {chain} | {contract[:12]}...")

            print(f"[OKX Spot] Итого записей: {added} | Успешно получено адресов: {addresses_fetched}")
            return added

        except Exception as e:
            print(f"[OKX Spot] Критическая ошибка: {e}")
            return 0

    def enrich_spot_from_exchanges(self, master_password: str):
        """Обогащение Spot-контрактами со всех бирж + сбор торговых пар"""
        total = 0
        print("[ContractFetcher] Начинаем обогащение Spot с бирж...")

        # Вызываем все три метода последовательно
        total += self.fetch_binance_spot_deposits(master_password)
        total += self.fetch_bybit_spot_deposits(master_password)
        total += self.fetch_okx_spot_deposits(master_password)

        print(f"[ContractFetcher] ИТОГО добавлено/обновлено {total} записей из Spot бирж")
        return total
    
    # ====================== FUTURES С БИРЖ ======================
    def fetch_binance_futures(self, master_password: str):
        """Импорт фьючерсов Binance (PERPETUAL + QUARTERLY) — публичный endpoint"""
        added = 0
        try:
            print(f"[Binance Futures] Запрашиваем список фьючерсов...")

            import requests
            resp = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=15)
            print(f"[DEBUG Binance Futures] Status code: {resp.status_code}")

            if resp.status_code != 200:
                print(f"[DEBUG Binance Futures] Response: {resp.text[:300]}...")
                return 0

            data = resp.json()
            symbols = data.get('symbols', [])

            for s in symbols:
                if s.get('status') != 'TRADING':
                    continue
                base = s.get('baseAsset')
                symbol = s.get('symbol')
                c_type = s.get('contractType', 'PERPETUAL')

                token_data = {
                    "token": base,
                    "exchange": "Binance",
                    "mode": "Futures",
                    "network": "",
                    "contract_address": "",
                    "futures_symbol": symbol,
                    "contract_type": c_type,
                    "source": "Binance Futures API"
                }
                self.registry.add_token_full(token_data)
                added += 1

            print(f"[Binance Futures] Итого записей: {added}")
            return added
        except Exception as e:
            print(f"[Binance Futures] Критическая ошибка: {e}")
            return 0

    def fetch_bybit_futures(self, master_password: str):
        """Импорт фьючерсов Bybit (linear perpetual)"""
        added = 0
        try:
            print(f"[Bybit Futures] Запрашиваем список фьючерсов...")
            api_key, api_secret = self._load_keys(master_password, "Bybit")

            from pybit.unified_trading import HTTP
            session = HTTP(api_key=api_key, api_secret=api_secret, testnet=False)

            data = session.get_instruments_info(category="linear")
            for s in data.get('result', {}).get('list', []):
                base = s.get('baseCoin')
                symbol = s.get('symbol')

                token_data = {
                    "token": base,
                    "exchange": "Bybit",
                    "mode": "Futures",
                    "network": "",
                    "contract_address": "",
                    "futures_symbol": symbol,
                    "contract_type": "PERPETUAL",
                    "source": "Bybit Futures API"
                }
                self.registry.add_token_full(token_data)
                added += 1

            print(f"[Bybit Futures] Итого записей: {added}")
            return added
        except Exception as e:
            print(f"[Bybit Futures] Критическая ошибка: {e}")
            return 0

    def fetch_okx_futures(self, master_password: str):
        """Импорт фьючерсов OKX (SWAP perpetual) — signed запрос"""
        added = 0
        try:
            print(f"[OKX Futures] Запрашиваем список фьючерсов...")

            config = self._load_encrypted_config(master_password)
            okx_data = config.get('OKX', {})
            api_key = okx_data.get('api_key', '') or okx_data.get('key', '')
            api_secret = okx_data.get('api_secret', '') or okx_data.get('secret', '')
            passphrase = okx_data.get('passphrase', '') or okx_data.get('pass', '')

            print(f"[DEBUG OKX Futures] Key: {len(api_key)} | Secret: {len(api_secret)} | Passphrase: {len(passphrase)}")

            import requests
            import hmac
            import hashlib
            import base64
            from datetime import datetime

            url = "https://www.okx.com/api/v5/public/instruments"
            timestamp = datetime.utcnow().isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            method = "GET"
            request_path = "/api/v5/public/instruments?instType=SWAP"

            pre_hash = timestamp + method + request_path
            signature = base64.b64encode(
                hmac.new(api_secret.encode('utf-8'), pre_hash.encode('utf-8'), hashlib.sha256).digest()
            ).decode('utf-8')

            headers = {
                'OK-ACCESS-KEY': api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': passphrase,
                'Content-Type': 'application/json'
            }

            resp = requests.get(f"{url}?instType=SWAP", headers=headers, timeout=15)
            print(f"[DEBUG OKX Futures] Status code: {resp.status_code}")

            if resp.status_code != 200:
                print(f"[DEBUG OKX Futures] Response: {resp.text[:300]}...")
                return 0

            instruments = resp.json().get('data', [])
            print(f"[DEBUG OKX Futures] Найдено инструментов: {len(instruments)}")

            for s in instruments:
                # Правильное извлечение base-токена
                base = s.get('baseCcy') or s.get('uly', '').split('-')[0] or s.get('instId', '').split('-')[0]
                if not base:
                    continue

                symbol = s.get('instId')

                token_data = {
                    "token": base.upper(),
                    "exchange": "OKX",
                    "mode": "Futures",
                    "network": "",
                    "contract_address": "",
                    "futures_symbol": symbol,
                    "contract_type": "PERPETUAL",
                    "source": "OKX Futures API"
                }
                self.registry.add_token_full(token_data)
                added += 1

            print(f"[OKX Futures] Итого записей: {added}")
            return added

        except Exception as e:
            print(f"[OKX Futures] Критическая ошибка: {e}")
            return 0
    
    def enrich_futures_from_exchanges(self, master_password: str):
        """Обогащение Futures со всех бирж"""
        total = 0
        print("[ContractFetcher] Начинаем обогащение Futures с бирж...")

        total += self.fetch_binance_futures(master_password)
        total += self.fetch_bybit_futures(master_password)
        total += self.fetch_okx_futures(master_password)

        print(f"[ContractFetcher] ИТОГО добавлено/обновлено {total} записей из Futures бирж")
        return total