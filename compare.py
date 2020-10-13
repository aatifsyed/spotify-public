# %%
import flatten_dict
import pandas as pd
import pyperclip
import requests
import utils

from typing import List

# %%
# Convenience for getting permission
scopes = [scope for scope in utils.all_scopes if "read" in scope]
pyperclip.copy(utils.generate_auth_url(scopes=scopes))
token = utils.url_get_token(input("Authorized URL"))

# %%
# Session object to deal with auth
session = requests.Session()
session.headers["Authorization"] = f"Bearer {token}"

# %%
playlists = utils.spotify_yield_from_page(
    url=f"{utils.base_url}/me/playlists", session=session
)

dfs: List[pd.DataFrame] = []

# Gather all our data
for playlist in playlists:
    print(playlist["name"])

    if playlist["name"] == "Windows Media Player":
        # zero length!
        continue

    tracks = utils.spotify_track_pager_add_audio_features(
        token=token,
        track_pager_url=f"{utils.base_url}/playlists/{playlist['id']}/tracks",
    )

    # Add a playlist column for comparing between playlists
    tracks = ({**track, "playlist": playlist} for track in tracks)

    tracks = (flatten_dict.flatten(d=track, reducer="dot") for track in tracks)

    df = pd.DataFrame(tracks)
    dfs.append(df)

# Merge into one table
df = pd.concat(dfs, axis="index")

# %%
# Plot different curves for each hue
utils.plot_features_popularity(df=df, hue="playlist.name")

# %%
