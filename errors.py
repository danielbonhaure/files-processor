
class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class ConfigError(Error):
    """Raised when the a configuration value is wrong"""
    pass
