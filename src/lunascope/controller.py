
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

from . import __version__

import lunapi as lp

import os, sys, threading
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QModelIndex, QObject, Signal, Qt, QSortFilterProxyModel
from PySide6.QtGui import QAction, QStandardItemModel
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel, QFrame, QSizePolicy, QMessageBox, QLayout
from PySide6.QtWidgets import QMainWindow, QProgressBar, QTableView, QAbstractItemView


from .components.slist import SListMixin
from .components.metrics import MetricsMixin
from .components.hypno import HypnoMixin
from .components.anal import AnalMixin
from .components.signals import SignalsMixin
from .components.settings import SettingsMixin
from .components.ctree import CTreeMixin
from .components.spectrogram import SpecMixin
from .components.soappops import SoapPopsMixin



# ------------------------------------------------------------
# main GUI controller class

class Controller( QMainWindow,
                  SListMixin , MetricsMixin ,
                  HypnoMixin , SoapPopsMixin, 
                  AnalMixin , SignalsMixin, 
                  SettingsMixin, CTreeMixin ,
                  SpecMixin ):

    def __init__(self, ui, proj):
        super().__init__()

        # GUI
        self.ui = ui

        # Luna
        self.proj = proj
        
        # send compute to a different thread
        self._exec = ThreadPoolExecutor(max_workers=1)
        self._busy = False

        # initiate each component
        self._init_slist()
        self._init_metrics()
        self._init_hypno()
        self._init_anal()
        self._init_signals()
        self._init_settings()
        self._init_ctree()
        self._init_spec()
        self._init_soap_pops()

        # for the tables added above, ensure all are read-only
        for v in self.ui.findChildren(QTableView):
            v.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # redirect luna stderr
