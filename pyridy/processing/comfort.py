import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy import signal
from tqdm.auto import tqdm

from pyridy import Campaign
from pyridy.file import RDYFile
from pyridy.osm.utils import OSMResultNode
from pyridy.processing import PostProcessor
from pyridy.utils import LinearAccelerationSeries, GPSSeries
from pyridy.widgets import Map

logger = logging.getLogger(__name__)


class ComfortProcessor(PostProcessor):
    def __init__(self, campaign: Campaign, f_s: int = 200, v_thres: float = 0, method='EN12299', osm_integration=True):
        """ The Comfort processor can process acceleration data of a campaign according to the EN 12299 standard
        and Wz (Sperling-Index) Method.

        Parameters
        ----------
        campaign: pyridy.Campaign
            An object used to import and evaluate several measurements made using Ridy.
        f_s: int
            Sample rate, as ordinary frequency [Hz]. Defaults to 200.
        v_thres: float
            Threshold velocity. Defaults to 0.
        method: str
            Standard to process acceleration data. Defaults to the EN 12299 standard.

        Raises
        -------
        ValueError: Raised if method is not supported ("EN1299" or "Wz")
        """
        super(ComfortProcessor, self).__init__(campaign)
        self.f_s = f_s
        self.v_thres = v_thres
        self.osm_integration = osm_integration

        if method not in ['EN12299', 'Wz']:
            raise ValueError(f'Method must be "EN1299" or "Wz", not {method}')
        if method == 'Wz':
            raise NotImplementedError('The Wz method has not been implemented yet.')

    @staticmethod
    def calc_comfort_en12999(acc_x: np.ndarray, acc_y: np.ndarray, acc_z: np.ndarray, f_s: int = 200):
        """
        Static method that works purely with numpy arrays for optional use on non campaign like data

        Parameters
        ----------
        acc_x: np.ndarray
            Acceleration according to x-axis.
        acc_y: np.ndarray
            Acceleration according to y-axis.
        acc_z: np.ndarray
            Acceleration according to z-axis.
        f_s: int
            Sample rate, as ordinary frequency [Hz]. Defaults to 200.

        Returns
        -------
        n_mv: ndarray
        t: ndarray
            Array of segment times
        cc_x: ndarray
            Square magnitude of x
        cc_y: ndarray
            Square magnitude of y
        cc_z: ndarray
            Square magnitude of z

        """
        # The evaluation assumes the phone is laying on the floor pointing in the direction of travel
        Wb = ComfortProcessor.Wb(f_s)
        Wd = ComfortProcessor.Wd(f_s)

        a_x_wd = signal.lfilter(Wd[0], Wd[1], acc_x)  # Adjusting to vehicle coordinate system
        a_y_wd = signal.lfilter(Wd[0], Wd[1], acc_y)
        a_z_wb = signal.lfilter(Wb[0], Wb[1], acc_z)

        # Moving RMS over 5s window
        f_x, t, Pa_x = signal.spectrogram(a_x_wd, f_s, nperseg=5 * f_s, noverlap=0, mode='psd')
        f_y, _, Pa_y = signal.spectrogram(a_y_wd, f_s, nperseg=5 * f_s, noverlap=0, mode='psd')
        f_z, _, Pa_z = signal.spectrogram(a_z_wb, f_s, nperseg=5 * f_s, noverlap=0, mode='psd')

        cc_x = np.sqrt(np.trapz(Pa_x, f_x, axis=0))
        cc_y = np.sqrt(np.trapz(Pa_y, f_y, axis=0))
        cc_z = np.sqrt(np.trapz(Pa_z, f_z, axis=0))

        a_x_p95 = np.percentile(cc_x, 95)
        a_y_p95 = np.percentile(cc_y, 95)
        a_z_p95 = np.percentile(cc_z, 95)

        n_mv = 6 * np.sqrt(a_x_p95 ** 2 + a_y_p95 ** 2 + a_z_p95 ** 2)
        return n_mv, t, cc_x, cc_y, cc_z

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

    def execute(self):
        """ Executes the Comfort Processor on the given axes

        Returns
        ----------
        """

        f: RDYFile
        for f in tqdm(self.campaign):
            if len(f.measurements[LinearAccelerationSeries]) == 0:
                logger.warning("({}) LinearAccelerationSeries is empty, can't execute ExcitationProcessor "
                               "on this file".format(f.filename))
                continue
            else:
                lin_acc_df = f.measurements[LinearAccelerationSeries].to_df()
                df = lin_acc_df.resample(timedelta(seconds=1 / self.f_s)).mean().interpolate()
                t_df = (df.index.values - df.index.values[0]) / np.timedelta64(1, "s")

                # The evaluation assumes the phone is laying on the floor pointing in the direction of travel
                Wb = self.Wb(self.f_s)
                Wd = self.Wd(self.f_s)

                a_x_wd = signal.lfilter(Wd[0], Wd[1], df['lin_acc_y'].values)  # Adjusting to vehicle coordinate system
                a_y_wd = signal.lfilter(Wd[0], Wd[1], df['lin_acc_x'].values)
                a_z_wb = signal.lfilter(Wb[0], Wb[1], df['lin_acc_z'].values)

                # Moving RMS over 5s window
                f_x, t, Pa_x = signal.spectrogram(a_x_wd, self.f_s, nperseg=5 * self.f_s, noverlap=0, mode='psd')
                f_y, _, Pa_y = signal.spectrogram(a_y_wd, self.f_s, nperseg=5 * self.f_s, noverlap=0, mode='psd')
                f_z, _, Pa_z = signal.spectrogram(a_z_wb, self.f_s, nperseg=5 * self.f_s, noverlap=0, mode='psd')

                # Convert time back np.datetime64
                if type(df.index.values[0]) == np.datetime64:
                    t = df.index.values[0] + t.astype('timedelta64[s]')
                else:
                    t = t.astype('timedelta64[s]')

                cc_x = np.sqrt(np.trapz(Pa_x, f_x, axis=0))
                cc_y = np.sqrt(np.trapz(Pa_y, f_y, axis=0))
                cc_z = np.sqrt(np.trapz(Pa_z, f_z, axis=0))

                if len(f.measurements[GPSSeries]) > 0:
                    gps_df = f.measurements[GPSSeries].to_df()
                    # Create df
                    df_cc = pd.DataFrame.from_dict({'t': t,
                                                    'cc_x': cc_x,
                                                    'cc_y': cc_y,
                                                    'cc_z': cc_z})
                    df_cc.set_index('t', inplace=True)

                    df_cc = pd.concat([df_cc, gps_df]).sort_index()
                    df_cc = df_cc.resample(timedelta(seconds=5)).mean().interpolate()

                    a_x_p95 = np.percentile(df_cc[df_cc['speed'] > self.v_thres]['cc_x'].values, 95)
                    a_y_p95 = np.percentile(df_cc[df_cc['speed'] > self.v_thres]['cc_y'].values, 95)
                    a_z_p95 = np.percentile(df_cc[df_cc['speed'] > self.v_thres]['cc_z'].values, 95)
                else:
                    logger.warning(
                        "(%s) GPSSeries is empty, can't use v_thres to filter acceleration for comfort calculation" % f.filename)
                    a_x_p95 = np.percentile(cc_x, 95)
                    a_y_p95 = np.percentile(cc_y, 95)
                    a_z_p95 = np.percentile(cc_z, 95)

                n_mv = 6 * np.sqrt(a_x_p95 ** 2 + a_y_p95 ** 2 + a_z_p95 ** 2)

                # Peak nodes for OSM
                # if self.osm_integration and len(f.measurements[GPSSeries]) > 0:
                #     if self.campaign.osm:
                #         lin_s_abs = np.abs(lin_s_hp)
                #
                #         p_idxs, prop = signal.find_peaks(lin_s_hp, height=self.p_thres, distance=self.p_dist)
                #         peaks = lin_s_abs[p_idxs]
                #         lons, lats = df.lon[p_idxs], df.lat[p_idxs]
                #
                #         xs, ys = config.proj(lons, lats)
                #         if f.matched_line:
                #             trk = f.matched_line.tracks[0]
                #             way_lines = [convert_way_to_line_string(w, frmt="x,y") for w in trk.ways]
                #             for i, coord in enumerate(zip(xs, ys)):
                #                 p = Point(*coord)
                #
                #                 # Get the closest way to point
                #                 dists = [line.distance(p) for line in way_lines]
                #                 min_d = min(dists)
                #                 if min_d <= config.options["RESULT_MATCHING_MAX_DISTANCE"]:
                #                     line = way_lines[dists.index(min_d)]
                #                     way = trk.ways[dists.index(min_d)]
                #                     pp = line.interpolate(line.project(p))  # Projection of GPS point to OSM line
                #                     lon, lat = config.proj(pp.x, pp.y, inverse=True)
                #
                #                     r_node = OSMResultNode(lon, lat, peaks[i], f, proc=self, direction=ax)
                #
                #                     if "results" not in way.attributes:
                #                         way.attributes["results"] = [r_node]
                #                     else:
                #                         way.attributes["results"].append(r_node)
                #
                #     else:
                #         logger.warning("(%s) Campaign contains no OSM data, can't integrate results" % f.filename)

                if ComfortProcessor not in self.campaign.results:
                    self.campaign.results[ComfortProcessor] = {f.filename: {'n_mv': n_mv,
                                                                            'cc_x': cc_x,
                                                                            'cc_y': cc_y,
                                                                            'cc_z': cc_z,
                                                                            't': t}}
                else:
                    self.campaign.results[ComfortProcessor][f.filename] = {'n_mv': n_mv,
                                                                           'cc_x': cc_x,
                                                                           'cc_y': cc_y,
                                                                           'cc_z': cc_z,
                                                                           't': t}

        params = self.__dict__.copy()
        params.pop("campaign")
        if ComfortProcessor not in self.campaign.results:
            self.campaign.results[ComfortProcessor] = {"params": params}
        else:
            self.campaign.results[ComfortProcessor]["params"] = params

    # Filter functions
    @staticmethod
    def Wb(f_s: int):

        f1, f2 = 0.4, 100  # [Hz]
        f3, f4 = 16, 16  # [Hz]
        f5, f6 = 2.5, 4  # [Hz]

        Q1, Q2 = 1 / np.sqrt(2), 0.63  # [-]
        Q3, Q4 = 0.8, 0.8  # [-]

        K = 0.4  # [-]

        # Define numerators and denominators of all four filters
        Hlb = np.array([0, 0, np.square(2 * np.pi * f2)])
        Hla = np.array([1, (2 * np.pi * f2) / Q1, np.square(2 * np.pi * f2)])

        Hhb = np.array([1, 0, 0])
        Hha = np.array([1, (2 * np.pi * f1) / Q1, np.square(2 * np.pi * f1)])

        Htb = np.array([0, np.square(2 * np.pi * f4) / (2 * np.pi * f3), np.square(2 * np.pi * f4)])
        Hta = np.array([1, (2 * np.pi * f4) / Q2, np.square(2 * np.pi * f4)])

        Hsb = np.array([K / np.square(2 * np.pi * f5), K / (Q3 * 2 * np.pi * f5), K])
        Hsa = np.array([1 / np.square(2 * np.pi * f6), 1 / (Q4 * 2 * np.pi * f6), 1])

        # Convolve filters
        Hb = np.convolve(np.convolve(Hlb, Hhb), np.convolve(Htb, Hsb))
        Ha = np.convolve(np.convolve(Hla, Hha), np.convolve(Hta, Hsa))

        # Create digital filter from analog coefficients
        return signal.bilinear(Hb, Ha, f_s)

    @staticmethod
    def Wc(f_s: int):

        f1, f2 = 0.4, 100  # [Hz]
        f3, f4 = 8, 8  # [Hz]

        Q1, Q2 = 1 / np.sqrt(2), 0.63  # [-]

        # Define numerators and denominators of all three filters
        Hlb = np.array([0, 0, np.square(2 * np.pi * f2)])
        Hla = np.array([1, (2 * np.pi * f2) / Q1, np.square(2 * np.pi * f2)])

        Hhb = np.array([1, 0, 0])
        Hha = np.array([1, (2 * np.pi * f1) / Q1, np.square(2 * np.pi * f1)])

        Htb = np.array([0, np.square(2 * np.pi * f4) / (2 * np.pi * f3), np.square(2 * np.pi * f4)])
        Hta = np.array([1, (2 * np.pi * f4) / Q2, np.square(2 * np.pi * f4)])

        # Convolve filters
        Hb = np.convolve(np.convolve(Hlb, Hhb), Htb)
        Ha = np.convolve(np.convolve(Hla, Hha), Hta)

        # Create digital filter from analog coefficients
        return signal.bilinear(Hb, Ha, f_s)

    @staticmethod
    def Wd(f_s: int):

        f1, f2 = 0.4, 100  # [Hz]
        f3, f4 = 2, 2  # [Hz]

        Q1, Q2 = 1 / np.sqrt(2), 0.63  # [-]

        # Define numerators and denominators of all three filters
        Hlb = np.array([0, 0, np.square(2 * np.pi * f2)])
        Hla = np.array([1, (2 * np.pi * f2) / Q1, np.square(2 * np.pi * f2)])

        Hhb = np.array([1, 0, 0])
        Hha = np.array([1, (2 * np.pi * f1) / Q1, np.square(2 * np.pi * f1)])

        Htb = np.array([0, np.square(2 * np.pi * f4) / (2 * np.pi * f3), np.square(2 * np.pi * f4)])
        Hta = np.array([1, (2 * np.pi * f4) / Q2, np.square(2 * np.pi * f4)])

        # Convolve filters
        Hb = np.convolve(np.convolve(Hlb, Hhb), Htb)
        Ha = np.convolve(np.convolve(Hla, Hha), Hta)

        # Create digital filter from analog coefficients
        return signal.bilinear(Hb, Ha, f_s)

    @staticmethod
    def Wp(f_s: int):

        f1 = 0  # [Hz]
        f2 = 100  # [Hz]
        f3 = 2  # [Hz]
        f4 = 2  # [Hz]

        Q1 = 1 / np.sqrt(2)  # [-]
        Q2 = 0.63  # [-]

        K = 1  # [-]

        # Define numerators and denominators of all three filters
        Hlb = np.array([0, 0, np.square(2 * np.pi * f2)])
        Hla = np.array([1, (2 * np.pi * f2) / Q1, np.square(2 * np.pi * f2)])

        Hhb = np.array([1, 0, 0])
        Hha = np.array([1, (2 * np.pi * f1) / Q1, np.square(2 * np.pi * f1)])

        Htb = np.array([0, np.square(2 * np.pi * f4) / (2 * np.pi * f3), np.square(2 * np.pi * f4)])
        Hta = np.array([1, (2 * np.pi * f4) / Q2, np.square(2 * np.pi * f4)])

        # Convolve filters
        Hb = np.convolve(np.convolve(Hlb, Hhb), Htb)
        Ha = np.convolve(np.convolve(Hla, Hha), Hta)

        # Create digital filter from analog coefficients
        return signal.bilinear(Hb, Ha, f_s)
