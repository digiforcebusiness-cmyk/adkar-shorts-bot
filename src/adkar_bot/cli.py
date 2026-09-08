import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from . import config
from .config import ConfigError, assert_configured
from .corpus import load_corpus
from .metadata import build_description, build_tags, build_title
from .render import render
from .selector import load_state, next_dhikr, record, save_state
from .youtube import build_client, upload_video

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
    assert_configured()
    _corpus, _state, dhikr = _pick()
    out = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4")
    log.info("rendered %s -> %s", dhikr.id, out)
    return 0


def cmd_publish(args) -> int:
    assert_configured()
    client_id = _require_env("YT_CLIENT_ID")
    client_secret = _require_env("YT_CLIENT_SECRET")
    refresh_token = _require_env("YT_REFRESH_TOKEN")

    count = getattr(args, "count", None) or config.PUBLISH_COUNT
    if count > config.MAX_UPLOADS_PER_DAY:
        log.warning(
            "asked for %d uploads; the default API quota affords %d "
            "(%d units/day / %d per videos.insert). The uploads past that "
            "will fail with quotaExceeded unless Google has raised the quota.",
            count, config.MAX_UPLOADS_PER_DAY,
            config.DAILY_QUOTA_UNITS, config.UPLOAD_COST_UNITS,
        )

    client = build_client(client_id, client_secret, refresh_token)

    uploaded = 0
    for n in range(1, count + 1):
        # Re-read corpus and state every pass: the previous iteration wrote
        # state to disk, and reading it back is what guarantees the next pick
        # is a different dhikr. One code path, same as a sequence of runs.
        corpus, state, dhikr = _pick()
        video = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4")

        try:
            video_id = upload_video(
                client, video,
                build_title(dhikr), build_description(dhikr), build_tags(dhikr),
            )
        except Exception:
            # State for everything already uploaded is on disk, so the caller
            # can still commit it and the next run will not repeat those.
            log.error(
                "upload %d of %d failed on %s; %d already uploaded and saved",
                n, count, dhikr.id, uploaded,
            )
            raise

        now = datetime.now(timezone.utc).isoformat()
        save_state(record(state, dhikr, video_id, now, corpus=corpus),
                   config.STATE_PATH)
        uploaded += 1
        log.info("uploaded %s as %s (%s) - %d of %d",
                 dhikr.id, video_id, config.PRIVACY_STATUS, n, count)

    log.info("published %d video(s) this run", uploaded)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="adkar-bot")
    subs = parser.add_subparsers(dest="cmd", required=True)
    subs.add_parser("render").set_defaults(func=cmd_render)
    pub = subs.add_parser("publish")
    pub.add_argument(
        "--count", type=int, default=None,
        help="how many adkar to upload this run "
             "(default: PUBLISH_COUNT env, or 1)",
    )
    pub.set_defaults(func=cmd_publish)
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