#        restore = redirect_fds_to_widget(self.ui.txt_out, fds=(1,2), label=False)

        # set up menu items: open projects
        act_load_slist = QAction("Load S-List", self)
        act_build_slist = QAction("Build S-List", self)
        act_load_edf = QAction("Load EDF", self)
        act_load_annot = QAction("Load Annotations", self)
        act_refresh = QAction("Refresh", self)

        # connect to same slots as buttons
        act_load_slist.triggered.connect(self.open_file)
        act_build_slist.triggered.connect(self.open_folder)
        act_load_edf.triggered.connect(self.open_edf)
        act_load_annot.triggered.connect(self.open_annot)
        act_refresh.triggered.connect(self._refresh)

        self.ui.menuProject.addAction(act_load_slist)
        self.ui.menuProject.addAction(act_build_slist)
        self.ui.menuProject.addSeparator()
        self.ui.menuProject.addAction(act_load_edf)
        self.ui.menuProject.addAction(act_load_annot)
        self.ui.menuProject.addSeparator()
        self.ui.menuProject.addAction(act_refresh)

        # set up menu items: viewing
        self.ui.menuView.addAction(self.ui.dock_slist.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_settings.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_sig.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_sigprop.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_annot.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_annots.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_spectrogram.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_hypno.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_console.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_outputs.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_help.toggleViewAction())

        # set up menu: about
        act_about = QAction("Help", self)

        act_about.triggered.connect(
            lambda: (
                lambda box=QMessageBox(self): (
                    box.setWindowTitle("About Lunascope"),
                    box.setIcon(QMessageBox.Information),
                    box.setTextFormat(Qt.RichText),
                    box.setText(
                        f"<p>Lunascope v{__version__}</p>"
                        "<p>Documentation:<br> <a href='http://zzz-luna.org/lunascope'>http://zzz-luna.org/lunascope</a></p>"
                        "<p>Created by Shaun Purcell</p>"
                        "<p>Developed and maintained by Lorcan Purcell</p>"
                    ),
                    box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding),
                    box.layout().setSizeConstraint(QLayout.SetMinimumSize),
                    (
                        lambda lbl=box.findChild(QLabel): lbl.setOpenExternalLinks(True)
                        if lbl else None
                    )(),
                    box.exec()
                )
            )()
        )

        self.ui.menuAbout.addAction(act_about)   

        # window title
        self.ui.setWindowTitle(f"Lunascope v{__version__}")
        
        # short keyboard cuts
        add_dock_shortcuts( self.ui, self.ui.menuView )

        # arrange docks: hide some docks
        self.ui.dock_help.hide()
        self.ui.dock_console.hide()
        self.ui.dock_outputs.hide()
        self.ui.dock_sigprop.hide()

        # arrange docks: lock and resize
        self.ui.setCorner(Qt.TopRightCorner,    Qt.RightDockWidgetArea)
        self.ui.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        # arrange docks: lower docks (console/output)
        w = self.ui.width()

        self.ui.resizeDocks([ self.ui.dock_console , self.ui.dock_outputs ],
                            [int(w*0.6), int(w*0.45)], Qt.Horizontal)

        # arrange docks: left docks (samples, settings)
        self.ui.resizeDocks([ self.ui.dock_slist , self.ui.dock_settings ],
                            [int(w*0.7), int(w*0.3) ], Qt.Vertical )

        
        # arrange docks: right docks (signals, annots, events)
        h = self.ui.height()
        self.ui.resizeDocks([ self.ui.dock_sig, self.ui.dock_annot, self.ui.dock_annots ] , 
                            [int(h*0.5), int(h*0.4), int(h*0.1) ],
                            Qt.Vertical)
        w_right = 320
        self.ui.resizeDocks([self.ui.dock_slist, self.ui.dock_sig], [self.width()-w_right, w_right], Qt.Horizontal)

        # arrange docks: general
        self.ui.centralWidget().setMinimumWidth(0)
        self.ui.centralWidget().setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


        # ------------------------------------------------------------
        # set up status bar

        # ID | EDF-type start time/date | hms(act) / hms(tot) / epochs | # sigs / # annots | progress bar

        def mk_section(text):
            lab = QLabel(text)
            lab.setAlignment(Qt.AlignLeft)
            lab.setFrameShape(QFrame.StyledPanel)
            lab.setFrameShadow(QFrame.Sunken)
            lab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            return lab

        def vsep():
            s = QFrame(); s.setFrameShape(QFrame.VLine); s.setFrameShadow(QFrame.Sunken)
            return s

        sb = self.ui.statusbar

        sb.setSizeGripEnabled(True)
        
        self.sb_id     = mk_section( "" ); 
        self.sb_start  = mk_section( "" ); 
        self.sb_dur    = mk_section( "" );
        self.sb_ns     = mk_section( "" );
        self.sb_progress = QProgressBar()
        self.sb_progress.setRange(0, 100)
        self.sb_progress.setValue(0)

        sb.addPermanentWidget(self.sb_id ,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_start,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_dur,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_ns,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_progress,1)
        sb.addPermanentWidget(vsep(),0)


        # ------------------------------------------------------------
        # size overall app window
        
        self.ui.resize(1200, 800)


    
    # ------------------------------------------------------------
    # attach a new record
    # ------------------------------------------------------------

    def _attach_inst(self, current: QModelIndex, _):

        # get ID from (possibly filtered) table
        if not current.isValid():
            return
        
        # clear existing stuff
        self._clear_all()

        # get/set parameters
        self.proj.clear_vars()
        self.proj.reinit()
        param = self._parse_tab_pairs( self.ui.txt_param )
        for p in param:
            self.proj.var( p[0] , p[1] )

        # attach the individual by ID (i.e. as list may be filtered)
        id_str = current.siblingAtColumn(0).data(Qt.DisplayRole)
        
        # attach EDF
        try:
            self.p = self.proj.inst( id_str )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Problem attaching individual {id_str}\nError:\n{e}",
            )
            return
            
        # and update things that need updating
        self._update_metrics()
        self._render_histogram()
        self._update_spectrogram_list()
        self._update_soap_list()
        self._update_params()

        # initially, no signals rendered
        self.rendered = False

        # draw
        self.curves = [ ] 
        self._render_signals_simple()

        # hypnogram + stats if available
        self._calc_hypnostats()

    # ------------------------------------------------------------
    #
    # clear for a new record
    #
    # ------------------------------------------------------------

    def _clear_all(self):

        if getattr(self, "events_table_proxy", None) is not None:
            clear_rows( self.events_table_proxy )

        if getattr(self, "anal_table_proxy", None) is not None:
            clear_rows( self.anal_table_proxy , keep_headers = False )

        clear_rows( self.ui.tbl_desc_signals )
        clear_rows( self.ui.tbl_desc_annots )
        clear_rows( self.ui.anal_tables ) 
        clear_rows( self.ui.tbl_soap1 )
        clear_rows( self.ui.tbl_pops1 )
        clear_rows( self.ui.tbl_hypno1 )
        clear_rows( self.ui.tbl_hypno2 )
        clear_rows( self.ui.tbl_hypno3 )

        self.ui.combo_spectrogram.clear()
        self.ui.combo_pops.clear()
        self.ui.combo_soap.clear()

        self.ui.txt_out.clear()
        self.ui.txt_inp.clear()
        
        self.spectrogramcanvas.ax.cla()
        self.spectrogramcanvas.figure.canvas.draw_idle()

        self.hypnocanvas.ax.cla()
        self.hypnocanvas.figure.canvas.draw_idle()

        self.soapcanvas.ax.cla()
        self.soapcanvas.figure.canvas.draw_idle()

        self.popscanvas.ax.cla()
        self.popscanvas.figure.canvas.draw_idle()
            
        self.popshypnocanvas.ax.cla()
        self.popshypnocanvas.figure.canvas.draw_idle()
        

# ------------------------------------------------------------
#
# clear up tables
#
# ------------------------------------------------------------


