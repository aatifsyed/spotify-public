"""
Just take an authorised url, and download that user's library, saving it to an archive
"""

# %%
import flat_table
import pandas as pd
import pyperclip
import utils

from datetime import datetime

# %%
request_url = utils.generate_auth_url()
pyperclip.copy(request_url)

# %%
token = utils.url_get_token(input("Enter authorized url"))
print(token)
pyperclip.copy(token)

# %%
# Get library
df = pd.DataFrame(
    utils.spotify_track_pager_add_audio_features(
        token=token, track_pager_url=utils.library_url
    )
)
df = flat_table.normalize(df=df, expand_dicts=True, expand_lists=False)

# %%
names = df["user.display_name"].unique()
if len(names) == 1:
    name = names[0]
else:
    raise Exception

# %%
df.to_hdf(path_or_buf="archive.hdf", key=f"{name}-Library-{datetime.now().isoformat()}")

# %%
