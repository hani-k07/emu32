import os

# Must be set before Qt creates the application, so GUI tests run headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
