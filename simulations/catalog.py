"""Ordered missions in the introductory file explorer course."""

TRAINING_CODES = ("FILES-101", "FILES-102", "FILES-103")
PROTOTYPE_FILES = ("files_001_v2.json", "files_001_v3.json", "files_101_v2.json", "files_101_v3.json", "files_101_v4.json") + tuple(
    f"{code.lower().replace('-', '_')}_v1.json" for code in TRAINING_CODES
)
