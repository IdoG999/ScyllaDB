from __future__ import annotations

import argparse
import json
import secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen


AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict:
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LinkedIn OAuth helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_parser = subparsers.add_parser("auth-url", help="Build LinkedIn OAuth authorize URL")
    auth_parser.add_argument("--client-id", required=True, help="LinkedIn app client id")
    auth_parser.add_argument("--redirect-uri", required=True, help="OAuth redirect URI")
    auth_parser.add_argument(
        "--scope",
        default="r_marketing_leadgen_automation",
        help="Space-separated OAuth scopes",
    )
    auth_parser.add_argument("--state", help="CSRF state value (auto-generated if omitted)")

    exchange_parser = subparsers.add_parser("exchange-code", help="Exchange auth code for token")
    exchange_parser.add_argument("--client-id", required=True, help="LinkedIn app client id")
    exchange_parser.add_argument("--client-secret", required=True, help="LinkedIn app client secret")
    exchange_parser.add_argument("--redirect-uri", required=True, help="OAuth redirect URI")
    exchange_parser.add_argument("--code", required=True, help="Authorization code")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "auth-url":
        state = args.state or secrets.token_urlsafe(24)
        url = build_authorize_url(
            client_id=args.client_id,
            redirect_uri=args.redirect_uri,
            scope=args.scope,
            state=state,
        )
        print("Open this URL in your browser:")
        print(url)
        print("")
        print(f"Use and verify this state value: {state}")
        return

    if args.command == "exchange-code":
        token_payload = exchange_code_for_token(
            client_id=args.client_id,
            client_secret=args.client_secret,
            redirect_uri=args.redirect_uri,
            code=args.code,
        )
        access_token = token_payload.get("access_token", "")
        expires_in = token_payload.get("expires_in", "")
        print("Token response:")
        print(json.dumps(token_payload, indent=2))
        print("")
        if access_token:
            print("Export command:")
            print(f'export LINKEDIN_ACCESS_TOKEN="{access_token}"')
        if expires_in:
            print(f"# expires_in: {expires_in} seconds")


if __name__ == "__main__":
    main()
