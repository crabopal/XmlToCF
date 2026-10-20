"""xml2cf — compile Designer XML dumps to .cf without the 1C platform."""

from .compiler import CompileReport, compile_dump, supported_types

__version__ = "0.2.0"
__all__ = ["compile_dump", "CompileReport", "supported_types", "__version__"]
