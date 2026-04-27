import os
import json
from collections import defaultdict

class TokenRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
            cls._instance._load_from_file()
        return cls._instance

    @property
    def tokens(self):
        """Только реальные токены (Spot + Futures)"""
        return [v for v in self._data.values() if v.get("type") != "monitoring_config"]

    def _load_from_file(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'token_registry.json')
        self._data = {}

        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                try:
                    raw_tokens = json.load(f)
                except:
                    raw_tokens = []
        else:
            raw_tokens = []

        for token in raw_tokens:
            self.add_token_full(token)

        self._save_to_file()

    def add_token_full(self, token_data: dict):
        """Добавляет/обновляет запись. Дубли невозможны."""
        token_data = token_data.copy()

        if token_data.get("type") == "monitoring_config":
            key = (token_data.get("token", "").upper(), "monitoring_config", "", "")
            self._data[key] = token_data
            self._save_to_file()
            return

        # Нормализация Spot / Futures
        network_map = {
            "SOL": "SOLANA", "SOLANA": "SOLANA",
            "ETH": "ETH", "ERC20": "ETH", "ERC-20": "ETH", "ER20": "ETH", "ETHER": "ETH",
            "BERA": "BERACHAIN", "BERACHAIN": "BERACHAIN",
            "ARBI": "ARBITRUM", "ARB": "ARBITRUM", "ARBITRUM": "ARBITRUM", "ARBITRUM ONE": "ARBITRUM",
            "OP": "OPTIMISM", "OPT": "OPTIMISM", "OPTIMISM": "OPTIMISM",
            "BASE": "BASE",
            "BSC": "BSC",
            "MATIC": "POLYGON", "POLYGON": "POLYGON",
            "AVAX": "AVALANCHE", "CAVAX": "AVALANCHE", "AVALANCHE": "AVALANCHE",
            "KLAY": "KLAYTN", "KLAYTN": "KLAYTN",
            "TON": "TON",
            "TRX": "TRON", "TRON": "TRON",
            "XRP": "XRP",
            "ADA": "CARDANO",
            "DOT": "POLKADOT",
            "NEAR": "NEAR",
            "SUI": "SUI",
            "ZKSYNC": "ZKSYNC ERA", "ZK": "ZKSYNC ERA", "ZKSYNC ERA": "ZKSYNC ERA",
            "MANTLE": "MANTLE",
            "LINEA": "LINEA",
            "SCROLL": "SCROLL",
            "CHILIZ": "CHILIZ", "CHZ2": "CHILIZ",
            "EOS": "EOS", "VAULTA": "EOS", "CORE.VAULTA": "EOS",
            "ENDURANCE": "ENDURANCE",
            "KOKTC": "KOKTC",
            "MERLIN": "MERLIN",
            "STARKNET": "STARKNET",
            "HYPEREVM": "HYPEREVM",
            "MONAD": "MONAD",
            "RONIN": "RONIN",
            "PLASMA": "PLASMA",
            "ZIRCUIT": "ZIRCUIT",
            "KROMA": "KROMA",
        }

        token_data["token"] = str(token_data.get("token", "")).strip().upper()
        raw_network = str(token_data.get("network", "")).strip().upper()
        token_data["network"] = network_map.get(raw_network, raw_network)
        token_data["contract_address"] = str(token_data.get("contract_address", "")).strip().lower()

        if token_data.get("mode") == "Futures":
            key = (
                token_data["token"],
                token_data.get("exchange", ""),
                "Futures",
                token_data.get("futures_symbol", "").strip()
            )
        else:
            key = (
                token_data["token"],
                token_data.get("exchange", ""),
                "Spot",
                token_data.get("network", ""),
                token_data.get("contract_address", "")
            )

        self._data[key] = token_data
        self._save_to_file()

    def _save_to_file(self):
        """Сохраняем ВСЕ записи (включая monitoring_config)"""
        path = os.path.join(os.path.dirname(__file__), '..', 'data', 'token_registry.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(list(self._data.values()), f, ensure_ascii=False, indent=2)

    def get_all_tokens(self):
        return self.tokens

    # ====================== МОНИТОРИНГ КОНФИГУРАЦИЯ ======================
    def save_monitoring_config(self, token: str, config: dict):
        """config = { "Binance": {...}, "Bybit": {...}, "OKX": {...} }"""
        key = (token.upper(), "monitoring_config", "", "")
        self._data[key] = {
            "token": token.upper(),
            "type": "monitoring_config",
            "config": config
        }
        self._save_to_file()

    def get_monitoring_config(self, token: str) -> dict:
        """Возвращает { "Binance": {...}, "Bybit": {...}, "OKX": {...} }"""
        key = (token.upper(), "monitoring_config", "", "")
        entry = self._data.get(key)
        return entry.get("config", {}) if entry else {}

    def clear_registry(self):
        self._data = {}
        self._save_to_file()

    # ====================== ПРОКСИ ======================
    def enrich_spot_from_exchanges(self, master_password: str = None):
        from core.contract_fetcher import ContractFetcher
        fetcher = ContractFetcher()
        return fetcher.enrich_spot_from_exchanges(master_password)

    def enrich_futures_from_exchanges(self, master_password: str = None):
        from core.contract_fetcher import ContractFetcher
        fetcher = ContractFetcher()
        return fetcher.enrich_futures_from_exchanges(master_password)

    def enrich_futures(self, master_password: str = None):
        return self.enrich_futures_from_exchanges(master_password)


# Глобальный экземпляр
token_registry = TokenRegistry()