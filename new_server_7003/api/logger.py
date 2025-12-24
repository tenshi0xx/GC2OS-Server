import warnings
from typing import Literal, Type
"""
Logging Module (Helps decrease or easier formatting)
"""


"Dict For Warning Stuff"
warn_dict = [
    UserWarning,
    DeprecationWarning,
    SyntaxWarning,
    RuntimeWarning,
    FutureWarning,
    ImportWarning,
    ResourceWarning,
    BytesWarning,
    UnicodeWarning
    ]

def module_log(message: str, module_name: str) -> None:
    print('f[{module_name}] {message}')
    
def warn_log(message: str, module_name: str, warn_type: warn_dict, warn_level: int = 1) -> None:
    if not 1 <= warn_level <= 3:
        raise ValueError("warn_level must be between 1 and 3 \n Defaulting to 1")
        warn_level = 1
    warnings.warn('f[{module_name}] {messages}', warn_type, warn_level)

def error_log(message: str, module_name: str) -> None:
    print('f[Error] [{module_name}] {message}')
