import logging
from datetime import timedelta

import numpy as np
from scipy import signal
from tqdm.auto import tqdm

from pyridy import Campaign
from pyridy.file import RDYFile
from pyridy.processing import PostProcessor
from pyridy.utils import LinearAccelerationSeries

logger = logging.getLogger(__name__)


class ComfortProcessor(PostProcessor):
    def __init__(self, campaign: Campaign, f_s: int = 200, v_thres: float = 10/3.6, method='EN12299'):
        """ The Comfort processor can process acceleration data of a campaign according to the EN 12299 standard
        and Wz (Sperling-Index) Method.

        Parameters
        ----------
        campaign
        f_s
        v_thres
        method
        """
        super(ComfortProcessor, self).__init__(campaign)
        self.f_s = f_s

        if method not in ['EN12299', 'Wz']:
            raise ValueError(f'Method must be "EN1299" or "Wz", not {method}')

    def execute(self):
        """ Executes the Comfort Processor on the given axes

        Parameters
        ----------
        """

        f: RDYFile
        for f in tqdm(self.campaign):
            if len(f.measurements[LinearAccelerationSeries]) == 0:
                logger.warning("({}) LinearAccelerationSeries is empty, can't execute ExcitationProcessor "
                               "on this file".format(f.filename))
                continue
            else:
                df = f.measurements[LinearAccelerationSeries].to_df()

                df = df.resample(timedelta(seconds=1 / self.f_s)).mean().interpolate()
                t = (df.index.values - df.index.values[0]) / np.timedelta64(1, "s")

                # The evaluation assumes the phone is laying on the floor pointing in the direction of travel

                Wb = self.Wb(self.f_s)
                Wd = self.Wd(self.f_s)

                a_x_wd = signal.filtfilt(Wd[0], Wd[1], df['lin_acc_y'].values)  # Adjusting to vehicle coordinate system
                a_y_wd = signal.filtfilt(Wd[0], Wd[1], df['lin_acc_x'].values)
                a_z_wb = signal.filtfilt(Wb[0], Wb[1], df['lin_acc_z'].values)

                # Moving RMS over 5s window
                f_x, t_x, Pa_x = signal.spectrogram(a_x_wd, self.f_s, nperseg=5 * self.f_s, noverlap=0, mode='psd')
                f_y, t_y, Pa_y = signal.spectrogram(a_y_wd, self.f_s, nperseg=5 * self.f_s, noverlap=0, mode='psd')
                f_z, t_z, Pa_z = signal.spectrogram(a_z_wb, self.f_s, nperseg=5 * self.f_s, noverlap=0, mode='psd')

                cc_x = np.sqrt(np.trapz(Pa_x, f_x, axis=0))
                cc_y = np.sqrt(np.trapz(Pa_y, f_y, axis=0))
                cc_z = np.sqrt(np.trapz(Pa_z, f_z, axis=0))

                a_x_p95 = np.percentile(cc_x, 95)
                a_y_p95 = np.percentile(cc_y, 95)
                a_z_p95 = np.percentile(cc_z, 95)

                n_mv = 6 * np.sqrt(a_x_p95 ** 2 + a_y_p95 ** 2 + a_z_p95 ** 2)
                if ComfortProcessor not in self.campaign.results:
                    self.campaign.results[ComfortProcessor] = {f.filename: {'n_mv': n_mv,
                                                                            'cc_x': cc_x,
                                                                            'cc_y': cc_y,
                                                                            'cc_z': cc_z,
                                                                            't': t_x}}
                else:
                    self.campaign.results[ComfortProcessor][f.filename] = {'n_mv': n_mv,
                                                                           'cc_x': cc_x,
                                                                           'cc_y': cc_y,
                                                                           'cc_z': cc_z,
                                                                           't': t_x}

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
