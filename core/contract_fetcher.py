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
        api_key, api_secret = self._load_keys(master_password, "Bybit")
        added = 0
        addresses_fetched = 0

        try:
            print(f"[Bybit] Запрашиваем tickers spot...")
            from pybit.unified_trading import HTTP
            session = HTTP(api_key=api_key, api_secret=api_secret, testnet=False)

            # Получаем все спот-монеты
            tickers = session.get_tickers(category="spot")
            symbols = {t['symbol'].split('USDT')[0] for t in tickers['result']['list'] if t['symbol'].endswith('USDT')}

            for base in symbols:
                try:
                    dep = session.get_deposit_coin_info(coin=base)
                    if isinstance(dep, dict) and 'result' in dep:
                        for net_info in dep.get('result', []):
                            network = net_info.get('chain', '') or net_info.get('network', '')
                            contract = net_info.get('contractAddress', '') or net_info.get('address', '')
                            if contract and network:
                                token_data = {
                                    "token": base,
                                    "exchange": "Bybit",
                                    "mode": "Spot",
                                    "network": network,
                                    "contract_address": contract,
                                    "source": "Bybit Deposit API"
                                }
                                self.registry.add_token_full(token_data.copy())
                                added += 1
                                addresses_fetched += 1
                                print(f"  → Bybit {base} | {network} | {contract[:12]}...")
                except:
                    continue  # пропускаем монеты без депозита

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