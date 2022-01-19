import logging
from datetime import timedelta
from typing import Union

import numpy as np
from scipy import signal, integrate

from pyridy import Campaign
from pyridy.processing import PostProcessor
from pyridy.utils import LinearAccelerationSeries

logger = logging.getLogger(__name__)


class ExcitationProcessor(PostProcessor):
    def __init__(self, campaign: Campaign, f_s: int = 200, f_c: float = 0.1, order: int = 4):
        """

        Parameters
        ----------
        campaign
        f_s
        f_c
        order
        """
        super(ExcitationProcessor, self).__init__(campaign)
        self.f_s = f_s
        self.f_c = f_c
        self.order = order

        self.b, self.a = signal.butter(self.order, 2 * self.f_c / self.f_s, 'high')  # High Pass (2*f_c/f_s)

    def execute(self, axes: Union[str, list] = "z"):
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

        for f in self.campaign:
            if len(f.measurements[LinearAccelerationSeries]) == 0:
                logger.warning("(%s) LinearAccelerationSeries is empty, can't execute ExcitationProcessor on this file")
                continue
            else:
                df = f.measurements[LinearAccelerationSeries].to_df()
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
                    lin_acc_hp = signal.filtfilt(self.b, self.a, lin_acc, padlen=150)
                    lin_v = integrate.cumtrapz(lin_acc_hp, t, initial=0)
                    df["lin_v_" + ax] = lin_v

                    # Remove offset by applying high pass filter again
                    lin_v_hp = signal.filtfilt(self.b, self.a, lin_v, padlen=150)
                    lin_s = integrate.cumtrapz(lin_v_hp, t, initial=0)
                    df["lin_s_" + ax] = lin_s

                if ExcitationProcessor not in self.campaign.results:
                    self.campaign.results[ExcitationProcessor] = {f.name: df}
                else:
                    self.campaign.results[ExcitationProcessor][f.name] = df

        params = self.__dict__.copy()
        params.pop("campaign")
        if ExcitationProcessor not in self.campaign.results:
            self.campaign.results[ExcitationProcessor] = {"params": params}
        else:
            self.campaign.results[ExcitationProcessor]["params"] = params
        pass
