# %%
import flatten_dict
import pandas as pd
import pyperclip
import requests
import utils

from datetime import datetime
from typing import List

# %%
# Convenience for getting permission
scopes = [scope for scope in utils.all_scopes if "read" in scope]
pyperclip.copy(utils.generate_auth_url(scopes=scopes))
token = utils.url_get_token(input("Authorized URL"))

# %%
dfs: List[pd.DataFrame] = []

session = requests.Session()
session.headers["Authorization"] = f"Bearer {token}"
user = session.get(url=f"{utils.base_url}/me").json()

range_and_urls = ((key[1], utils.top_urls[key]) for key in utils.top_urls.keys() if key[0] is "tracks")

# Gather all our data
for time_range, pager in range_and_urls:
    tracks = utils.spotify_track_pager_add_audio_features(
        token=token,
        track_pager_url=pager,
    )

    # Add a range column for comparing between ranges
    tracks = ({**track, "time_range": time_range} for track in tracks)

    tracks = ({**track, "user": user} for track in tracks)

    tracks = (flatten_dict.flatten(d=track, reducer="dot") for track in tracks)

    df = pd.DataFrame(tracks)
    dfs.append(df)

# Merge into one table
df = pd.concat(dfs, axis="index")

# %%
# Plot different curves for each hue
utils.plot_features_popularity(df=df, hue="time_range")

# %%
gathered_at = datetime.now()
df["gathered_at"] = gathered_at
df.to_hdf(path_or_buf="my_tops.hdf", key=str(gathered_at))
# %%
