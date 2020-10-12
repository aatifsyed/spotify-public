# %%
import itertools
import requests
import time

from typing import Dict, Generator, List, Optional, Union
from urllib import parse

# %%
backoffs: int = 0
gets: int = 0


def print_assert_ok(response: requests.Response) -> None:
    if response.status_code is not requests.codes["ok"]:
        print(response.status_code)
        print(response.headers)
        print(response.content)
        raise AssertionError("Didn't get HTTP 200 OK")


def spin_get(
    *args,
    session: Union[type(requests), requests.Session] = requests,
    assert_ok: bool = True,
    **kwargs,
) -> requests.Response:
    """A wrapper around requests.get, which sleeps and retries if the server sends back a 429 (Too Many Requests)"""

    global gets
    gets += 1

    while True:
        response = session.get(*args, **kwargs)

        if response.status_code == requests.codes["too_many_requests"]:
            global backoffs
            backoffs += 1
            # TODO: retry-after can also be a HTTP Date
            cooldown = int(response.headers["retry-after"])
            time.sleep(cooldown)
            continue

        else:
            if assert_ok:
                print_assert_ok(response)
            return response


def spotify_yield_from_page(url: str, session: requests.Session) -> Generator:
    response = spin_get(url=url, session=session)

    items: List = response.json()["items"]
    next_url: Optional[str] = response.json()["next"]

    if items:
        yield from items
        if next_url:
            yield from spotify_yield_from_page(url=next_url, session=session)


def spotify_yield_from_list(url: str, session: requests.Session, **kwargs) -> Generator:
    response = session.get(url, **kwargs)
    print_assert_ok(response)
    # Assume all we get back is a list
    _, lis = response.json().popitem()
    yield from lis


# https://stackoverflow.com/a/8991553
def grouper(n, iterable):
    """Group an iterable into chunks"""
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, n))
        if not chunk:
            return
        yield chunk


def standardise_track_generator(
    candidate_generator: Generator[dict, None, None]
) -> Generator[dict, None, None]:
    """Spotify has two types track objects:
    `saved_track_object` etc. - {added_at: ..., track: ...}
    `track_object` = {...}

    This leaves the former unchanged, and returns the latter as
    {track: ...}"""
    peek = next(candidate_generator)

    if "track" in peek.keys():
        standardised_generator = candidate_generator
    else:
        if peek["type"] != "track":
            print(peek)
            raise RuntimeError("Expected track object, but didn't get one")
        standardised_generator = ({"track": obj} for obj in candidate_generator)
        peek = {"track": peek}

    return itertools.chain([peek], standardised_generator)


def tracks_get_audio_features(
    track_generator: Generator[dict, None, None], session: requests.Session
) -> Generator[dict, None, None]:

    maximum_queries_per_request = 100

    for track_batch in grouper(maximum_queries_per_request, track_generator):

        track_ids = (track_object["track"]["id"] for track_object in track_batch)

        audio_features_generator = spotify_yield_from_list(
            url="https://api.spotify.com/v1/audio-features",
            session=session,
            # Unavailable tracks will have "None" as an ID
            params={
                "ids": ",".join(
                    track_id if track_id is not None else "" for track_id in track_ids
                )
            },
        )

        yield from audio_features_generator


def spotify_track_pager_add_audio_features(
    token: str, track_pager_url: str, append_user: bool = True
):

    # Establish a session for authorization
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {token}"

        user = spin_get(url="https://api.spotify.com/v1/me", session=session).json()

        track_generator = spotify_yield_from_page(url=track_pager_url, session=session)
        track_generator = standardise_track_generator(track_generator)

        g0, g1 = itertools.tee(track_generator, 2)

        audio_features_generator = tracks_get_audio_features(
            track_generator=g0, session=session
        )

        yield from (
            {
                **track_object,
                "user": user,
                "audio_features": audio_features,
            }
            for track_object, audio_features in zip(g1, audio_features_generator)
        )


# %%

# gets pages of https://developer.spotify.com/documentation/web-api/reference/object-model/#saved-track-object
library_url = "https://api.spotify.com/v1/me/tracks"
top_urls = {
    (
        typ,
        time_range,
    ): f"https://api.spotify.com/v1/me/top/{typ}?time_range={time_range}"
    for typ, time_range in itertools.product(
        ["artists", "tracks"], ["long_term", "medium_term", "short_term"]
    )
}

scopes = [
    line
    for line in """\
ugc-image-upload
user-top-read
user-read-playback-position
user-read-playback-state
user-library-modify
streaming
user-read-private
user-follow-modify
user-library-read
playlist-modify-public
user-read-currently-playing
user-modify-playback-state
user-follow-read
playlist-read-collaborative
playlist-read-private
app-remote-control
user-read-email
user-read-recently-played
playlist-modify-private
""".splitlines()
]


def generate_auth_url():
    global scopes
    pr = requests.PreparedRequest()
    pr.prepare_url(
        url="https://accounts.spotify.com/authorize",
        params={
            "client_id": "6306b3af252b4b2c8a55c1db34c5da95",
            "response_type": "token",
            "redirect_uri": "https://example.com",
            "scope": " ".join(scope for scope in scopes if "read" in scope),
        },
    )
    return pr.url


def url_get_token(url: str):
    split = parse.urlsplit(url)
    queries = parse.parse_qs(split.fragment)
    return queries["access_token"].pop()