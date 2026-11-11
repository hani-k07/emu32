# PyInstaller build of the Windows program folder.
# Run from the repository root:
#   pyinstaller --noconfirm --distpath build/dist --workpath build/work packaging/emu32.spec
# The result, build/dist/emu32, is both the portable folder and the installer's source.
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

root = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 - set by PyInstaller

# The engines load their DLL from their own package folder, so keep that layout.
# Unicorn also imports its architecture modules by name at run time.
engine_libraries, engine_modules = [], []
for package in ("keystone", "unicorn", "capstone"):
    engine_libraries += collect_dynamic_libs(package)
    engine_modules += collect_submodules(package)

analysis = Analysis(  # noqa: F821
    [os.path.join(root, "packaging", "launch.py")],
    pathex=[os.path.join(root, "src")],
    binaries=engine_libraries,
    hiddenimports=engine_modules,
    datas=collect_data_files("emu32"),  # examples and help pages
    excludes=["tkinter", "unittest", "pytest", "pydoc"],
)
pyz = PYZ(analysis.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="emu32",
    # EMU32_CONSOLE=1 builds with a console window, to see errors while debugging a build.
    console=os.environ.get("EMU32_CONSOLE") == "1",
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="emu32", upx=False)  # noqa: F821

# Unicorn recovers from some memory faults with longjmp. With Control Flow Guard on, Windows
# rejects that jump and ends the process (0xC0000409). python.exe is built without CFG, so the
# launcher is set to match. See docs/decisions.md D45.
import struct  # noqa: E402

launcher = os.path.join(DISTPATH, "emu32", "emu32.exe")  # noqa: F821
with open(launcher, "r+b") as file:
    image = bytearray(file.read())
    header = struct.unpack_from("<I", image, 0x3C)[0]
    assert image[header : header + 4] == b"PE\0\0", "not a PE file"
    field = header + 24 + 70  # OptionalHeader.DllCharacteristics
    flags = struct.unpack_from("<H", image, field)[0]
    struct.pack_into("<H", image, field, flags & ~0x4000)  # IMAGE_DLLCHARACTERISTICS_GUARD_CF
    file.seek(0)
    file.write(image)
