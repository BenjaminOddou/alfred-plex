<img src="public/icon_dark_mode.webp#gh-dark-mode-only" alt="logo-dark" height="55"/>
<img src="public/icon_light_mode.webp#gh-light-mode-only" alt="logo-light" height="55"/>

[![made with heart by Benjamin Oddou](https://img.shields.io/badge/made%20with%20%E2%99%A5%20by-benjamin%20oddou-DBA33A.svg?style=flat)](https://github.com/BenjaminOddou)
[![saythanks](https://img.shields.io/badge/say-thanks-000000.svg?style=flat)](https://saythanks.io/to/BenjaminOddou)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-986821.svg)](https://www.python.org/downloads/macos/)

✨ Welcome to the Alfred Plex repository: **An Alfred Workflow** ✨

![vlc](public/vlc.gif)

## ✅ Prerequisites

* MacOS.
* Alfred 5. Note that the [Alfred Powerpack](https://www.alfredapp.com/powerpack/) is required to use workflows.
* An access to a plex media server.
* Requires **python 3.8** or above.

## ⬇️ Installation

1. [Download the workflow](https://github.com/BenjaminOddou/alfred-plex/releases/latest).
2. Double click the `.alfredworkflow` file to install.

## 🏎️ Plex API

This workflow uses the [Python-PlexAPI](https://github.com/pkkid/python-plexapi) but doesn't cover all capabilities of this tool. If you see a good feature from the Python-PlexAPI that can be incorporated in this workflow, please let me know by opening an issue or sending a pull request.

## 🧰 Setup the workflow

Install Python 3.8 or above. Check your version with:

```shell
python --version
```

## 🧙‍♂️ Invoke the workflow

Launch the menu with `plex`. You can edit this trigger in the [Workflow Configuration](https://www.alfredapp.com/help/workflows/user-configuration/) panel.

The workflow is divided in 6 parts :

1. Search medias throughout your servers.
2. Search medias using discover.
3. Manage your plex accounts.
4. Manage servers and perform actions.
5. Manage presets to rapidly search medias.
6. Workflow configuration + filter & sort options.

![menu](public/menu.webp)

To use this workflow, you need to add server(s).In order to do so, you must connect to an account that have access to a plex media server with your credentials. **If you're not the owner of the server, you won't have access to the server settings**.

Go to the `Plex Accounnt` section to know more on how to manage your accounts.

## 🤖 Usage of the workflow

### Plex Search : Search medias throughout your servers

#### 1. Simple search

In this mode, you search medias on your servers directly by typing your request. You can optionally add a `/` followed by one of the following media types: *track, album, artist, collection, actor, director, genre, movie, photo, photoalbum, playlist, show, episode, clip*.

Link to the [Python-PlexAPI documentation](https://python-plexapi.readthedocs.io/en/latest/modules/server.html#plexapi.server.PlexServer.search).

![simple_search](public/simple_search.webp)

#### 2. Advance search

In this mode, you search medias on your library sections. To enter this mode, you can use `filters` and/or `advanced filters`. 

To know how to use them, go to the section : `Plex Help`.

Link to the [Python-PlexAPI documentation](https://python-plexapi.readthedocs.io/en/latest/modules/library.html#plexapi.library.LibrarySection.search).

The following example `libtype=movie/decade=1980/country=france` returns `movies` released between `1980` and `1990` in the country `France`.

![filters_full_1](public/filters_full_1.webp)

#### 3. Actions on medias

> The following actions can be configured in the user configuration panel

1. Nested search. Press <kbd>⏎</kbd> on one of the following media types: *actor, director, collection, artist, album, genre, show, season*, to trigger a nested search.
2. Open the media on the web. Simply press <kbd>⌘</kbd><kbd>⏎</kbd> to open the media on plex. Not available for *genre* media type.
3. Stream the media with VLC / IINA. This is only available for the following media types: *movie, episode, clip, track, album*. Press <kbd>⌥</kbd><kbd>⏎</kbd> to open the media in VLC / IINA. *It requires VLC 3.0+ or IINA 1.0.0+ and the corresponding cli. See below to know how to install the cli*. If you have multiple versions of the same *movie, episode, clip*, you'll be asked to choose the file you want to play.
4. Get infos of movies and tv shows using the [Movie and TV Show Search](https://github.com/tmcknight/Movie-and-TV-Show-Search-Alfred-Workflow) Alfred workflow by [Tom McKnight](https://github.com/tmcknight). Press <kbd>⌃</kbd><kbd>⏎</kbd> to trigger the workflow. *It requires `Movie and TV Show Search` Alfred workflow 2.16.0 or above*. Only available for *movie, show* media types.

#### 4. VLC and IINA integration

If you don't have VLC / IINA on your mac, run the following command to install it via homebrew:

```shell
brew install --cask vlc
brew install --cask iina
```

If you already have VLC / IINA installed check the presence of the cli with:

```shell
which vlc
which iina
```

If it is not found, uninstall VLC / IINA and reinstall it using homebrew.

Link to the VLC [homebrew formulae](https://formulae.brew.sh/cask/vlc).
Link to the IINA [homebrew formulae](https://formulae.brew.sh/cask/iina).

### Plex Discover : Search medias using discover

Search medias and people on [Plex Discover](https://support.plex.tv/articles/discover/). You can perform the same actions ** listed [above](#3-actions-on-medias).

** Except streaming with VLC / IINA. Note that nested search allows you to search media title within your servers.

![discover](public/discover.webp)

### Plex Accounts : Manage your plex accounts

Connect one or more account to add plex media servers. In this section you can :
* See the list of your servers. Servers that aren't added to the workflow are greyed out.
* Manage connected users.
* Manage connected devices.
* Manage your whatchlist.

![plex_account](public/plex_account.webp)

> Removing a plex account will remove all the servers connected. You can also remove a server directly in the Plex Media Servers section.

### Plex Media Servers : Manage servers and perform actions

Select the server to view its informations and perform actions.
* Download last version of plex media server from the web.
* Backup logs and databases.
* Display connected account.
* Manage running sessions.
* Perform actions on library sections:
  * Scan library sections (search for new medias).
  * Refresh library sections (download fresh media info from the internet).
  * Display history.
  * Display library sections sizes.
* Display and modify settings of the server.
* Display real time server statistics.

> New values for settings must match the setting type and must be valid python. For example, boolean must be True or False with capital letter and string must be quoted.

![server_actions](public/server_actions.webp)

### Plex Presets : Manage presets to rapidly search medias

#### 1. Create a preset

Create easily preset by pressing <kbd>⏎</kbd> on `Add a new Preset`. Input a `value` for the preset **WITH FULL FILTERS NAMES**. Then input a `title` and a `subtitle` separated by a `/`.

#### 2. Modify a preset

Simply press <kbd>⌘</kbd><kbd>⏎</kbd> to enter in the modified mode. Press <kbd>⏎</kbd> to edit the `title/subtitle` or the `value`.

![preset_modify](public/preset_modify.webp)

#### 3. Apply a preset

Simply press <kbd>⏎</kbd> on a preset to apply its value to the search workflow.

![preset_entry](public/preset_entry.webp)

### Plex Help : Workflow configuration + filter & sort options

You can manage workflow cache, data and edit filter alias.

![plex_help](public/plex_help.webp)

Filters, fields and sorts options are generated based on your libraries metadata. This will vary regarding your medias and agents used to gather information. 

#### 1. Filters

> Filters can be aliased, see section `4. Aliases` below

Plex filters can be applied by typing `filterName=value`. Use `/` to separate them. Find the list of filters under each library sections of your servers.

Example: `libtype=movie/actor=adam driver`. It returns `movies` with `Adam Driver`.

![filters_full_2](public/filters_full_2.webp)

#### 2. Fields (advanced filters)

Plex fields (or advanced filters) can be applied by typing `advancedFilters={<FILTER>}` (or `af={<FILTER>}` in `alias mode`). There is certain conditions you have to respect to make advance filters working:

* Use `/` to separate advanced filter from other filters.
* You must use them along with a `libtype`.
* You must provide a valid Python *dict* or valid *JSON* syntax. Double quotes `"` and single quotes `'` are valid.

To know more on how to use these filters, check the [Python-PlexAPI documentation](https://python-plexapi.readthedocs.io/en/latest/modules/library.html#plexapi.library.LibrarySection.search).

Find the list of fields under each library sections of your servers.

Example:  `libtype=episode/advancedFilters={'show.title': 'one piece', 'episode.index': '1074'}`. It returns `episodes` where `episode number` is `1074` and the title of the show contains `one piece`.

![advanced_filters](public/advanced_filters.webp)

#### 3. Sorts

You can sort results by typing `sort=sortName:dir` (or `so=sortName:dir` in `alias mode`). Direction can be `:asc` for ascending or `:desc` for descending.

Example: `libtype=movie/sort=originallyAvailableAt:desc`. This will display `movies` from the `most recent` to the `older` one.

![sorts](public/sorts.webp)

#### 4. Alias

Aliases are enabled by default, and allows you, when activated, to write filters more easily. `libtype` becomes `lt`, `studio` becomes `st`...

You can disable this behavior in the user control panel by unticking the `📜 Use alias` parameter.

Aliases file can be edited, but be careful about double values. It is the `aliases.json` file located under the `📁 Data folder` (`~/Library/Application Support/Alfred/Workflow Data/com.benjamino.plex` by default).

Example: `af={'addedAt>>': '30d'}/lt=show`. It returns `shows` added or `shows` containing new elements (seasons, epidodes) in plex during the last `30 days`.

![aliases](public/aliases.webp)

## ⚖️ License

[MIT License](LICENSE) © Benjamin Oddou
