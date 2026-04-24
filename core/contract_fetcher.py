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

    # ==================== BINANCE ====================
    def fetch_binance_spot_deposits(self, master_password: str):
        api_key, api_secret = self._load_keys(master_password, "Binance")
        added = 0
        addresses_fetched = 0

        # === ОТЛАДКА КЛЮЧЕЙ ===
        print(f"[DEBUG] API Key length: {len(api_key)}")
        print(f"[DEBUG] API Secret length: {len(api_secret) if api_secret else 0}")

        try:
            print(f"[Binance] Запрашиваем список монет и адресов (signed request)...")

            timestamp = int(time.time() * 1000)
            params = f"timestamp={timestamp}&recvWindow=60000"
            signature = hmac.new(
                api_secret.encode('utf-8') if api_secret else b'',
                params.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            url = f"https://api.binance.com/sapi/v1/capital/config/getall?{params}&signature={signature}"
            headers = {'X-MBX-APIKEY': api_key} if api_key else {}

            print(f"[DEBUG] Запрос URL: {url[:120]}...")  # частично, чтобы не спойлерить секрет

            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            coins = resp.json()

            for coin in coins:
                base = coin.get('coin')
                if not base:
                    continue

                for net in coin.get('networkList', []):
                    if not net.get('depositEnable', False):
                        continue
                    network = net.get('network', '')
                    contract = net.get('contractAddress', '') or net.get('address', '')
                    if contract and network:
                        token_data = {
                            "token": base,
                            "exchange": "Binance",
                            "mode": "Spot",
                            "network": network,
                            "contract_address": contract,
                            "source": "Binance Public Coin Info"
                        }
                        self.registry.add_token_full(token_data.copy())
                        added += 1
                        addresses_fetched += 1
                        print(f"  → Binance {base} | {network} | {contract[:12]}...")

            print(f"[Binance Spot] Итого записей: {added} | Успешно получено адресов: {addresses_fetched}")
            return added

        except Exception as e:
            print(f"[Binance Spot] Критическая ошибка: {e}")
            return 0

    # ==================== BYBIT ====================
    def fetch_bybit_spot_deposits(self, master_password: str):
        added = 0
        addresses_fetched = 0

        try:
            print(f"[Bybit] Запрашиваем публичный список монет и адресов...")

            api_key, api_secret = self._load_keys(master_password, "Bybit")

            import requests
            import time
            import hmac
            import hashlib

            url = "https://api.bybit.com/v5/asset/coin/query-info"
            timestamp = str(int(time.time() * 1000))
            recv_window = "10000"
            query_string = f"recvWindow={recv_window}"

            # Правильная строка подписи Bybit v5 (timestamp + api_key + recv_window + query_string)
            param_str = f"{timestamp}{api_key}{recv_window}{query_string}"
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
                'Content-Type': 'application/json'
            }

            full_url = f"{url}?{query_string}"

            resp = requests.get(full_url, headers=headers, timeout=15)
            print(f"[DEBUG Bybit] Status code: {resp.status_code}")

            if resp.status_code != 200:
                print(f"[DEBUG Bybit] Response: {resp.text[:500]}...")
                return 0

            data = resp.json()
            print(f"[DEBUG Bybit] retCode: {data.get('retCode')}, retMsg: {data.get('retMsg')}")

            coin_list = data.get('result', {}).get('rows', [])
            print(f"[DEBUG Bybit] Найдено монет: {len(coin_list)}")

            for coin in coin_list:
                base = coin.get('coin')
                if not base:
                    continue

                chains = coin.get('chains', [])
                for net in chains:
                    network = net.get('chain', '') or net.get('chainType', '')
                    contract = net.get('contractAddress', '')

                    token_data = {
                        "token": base,
                        "exchange": "Bybit",
                        "mode": "Spot",
                        "network": network.upper() if network else "",
                        "contract_address": contract,
                        "source": "Bybit v5 Coin Info"
                    }
                    self.registry.add_token_full(token_data.copy())
                    added += 1

                    if contract and network:
                        addresses_fetched += 1
                        print(f"  → Bybit {base} | {network} | {contract[:12]}...")
                    else:
                        print(f"  → Bybit {base} | {network or '---'} | {contract or '---'}")

            print(f"[Bybit Spot] Итого записей: {added} | Успешно получено адресов: {addresses_fetched}")
            return added

        except Exception as e:
            print(f"[Bybit Spot] Критическая ошибка: {e}")
            return 0

    # ==================== OKX ====================
    def fetch_okx_spot_deposits(self, master_password: str):
        added = 0
        addresses_fetched = 0

        try:
            print(f"[OKX] Запрашиваем публичный список монет и адресов...")

            # Загружаем конфиг
            config = self._load_encrypted_config(master_password)
            okx_data = config.get('OKX', {})
            api_key = okx_data.get('api_key', '') or okx_data.get('key', '')
            api_secret = okx_data.get('api_secret', '') or okx_data.get('secret', '')
            passphrase = okx_data.get('passphrase', '') or okx_data.get('pass', '')

            if not passphrase:
                print("[OKX] Passphrase не найден в конфиге.")
                passphrase = input("Введите OKX Passphrase: ").strip()

            print(f"[DEBUG OKX] Key: {len(api_key)} | Secret: {len(api_secret)} | Passphrase: {len(passphrase)}")

            import requests
            import time
            import hmac
            import hashlib
            import base64
            from datetime import datetime, timezone

            # Синхронизация времени
            time_resp = requests.get("https://www.okx.com/api/v5/public/time", timeout=10)
            server_ts = int(time_resp.json()['data'][0]['ts'])
            timestamp = datetime.fromtimestamp(server_ts / 1000, tz=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

            method = "GET"
            request_path = "/api/v5/asset/currencies"
            pre_hash = timestamp + method + request_path
            signature = base64.b64encode(
                hmac.new(api_secret.encode('utf-8'), pre_hash.encode('utf-8'), hashlib.sha256).digest()
            ).decode('utf-8')

            headers = {
                'OK-ACCESS-KEY': api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': passphrase,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }

            resp = requests.get(
                "https://www.okx.com/api/v5/asset/currencies",
                headers=headers,
                timeout=20
            )

            print(f"[DEBUG OKX] Status code: {resp.status_code}")
            if resp.status_code != 200:
                print(f"[DEBUG OKX] Response: {resp.text[:400]}...")
                return 0

            data = resp.json()

            for coin in data.get('data', []):
                base = coin.get('ccy')
                if not base:
                    continue

                # Очистка + перевод сети в UPPERCASE
                raw_chain = coin.get('chain', '')
                chain = raw_chain.replace(base, '').replace('-', '').strip().upper() or raw_chain.upper()
                contract = coin.get('ctAddr', '') or coin.get('addr', '')

                token_data = {
                    "token": base,
                    "exchange": "OKX",
                    "mode": "Spot",
                    "network": chain,
                    "contract_address": contract,
                    "source": "OKX Public Currencies"
                }
                self.registry.add_token_full(token_data.copy())
                added += 1

                if contract and chain:
                    addresses_fetched += 1
                    print(f"  → OKX {base} | {chain} | {contract[:12]}...")
                else:
                    print(f"  → OKX {base} | {chain or '---'} | {contract or '---'}")

            print(f"[OKX Spot] Итого записей: {added} | Успешно получено адресов: {addresses_fetched}")
            return added

        except Exception as e:
            print(f"[OKX Spot] Критическая ошибка: {e}")
            return 0

    def enrich_spot_from_exchanges(self, binance=True, bybit=True, okx=True, master_password: str = None):
        if not master_password:
            print("[ContractFetcher] Ошибка: мастер-пароль не передан")
            return 0

        total = 0
        if binance:
            total += self.fetch_binance_spot_deposits(master_password)
        if bybit:
            total += self.fetch_bybit_spot_deposits(master_password)
        if okx:
            total += self.fetch_okx_spot_deposits(master_password)

        self.registry._save_to_file()
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
    
    def enrich_futures_from_exchanges(self, binance=True, bybit=True, okx=True, master_password: str = None):
        """Главный метод — обогащение фьючерсами со всех бирж"""
        if not master_password:
            print("[ContractFetcher] Ошибка: мастер-пароль не передан")
            return 0

        total = 0

        if binance:
            total += self.fetch_binance_futures(master_password)
        if bybit:
            total += self.fetch_bybit_futures(master_password)
        if okx:
            total += self.fetch_okx_futures(master_password)

        print(f"[ContractFetcher] ИТОГО добавлено/обновлено {total} записей из Futures бирж")
        return total