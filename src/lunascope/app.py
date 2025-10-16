
#  --------------------------------------------------------------------
#
#  This file is part of Luna.
#
#  LUNA is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Luna is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Luna. If not, see <http:#www.gnu.org/licenses/>.
#
#  Please see LICENSE.txt for more details.
#
#  --------------------------------------------------------------------

import lunapi as lp

import argparse
from pathlib import Path
import sys, os

import pyqtgraph as pg
from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication
from importlib.resources import files, as_file

from .controller import Controller

# suppress macOS warnings
os.environ["OS_ACTIVITY_MODE"] = "disable"


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
    app = QApplication(sys.argv)

    # initiate silent luna
    proj = lp.proj()
    proj.silence( True )
    
    ui = _load_ui()
    controller = Controller(ui, proj)
    ui.show()
   
    if args.slist_file:
        folder_path = str(Path( args.slist_file ).parent) + os.sep
        proj.var( 'path' , folder_path )
        controller._read_slist_from_file( args.slist_file )
    try:
        return app.exec()
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

