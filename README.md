<img src="public/icon_dark_mode.webp#gh-dark-mode-only" alt="logo-dark" height="55"/>
<img src="public/icon_light_mode.webp#gh-light-mode-only" alt="logo-light" height="55"/>

[![made with hearth by Benjamin Oddou](https://img.shields.io/badge/made%20with%20%E2%99%A5%20by-benjamin%20oddou-DBA33A.svg?style=flat)](https://github.com/BenjaminOddou)
[![saythanks](https://img.shields.io/badge/say-thanks-000000.svg?style=flat)](https://saythanks.io/to/BenjaminOddou)

✨ Welcome to the Alfred Plex repository: **An Alfred Workflow** ✨

![vlc](public/vlc.gif)

## ✅ Prerequisites

* 🍎 MacOS.
* 🎩 Alfred 5. Note that the [Alfred Powerpack](https://www.alfredapp.com/powerpack/) is required to use workflows.
* 📺 An access to a plex media server.
* ❗ Requires **python 3.6** or above.

## 🏎️ Plex API

This workflow uses the [Python-PlexAPI](https://github.com/pkkid/python-plexapi) but doesn't cover all capabilities of this tool. If you see a good feature from the Python-PlexAPI that can be incorporated in this workflow, please let me know by opening an issue or sending a pull request.

## ⬇️ Installation

1. [Download the workflow](https://github.com/BenjaminOddou/alfred-plex/releases/latest).
2. Double click the `.alfredworkflow` file to install.

## 🧰 Setup the workflow

☑️ Install Python 3.6 or above. Check your version with:

```shell
python --version
```

## 🧙‍♂️ Invoke the Workflow

The workflow is divided in 4 parts :

1. `cplex`: Manage servers and perform actions (scan libraries, modify settings, backup logs and databases...).
2. `splex`: Search medias throughout your servers.
3. `dplex`: Filtering & sorting options of your plex media server(s).
4. `pplex`: Manage presets to rapidly search medias.

You can edit these triggers (flagged with a `🕹️` symbol) in the user configuration panel.

## 🤖 Usage of the workflow

### ⚙️ Manage servers and perform actions

> 💡 Use `cplex` to trigger this flow.

Quickly add a server by accessing any XML page from the API, copy the URL and paste it in the Alfred search bar. To display the XML page, you'll need to:
1. Sign in to your Plex account in Plex Web App.
2. Browse to a library item and click `View XML` button.

Follow the [Plex Documentation](https://support.plex.tv/articles/201998867-investigate-media-information-and-formats/) to for more details.

Click on the server to display informations and perform actions.
* Download last version of plex media server from the web.
* Backup logs and databases.
* Display connected accounts.
* Display connected devices (keeps history of devices).
* Display running sessions.
* Perform actions on library sections:
  * Scan library sections (search for new medias).
  * Refresh library sections (download fresh media info from the internet).
  * Display history.
  * Display library sections sizes.
* Display and modify settings of the server.

> 💡 New values for settings must match the setting type and must be valid python. For example, boolean must be True or False with capital letter and string must be quoted.

![server_actions](public/server_actions.webp)

### 🔍 Search medias throughout your servers

> 💡 Use `splex` to trigger this flow.

#### 1. Simple search

In this mode, you search medias on your servers directly by typing your request. You can optionally add a `/` followed by one of the following media types: *track, album, artist, collection, actor, director, genre, movie, photo, photoalbum, playlist, show, episode, clip*.

Link to the [Python-PlexAPI documentation](https://python-plexapi.readthedocs.io/en/latest/modules/server.html#plexapi.server.PlexServer.search).

![simple_search](public/simple_search.webp)

#### 2. Advance search

In this mode, you search medias on your library sections. To enter this mode, you can use `filters` and/or `advanced filters`. 

To know how to use them, go to the next section (`📖 Filtering & sorting options of your plex media server(s)`)

Link to the [Python-PlexAPI documentation](https://python-plexapi.readthedocs.io/en/latest/modules/library.html#plexapi.library.LibrarySection.search).

The following example returns `movies` released between `1980` and `1990` in the country `France`.

![filters_full_1](public/filters_full_1.webp)

#### 3. Actions on medias

1. Open the media on the web. Simply press ⏎ to open the media on plex. There is exception for the following media typess: *actor, collection, director, artist, genre*, see `3.` below.
2. Stream the media with `VLC`. This is only available for the following media types: *movie, episode, track, clip*. Press ⌘⏎ to open the media in `VLC`. 🚨 **It requires `VLC` 3.0 or above and the vlc cli. See below to know how to install the cli.** 🚨
3. Nested search. If you press ⏎ on one of the following media types *actor, collection, director, artist, genre*, this will trigger an advance search.

#### 4. VLC integration

If you don't have `VLC` on your mac, run the following command to install it via `homebrew`:

```shell
brew install --cask vlc
```

If you already have `VLC` installed check the presence of the cli with:

```shell
which vlc
```

If it is not found, uninstall `VLC` and reinstall it using `homebrew`.

Link to the [homebrew formulae](https://formulae.brew.sh/cask/vlc).

### 📖 Filtering & sorting options of your plex media server(s)

> 💡 Use `dplex` to trigger this flow.

Filters, fields and sorts options are generated based on your libraries metadata. This will vary regarding your medias and agents used to gather information. 

#### 1. Filters

> 💡 Filters can be aliased, see section `4. Aliases` below

Plex filters can be applied by typing `filterName=value`. Use `/` to separate them. Find the list of filters under each library sections of your servers.

Example: `libtype=movie/actor=834`. It returns `movies` with `Adam Driver`.

![filters_full_2](public/filters_full_2.webp)

#### 2. Fields (advanced filters)

Plex fields (or advanced filters) can be applied by typing `advancedFilters={<FILTER>}` (or `af={<FILTER>}` in `alias mode`). There is certain conditions you have to respect to make advance filters working:

* Use `/` to separate advanced filter from other filters.
* You must use them along with a `libtype`.
* You must provide a valid Python *dict* or valid *JSON* syntax. Double quotes `"` and single quotes `'` are valid.

To know more on how to use these filters, check the [Python-PlexAPI documentation](https://python-plexapi.readthedocs.io/en/latest/modules/library.html#plexapi.library.LibrarySection.search).

Find the list of fields under each library sections of your servers.

Example:  `libtype=episode/advancedFilters={'show.title': 'one piece', 'episode.index': '1'}`. It returns `episodes` where `episode number` is `1` and the title of the show contains `one piece`.

![advanced_filters](public/advanced_filters.webp)

#### 3. Sorts

You can sort results by typing `sort=sortName:dir` (or `so=sortName:dir` in `alias mode`). Direction can be `:asc` for ascending or `:desc` for descending.

Example: `libtype=movie/sort=originallyAvailableAt:desc`. This will display `movies` from the `most recent` to the `older` one.

![sorts](public/sorts.webp)

#### 4. Aliases

Aliases are enabled by default, and allows you, when activated, to write filters more easily. `libtype` becomes `lt`, `studio` becomes `st`...

You can disable this behavior in the user control panel. Just select `No 👎` for the `📜 Use aliases` parameter.

Aliases file can be edited, but be careful about double values. It is the `aliases.json` file located under the `📁 Data Folder` (`~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex` by default).

Example: `af={'addedAt>>': '30d'}/lt=movie`. It returns `movies` added in plex during the last `30 days`.

![aliases](public/aliases.webp)

### 🛠️ Manage presets to rapidly search medias

> 💡 Use `pplex` to trigger this flow.

#### 1. Create a preset

Create easily preset by pressing ⏎ on `Add a new Preset`. Input a `value` for the preset **WITH FULL FILTERS NAMES**. Then input a `title` and a `subtitle` separated by a `/`.

#### 2. Modify a preset

Simply press ⌘⏎ to enter in the modified mode. Press ⏎ to edit the `title/subtitle` or the `value`.

![preset_modify](public/preset_modify.webp)

#### 3. Apply a preset

Simply press ⏎ on a preset to apply its value to the search workflow.

![preset_entry](public/preset_entry.webp)

## ⚖️ License

[MIT License](LICENSE) © Benjamin Oddou
