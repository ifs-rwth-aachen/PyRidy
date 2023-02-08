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
        """
        Class that describes an Android sensor

        See https://developer.android.com/reference/android/hardware/Sensor for documentation on individual parameters

        Parameters
        ----------
        name: str
            Sensor's name.
        vendor: str
            Vendor string of the sensor.
        string_type: str
            A constant string describing the sensor's type.
        power: float
            The power in mA used by this sensor while in use.
        resolution: float
            Resolution of the sensor in the sensor's unit.
        version: int
            Version of the sensor's module.
        type: int
            Generic type of this sensor.
        max_delay: int
            The delay between two sensor events corresponding to the lowest frequency that this sensor supports.
        max_range: int
            Maximum range of the sensor in the sensor's unit.
        min_delay: int
            The minimum delay allowed between two events in microseconds or zero if this sensor only returns a value when the data it's measuring changes.
        """
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
