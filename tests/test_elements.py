import logging

from pyridy.osm.utils import OSMResultNode


def test_osmresult_node(caplog):
    caplog.set_level(logging.DEBUG)
    n = OSMResultNode(node_id=1, lat=0.0, lon=0.0)
    assert True
