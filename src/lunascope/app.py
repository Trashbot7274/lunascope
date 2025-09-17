# src/lunascope/app.py

import sys
import argparse
from pathlib import Path

import lunapi as lp
import pyqtgraph as pg
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication
from importlib.resources import files, as_file

from .controller import Controller


def _load_ui():
    ui_res = files("lunascope.ui").joinpath("main.ui")
    with as_file(ui_res) as p:
        f = QFile(str(p))
        if not f.open(QFile.ReadOnly):
            raise RuntimeError(f"Cannot open UI file: {p}")
        try:
            loader = QUiLoader()
            loader.registerCustomWidget(pg.PlotWidget)
            ui = loader.load(f)
        finally:
            f.close()
    if ui is None:
        raise RuntimeError("Failed to load UI")
    return ui


def _parse_args(argv):
    ap = argparse.ArgumentParser(prog="lunascope")
    ap.add_argument("slist_file", nargs="?", help="optional sample list file")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    proj = lp.proj()  # required

    app = QApplication(sys.argv)  # Qt wants real sys.argv
    ui = _load_ui()
    ui.show()

    controller = Controller(ui, proj)

    if args.slist_file:
        controller._read_slist_from_file( args.slist_file )

    try:
        return app.exec()
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

