# Run PyInstaller from the task2 directory so all paths are deterministic.
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Prefer a full Python distribution's own Tcl/Tk runtime. The bundled Python
# used in this environment omits Tcl scripts, so point PyInstaller's hook to
# the local script assets using short paths relative to this build directory.
if not os.environ.get("TCL_LIBRARY"):
    _base_tcl = os.path.join(sys.base_prefix, "tcl")
    _has_tcl = any(Path(_base_tcl).glob("tcl*/init.tcl"))
    if not _has_tcl or "codex-runtimes" in sys.base_prefix.lower():
        os.environ["TCL_LIBRARY"] = "tcl-runtime/tcl8.6"
        os.environ["TK_LIBRARY"] = "tcl-runtime/tk8.6"

sentencepiece_datas, sentencepiece_binaries, sentencepiece_hiddenimports = collect_all("sentencepiece")

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=sentencepiece_binaries,
    datas=[
        ("model/text-to-sql-small", "model/text-to-sql-small"),
        ("model/labels.json", "model"),
        ("model/vocab.json", "model"),
        ("model/tiny_slm.pt", "model"),
        *sentencepiece_datas,
    ],
    hiddenimports=[
        "gui",
        "transformers.models.t5.configuration_t5",
        "transformers.models.t5.modeling_t5",
        "transformers.models.t5.tokenization_t5",
        *sentencepiece_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "notebook", "jupyter", "flan-t5-small"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="EulerQ_TextToSQL",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
