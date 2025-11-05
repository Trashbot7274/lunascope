
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
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

import pyqtgraph as pg

from  .helpers import clear_rows, add_dock_shortcuts, pick_two_colors, override_colors, random_darkbg_colors

from .components.slist import SListMixin
from .components.metrics import MetricsMixin
from .components.hypno import HypnoMixin
from .components.anal import AnalMixin
from .components.signals import SignalsMixin
from .components.settings import SettingsMixin
from .components.masks import MasksMixin
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
                  SpecMixin , MasksMixin ):

    def __init__(self, ui, proj):
        super().__init__()

        # GUI
        self.ui = ui

        # Luna
        self.proj = proj
        
        # send compute to a different thread
        self._exec = ThreadPoolExecutor(max_workers=1)
        self._busy = False

        # setups
        self._init_colors()
        
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
        self._init_masks()
        
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
        self.ui.menuView.addAction(self.ui.dock_annot.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_annots.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_spectrogram.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_hypno.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_mask.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_console.toggleViewAction())
        self.ui.menuView.addAction(self.ui.dock_outputs.toggleViewAction())
        self.ui.menuView.addSeparator()
        self.ui.menuView.addAction(self.ui.dock_help.toggleViewAction())

        # set up menu: about
        act_about = QAction("Help", self)

        act_about.triggered.connect( self.show_about )
        
        # palette menu
        act_pal_spectrum = QAction("Spectrum", self)
        act_pal_white    = QAction("White", self)
        act_pal_muted    = QAction("Muted", self)
        act_pal_black    = QAction("Black", self)
        act_pal_random   = QAction("Random", self)
        act_pal_load     = QAction("Bespoke (load)", self)
        act_pal_bespoke  = QAction("Bespoke (apply)", self)
        act_pal_user     = QAction("Pick", self)

        act_pal_spectrum.triggered.connect(self._set_spectrum_palette)
        act_pal_white.triggered.connect(self._set_white_palette)
        act_pal_muted.triggered.connect(self._set_muted_palette)
        act_pal_black.triggered.connect(self._set_black_palette)
        act_pal_random.triggered.connect(self._set_random_palette)
        act_pal_load.triggered.connect(self._load_palette)
        act_pal_load.triggered.connect(self._set_bespoke_palette)
        act_pal_user.triggered.connect(self._select_user_palette)
        
        self.ui.menuPalettes.addAction(act_pal_spectrum)
        self.ui.menuPalettes.addAction(act_pal_white)
        self.ui.menuPalettes.addAction(act_pal_muted)
        self.ui.menuPalettes.addAction(act_pal_black)
        self.ui.menuPalettes.addAction(act_pal_random)
        self.ui.menuPalettes.addSeparator()
        self.ui.menuPalettes.addAction(act_pal_user)
        self.ui.menuPalettes.addSeparator()
        self.ui.menuPalettes.addAction(act_pal_load)
        self.ui.menuPalettes.addAction(act_pal_bespoke)
        
        # about menu
        self.ui.menuAbout.addAction(act_about)   

        # window title
        self.ui.setWindowTitle(f"Lunascope v{__version__}")

        # add QSplitter for console
        container = self.ui.console_splitter
        layout = container.layout()  # that's your console_layout
        splitter = QSplitter(Qt.Vertical)
        self.ui.txt_out.setParent(None)
        self.ui.txt_inp.setParent(None)
        splitter = QSplitter(Qt.Vertical, container)
        splitter.addWidget(self.ui.txt_out)
        splitter.addWidget(self.ui.txt_inp)
        layout.addWidget(splitter)
        
        # add QSplitter for output
        container2 = self.ui.anal_out_frame
        layout2 = container2.layout()  # that's your console_layout
        self.ui.anal_tables.setParent(None)
        self.ui.anal_right_table.setParent(None)
        splitter2 = QSplitter(Qt.Horizontal, container2)
        splitter2.addWidget(self.ui.anal_tables)
        splitter2.addWidget(self.ui.anal_right_table)
        layout2.addWidget(splitter2)

        # short keyboard cuts
        add_dock_shortcuts( self.ui, self.ui.menuView )

        # arrange docks: hide some docks
        self.ui.dock_help.hide()
        self.ui.dock_console.hide()
        self.ui.dock_outputs.hide()
        
        # arrange docks: lock and resize
        self.ui.setCorner(Qt.TopRightCorner,    Qt.RightDockWidgetArea)
        self.ui.setCorner(Qt.BottomRightCorner, Qt.RightDockWidgetArea)

        # arrange docks: lower docks (console/output)
        w = self.ui.width()

        self.ui.resizeDocks([ self.ui.dock_console , self.ui.dock_outputs ],
                            [ int(w*0.6), int(w*0.4)], Qt.Horizontal)

        # arrange docks: left docks (samples, settings)
        self.ui.resizeDocks([ self.ui.dock_slist , self.ui.dock_settings ],
                            [int(w*0.7), int(w*0.3) ], Qt.Vertical )

        
        # arrange docks: right docks (signals, annots, events)
        h = self.ui.height()
        self.ui.resizeDocks([ self.ui.dock_sig, self.ui.dock_annot, self.ui.dock_annots , self.ui.dock_mask ] , 
                            [  int(h*0.35), int(h*0.25), int(h*0.1) , int(h*0.1) ],
                            Qt.Vertical)
        w_right = 380
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

        # initiate graphs
        self.curves = [ ]
        self.annot_curves = [ ] 

        # and update things that need updating
        self._update_metrics()
        self._render_hypnogram()
        self._update_spectrogram_list()
        self._update_mask_list()
        self._update_soap_list()
        self._update_params()

        # initially, no signals rendered / not rendered / not current
        self._set_render_status( False , False )

        # draw
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

        # filters: chennels -> filters
        self.fmap = { } 

        # filter label -> frqs
        self.fmap_frqs = {
            "0.3-35Hz": [0.3,35] ,
            "Slow": [0.5,1] ,
            "Delta": [1,4],
            "Theta": [4,8],
            "Alpha": [8,11],
            "Sigma": [11,15],
            "Beta": [15,30] ,
            "Gamma": [30,50] } 

        # SR + label --> butterworth model
        self.fmap_flts = { } 

    #
    # helper to handle render button
    #


    def _set_render_status(self, rendered , current ):
        # three modes:
        #   initial (pg1_simple)     not rendered (ignore changed) --> red
        #   post render              render and not changed        --> green
        #   post render, post Exec   render and changed            --> amber
        
        self.rendered = rendered
        self.current  = current

        if self.rendered:
            if self.current:
                self.ui.butt_render.setStyleSheet("background-color: #2E8B57; color: #FFFFFF;")
            else:
                self.ui.butt_render.setStyleSheet("background-color: #FFC107; color: #5C0000;")
        else:
            self.ui.butt_render.setStyleSheet("background-color: #F8F8F8; color: #8B0000;")

            
    #
    # handle palettes
    #

    def _init_colors(self):

        self.cmap = {}

        self.cmap_list = [ ]
        self.cmap_rlist = [ ] 

        self.stgcols_hex = {
            'N1': '#20B2DA',  # rgba(32,178,218,1)
            'N2': '#0000FF',  # blue
            'N3': '#000080',  # navy
            'R':  '#FF0000',  # red
            'W':  '#008000',  # green (CSS "green")
            '?':  '#808080',  # gray
            'L':  '#FFFF00',  # yellow
        }

        
    def _set_default_palette(self):        
        if not hasattr(self, 'palset'):
            self._set_spectrum_palette()
            self.palset = 'spectrum'


    def set_palette(self):
        if not hasattr(self, 'palset'):
            self._set_default_palette()
        if self.palset == 'spectrum': self._set_spectrum_palette()
        if self.palset == 'white': self._set_white_palette()
        if self.palset == 'black': self._set_black_palette()
        if self.palset == 'muted': self._set_muted_palette()
        if self.palset == 'random': self._set_random_palette()
        if self.palset == 'bespoke': self._set_bespoke_palette()
        if self.palset == 'user': self._set_user_palette()
            
    def _set_spectrum_palette(self):
        self.palset = 'spectrum'
        self.ui.pg1.setBackground('black')        
        nchan = len( self.ui.tbl_desc_signals.checked() )
        self.colors = [pg.intColor(i, hues=nchan) for i in range(nchan)]
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = [pg.intColor(i, hues=nanns) for i in range(nanns)]
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()
        
    def _set_white_palette(self):        
        self.palset = 'white'
        self.ui.pg1.setBackground('#E0E0E0')
        nchan = len( self.ui.tbl_desc_signals.checked() )      
        self.colors = ['#101010'] * nchan
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = ['#101010'] * nanns
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()

    def _set_muted_palette(self):
        self.palset = 'muted'
        self.ui.pg1.setBackground('#E0E0E0')
        nchan = len( self.ui.tbl_desc_signals.checked() )
        self.colors = ['#101010'] * nchan
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = ['#101010'] * nanns
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()

    def _set_black_palette(self):
        self.palset = 'black'
        self.ui.pg1.setBackground('#101010')
        nchan = len( self.ui.tbl_desc_signals.checked() )
        self.colors = ['#E0E0E0'] * nchan
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = ['#E0E0E0'] * nanns
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()
        
    def _set_random_palette(self):
        self.palset = 'random'
        self.ui.pg1.setBackground('#101010')
        nchan = len( self.ui.tbl_desc_signals.checked() )
        self.colors = random_darkbg_colors( nchan )
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = random_darkbg_colors( nanns )
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()

    def _select_user_palette(self):
        self.palset = 'user'
        self.c1, self.c2 = pick_two_colors()
        self.ui.pg1.setBackground(self.c1)
        nchan = len( self.ui.tbl_desc_signals.checked() )
        self.colors = [self.c2] * nchan
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = [self.c2] * nanns
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()

    def _set_user_palette(self):
        self.palset = 'user'
        # assume self.c1 and self.c2 already set
        #self.c1, self.c2 = pick_two_colors()
        self.ui.pg1.setBackground(self.c1)
        nchan = len( self.ui.tbl_desc_signals.checked() )
        self.colors = [self.c2] * nchan
        anns = self.ui.tbl_desc_annots.checked()
        nanns = len( anns )
        self.acolors = [self.c2] * nanns
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()
        
    def _set_bespoke_palette(self):        
        # back default black (i.e. for things not seen)
        self._set_black_palette()
        self.palset = 'bespoke'
        chs = self.ui.tbl_desc_signals.checked()
        # re-order list
        if self.cmap_list:
            chs = sorted( chs, key=lambda x: (self.cmap_list.index(x) if x in self.cmap_list else len(self.cmap_list) + chs.index(x)))
            chs.reverse()
        nchan = len( chs )
        # set signal colors
        self.colors = override_colors(self.colors, chs, self.cmap)
        # and annots
        anns = self.ui.tbl_desc_annots.checked()
        if self.cmap_rlist:
            anns = sorted( anns, key=lambda x: (self.cmap_list.index(x) if x in self.cmap_list else len(self.cmap_list) + anns.index(x)))
        self.acolors = override_colors(self.acolors, anns, self.cmap)
        self.acolors = self._update_stage_cols( self.acolors , anns )
        self._update_cols()


    def _update_stage_cols(self,pal,anns):
        return [self.stgcols_hex.get(a_i, p_i) for a_i, p_i in zip(anns, pal)]

    
    def _load_palette(self):
        txt_file, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Open color map",
            "",
            "Text (*.txt);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if txt_file:
            try:
                text = open(txt_file, "r", encoding="utf-8").read()
                
                self.cmap = {}
                self.cmap_list = [ ]
                self.cmap_rlist = [ ] 
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.replace("=", " ").replace("\t", " ").split()
                    if len(parts) >= 2:
                        self.cmap[parts[0]] = parts[1]
                        self.cmap_list.append( parts[0] )

                # reverse order (for plotting goes y 0 - 1 is bottom - top currently
                # and can't be bothered to fix
                self.cmap_rlist = list(reversed(self.cmap_list))
                
                # and set them
                self._set_bespoke_palette()
                
            except (UnicodeDecodeError, OSError) as e:
                QMessageBox.critical(
                    None,
                    "Error opening color map",
                    f"Could not load {txt_file}\nException: {type(e).__name__}: {e}"
                )
            
    def _update_cols(self):
        for c, col in zip(self.curves, self.colors):
            c.setPen(pg.mkPen(col, width=1, cosmetic=True))
        for c, col in zip(self.annot_curves, self.acolors):
            c.setPen(pg.mkPen(col, width=1, cosmetic=True))

                
        
    def show_about(self):
        box = QMessageBox(self)
        box.setWindowTitle("About Lunascope")
        box.setIcon(QMessageBox.Information)
        box.setTextFormat(Qt.RichText)

        # compute versions
        x = lp.version()  # { lunapi:ver, luna:ver }
        box.setText(
            f"<p>Lunascope v{__version__}</p>"
            f"<p>Lunapi {x['lunapi']}</p>"
            f"<p>Luna {x['luna']}</p>"
            "<p>Documentation:<br> <a href='http://zzz-luna.org/lunascope'>"
            "http://zzz-luna.org/lunascope</a></p>"
            "<p>Created by Shaun Purcell</p>"
            "<p>Developed and maintained by Lorcan Purcell</p>"
        )

        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        box.layout().setSizeConstraint(QLayout.SetMinimumSize)

        lbl = box.findChild(QLabel)
        if lbl:
            lbl.setOpenExternalLinks(True)

        box.exec()

