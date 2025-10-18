from lighter import SignerClient

def make_signer(base_url: str, account_index: int, api_key_index: int,
                api_pk: str, eth_pk: str) -> SignerClient:
    # Mirrors lighter-python sample: local signing + API client in one
    # Note: SignerClient uses api_pk for signing, eth_pk is not used in the constructor
    return SignerClient(
        url=base_url,
        private_key=api_pk,
        api_key_index=api_key_index,
        account_index=account_index,
    )

async def create_auth_token(client: SignerClient, ttl_secs: int = 60) -> str:
    return await client.create_auth_token_with_expiry(ttl_secs)

async def sign_create_order(client: SignerClient, body: dict):
    # Returns dict with keys: tx_type, tx_info
    return await client.sign_create_order(body)
