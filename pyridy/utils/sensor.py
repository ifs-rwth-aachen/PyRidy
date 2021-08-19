class Sensor:
    def __init__(self,
                 name: str = None,
                 vendor: str = None,
                 string_type: str = None,
                 power: float = None,
                 resolution: float = None,
                 version: int = None,
                 type: int = None,
                 max_delay: int = None,
                 max_range: float = None,
                 min_delay: int = None):

        self.name = name
        self.vendor = vendor
        self.string_type = string_type
        self.power = power
        self.resolution = resolution
        self.version = version
        self.type = type
        self.max_delay = max_delay
        self.max_range = max_range
        self.min_delay = min_delay
        pass

    def __repr__(self):
        return self.string_type + " " + self.name
