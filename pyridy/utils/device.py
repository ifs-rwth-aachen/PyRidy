from typing import Union

from pandas import Series


class Device:
    def __init__(self,
                 api_level: Union[int, Series] = None,
                 base_os: Union[str, Series] = None,
                 brand: Union[str, Series] = None,
                 manufacturer: Union[str, Series] = None,
                 device: Union[str, Series] = None,
                 product: Union[str, Series] = None,
                 model: Union[str, Series] = None):

        if type(api_level) == Series:
            self.api_level = api_level[0] if len(api_level) > 0 else None
        else:
            self.api_level = api_level

        if type(base_os) == Series:
            self.base_os = base_os[0] if len(base_os) > 0 else None
        else:
            self.base_os = base_os

        if type(brand) == Series:
            self.brand = brand[0] if len(brand) > 0 else None
        else:
            self.brand = brand

        if type(manufacturer) == Series:
            self.manufacturer = manufacturer[0] if len(manufacturer) > 0 else None
        else:
            self.manufacturer = manufacturer

        if type(device) == Series:
            self.device = device[0] if len(device) > 0 else None
        else:
            self.device = device

        if type(product) == Series:
            self.product = product[0] if len(product) > 0 else None
        else:
            self.product = product

        if type(model) == Series:
            self.model = model[0] if len(model) > 0 else None
        else:
            self.model = model

    def __repr__(self):
        return "Brand: %s, Model: %s, Product: %s, Device: %s, Manufacturer: %s, Base OS: %s, API Level: %d " \
               % (self.brand, self.model, self.product, self.device, self.manufacturer, self.base_os,
                  self.api_level if self.api_level else -1)
