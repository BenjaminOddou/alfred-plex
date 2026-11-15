"""Test doubles.

* :class:`FakeSession` replaces ``requests.Session``: real plexapi objects are
  built from real Plex XML, without any network access.
* :class:`FakeAccount` replaces ``MyPlexAccount`` (plex.tv).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

MID = "mid-home"
BASE_URL = "http://192.168.1.10:32400"
TOKEN = "server-token"
ACCOUNT_UUID = "acc-uuid-1"
ACCOUNT_TOKEN = "account-token"

IDENTITY = f'<MediaContainer friendlyName="Home Server" machineIdentifier="{MID}" version="1.41.2.1" myPlex="1"/>'

SECTIONS = """<MediaContainer size="3">
  <Directory key="1" type="movie" title="Movies" agent="tv.plex.agents.movie" scanner="Plex Movie"
             refreshing="0" updatedAt="1700000000" uuid="s1"/>
  <Directory key="2" type="show" title="TV Shows" agent="tv.plex.agents.series" scanner="Plex TV Series"
             refreshing="1" updatedAt="1710000000" uuid="s2"/>
  <Directory key="3" type="artist" title="Music" agent="tv.plex.agents.music" scanner="Plex Music"
             refreshing="0" updatedAt="1690000000" uuid="s3"/>
</MediaContainer>"""

MATRIX = """<Video ratingKey="10" key="/library/metadata/10" guid="plex://movie/5d7768" type="movie"
       title="The Matrix" librarySectionID="1" librarySectionTitle="Movies" year="1999" duration="8160000"
       studio="Warner Bros." thumb="/library/metadata/10/thumb/1">
  <Media id="100"><Part id="1000" key="/library/parts/1000/1/file.mkv" size="1000"/></Media>
  <Director tag="Lana Wachowski"/><Director tag="Lilly Wachowski"/>
  <Guid id="imdb://tt0133093"/><Guid id="tmdb://603"/>
</Video>"""

INCEPTION = """<Video ratingKey="11" key="/library/metadata/11" guid="plex://movie/inception" type="movie"
       title="Inception" librarySectionID="1" year="2010" duration="8880000" studio="Legendary">
  <Media id="110"><Part id="1100" key="/library/parts/1100/1/a.mkv" size="2000"/></Media>
  <Media id="111"><Part id="1110" key="/library/parts/1110/1/b.mkv" size="9000"/></Media>
</Video>"""

THEME = """<Track ratingKey="30" key="/library/metadata/30" guid="plex://track/theme" type="track"
       title="Matrix Theme" grandparentTitle="Don Davis" parentTitle="The Matrix OST" index="1"
       duration="200000" parentKey="/library/metadata/29" grandparentKey="/library/metadata/28">
  <Media id="300"><Part id="3000" key="/library/parts/3000/1/theme.flac"/></Media>
</Track>"""

ALBUM = """<Directory ratingKey="29" key="/library/metadata/29/children" guid="plex://album/ost" type="album"
       title="The Matrix OST" parentTitle="Don Davis" year="1999" leafCount="12" studio="Varese"/>"""

HUB_SEARCH = f"""<MediaContainer size="3">
  <Hub hubIdentifier="movie" title="Movies" type="movie" size="1">{MATRIX}</Hub>
  <Hub hubIdentifier="album" title="Albums" type="album" size="1">{ALBUM}</Hub>
  <Hub hubIdentifier="track" title="Tracks" type="track" size="1">{THEME}</Hub>
  <Hub hubIdentifier="actor" title="Actors" type="actor" size="1">
    <Directory id="77" tag="Keanu Reeves" tagKey="5d776" type="tag" tagType="6"/>
  </Hub>
