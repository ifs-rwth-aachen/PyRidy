import pyproj
from ipyleaflet import Icon, TileLayer


# Projections
proj = pyproj.Proj(proj='utm', zone=32, ellps='WGS84', preserve_units=True)
geod = pyproj.Geod(ellps='WGS84')

# Maps
OPEN_STREET_MAP_DE = TileLayer(
    url='https://{s}.tile.openstreetmap.de/{z}/{x}/{y}.png',
    max_zoom=19,
    name="OpenStreetMap"
)

OPEN_STREET_MAP_BW = TileLayer(  # No longer maintained
    url='https://{s}.tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png',
    max_zoom=19,
    name="OpenStreetMap BW"
)

OPEN_RAILWAY_MAP = TileLayer(
    url='https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png',
    max_zoom=19,
    attribution='<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>, Style: <a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA 2.0</a> <a href="http://www.openrailwaymap.org/">OpenRailwayMap</a> and OpenStreetMap',
    name='OpenRailwayMap'
)

# Add Start/End markers
START_ICON = Icon(
    icon_url='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
    shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    icon_size=[25, 41],
    icon_anchor=[12, 41],
    popup_anchor=[1, -34],
    shadow_size=[41, 41])

END_ICON = Icon(
    icon_url='https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
    shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    icon_size=[25, 41],
    icon_anchor=[12, 41],
    popup_anchor=[1, -34],
    shadow_size=[41, 41])

# Options that can be altered by user
options = {
    "OSM_TIMEOUT": 180,
    "OSM_RETRIES": 3,
    "OSM_BOUNDING_BOX_OPTIMIZATION": True,
    "OSM_BOUNDING_BOX_SPLIT_IOU_THRES": .5,
    "OSM_SINGLE_BOUNDING_BOX": False,
    "SOCKET_TIMEOUT": 300,
    "MAP_MATCHING_DEFAULT_ALGORITHM": "nx",
    "MAP_MATCHING_V_THRES": 1.0,
    "MAP_MATCHING_ALPHA": 1.0,
    "MAP_MATCHING_BETA": 1.0,
    "MAP_MATCHING_MIN_LINE_MATCH_RATIO": .2,
    "TRACK_RESOLUTION": .5,
    "RESULT_MATCHING_MAX_DISTANCE": 5
}

# Used colors
colors = []

# Location of the overpass cache (path relative to project root)
OSM_OVERPASS_CACHE = 'overpass_cache'
