import logging

import pytest

import pyridy
from pyridy.processing import PostProcessor


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_post_processor(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_files("files/sqlite/sample2.sqlite", sync_method="ntp_time")

    proc = PostProcessor(my_campaign, method="acc", thres_lo=0.3, thres_hi=0.4, v_thres=1, sampling_period="100ms")
    assert not proc.trk_conds[0].empty


def test_create_map(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_files("files/sqlite/sample2.sqlite", sync_method="ntp_time")

    proc = PostProcessor(my_campaign, method="acc", thres_lo=0.3, thres_hi=0.4, v_thres=1, sampling_period="100ms")
    m = proc.create_map(hide_good_sections=True)
    assert m is not None
