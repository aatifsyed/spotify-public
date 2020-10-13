# %%
import flatten_dict
import pandas as pd
import pyperclip
import requests
import utils

from typing import List

# %%
scopes = [scope for scope in utils.all_scopes if "read" in scope]
pyperclip.copy(utils.generate_auth_url(scopes=scopes))

tokens: List[str] = []

while True:
    try:
        token = utils.url_get_token(input("Authorized URL"))
        tokens.append(token)
    except KeyError:
        break

# %%
dfs: List[pd.DataFrame] = []

for token in tokens:

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"
    user = session.get(url=f"{utils.base_url}/me").json()

    tracks = utils.spotify_track_pager_add_audio_features(
        token=token, track_pager_url=f"{utils.base_url}/me/tracks"
    )

    # Add a user column for comparing between users
    tracks = ({**track, "user": user} for track in tracks)

    tracks = (flatten_dict.flatten(d=track, reducer="dot") for track in tracks)

    # Make a table
    df = pd.DataFrame(tracks)

    df.added_at = pd.to_datetime(df.added_at)

df = pd.concat(dfs, axis="index")

# %%
utils.plot_features_popularity(df=df, hue="user.display_name")