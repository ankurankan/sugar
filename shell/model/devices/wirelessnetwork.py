from model.devices import device

class Device(device.Device):
    def __init__(self, nm_device):
        device.Device.__init__(self)
        self._nm_device = device

    def get_type(self):
        return 'wirelessnetwork'

    def get_level(self):
        return self._nm_device.get_strength()
