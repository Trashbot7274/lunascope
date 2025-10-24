
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

from  .helpers import clear_rows, add_dock_shortcuts

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
                        "<p>Documentation:<br> <a href='http://zzz-luna.org/lunascope'>"
                        "http://zzz-luna.org/lunascope</a></p>"
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
        self._render_hypnogram()
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


        #clear_rows( self.ui.tbl_desc_signals )
        #clear_rows( self.ui.tbl_desc_annots )

        if getattr(self, "signals_table_proxy", None) is not None:
            clear_rows( self.signals_table_proxy )

        if getattr(self, "annots_table_proxy", None) is not None:
            clear_rows( self.annots_table_proxy )

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
        # self.ui.txt_inp.clear() 
        
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
        

