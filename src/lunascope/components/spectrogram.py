
import lunapi as lp

from PySide6.QtWidgets import QApplication, QVBoxLayout, QTableView

from .mplcanvas import MplCanvas
from .plts import plot_hjorth, plot_spec


class SpecMixin:

    def _init_spec(self):

        self.ui.host_spectrogram.setLayout(QVBoxLayout())
        self.spectrogramcanvas = MplCanvas(self.ui.host_spectrogram)
        self.ui.host_spectrogram.layout().setContentsMargins(0,0,0,0)
        self.ui.host_spectrogram.layout().addWidget( self.spectrogramcanvas )

        # wiring
        self.ui.butt_spectrogram.clicked.connect( self._calc_spectrogram )
        self.ui.butt_hjorth.clicked.connect( self._calc_hjorth )

    def _update_spectrogram_list(self):
        # list all channels with sample frequencies > 32 Hz
        df = self.p.headers()
        chs = df.loc[df['SR'] >= 32, 'CH'].tolist()
        self.ui.combo_spectrogram.addItems( chs )
        
    # ------------------------------------------------------------
    # Caclculate a spectrogram
    # ------------------------------------------------------------

    def _calc_spectrogram(self):

        # get current channel
        ch = self.ui.combo_spectrogram.currentText()

        # check it still exists in the in-memory EDF
        if ch not in self.p.edf.channels():
            return
        
        # plot
        plot_spec( ch , ax=self.spectrogramcanvas.ax , p = self.p , gui = self.ui )
        self.spectrogramcanvas.draw_idle()

    def _calc_hjorth(self):
        ch = self.ui.combo_spectrogram.currentText()

        # check it still exists in the in-memory EDF                                                                                                                     
        if ch not in self.p.edf.channels():
            return

        plot_hjorth( ch , ax=self.spectrogramcanvas.ax , p = self.p , gui = self.ui )
        self.spectrogramcanvas.draw_idle()

    
    



       

    




   