def clear_rows(target, *, keep_headers: bool = True) -> None:
    """
    Clear all rows. If keep_headers=False, also clear header labels.
    `target` can be QTableView, QSortFilterProxyModel, or a plain model.
    """
    # Normalize to a model (and remember how to reattach if we rebuild)
    if hasattr(target, "model"):          # QTableView
        view = target
        model = view.model()
        set_model = view.setModel
    else:                                 # model or proxy
        view = None
        model = target
        set_model = None
    if model is None:
        return

    proxy = model if isinstance(model, QSortFilterProxyModel) else None
    src = proxy.sourceModel() if proxy else model
    if src is None:
        return

    rc = src.rowCount()

    # Fast path: QStandardItemModel
    if isinstance(src, QStandardItemModel):
        if rc:
            src.removeRows(0, rc)
        if not keep_headers:
            cols = src.columnCount()
            if cols:
                src.setHorizontalHeaderLabels([""] * cols)
        return

    # Generic path: try to remove rows via API
    ok = True
    if rc and hasattr(src, "removeRows"):
        try:
            ok = bool(src.removeRows(0, rc))
        except Exception:
            ok = False
    if ok:
        if not keep_headers and hasattr(src, "setHeaderData"):
            cols = src.columnCount()
            for c in range(cols):
                try:
                    src.setHeaderData(c, QtCore.Qt.Horizontal, "")
                except Exception:
                    pass
        return

    # Fallback: rebuild an empty QStandardItemModel, preserving or blanking headers
    cols = src.columnCount()
    headers = [
        src.headerData(c, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)
        for c in range(cols)
    ]
    new = QStandardItemModel(view or proxy)
    new.setColumnCount(cols)
    if keep_headers:
        new.setHorizontalHeaderLabels([("" if h is None else str(h)) for h in headers])
    else:
        new.setHorizontalHeaderLabels([""] * cols)

    if proxy:
        proxy.setSourceModel(new)
    elif set_model:
        set_model(new)

    
        
# ------------------------------------------------------------
#
# dock menu toggle
#
# ------------------------------------------------------------

def add_dock_shortcuts(win, view_menu):

    # hide/show all

    act_show_all = QAction("Show/Hide All Docks", win, checkable=False)
    act_show_all.setShortcut("Ctrl+0")
    
    def toggle_all():
        docks = win.findChildren(QDockWidget)
        all_hidden = all(not d.isVisible() for d in docks)
        # If all hidden → show all, else hide all
        for d in docks:
            d.setVisible(all_hidden)

    act_show_all.triggered.connect(toggle_all)
    view_menu.addAction(act_show_all)

    # control individual docks

    for act in win.menuView.actions():
        if act.text() == "(1) Project sample list":
            act.setShortcut("Ctrl+1")
        elif act.text() == "(2) Parameters":
            act.setShortcut("Ctrl+2")
        elif act.text() == "(3) Signals":
            act.setShortcut("Ctrl+3")
        elif act.text() == "(4) Annotations":
            act.setShortcut("Ctrl+4")
        elif act.text() == "(5) Instances":
            act.setShortcut("Ctrl+5")
        elif act.text() == "(6) Spectrograms":
            act.setShortcut("Ctrl+6")
        elif act.text() == "(7) Hypnograms":
            act.setShortcut("Ctrl+7")
        elif act.text() == "(8) Console":
            act.setShortcut("Ctrl+8")
        elif act.text() == "(9) Outputs":
            act.setShortcut("Ctrl+9")
        elif act.text() == "(/) Signal properties": 
            act.setShortcut("Ctrl+/")
        elif act.text() == "(-) Commands":
            act.setShortcut("Ctrl+-")

    return act_show_all




# ------------------------------------------------------------
# helper: redirect stderr to widget

class _FdPump(QObject):
    line = Signal(str)
    
def redirect_fds_to_widget(widget, fds=(1, 2), label=True):
    """
    Redirect given OS fds (1=stdout, 2=stderr) to a QPlainTextEdit-like widget.
    Returns a restore() function. Use in try/finally.
    """
    pump = _FdPump()
    pump.line.connect(widget.appendPlainText)

    readers = []
    saved = []
    for fd in fds:
        r, w = os.pipe()
        saved.append(os.dup(fd))      # save original
        os.dup2(w, fd)                # redirect fd -> pipe write end
        os.close(w)

        def _reader(pipe_r=r, tag=("stdout" if fd == 1 else "stderr")):
            with os.fdopen(pipe_r, "r", buffering=1, errors="replace") as f:
                for line in f:
                    msg = f"[{tag}] {line.rstrip()}" if label else line.rstrip()
                    pump.line.emit(msg)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        readers.append(t)
    
    
    def restore():
        # flush Python-level streams first
        try: sys.stdout.flush()
        except Exception: pass
        try: sys.stderr.flush()
        except Exception: pass

        for fd, old in zip(fds, saved):
            os.dup2(old, fd)
            os.close(old)

    return restore
