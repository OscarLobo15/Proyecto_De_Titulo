def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "********"
    return f"{token[:4]}...{token[-4:]}"

