import io
import itertools
import logging
from typing import Tuple, List, Union, Optional

from ipyleaflet import Map as LeafletMap, ScaleControl, FullScreenControl, Polyline, Icon, Marker, GeoData, \
    LayersControl, basemaps, basemap_to_tiles, Circle, LayerGroup
from ipywidgets import HTML

from pyridy.file import RDYFile
from pyridy.osm.utils.elements import OSMRailwaySignal, OSMRailwaySwitch, OSMLevelCrossing, OSMResultNode, OSMRailwayElement
from pyridy.utils import GPSSeries
from pyridy import config

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pyridy.campaign import Campaign


logger = logging.getLogger(__name__)


class Map(LeafletMap):
    """
    extends the map widget from ipyleaflet with functions to populate the map with campaign data
    """

    def __init__(self, **kwargs):
        defaults = dict(
            zoom=12,
            scroll_wheel_zoom=True,
            basemap=config.OPEN_STREET_MAP_DE,
        )
        super().__init__(**(defaults | kwargs))
        self._set_up_controls()
        self._add_tile_layers()

    def refresh_controls(self):
        """
        The controls refresh themselves automatically; no need to do this manually
        Returns
        -------

        """
        pass

    def _set_up_controls(self):
        self.add(ScaleControl(position='bottomleft'))
        self.add(FullScreenControl())
        self.add(LayersControl(position='topright'))

    def _add_tile_layers(self):
        self.railwaymap = config.OPEN_RAILWAY_MAP
        self.add(self.railwaymap)
        self.railwaymap.opacity = 0.4
        # noinspection PyUnresolvedReferences
        positron = basemap_to_tiles(basemaps.CartoDB.Positron)
        positron.base = True
        self.add(positron)

    def add_measurements(self, campaign: 'Campaign') -> Union[None, List[LayerGroup]]:
        """ Add all GPS tracks from the campaign files to a Map

        Parameters
        ----------
        campaign: Campaign
            pyridy Campaign

        Returns
        -------
        None

        """
        measurement_layers = []

        for file in campaign.files:
            if len(file.measurements[GPSSeries]) == 0:
                logger.warning(f"Coordinates are empty in file: {file.filename}")
                continue

            track = create_measurement_layer(file)
            self.add(track)
            measurement_layers.append(track)

        return measurement_layers

    def add_measurement(self, file: RDYFile) -> None:
        """ Adds a GPS track from a file to the Map

        Parameters
        ----------
        campaign: Campaign
            pyridy Campaign
        name: str
            Name of the file that should be drawn onto the map
        file: RDYFile
            Alternatively, provide RDYFile that should be drawn on the map

        Returns
        -------
        The measurement layer

        """
        measurement_layer = create_measurement_layer(file)
        measurement_layer.name = file.filename
        self.add(measurement_layer)
        self.refresh_controls()
        return measurement_layer

    def add_osm_routes(self, campaign: 'Campaign') -> Union[None, LayerGroup]:
        """ Adds OSM Routes from the downloaded OSM Region

        Parameters
        ----------
        campaign: Campaign
            pyridy.Campaign

        Returns
        -------
        None

        """
        if campaign.osm:
            railway_lines_layer = LayerGroup()
            railway_lines_layer.name = "Railway Lines"
            for line in campaign.osm.railway_lines:
                line_layer = LayerGroup()
                line_layer.name = line.name
                for track in line.tracks:
                    coords = track.to_ipyleaflet()
                    file_polyline = Polyline(locations=coords, color=line.color, fill=False, weight=4)
                    file_polyline.name = f'Track from {line.name}'
                    file_polyline.popup = HTML(value=line.name)
                    line_layer.add(file_polyline)
                railway_lines_layer.add(line_layer)
            self.add(railway_lines_layer)
            return railway_lines_layer
        else:
            logger.warning("No OSM region downloaded!")
            return None

    def add_osm_railway_elements(self, campaign: 'Campaign') -> LayerGroup:
        """ Draws railway elements using markers on top of a map

        Parameters
        ----------
        campaign: Campaign
            campaign whose railway elements should be drawn

        Returns
        -------
        The Railway Elements LayerGroup

        """
        railway_elements = LayerGroup()
        railway_elements.name = "Railway switches"
        if campaign.osm:
            for el in campaign.osm.railway_elements:
                if type(el) == OSMRailwaySwitch:
                    marker = create_marker((el.lat, el.lon), color="black")
                    railway_elements.add(marker)
                elif type(el) == OSMRailwaySignal:
                    pass
                elif type(el) == OSMLevelCrossing:
                    pass
                else:
                    pass
        return railway_elements

    def add_results(self, nodes: List[OSMResultNode], use_file_color=False):

        circles = []

        logger.debug(f"Add {len(nodes)} results to the map.")

        for n in nodes:
            circle = Circle()
            circle.location = n.lon, n.lat
            circle.radius = 2
            circle.color = n.f.color if use_file_color else n.color
            circle.fill_color = n.f.color if use_file_color else n.color
            circle.weight = 3
            circle.fill_opacity = 0.1
            circles.append(circle)

        l_circles = LayerGroup(layers=circles)
        self.add(l_circles)

        self.refresh_controls()

    def add_results_from_campaign(self, campaign: 'Campaign', use_file_color=False):
        nodes = list(itertools.chain.from_iterable([w.attributes.get("results", []) for w in campaign.osm.ways]))
        self.add_results(nodes, use_file_color=use_file_color)

    def to_html(self) -> str:
        """
        Converts this map to a static html document
        """
        html_buffer = io.StringIO()
        self.save(html_buffer)
        return html_buffer.getvalue()


def create_marker(pos: Tuple[float, float], popup: Union[str, HTML] = None, color: str = "orange"):
    # Add Start/End markers
    icon = Icon(
        icon_url=f'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-{color}.png',
        shadow_url='https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
        icon_size=[25, 41],
        icon_anchor=[12, 41],
        popup_anchor=[1, -34],
        shadow_size=[41, 41])

    marker = Marker(location=pos, draggable=False, icon=icon)

    if popup:
        assert type(popup) in [HTML, str]
        if type(popup) == HTML:
            message = popup
        else:
            message = HTML(value=popup)
        marker.popup = message

    return marker


def create_measurement_layer(file: RDYFile):
    gps_series = file.measurements[GPSSeries]
    coords = gps_series.to_ipyleaflef()

    if not coords:
        logger.warning(f"Coordinates are empty in file: {file.filename}")
        return None

    measurement_layer = LayerGroup()
    measurement_layer.name = file.filename

    file_polyline = Polyline(locations=coords, color=file.color, fill=False, weight=4,
                             dash_array='10, 10')
    file_message = HTML()
    file_message.value = f"<p>{str(file.filename or '')}<br>{str(getattr(file.device, 'manufacturer', ''))}<br>{str(getattr(file.device, 'model', ''))}</p>"
    file_polyline.popup = file_message
    measurement_layer.add(file_polyline)

    # Add Start/End markers
    start_message = HTML()
    end_message = HTML()
    start_message.value = "<p>Start:</p>" + file_message.value
    end_message.value = "<p>End:</p>" + file_message.value

    start_marker = create_marker(tuple(coords[0]), start_message, "green")
    end_marker = create_marker(tuple(coords[-1]), end_message, "red")

    measurement_layer.add(start_marker)
    measurement_layer.add(end_marker)

    return measurement_layer
