class Device:
    def __init__(self,
                 api_level: int = None,
                 base_os: str = None,
                 brand: str = None,
                 manufacturer: str = None,
                 device: str = None,
                 product: str = None,
                 model: str = None):
        self.api_level = api_level
        self.base_os = base_os
        self.brand = brand
        self.manufacturer = manufacturer
        self.device = device
        self.product = product
        self.model = model
