import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.vercel import Base  # noqa: E402


class handler(Base):
    pass
