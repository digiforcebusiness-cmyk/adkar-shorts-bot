# Background audio

Drop audio files here to play as background recitation under the rendered
Shorts. Any of these formats works:

- `.mp3`
- `.m4a`
- `.ogg`
- `.wav`

The bot picks one file per video automatically (deterministically, per
dhikr — see `src/adkar_bot/audio.py`). If this directory is empty, videos
render with a silent audio track instead, exactly as before.

**Warning:** if you drop in copyrighted Qur'an recitations, YouTube's
Content ID system can detect the match and claim the video. Depending on
the rights holder's policy, that claim may monetize the video on their
behalf, restrict it, or block it entirely in some regions. Only use audio
you have the rights to publish, or recitations explicitly licensed for
reuse. This is your decision to make — the bot does not ship, download,
or recommend any specific recitation.
