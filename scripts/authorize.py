"""One-time local OAuth bootstrap.

Run on your own machine, not in CI:
    py -3 scripts/authorize.py client_secret.json           # for YT_* secrets
    py -3 scripts/authorize.py client_secret.json YT_ADKAR  # for YT_ADKAR_* secrets
Then copy the printed refresh token into the GitHub repository secrets.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Duplicated from adkar_bot.config.SCOPES so this script runs standalone,
# before the package is installed. tests/test_authorize.py asserts the two
# stay in sync — a token minted with the wrong scopes fails at runtime.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(__doc__)
        return 2

    env_prefix = sys.argv[2] if len(sys.argv) == 3 else "YT"

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    # access_type=offline + consent is what actually returns a refresh token;
    # without consent, a re-auth returns none.
    #
    # select_account is load-bearing when you run this twice for two channels.
    # Without it the flow silently reuses whichever Google account the browser
    # is already signed into, so the second run mints another token for the
    # FIRST channel. That is not hypothetical - it happened here, and only
    # verify_channel caught it.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="select_account consent"
    )

    print("\nAdd these as GitHub repository secrets:\n")
    print(f"{env_prefix}_CLIENT_ID     = {flow.client_config['client_id']}")
    print(f"{env_prefix}_CLIENT_SECRET = {flow.client_config['client_secret']}")
    print(f"{env_prefix}_REFRESH_TOKEN = {creds.refresh_token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
