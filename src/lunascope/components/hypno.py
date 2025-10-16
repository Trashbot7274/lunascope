import pandas as pd
import numpy as np
import lunapi as lp

from PySide6.QtWidgets import QApplication, QVBoxLayout, QTableView
from PySide6.QtWidgets import QHeaderView

from .mplcanvas import MplCanvas
from .plts import hypno

class HypnoMixin:

    def _init_hypno(self):
        self.ui.host_hypnogram.setLayout(QVBoxLayout())
        self.hypnocanvas = MplCanvas(self.ui.host_hypnogram)
        self.ui.host_hypnogram.layout().setContentsMargins(0,0,0,0)
        self.ui.host_hypnogram.layout().addWidget( self.hypnocanvas )

        # calc hypnostats
        self.ui.butt_calc_hypnostats.clicked.connect( self._calc_hypnostats )

    # ------------------------------------------------------------
    # Run hypnostats
    # ------------------------------------------------------------

    def _calc_hypnostats(self):

        # clear items first
        self.hypnocanvas.ax.cla()
        self.hypnocanvas.figure.canvas.draw_idle()
        
        # test if we have somebody attached        
        if not hasattr(self, "p"): return

        # who has staging available
        if not self._has_staging(): return
        
        # make hypnogram
        ss = self.p.stages()
        hypno(ss.STAGE, ax=self.hypnocanvas.ax)
        self.hypnocanvas.draw_idle()
        
        # Luna call to get full HYPNO outputs
        res = self.p.silent_proc( 'EPOCH align & HYPNO' )
        
        df1 = self.p.table( 'HYPNO' )
        df2 = self.p.table( 'HYPNO' , 'SS' )
        df3 = self.p.table( 'HYPNO' , 'C' )
        
        # populate tables
        df1 = df1.T.reset_index()
        df1.columns = ["Variable", "Value"]        
        model = self.df_to_model( df1 )
        self.ui.tbl_hypno1.setModel( model )
        view = self.ui.tbl_hypno1
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSortingEnabled(True)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        view.resizeColumnsToContents()

        # populate stage table
        df2 = df2.drop(columns=["ID"])
        model = self.df_to_model( df2 )
        self.ui.tbl_hypno2.setModel( model )
        view = self.ui.tbl_hypno2
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        view.resizeColumnsToContents()

        # populate cycle table
        df3 = df3.drop(columns=["ID"])
        model = self.df_to_model( df3 )
        self.ui.tbl_hypno3.setModel(model)
        view = self.ui.tbl_hypno3
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        view.resizeColumnsToContents()
        
        # channel details
#        df = self.p.table( 'HEADERS' , 'CH' )        
#        df = df[ [ 'CH' , 'PDIM' , 'SR' , 'PMIN', 'PMAX' ] ]
#        model = self.df_to_model( df )
#        self.ui.tbl_desc_signals.setModel( model )

        
        
