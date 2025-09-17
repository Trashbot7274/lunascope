
import os, sys, threading
import lunapi as lp

from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import QModelIndex, QObject, Signal, Qt, QSortFilterProxyModel
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QStandardItemModel
from PySide6.QtWidgets import QDockWidget, QLabel, QFrame, QSizePolicy, QTableView

from .components.slist import SListMixin
from .components.metrics import MetricsMixin
from .components.hypno import HypnoMixin
from .components.anal import AnalMixin
from .components.signals import SignalsMixin
from .components.settings import SettingsMixin
from .components.manips import ManipsMixin
from .components.ctree import CTreeMixin
from .components.spectrogram import SpecMixin
from .components.soappops import SoapPopsMixin

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




class Controller( QMainWindow,
                  SListMixin , MetricsMixin ,
                  HypnoMixin , SoapPopsMixin, 
                  AnalMixin , SignalsMixin, ManipsMixin,
                  SettingsMixin, CTreeMixin , SpecMixin ):

    def __init__(self, ui, proj):
        super().__init__()

        self.ui = ui
        self.proj = proj
        self._init_slist()
        self._init_metrics()
        self._init_hypno()        
        self._init_anal()
        self._init_signals()
        self._init_settings()
        self._init_manips()
        self._init_ctree()
        self._init_spec()
        self._init_soap_pops()
        
        # redirect luna stderr
#        restore = redirect_fds_to_widget(self.ui.txt_out, fds=(1,2), label=False)

        # menu items
        self.ui.menuView.addAction(self.ui.dock_slist.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_header.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_sig.toggleViewAction())
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
        self.ui.menuView.addAction(self.ui.dock_settings.toggleViewAction())

        add_dock_shortcuts( self.ui, self.ui.menuView )

        # arrange docks

        self.ui.dock_help.hide()
        self.ui.dock_settings.hide()
        self.ui.setCorner(Qt.TopRightCorner,    Qt.RightDockWidgetArea)
        self.ui.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        w = self.ui.width()

        self.ui.resizeDocks([ self.ui.dock_console , self.ui.dock_outputs ],
                            [int(w*0.6), int(w*0.45)], Qt.Horizontal)

        h = self.ui.height()

        self.ui.resizeDocks([ self.ui.dock_sig , self.ui.dock_annot , self.ui.dock_annots ],
                            [int(w*0.5), int(w*0.3), int(w*0.2)], Qt.Vertical )

        self.ui.resizeDocks([ self.ui.dock_slist , self.ui.dock_header ],
                            [int(w*0.7), int(w*0.3) ], Qt.Vertical )
        
        # status bar

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
        
        self.sb_status = mk_section( "Ready" )
        self.sb_id     = mk_section( "<no EDF attached>" )
        self.sb_dur    = mk_section( "               " )
        self.sb_ns     = mk_section( "               " )
        self.sb_render = mk_section( "" );
        
        sb.addPermanentWidget(self.sb_status,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_render,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_id ,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_dur,1)
        sb.addPermanentWidget(vsep(),0)
        sb.addPermanentWidget(self.sb_ns,1)
        sb.addPermanentWidget(vsep(),0)

        self.sb_render.setText( "Rendered: F" );

        
    # ------------------------------------------------------------
    #
    # attach a new record
    #
    # ------------------------------------------------------------

    def _attach_inst(self, current: QModelIndex, _):

        # clear existing stuff
        self._clear_all()

        # get/set parameters
        self.proj.clear_vars()
        self.proj.reinit()
        param = self._parse_tab_pairs( self.ui.txt_param )
        for p in param:
            self.proj.var( p[0] , p[1] )

        print( 't1' ) 

        # attach the individual
        self.p = self.proj.inst( current.row() + 1 )

        print( 't2' )
                
        # and update some things
        self._update_metrics()
        self._render_histogram()
        self._update_spectrogram_list()
        self._update_soap_list()

        # initially, no signals rendered
        self.rendered = False

        # but initialize a separate ss for annotations only
        self.ssa = lp.segsrv( self.p )
        self.ssa.populate( chs = [ ] , anns = self.p.edf.annots() )
        self.ssa.set_annot_format6( False )  # pyqtgraph vs plotly

        # populate here, as used by plot_simple (prior to render)
        self.ss_anns = self.ui.tbl_desc_annots.checked()
        self.ss_chs = self.ui.tbl_desc_signals.checked()

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

        clear_rows( self.ui.anal_tables ) 

        self.ui.combo_spectrogram.clear()
        self.ui.combo_pops.clear()
        self.ui.combo_soap.clear()

        self.ui.txt_out.clear()
        self.ui.txt_inp.clear()
        
        self.spectrogramcanvas.ax.cla()
        self.spectrogramcanvas.figure.canvas.draw_idle()

        self.hypnocanvas.ax.cla()
        self.hypnocanvas.figure.canvas.draw_idle()

        # proxies used for slist, anal and instance tables
        #  self.events_table_proxy
        #  self.anal_table_proxy
        #  self.proxy  (slist)


# ------------------------------------------------------------
#
# clear up tables
#
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui, QtWidgets as QtW

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

    #
    # hide/show all
    #

    act_show_all = QAction("Show/Hide All Docks", win, checkable=False)
    act_show_all.setShortcut("Ctrl+0")
    
    def toggle_all():
        docks = win.findChildren(QDockWidget)
        any_hidden = any(not d.isVisible() for d in docks)
        # If any hidden → show all, else hide all
        for d in docks:
            d.setVisible(any_hidden)

    act_show_all.triggered.connect(toggle_all)
    view_menu.addAction(act_show_all)

    #
    # individual 
    #

    for act in win.menuView.actions():
        if act.text() == "(1) Project sample list":
            act.setShortcut("Ctrl+1")
        elif act.text() == "(2) EDF header":
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
        elif act.text() == "(-) Commands":
            act.setShortcut("Ctrl+-")
#            act.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_Question))
        elif act.text() == "(=) Parameters":
            act.setShortcut("Ctrl+=")
            #act.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_Exclam))

    return act_show_all

    
