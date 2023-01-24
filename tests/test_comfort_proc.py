import logging

import numpy as np
import pytest
from matplotlib import pyplot as plt

import pyridy
from pyridy.processing import ComfortProcessor
from scipy import signal


@pytest.fixture
def my_campaign():
    return pyridy.Campaign()


def test_comfort_proc_execution(caplog, my_campaign):
    caplog.set_level(logging.DEBUG)
    my_campaign.import_folder("files/sqlite/osm_mapping_test",
                              download_osm_data=False,
                              railway_types=["tram"],
                              osm_recurse_type="<")
    ComfortProcessor(my_campaign, v_thres=10/3.6).execute()

    t = my_campaign.results[ComfortProcessor]['osm_mapping_test.sqlite']['t']
    cc_x = my_campaign.results[ComfortProcessor]['osm_mapping_test.sqlite']['cc_x']
    cc_y = my_campaign.results[ComfortProcessor]['osm_mapping_test.sqlite']['cc_y']
    cc_z = my_campaign.results[ComfortProcessor]['osm_mapping_test.sqlite']['cc_z']
    n_mv = my_campaign.results[ComfortProcessor]['osm_mapping_test.sqlite']['n_mv']

    # fig, ax = plt.subplots(1, 1)
    #
    # ax.plot(t, cc_x, label='x')
    # ax.plot(t, cc_y, label='y')
    # ax.plot(t, cc_z, label='z')
    # ax.grid()
    # ax.legend()
    # plt.show()
    assert True


def test_filters(my_campaign, caplog):
    caplog.set_level(logging.DEBUG)
    fs = 400

    Wb = ComfortProcessor.Wb(fs)
    Wd = ComfortProcessor.Wd(fs)
    Wc = ComfortProcessor.Wc(fs)
    Wp = ComfortProcessor.Wp(fs)

    freq_b, resp_b = signal.freqz(Wb[0], Wb[1], worN=1024)
    angles_b = np.unwrap(np.angle(resp_b))

    freq_d, resp_d = signal.freqz(Wd[0], Wd[1], worN=1024)
    angles_d = np.unwrap(np.angle(resp_d))

    freq_c, resp_c = signal.freqz(Wc[0], Wc[1], worN=1024)
    angles_c = np.unwrap(np.angle(resp_c))

    freq_p, resp_p = signal.freqz(Wp[0], Wp[1], worN=1024)
    angles_p = np.unwrap(np.angle(resp_p))

    # Wb and Wd
    fig, axes = plt.subplots(2, 2, figsize=(9, 6))
    plt.subplots_adjust(hspace=0.5)

    axes[0, 0].loglog(freq_b * fs / (2 * np.pi), abs(resp_b))
    axes[0, 0].set_xlim(0.1, 100)
    axes[0, 0].set_ylim(1e-2, 2)
    axes[0, 0].set_xlabel("Frequency [Hz]")
    axes[0, 0].set_ylabel("Magnitude [-]")
    axes[0, 0].set_title('Magnitude Response W_b')
    axes[0, 0].grid(which='both', linestyle='-', linewidth=0.5)

    axes[1, 0].semilogx(freq_b * fs / (2 * np.pi), angles_b * 180 / np.pi)
    axes[1, 0].set_xlim(0.1, 100)
    axes[1, 0].set_xlabel("Frequency [Hz]")
    axes[1, 0].set_ylabel("Phase [°]")
    axes[1, 0].set_title('Phase Response W_b')
    axes[1, 0].grid(which='both', linestyle='-', linewidth=0.5)

    axes[0, 1].loglog(freq_d * fs / (2 * np.pi), abs(resp_d))
    axes[0, 1].set_xlim(0.1, 100)
    axes[0, 1].set_ylim(1e-2, 2)
    axes[0, 1].set_xlabel("Frequency [Hz]")
    axes[0, 1].set_ylabel("Magnitude [-]")
    axes[0, 1].set_title('Magnitude Response W_d')
    axes[0, 1].grid(which='both', linestyle='-', linewidth=0.5)

    axes[1, 1].semilogx(freq_d * fs / (2 * np.pi), angles_d * 180 / np.pi)
    axes[1, 1].set_xlim(0.1, 100)
    axes[1, 1].set_xlabel("Frequency [Hz]")
    axes[1, 1].set_ylabel("Phase [°]")
    axes[1, 1].set_title('Phase Response W_d')
    axes[1, 1].grid(which='both', linestyle='-', linewidth=0.5)

    plt.show()

    # Wc and Wp
    fig, axes = plt.subplots(2, 2, figsize=(9, 6))
    plt.subplots_adjust(hspace=0.5)

    axes[0, 0].loglog(freq_c * fs / (2 * np.pi), abs(resp_c))
    axes[0, 0].set_xlim(0.1, 100)
    axes[0, 0].set_ylim(1e-2, 2)
    axes[0, 0].set_xlabel("Frequency [Hz]")
    axes[0, 0].set_ylabel("Magnitude [-]")
    axes[0, 0].set_title('Magnitude Response W_c')
    axes[0, 0].grid(which='both', linestyle='-', linewidth=0.5)

    axes[1, 0].semilogx(freq_c * fs / (2 * np.pi), angles_c * 180 / np.pi)
    axes[1, 0].set_xlim(0.1, 100)
    axes[1, 0].set_xlabel("Frequency [Hz]")
    axes[1, 0].set_ylabel("Phase [°]")
    axes[1, 0].set_title('Phase Response W_c')
    axes[1, 0].grid(which='both', linestyle='-', linewidth=0.5)

    axes[0, 1].loglog(freq_p * fs / (2 * np.pi), abs(resp_p))
    axes[0, 1].set_xlim(0.1, 100)
    axes[0, 1].set_ylim(1e-2, 2)
    axes[0, 1].set_xlabel("Frequency [Hz]")
    axes[0, 1].set_ylabel("Magnitude [-]")
    axes[0, 1].set_title('Magnitude Response W_p')
    axes[0, 1].grid(which='both', linestyle='-', linewidth=0.5)

    axes[1, 1].semilogx(freq_p * fs / (2 * np.pi), angles_p * 180 / np.pi)
    axes[1, 1].set_xlim(0.1, 100)
    axes[1, 1].set_xlabel("Frequency [Hz]")
    axes[1, 1].set_ylabel("Phase [°]")
    axes[1, 1].set_title('Phase Response W_p')
    axes[1, 1].grid(which='both', linestyle='-', linewidth=0.5)

    plt.show()

    # Compare plots to EN 12299
    assert True
