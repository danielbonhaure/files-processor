
class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class ConfigError(Error):
    """Raised when a configuration value is wrong"""
    pass


class DescriptorError(Error):
    """Raised when a descriptor value is wrong"""
    pass