</MediaContainer>"""

MOVIES = f'<MediaContainer size="2" totalSize="2">{MATRIX}{INCEPTION}</MediaContainer>'
EMPTY = '<MediaContainer size="0" totalSize="0"/>'

MOVIE_META = """<MediaContainer size="0" totalSize="2">
  <Meta>
    <Type key="/library/sections/1/all?type=1" type="movie" title="Movies" active="1">
      <Filter filter="genre" filterType="string" key="/library/sections/1/genre?type=1" title="Genre" type="filter"/>
      <Filter filter="unwatched" filterType="boolean" key="/library/sections/1/unwatched?type=1" title="Unplayed" type="filter"/>
      <Filter filter="resolution" filterType="string" key="/library/sections/1/resolution?type=1" title="Resolution" type="filter"/>
      <Filter filter="hdr" filterType="boolean" key="/library/sections/1/hdr?type=1" title="HDR" type="filter"/>
      <Sort defaultDirection="desc" descKey="originallyAvailableAt:desc" key="originallyAvailableAt" title="Release Date"/>
      <Sort defaultDirection="asc" descKey="titleSort:desc" key="titleSort" title="Title"/>
      <Sort defaultDirection="desc" descKey="addedAt:desc" key="addedAt" title="Date Added"/>
      <Field key="title" title="Title" type="string"/>
      <Field key="year" title="Year" type="integer"/>
      <Field key="resolution" title="Resolution" type="resolution"/>
      <Field key="hdr" title="HDR" type="boolean"/>
      <Field key="genre" title="Genre" type="tag"/>
      <Field key="unwatched" title="Unplayed" type="boolean"/>
    </Type>
    <FieldType type="string"><Operator key="=" title="contains"/><Operator key="==" title="is"/></FieldType>
    <FieldType type="integer"><Operator key="=" title="is"/><Operator key="&gt;&gt;=" title="is greater than"/></FieldType>
    <FieldType type="tag"><Operator key="=" title="is"/><Operator key="!=" title="is not"/></FieldType>
    <FieldType type="resolution"><Operator key="=" title="is"/><Operator key="!=" title="is not"/></FieldType>
    <FieldType type="boolean"><Operator key="=" title="is true"/><Operator key="!=" title="is false"/></FieldType>
  </Meta>
</MediaContainer>"""

COLLECTIONS_META = """<MediaContainer size="0"><Meta>
  <Type key="/library/sections/1/collections" type="collection" title="Collections" active="0"/>
</Meta></MediaContainer>"""

GENRES = """<MediaContainer size="2">
  <Directory fastKey="/library/sections/1/all?genre=12" key="12" title="Action" type="genre"/>
  <Directory fastKey="/library/sections/1/all?genre=13" key="13" title="Science Fiction" type="genre"/>
</MediaContainer>"""

STREAMS = """<MediaContainer size="1">
<Video ratingKey="11" key="/library/metadata/11" guid="plex://movie/inception" type="movie" title="Inception" year="2010">
  <Media id="110"><Part id="1100" key="/library/parts/1100/1/a.mkv" size="2000">
    <Stream id="1" streamType="1" displayTitle="1080p (HEVC Main 10)"/>
    <Stream id="2" streamType="2" displayTitle="English (AAC Stereo)"/>
    <Stream id="3" streamType="3" displayTitle="French (SRT)"/>
  </Part></Media>
  <Media id="111"><Part id="1110" key="/library/parts/1110/1/b.mkv" size="9000">
    <Stream id="4" streamType="1" displayTitle="4K (HEVC Main 10 HDR)"/>
    <Stream id="5" streamType="2" displayTitle="English (TrueHD 7.1)"/>
  </Part></Media>
</Video></MediaContainer>"""

SESSIONS = """<MediaContainer size="1">
<Video ratingKey="10" key="/library/metadata/10" type="movie" title="The Matrix" year="1999" sessionKey="42"
       viewOffset="600000">
  <User id="1" title="neo" thumb="https://img/neo.png"/>
  <Player machineIdentifier="tv-1" product="Plex for LG" device="OLED" platform="webOS" state="playing"/>
  <Session id="abc123" bandwidth="1000" location="lan"/>
</Video></MediaContainer>"""

PREFS = """<MediaContainer size="3">
  <Setting id="FriendlyName" label="Friendly name" summary="Name of the server" type="text" default=""
           value="Home Server" hidden="0" advanced="0" group="general"/>
  <Setting id="LogVerbose" label="Verbose logging" summary="" type="bool" default="false" value="false"
           hidden="0" advanced="0" group="general"/>
  <Setting id="HiddenOne" label="Hidden" summary="" type="int" default="1" value="1" hidden="1"
           advanced="0" group="general"/>
</MediaContainer>"""

HISTORY = """<MediaContainer size="2">
  <Video historyKey="/status/sessions/history/1" ratingKey="10" key="/library/metadata/10" title="The Matrix"
         type="movie" year="1999" viewedAt="1731600000" accountID="1" deviceID="5" librarySectionID="1"/>
  <Video historyKey="/status/sessions/history/2" ratingKey="99" key="/library/metadata/99" title="Pilot"
         grandparentTitle="Lost" type="episode" index="1" parentIndex="1" viewedAt="1731500000"
         accountID="1" deviceID="9" librarySectionID="8"/>
