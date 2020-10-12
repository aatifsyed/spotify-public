# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
import flat_table
import ipywidgets as widgets
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import utils

from IPython.display import display, Markdown

# %%
data = pd.HDFStore(path="data.hdf")
print(data.keys())
df0 = pd.read_hdf(path_or_buf=data, key=input(f"One of: {data.keys()}"))
df1 = pd.read_hdf(path_or_buf=data, key=input(f"One of: {data.keys()}"))
df2 = pd.read_hdf(path_or_buf=data, key=input(f"One of: {data.keys()}"))
df = pd.concat([df0,df1,df2], axis="rows")
data.close()

# %%
features: pd.DataFrame = pd.read_csv(
    filepath_or_buffer="audio_features.table", delimiter="\t", comment="#"
)

# %%
# Pandas didn't interpret ints. Fix.
for feature in features.to_dict(orient="index").values():
    if feature["VALUE TYPE"] == "int":
        column = f"audio_features.{feature['KEY']}"
        df[column] = df[column].astype("int")

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
        hue="user.display_name",
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
