# %%
import itertools
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import time


from IPython.display import display, Markdown
from typing import Dict, Generator, Iterator, List, Optional, Union
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
    session: Optional[requests.Session] = None,
    assert_ok: bool = True,
    **kwargs,
) -> requests.Response:
    """A wrapper around requests.get, which sleeps and retries if the server sends back a 429 (Too Many Requests)"""

    global gets
    gets += 1

    while True:
        if session is None:
            response = requests.get(*args, **kwargs)
        else:
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


def spotify_yield_from_page(
    url: str,
    session: requests.Session,
) -> Iterator[Dict]:
    response = spin_get(url=url, session=session)

    print_assert_ok(response)

    items: List = response.json()["items"]
    next_url: Optional[str] = response.json()["next"]

    if items:
        yield from items
        if next_url:
            yield from spotify_yield_from_page(url=next_url, session=session)


def spotify_yield_from_list(
    url: str, session: requests.Session, **kwargs
) -> Iterator[Dict]:
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


def standardise_track_generator(candidate_generator: Iterator[Dict]) -> Iterator[Dict]:
    """Spotify has two types track objects:
    `saved_track_object` etc. = {added_at: ..., track: ...}
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
    track_generator: Iterator[Dict], session: requests.Session
) -> Iterator[Dict]:

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
    token: str, track_pager_url: str
) -> Iterator[Dict]:

    # Establish a session for authorization
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {token}"

        track_generator = spotify_yield_from_page(url=track_pager_url, session=session)
        track_generator = standardise_track_generator(track_generator)

        g0, g1 = itertools.tee(track_generator, 2)

        audio_features_generator = tracks_get_audio_features(
            track_generator=g0, session=session
        )

        yield from (
            {
                **track_object,
                "audio_features": audio_features,
            }
            for track_object, audio_features in zip(g1, audio_features_generator)
        )


# %%

base_url = "https://api.spotify.com/v1"
top_urls = {
    (
        typ,
        time_range,
    ): f"{base_url}/me/top/{typ}?time_range={time_range}"
    for typ, time_range in itertools.product(
        ["artists", "tracks"], ["long_term", "medium_term", "short_term"]
    )
}

all_scopes = [
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


def generate_auth_url(scopes: List[str]):
    global all_scopes

    for scope in scopes:
        if scope not in all_scopes:
            raise RuntimeError("Not sure that's a valid scope")

    pr = requests.PreparedRequest()
    pr.prepare_url(
        url="https://accounts.spotify.com/authorize",
        params={
            "client_id": "6306b3af252b4b2c8a55c1db34c5da95",
            "response_type": "token",
            "redirect_uri": "https://example.com",
            "scope": " ".join(scopes),
        },
    )
    return pr.url


def url_get_token(url: str):
    split = parse.urlsplit(url)
    queries = parse.parse_qs(split.fragment)
    return queries["access_token"].pop()


# %%


def plot_features_popularity(df: pd.DataFrame, hue: str = "user.display_name"):

    features: pd.DataFrame = pd.read_csv(
        filepath_or_buffer="audio_features.table", delimiter="\t", comment="#"
    )

    # Pandas didn't interpret ints. Fix.
    for feature in features.to_dict(orient="index").values():
        if feature["VALUE TYPE"] == "int":
            column = f"audio_features.{feature['KEY']}"
            df[column] = df[column].astype("int", errors="ignore")

    df["track.popularity"] = df["track.popularity"].astype("int")

    for feature in features.to_dict(orient="index").values():
        if feature["VALUE TYPE"] not in ("int", "float"):
            # Non-numeric data. Don't plot
            continue

        clip = (0, 1) if feature["unit interval?"] else None
        key = feature["KEY"]

        fig: plt.Figure
        ax: plt.Axes
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.kdeplot(
            data=df,
            x=f"audio_features.{key}",
            hue=hue,
            common_norm=False,
            fill=True,
            ax=ax,
            clip=clip,
        )
        ax.set(title=key.title(), xlim=clip)

        display(Markdown(data=f"# {key.title()}"))
        display(fig)
        display(Markdown(data=feature["VALUE DESCRIPTION"]))
        plt.close(fig)  # We display manually, so don't let matplotlib

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.kdeplot(
        data=df,
        x="track.popularity",
        hue=hue,
        common_norm=False,
        fill=True,
        ax=ax,
        clip=(0, 100),
    )
    ax.set(title="Popularity", xlim=(0, 100))
    display(Markdown(data="# Popularity"))
    fig.show()
