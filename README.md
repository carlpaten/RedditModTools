# RedditModTools

You will need to [create an app](https://ssl.reddit.com/prefs/apps/) in Reddit to use the scripts here. Then, copy `praw.template.ini` to `praw.ini` and fill it in.

Then, with Miniconda installed:

```bash
conda env create --file environment.yml
source activate reddit_mod_tools
```

## TODO

- Use only one reddit app for everyone (requires OAuth)
- Rewrite everything in F#/.NET Core (okay maybe not)
