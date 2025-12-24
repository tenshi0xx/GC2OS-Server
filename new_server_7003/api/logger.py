import warnings
from typing import Literal, Type
"""
Logging Module (Helps decrease or easier formatting)
"""


"Apparently Python didn't allow it"
"""
WARN_TYPES = {
    "user": UserWarning,
    "deprecation": DeprecationWarning,
    "syntax": SyntaxWarning,
    "runtime": RuntimeWarning,
    "future": FutureWarning,
    "import": ImportWarning,
    "resource": ResourceWarning,
    "bytes": BytesWarning,
    "unicode": UnicodeWarning,
}
"""
def module_log(message: str, module_name: str) -> None:
    print(f'[{module_name}] {message}')
    
def warn_log(message: str, module_name: str, warn_type: type[Warning]) -> None:
    warnings.warn(
        f'[{module_name}] {message}',
        category=warn_type,
        stacklevel=2
        )

def error_log(message: str, module_name: str) -> None:
    print(f'[Error] [{module_name}] {message}')
