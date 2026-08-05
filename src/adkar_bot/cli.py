import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from . import config
from .config import ConfigError, assert_configured
from .corpus import load_corpus
from .metadata import build_comment, build_description, build_tags, build_title
from .render import render
from .selector import load_state, next_dhikr, record, save_state
from .youtube import build_client, post_comment, upload_video

log = logging.getLogger("adkar_bot")


def _require_env(name: str) -> str:
    """Read a required secret, failing with an actionable message.

    os.environ[...] raises a bare KeyError that tells an operator nothing.
    """
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"{name} is not set. It is required to publish. "
            f"Set it as a GitHub repository secret, or export it locally."
        )
    return value


def _pick():
    corpus = load_corpus(config.CORPUS_PATH)
    state = load_state(config.STATE_PATH)
    return corpus, state, next_dhikr(corpus, state)


def cmd_render(_args) -> int:
    _corpus, _state, dhikr = _pick()
    out = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4")
    log.info("rendered %s -> %s", dhikr.id, out)
    return 0


def cmd_publish(_args) -> int:
    assert_configured()
    client_id = _require_env("YT_CLIENT_ID")
    client_secret = _require_env("YT_CLIENT_SECRET")
    refresh_token = _require_env("YT_REFRESH_TOKEN")

    corpus, state, dhikr = _pick()
    video = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4")

    client = build_client(client_id, client_secret, refresh_token)
    video_id = upload_video(
        client, video,
        build_title(dhikr), build_description(dhikr), build_tags(dhikr),
    )
    log.info("uploaded %s as %s (private)", dhikr.id, video_id)

    try:
        post_comment(client, video_id, build_comment(dhikr))
    except Exception:
        # The upload succeeded; never retry it just because the comment failed.
        log.warning("comment failed for %s; post it manually", video_id,
                    exc_info=True)

    now = datetime.now(timezone.utc).isoformat()
    save_state(record(state, dhikr, video_id, now, corpus=corpus),
               config.STATE_PATH)
    log.info("state saved; publish and pin %s manually", video_id)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="adkar-bot")
    subs = parser.add_subparsers(dest="cmd", required=True)
    subs.add_parser("render").set_defaults(func=cmd_render)
    subs.add_parser("publish").set_defaults(func=cmd_publish)
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2
    except Exception:
        log.exception("run failed; state not modified")
        return 1


if __name__ == "__main__":
    sys.exit(main())
