import pandas as pd
import numpy as np
import lunapi as lp

from PySide6.QtWidgets import QApplication, QVBoxLayout, QTableView

from .mplcanvas import MplCanvas

@staticmethod
def hypno(ss, e=None, ax=None, *, title=None, xsize=20, ysize=2, clear=True):
    """Plot a hypnogram into an existing Axes if provided."""
    ssn = lp.stgn(ss)
    if e is None:
        e = np.arange(len(ssn), dtype=float)
    e = e / 120.0

    created = False
    if ax is None:
        fig, ax = plt.subplots(figsize=(xsize, ysize))
        created = True
    elif clear:
        ax.clear()

    ax.plot(e, ssn, color='gray', linewidth=0.5, zorder=2)
    ax.scatter(e, ssn, c=lp.stgcol(ss), s=10, zorder=3)
    ax.set_ylabel('Sleep stage')
    ax.set_xlabel('Time (hrs)')
    ax.set_ylim(-3.5, 2.5)
    ax.set_xlim(0, float(np.nanmax(e)))
    ax.set_yticks([-3, -2, -1, 0, 1, 2], labels=['N3','N2','N1','R','W','?'])
    if title:
        ax.set_title(title)
    return ax  # caller decides whether to draw

            
            
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

        if not self._has_staging(): return

        # Luna command to generate hypno stats
        ss = self.p.stages()
        hypno(ss.STAGE, ax=self.hypnocanvas.ax)
        self.hypnocanvas.draw_idle()

        # get details
        self.p.eval( 'EPOCH align & HYPNO' )

        df1 = self.p.table( 'HYPNO' )
        df2 = self.p.table( 'HYPNO' , 'SS' )
        df3 = self.p.table( 'HYPNO' , 'C' )
        df4 = self.p.table( 'HYPNO' , 'E' )
        print(df1)
        
        # channel details
#        df = self.p.table( 'HEADERS' , 'CH' )        
#        df = df[ [ 'CH' , 'PDIM' , 'SR' , 'PMIN', 'PMAX' ] ]
#        model = self.df_to_model( df )
#        self.ui.tbl_desc_signals.setModel( model )

        # annotations
#        df = self.p.annots()
#        model = self.df_to_model( df )
#        self.ui.tbl_desc_annots.setModel( model )
        
        
