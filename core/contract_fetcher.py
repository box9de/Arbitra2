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

    def _load_keys(self, master_password: str, exchange: str):
        if not os.path.exists(self.encrypted_file):
            print(f"[ContractFetcher] Файл ключей не найден: {self.encrypted_file}")
            return None, None

        try:
            with open(self.encrypted_file, "rb") as f:
                encrypted_data = f.read()

            salt = b'ArbitraSalt2026'
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.fernet import Fernet
            import base64

            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
            key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
            fernet = Fernet(key)

            data = json.loads(fernet.decrypt(encrypted_data).decode())
            creds = data.get(exchange, {})
            return creds.get("api_key"), creds.get("api_secret")
        except Exception as e:
            print(f"[ContractFetcher] Ошибка расшифровки ключей для {exchange}: {e}")
            return None, None

    # ==================== BINANCE ====================
    def fetch_binance_spot_deposits(self, master_password: str):
        api_key, api_secret = self._load_keys(master_password, "Binance")
        added = 0
        addresses_fetched = 0

        try:
            print(f"[Binance] Запрашиваем список монет и адресов (signed request)...")

            timestamp = int(time.time() * 1000)
            params = f"timestamp={timestamp}"
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

                # УБРАЛИ базовую запись с пустыми полями
                # Добавляем ТОЛЬКО записи с реальной сетью и адресом

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

        try:
            session = HTTP(api_key=api_key, api_secret=api_secret, testnet=False)

            print(f"[Bybit] Запрашиваем tickers spot...")
            tickers = session.get_tickers(category="spot")
            for t in tickers.get('result', {}).get('list', []):
                symbol = t['symbol']
                if not symbol.endswith('USDT'):
                    continue
                base = symbol.replace('USDT', '')

                token_data = {
                    "token": base,
                    "exchange": "Bybit",
                    "mode": "Spot",
                    "network": "",
                    "contract_address": "",
                    "source": "Bybit Deposit API"
                }
                self.registry.add_token_full(token_data)
                added += 1

                try:
                    print(f"[Bybit] Запрашиваем deposit address для {base}...")
                    dep = None
                    # Надёжный fallback на оба метода
                    try:
                        dep = session.get_deposit_address(coin=base)
                    except AttributeError:
                        try:
                            dep = session.get_deposit_coin_info(coin=base)
                        except AttributeError:
                            print(f"  → Bybit: нет метода deposit для {base}")
                            continue

                    if dep and 'result' in dep:
                        for item in dep['result']:
                            network = item.get('chain', '') or item.get('network', '')
                            contract = item.get('contractAddress', '') or item.get('address', '')
                            if contract and network:
                                token_data["network"] = network
                                token_data["contract_address"] = contract
                                self.registry.add_token_full(token_data)
                                added += 1
                                print(f"  → Bybit {base} | {network} | {contract[:12]}...")
                except Exception as e:
                    print(f"  → deposit_address ошибка для {base}: {e}")

            print(f"[Bybit Spot] Итого добавлено/обновлено {added} записей")
            return added
        except Exception as e:
            print(f"[Bybit Spot] Критическая ошибка: {e}")
            return 0

    # ==================== OKX ====================
    def fetch_okx_spot_deposits(self, master_password: str):
        api_key, api_secret = self._load_keys(master_password, "OKX")
        added = 0

        try:
            account = AccountAPI.AccountAPI(
                api_key=api_key,
                api_secret_key=api_secret,
                passphrase="",
                flag="0"
            )

            print(f"[OKX] Запрашиваем instruments spot...")
            instruments = account.get_instruments(instType="SPOT")
            for inst in instruments.get('data', []):
                base = inst.get('baseCcy')
                if not base:
                    continue

                token_data = {
                    "token": base,
                    "exchange": "OKX",
                    "mode": "Spot",
                    "network": "",
                    "contract_address": "",
                    "source": "OKX Deposit API"
                }
                self.registry.add_token_full(token_data)
                added += 1

                try:
                    print(f"[OKX] Запрашиваем deposit address для {base}...")
                    dep = account.get_deposit_address(ccy=base)
                    if dep and 'data' in dep:
                        for item in dep['data']:
                            network = item.get('chain', '')
                            contract = item.get('addr', '')
                            if contract and network:
                                token_data["network"] = network
                                token_data["contract_address"] = contract
                                self.registry.add_token_full(token_data)
                                added += 1
                                print(f"  → OKX {base} | {network} | {contract[:12]}...")
                except Exception as e:
                    print(f"  → deposit_address ошибка для {base}: {e}")

            print(f"[OKX Spot] Итого добавлено/обновлено {added} записей")
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