</MediaContainer>"""

MATRIX_FULL = """<MediaContainer size="1">
<Video ratingKey="10" key="/library/metadata/10" guid="plex://movie/5d7768" type="movie" title="The Matrix"
       librarySectionID="1" librarySectionTitle="Movies" year="1999" duration="8160000" studio="Warner Bros."
       viewCount="1" userRating="8" audienceRating="8.5" contentRating="R" addedAt="1700000000"
       summary="A hacker learns the truth." thumb="/library/metadata/10/thumb/1" tagline="Welcome to the Real World"
       originallyAvailableAt="1999-03-31" audienceRatingImage="rottentomatoes://image.rating.upright">
  <Media id="100" videoResolution="1080" videoCodec="hevc" audioCodec="aac" container="mkv" bitrate="8000">
    <Part id="1000" key="/library/parts/1000/1/file.mkv" file="/movies/The Matrix (1999).mkv" size="8000000000"
          container="mkv">
      <Stream id="1" streamType="1" displayTitle="1080p (HEVC Main 10)"/>
      <Stream id="2" streamType="2" displayTitle="English (AAC 5.1)"/>
      <Stream id="3" streamType="3" displayTitle="French (SRT)"/>
    </Part>
  </Media>
  <Genre tag="Action"/><Genre tag="Science Fiction"/>
  <Director tag="Lana Wachowski"/><Writer tag="Lilly Wachowski"/><Country tag="United States of America"/>
  <Role tag="Keanu Reeves" role="Neo"/><Role tag="Carrie-Anne Moss" role="Trinity"/>
  <Collection tag="Keanu"/>
  <Guid id="tmdb://603"/>
</Video></MediaContainer>"""

SHOW = """<MediaContainer size="1">
<Directory ratingKey="20" key="/library/metadata/20/children" guid="plex://show/dark" type="show" title="Dark"
           year="2017" childCount="3" leafCount="26" viewedLeafCount="26" contentRating="TV-MA"
           thumb="/library/metadata/20/thumb/5" librarySectionID="2"/>
</MediaContainer>"""

SEASONS = """<MediaContainer size="2">
<Directory ratingKey="21" key="/library/metadata/21/children" parentRatingKey="20" type="season" title="Season 1"
           parentTitle="Dark" index="1" leafCount="10" thumb="/library/metadata/21/thumb/6"/>
<Directory ratingKey="22" key="/library/metadata/22/children" parentRatingKey="20" type="season" title="Season 2"
           parentTitle="Dark" index="2" leafCount="8" thumb="/library/metadata/22/thumb/7"/>
</MediaContainer>"""

COLLECTIONS = """<MediaContainer size="2">
  <Directory ratingKey="700" key="/library/collections/700/children" type="collection" title="Keanu" childCount="4"/>
  <Directory ratingKey="701" key="/library/collections/701/children" type="collection" title="Classics" childCount="9"/>
</MediaContainer>"""

PLAYLISTS = """<MediaContainer size="2">
  <Playlist ratingKey="500" key="/playlists/500/items" type="playlist" title="Favorites" playlistType="video"
            smart="0" leafCount="3"/>
  <Playlist ratingKey="501" key="/playlists/501/items" type="playlist" title="Smart one" playlistType="video"
            smart="1" leafCount="9"/>
</MediaContainer>"""

RESOLUTIONS = """<MediaContainer size="2">
  <Directory key="4k" title="4K" type="resolution"/>
  <Directory key="1080" title="1080p" type="resolution"/>
</MediaContainer>"""

PROVIDERS = """<MediaContainer size="1"><MediaProvider identifier="com.plexapp.plugins.library">
  <Feature type="content">
    <Directory id="1" durationTotal="36000000" storageTotal="50000000000"/>
    <Directory id="2" durationTotal="72000000" storageTotal="90000000000"/>
  </Feature>
</MediaProvider></MediaContainer>"""

BANDWIDTH = """<MediaContainer size="3">
  <StatisticsBandwidth accountID="1" deviceID="5" timespan="3" at="1731600000" lan="1" bytes="1048576"/>
  <StatisticsBandwidth accountID="1" deviceID="9" timespan="3" at="1731600000" lan="0" bytes="3145728"/>
  <StatisticsBandwidth accountID="1" deviceID="5" timespan="3" at="1731513600" lan="1" bytes="1048576"/>
</MediaContainer>"""

RESOURCES = """<MediaContainer size="1">
  <StatisticsResources at="1731600000" hostCpuUtilization="12.5" hostMemoryUtilization="40"
                       processCpuUtilization="3" processMemoryUtilization="5" timespan="6"/>
