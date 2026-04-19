class TokenRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tokens = {}  # exchange_name -> list of tokens
        return cls._instance

    def add_token(self, token: str, exchange: str):
        if exchange not in self.tokens:
            self.tokens[exchange] = []
        if token not in self.tokens[exchange]:
            self.tokens[exchange].append(token)

    def get_tokens(self, exchange: str):
        return self.tokens.get(exchange, [])


token_registry = TokenRegistry()