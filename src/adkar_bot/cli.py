import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from . import config
from .config import ConfigError, assert_configured
from .corpus import load_corpus
from .metadata import build_description, build_tags, build_title
from .profiles import PROFILES
from .render import render
from .selector import load_state, next_dhikr, record, save_state
from .youtube import build_client, upload_video, verify_channel

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


def _credentials(profile) -> tuple[str, str, str]:
    """Guard 1 against publishing to the wrong channel.

    Each profile reads credentials from names derived from its own prefix, so
    running one profile with the other's environment loaded fails by name
    before any network call rather than authenticating as the wrong channel.
    """
    return tuple(
        _require_env(f"{profile.env_prefix}_{suffix}")
        for suffix in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
    )


def _resolve_profile(args):
    """--profile, else the PROFILE env var, else fail.

    No default. A default here means a wrong-channel upload the first time
    someone forgets the flag. Validated here rather than by argparse's
    `choices`, so a bad PROFILE env var takes the same path as a bad flag -
    argparse does not check `choices` against a value it did not parse.
    """
    name = getattr(args, "profile", None) or os.environ.get("PROFILE") or ""
    if name not in PROFILES:
        raise ConfigError(
            f"profile {name!r} is not one of {sorted(PROFILES)}. "
            f"Pass --profile, or set the PROFILE environment variable."
        )
    return PROFILES[name]


def _pick(profile):
    corpus = load_corpus(profile.corpus_path)
    state = load_state(profile.state_path)
    return corpus, state, next_dhikr(corpus, state)


def cmd_render(args) -> int:
    profile = _resolve_profile(args)
    assert_configured(profile)
    _corpus, _state, dhikr = _pick(profile)
    out = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4", profile)
    log.info("rendered %s -> %s", dhikr.id, out)
    return 0


def cmd_publish(args) -> int:
    profile = _resolve_profile(args)
    assert_configured(profile)
    client_id, client_secret, refresh_token = _credentials(profile)

    count = getattr(args, "count", None) or profile.default_count
    if count > config.MAX_UPLOADS_PER_DAY:
        log.warning(
            "asked for %d uploads; the default API quota affords %d "
            "(%d units/day / %d per videos.insert). The uploads past that "
            "will fail with quotaExceeded unless Google has raised the quota.",
            count, config.MAX_UPLOADS_PER_DAY,
            config.DAILY_QUOTA_UNITS, config.UPLOAD_COST_UNITS,
        )

    client = build_client(client_id, client_secret, refresh_token)
    # Guard 2, before the first render: a wrong-channel run must cost a
    # 1-unit API call, not 20 seconds of ffmpeg and 1,600 units of upload.
    verify_channel(client, profile)

    uploaded = 0
    for n in range(1, count + 1):
        # Re-read corpus and state every pass: the previous iteration wrote
        # state to disk, and reading it back is what guarantees the next pick
        # is a different dhikr. One code path, same as a sequence of runs.
        corpus, state, dhikr = _pick(profile)
        video = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4", profile)

        try:
            video_id = upload_video(
                client, video,
                build_title(dhikr),
                build_description(dhikr, profile),
                build_tags(dhikr, profile),
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
                   profile.state_path)
        uploaded += 1
        log.info("uploaded %s as %s (%s) to %s - %d of %d",
                 dhikr.id, video_id, config.PRIVACY_STATUS,
                 profile.channel_handle, n, count)

    log.info("published %d video(s) to %s this run",
             uploaded, profile.channel_handle)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="adkar-bot")
    subs = parser.add_subparsers(dest="cmd", required=True)

    def _with_profile(sub):
        sub.add_argument(
            "--profile", choices=sorted(PROFILES), default=None,
            help="which channel to work against (env: PROFILE). Required.",
        )
        return sub

    _with_profile(subs.add_parser("render")).set_defaults(func=cmd_render)
    pub = _with_profile(subs.add_parser("publish"))
    pub.add_argument(
        "--count", type=int, default=None,
        help="how many to upload this run (default: the profile's own count)",
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