</MediaContainer>"""

BUTLER = """<ButlerTasks>
  <ButlerTask name="BackupDatabase" title="Backup Database" description="Create a backup" interval="3" enabled="1"
              scheduleRandomized="0"/>
</ButlerTasks>"""

ACTIVITIES = """<MediaContainer size="1">
  <Activity uuid="a1" type="library.update.section" cancellable="0" userID="1" title="Scanning Movies"
            subtitle="The Matrix" progress="42"/>
</MediaContainer>"""

ACCOUNTS = '<MediaContainer size="1"><Account id="1" name="neo" key="/accounts/1"/></MediaContainer>'
DEVICES = '<MediaContainer size="1"><Device id="5" name="Living room TV" platform="webOS"/></MediaContainer>'


def default_routes() -> dict:
    def section_all(query: dict) -> str:
        if query.get("includeMeta"):
            return MOVIE_META
        if query.get("type") == "18":
            return COLLECTIONS
        return MOVIES

    return {
        "/": IDENTITY,
        "/library": '<MediaContainer identifier="com.plexapp.plugins.library" title1="Plex Library"/>',
        "/library/sections": SECTIONS,
        "/library/sections/1/all": section_all,
        "/library/sections/1/collections": COLLECTIONS_META,
        "/library/sections/2/all": EMPTY,
        "/library/sections/3/all": EMPTY,
        "/library/sections/1/genre": GENRES,
        "/library/all": lambda q: MOVIES if q.get("guid") == "plex://movie/5d7768" else EMPTY,
        "/hubs/search": HUB_SEARCH,
        "/library/metadata/11": STREAMS,
        "/status/sessions": SESSIONS,
        "/status/sessions/terminate": EMPTY,
        "/:/prefs": PREFS,
        "/updater/status": EMPTY,
        "/status/sessions/history/all": HISTORY,
        "/accounts": ACCOUNTS,
        "/devices": DEVICES,
        "/library/sections/1/refresh": EMPTY,
        "/library/sections/1/resolution": RESOLUTIONS,
        "/library/sections/1/analyze": EMPTY,
        "/library/sections/1/emptyTrash": EMPTY,
        "/library/metadata/10": MATRIX_FULL,
        "/library/metadata/10/refresh": EMPTY,
        "/library/metadata/10/analyze": EMPTY,
        "/library/recentlyAdded": MOVIES,
        "/hubs/continueWatching/items": f'<MediaContainer size="1">{INCEPTION}</MediaContainer>',
        "/playlists": PLAYLISTS,
        "/playlists/500": PLAYLISTS,
        "/playlists/500/items": EMPTY,
        "/media/providers": PROVIDERS,
        "/statistics/bandwidth": BANDWIDTH,
        "/statistics/resources": RESOURCES,
        "/butler": BUTLER,
        "/butler/BackupDatabase": EMPTY,
        "/activities": ACTIVITIES,
        "/:/scrobble": EMPTY,
        "/:/unscrobble": EMPTY,
        "/:/rate": EMPTY,
        "/library/clean/bundles": EMPTY,
        "/photo/:/transcode": "JPEG-BYTES",
        "/library/metadata/20": SHOW,
        "/library/metadata/20/children": SEASONS,
        "/library/optimize": EMPTY,
    }


class FakeResponse:
    def __init__(self, url: str, text: str, status: int = 200, content_type: str = "text/xml;charset=utf-8"):
        self.url = url
        self.text = text
        self.content = text.encode()
        self.status_code = status
        self.headers = {"Content-Type": content_type}

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self):
        return json.loads(self.text)


class FakeSession:
    """Answer plexapi requests from a ``{path: xml | callable(query) -> xml}`` table."""

    def __init__(self, routes: dict | None = None) -> None:
        self.routes = default_routes() if routes is None else routes
        self.calls: list[tuple[str, str, dict]] = []
        self._lock = threading.Lock()

    def _request(self, method: str, url: str, params=None, **_):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        query.update({k: str(v) for k, v in (params or {}).items()})
        with self._lock:
            self.calls.append((method, parts.path, query))
        handler = self.routes.get(parts.path)
        if handler is None:
            return FakeResponse(url, "Not Found", 404)
        return FakeResponse(url, handler(query) if callable(handler) else handler)

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def put(self, url, **kwargs):
        return self._request("PUT", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._request("DELETE", url, **kwargs)

    def paths(self) -> list[str]:
        return [path for _, path, _ in self.calls]


class FakeDevice(SimpleNamespace):
    deleted = False

    def delete(self):
        self.deleted = True


class FakeAccount:
    """Minimal stand-in for ``plexapi.myplex.MyPlexAccount``."""

    DISCOVER = "https://discover.provider.plex.tv"
    METADATA = "https://metadata.provider.plex.tv"

    def __init__(self, uuid: str = ACCOUNT_UUID, token: str = ACCOUNT_TOKEN) -> None:
        self.uuid = uuid
        self.authToken = token
        self.title = self.friendlyName = self.username = "neo"
        self.email = "neo@example.com"
        self.subscriptionActive = True
        self.subscriptionDescription = "Lifetime"
        self.watchlist_items = [
            SimpleNamespace(guid="plex://movie/5d7768", title="The Matrix", type="movie", year=1999,
                            duration=8160000, childCount=None, thumb="https://img/w1.jpg", contentRating="R"),
        ]
        self.thumb = "https://img/neo.png"
        self._session = FakeSession({"/w1.jpg": "WATCHLIST-POSTER", "/1.jpg": "DISCOVER-POSTER",
                                     "/neo.png": "\x89PNG-NEO", "/trinity.png": "\x89PNG-TRINITY"})
        self.added: list[str] = []
        self.removed: list[str] = []
        self.queries: list[tuple[str, dict]] = []
        self.discover_payload: dict = {"MediaContainer": {}}
        now = datetime.now()
        common = {"createdAt": now - timedelta(days=400), "publicAddress": "", "productVersion": "1.0",
                  "model": "", "vendor": "", "screenResolution": ""}
        self.devices_list = [
            FakeDevice(name="Alfred Plex", platform="macOS", platformVersion="15.1", product="Alfred Workflow",
                       device="OSX", clientIdentifier="dev-1", token=token, provides="controller",
                       lastSeenAt=now - timedelta(days=500), **common),
            FakeDevice(name="iPhone", platform="iOS", platformVersion="18.0", product="Plex for iOS",
                       device="iPhone", clientIdentifier="dev-2", token="other", provides="client,player",
                       lastSeenAt=now - timedelta(days=2), **common),
            FakeDevice(name="Old iPad", platform="iOS", platformVersion="12.0", product="Plex for iOS",
                       device="iPad", clientIdentifier="dev-3", token="old", provides="client,player",
                       lastSeenAt=now - timedelta(days=200), **common),
            FakeDevice(name="NAS", platform="Linux", platformVersion="5.10", product="Plex Media Server",
                       device="NAS", clientIdentifier="dev-4", token="nas", provides="server",
                       lastSeenAt=now - timedelta(days=300), **common),
        ]
        self.resources_list: list = []

    def watchlist(self, **_):
        return list(self.watchlist_items)

    def addToWatchlist(self, item):
        self.added.append(item.guid)

    def removeFromWatchlist(self, item):
        self.removed.append(item.guid)

    def devices(self):
        return list(self.devices_list)

    def device(self, name=None, clientId=None):
        return next(d for d in self.devices_list if d.clientIdentifier == clientId)

    def resources(self):
        return list(self.resources_list)

    def users(self):
        server = SimpleNamespace(numLibraries=3, name="Home Server")
        return [SimpleNamespace(title="trinity", username="trinity", email="trinity@example.com", home=False,
                                restricted=False, servers=[server, server], id=2,
                                thumb="https://img/trinity.png")]

    def query(self, url, method=None, headers=None, params=None, **_):
        self.queries.append((url, dict(params or {})))
        if url.startswith(self.METADATA):
            from xml.etree import ElementTree

            return ElementTree.fromstring(
                '<MediaContainer><Video><Guid id="imdb://tt1375666"/><Guid id="tmdb://27205"/></Video></MediaContainer>'
            )
        return self.discover_payload


def discover_search_payload() -> dict:
    return {"MediaContainer": {"SearchResults": [
        {"id": "external", "SearchResult": [
            {"Metadata": {"type": "movie", "title": "The Matrix", "year": 1999, "duration": 8160000,
                          "guid": "plex://movie/5d7768", "ratingKey": "5d7768", "thumb": "https://img/1.jpg"}},
            {"Metadata": {"type": "show", "title": "Dark", "year": 2017, "childCount": 3,
                          "guid": "plex://show/dark", "ratingKey": "dark"}},
        ]},
        {"id": "people", "SearchResult": [
            {"Directory": {"type": "person", "title": "Keanu Reeves", "id": "keanu", "ratingKey": "keanu"}},
        ]},
        {"id": "plex", "SearchResult": [{"Metadata": {"type": "movie", "title": "Ignored"}}]},
    ]}}
