import itertools
import logging
from datetime import timedelta
from typing import Union

import numpy as np
import pandas as pd
from scipy import signal, integrate
from shapely.geometry import Point
from tqdm.auto import tqdm

from pyridy import Campaign, config
from pyridy.file import RDYFile
from pyridy.osm.utils import convert_way_to_line_string, OSMResultNode
from pyridy.processing import PostProcessor
from pyridy.utils import LinearAccelerationSeries, GPSSeries
from pyridy.widgets import Map

logger = logging.getLogger(__name__)


class ExcitationProcessor(PostProcessor):
    def __init__(self, campaign: Campaign, f_s: int = 200, f_c: float = 1, order: int = 4,
                 p_thres: float = .025, p_dist: int = 50, osm_integration=True):
        """
        The ExcitationProcessor performs a double integration of the acceleration data to calculate
        excitations. High-Pass Filters are applied to remove static offset and drift. Hence, the resulting
        excitations only represent high-frequent excitations but no quasi-static movements

        Parameters
        ----------
        campaign: Campaign
            The measurement campaign on which the ExcitationProcessor should be applied. Results are saved directly
            in the campaign.
        f_s: int, default: 200
            Sampling frequency to be used.
        f_c: float, default: 1
            Cut-Off frequency for the high-pass filter
        order: int, default: 4
            Order of the high-pass filter
        p_thres: float, default .025
        p_dist: int, default 50
        osm_integration: bool, default True
        """
        super(ExcitationProcessor, self).__init__(campaign)
        self.f_s = f_s
        self.f_c = f_c
        self.order = order

        self.p_thres = p_thres
        self.p_dist = p_dist
        self.osm_integration = osm_integration

        # self.b, self.a = signal.butter(self.order, self.f_c, 'high', analog=True)  # High Pass (2*f_c/f_s)
        # self.z, self.p = signal.bilinear(self.b, self.a, fs=self.f_s)
        self.fir_bp = signal.firwin(4001, [.5, 50], pass_zero=False, fs=200)

    def execute(self, axes: Union[str, list] = "z", intp_gps: bool = True, reset: bool = False):
        """
        Executes the processor on the given axes

        Parameters
        ----------
        axes: Union[str, list], default: "z"
            Axes to which processor should be applied to. Can be a single axis or a list of axes
        intp_gps: bool, default: True
            If true interpolates the GPS measurements onto the results
        reset: bool
            Resets all result nodes

        Raises
        -------
        ValueError: Raised if axes are not of type list or str, or not in the format 'x', 'y' or 'z'
        """
        if type(axes) == str:
            if axes not in ["x", "y", "z"]:
                raise ValueError("axes must be 'x', 'y' or 'z', or list of these values")
            else:
                axes = [axes]
        elif type(axes) == list:
            for ax in axes:
                if ax not in ["x", "y", "z"]:
                    raise ValueError("axes must be 'x', 'y' or 'z', or list of these values")
        else:
            raise ValueError("axes must be list or str")

        if reset and self.campaign.osm:
            self.campaign.osm.reset_way_attributes()

        f: RDYFile
        for f in tqdm(self.campaign):
            if len(f.measurements[LinearAccelerationSeries]) == 0:
                logger.warning("({}) LinearAccelerationSeries is empty, can't execute ExcitationProcessor "
                               "on this file".format(f.filename))
                continue
            else:
                lin_acc_df = f.measurements[LinearAccelerationSeries].to_df()

                if len(f.measurements[GPSSeries]) > 0:
                    gps_df = f.measurements[GPSSeries].to_df()
                    df = pd.concat([lin_acc_df, gps_df]).sort_index()
                else:
                    logger.warning(
                        "(%s) GPSSeries is empty, can't interpolate GPS values onto results" % f.filename)
                    df = lin_acc_df

                df = df.resample(timedelta(seconds=1 / self.f_s)).mean().interpolate()
                t = (df.index.values - df.index.values[0]) / np.timedelta64(1, "s")

                for ax in axes:
                    if ax == "x":
                        lin_acc = df.lin_acc_x
                    elif ax == "y":
                        lin_acc = df.lin_acc_y
                    elif ax == "z":
                        lin_acc = df.lin_acc_x
                    else:
                        raise ValueError("axes must be 'x', 'y' or 'z', or list of these values")

                    # High pass filter first to remove static offset
                    lin_acc_hp = signal.filtfilt(self.fir_bp, 1, lin_acc)

                    lin_v = integrate.cumtrapz(lin_acc_hp, t, initial=0)
                    lin_v_hp = signal.filtfilt(self.fir_bp, 1, lin_v)
                    df["lin_v_" + ax] = lin_v_hp

                    lin_s = integrate.cumtrapz(lin_v_hp, t, initial=0)
                    lin_s_hp = signal.filtfilt(self.fir_bp, 1, lin_s)
                    df["lin_s_" + ax] = lin_s_hp

                    # Peak nodes for OSM
                    if self.osm_integration and len(f.measurements[GPSSeries]) > 0:
                        if self.campaign.osm:
                            lin_s_abs = np.abs(lin_s_hp)

                            p_idxs, prop = signal.find_peaks(lin_s_hp, height=self.p_thres, distance=self.p_dist)
                            peaks = lin_s_abs[p_idxs]
                            lons, lats = df.lon[p_idxs], df.lat[p_idxs]
                            xs, ys = config.proj(lons, lats)
                            if f.matched_line:
                                trk = f.matched_line.tracks[0]
                                way_lines = [convert_way_to_line_string(w, frmt="x,y") for w in trk.ways]
                                for i, coord in enumerate(zip(xs, ys)):
                                    p = Point(*coord)

                                    # Get the closest way to point
                                    dists = [line.distance(p) for line in way_lines]
                                    min_d = min(dists)
                                    if min_d <= config.options["RESULT_MATCHING_MAX_DISTANCE"]:
                                        line = way_lines[dists.index(min_d)]
                                        way = trk.ways[dists.index(min_d)]
                                        pp = line.interpolate(line.project(p))  # Projection of GPS point to OSM line
                                        lon, lat = config.proj(pp.x, pp.y, inverse=True)
                                        r_node = OSMResultNode(lon, lat, peaks[i], f, proc=self, direction=ax)
                                        if "results" not in way.attributes:
                                            way.attributes["results"] = [r_node]
                                        else:
                                            way.attributes["results"].append(r_node)

                        else:
                            logger.warning("(%s) Campaign contains no OSM data, can't integrate results" % f.filename)

                if ExcitationProcessor not in self.campaign.results:
                    self.campaign.results[ExcitationProcessor] = {f.filename: df}
                else:
                    self.campaign.results[ExcitationProcessor][f.filename] = df

        params = self.__dict__.copy()
        params.pop("campaign")
        if ExcitationProcessor not in self.campaign.results:
            self.campaign.results[ExcitationProcessor] = {"params": params}
        else:
            self.campaign.results[ExcitationProcessor]["params"] = params

    def create_map(self, use_file_color=False) -> Map:
        """
        Creates a pyridy.widgets Map showing the GPS tracks of measurement files and adds the nodes to the map.

        Parameters
        ----------
        use_file_color: bool
        Defaults to False.

        Returns
        -------
        m: pyridy.widgets Map
        """
        m = self.campaign.create_map(show_gps_tracks=True, show_railway_elements=False)
        m.add_results_from_campaign(self.campaign, use_file_color=use_file_color)
        return m
