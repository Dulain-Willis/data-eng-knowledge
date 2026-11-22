"""Regression check for checks/no_meta_first_line.has_meta_line: leading blank lines must not hide the line."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from no_meta_first_line import has_meta_line

assert has_meta_line("Advanced·Spark · 35 min · 11 challenges\nx")
assert has_meta_line("\n\nBeginner · 5 min · 1 challenge\nx")
assert not has_meta_line("# Title\nBeginner · 5 min · 1 challenge")
print("ok")
