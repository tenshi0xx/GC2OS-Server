import warnings

"""
Logging Module (Helps decrease or easier formatting)
"""


"Dict For Warning Stuff"
warn_dict = ["UserWarning", "DeprecationWarning", "SyntaxWarning", "RuntimeWarning", "FutureWarning", "ImportWarning", "ResourceWarning", "BytesWarning", "UnicodeWarning"]

def module_log(message: string, module_name: string):
    print('[${module_name}] ${message}')
def warn_log(message: string, module_name: string, warn_type: warn_dict, warn_level: int(1, 3)):
    warnings.warn('[${module_name}] ${messages}', warn_type, warn_level)
def error_log(message: string, module_name: string):
    print('[Error] [${module_name}] ${message}')
