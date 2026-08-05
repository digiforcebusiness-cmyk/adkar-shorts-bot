"""One-time local OAuth bootstrap.

Run on your own machine, not in CI:
    py -3 scripts/authorize.py client_secret.json
Then copy the printed refresh token into the GitHub repository secrets.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Duplicated from adkar_bot.config.SCOPES so this script runs standalone,
# before the package is installed. tests/test_authorize.py asserts the two
# stay in sync — a token minted with the wrong scopes fails at runtime.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    # access_type=offline + prompt=consent is what actually returns a refresh
    # token. Without prompt=consent, a re-auth returns none.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )

    print("\nAdd these as GitHub repository secrets:\n")
    print(f"YT_CLIENT_ID     = {flow.client_config['client_id']}")
    print(f"YT_CLIENT_SECRET = {flow.client_config['client_secret']}")
    print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
