import shutil
import unittest


requires_go = unittest.skipUnless(
    shutil.which("go"),
    "Go toolchain required: install.py builds okfctl at install time",
)


def class_requires_go(cls):
    return requires_go(cls)
