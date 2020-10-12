# %%
import flat_table
import itertools
import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
import utils

from IPython.display import display, Markdown

import importlib

importlib.reload(utils)

# %%

session = requests.Session()
token = "CHANGEME"
session.headers["Authorization"] = f"Bearer {token}"

user_id = "CHANGEME"

playlists = utils.spotify_yield_from_page(
    url=f"https://api.spotify.com/v1/users/{user_id}/playlists", session=session
)

# %%
dfs = []
for playlist in playlists:
    playlist_id = playlist["id"]
    print(playlist["name"], end="")
    tracks = utils.spotify_track_pager_add_audio_features(
        token=token,
        track_pager_url=f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
    )
    df = pd.DataFrame(tracks)
    df["playlist"] = list(itertools.repeat(playlist, len(df)))
    df = flat_table.normalize(df=df, expand_dicts=True, expand_lists=False)
    print(f": {len(df)}")
    dfs.append(df)


# %%
df = pd.concat(dfs, axis="rows")
# Some not permitted tracks have NaN features. Drop.
df = df[df["audio_features.duration_ms"].notna()]

# %%
features: pd.DataFrame = pd.read_csv(
    filepath_or_buffer="audio_features.table", delimiter="\t", comment="#"
)

# %%
# Pandas didn't interpret ints. Fix.
for feature in features.to_dict(orient="index").values():
    if feature["VALUE TYPE"] == "int":
        column = f"audio_features.{feature['KEY']}"
        df[column] = df[column].astype("int", errors="ignore")

df["track.popularity"] = df["track.popularity"].astype("int")
# %%
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
        hue="playlist.name",
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

# %%
fig: plt.Figure
ax: plt.Axes
fig, ax = plt.subplots(figsize=(12, 6))
sns.kdeplot(
    data=df,
    x="track.popularity",
    hue="user.display_name",
    common_norm=False,
    fill=True,
    ax=ax,
    clip=(0, 100),
)
ax.set(title="Popularity", xlim=(0, 100))
display(Markdown(data="# Popularity"))
fig.show()
