
import lunapi as lp

from PySide6.QtWidgets import QApplication, QVBoxLayout, QTableView

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import QMainWindow, QProgressBar, QStatusBar
from PySide6 import QtCore, QtWidgets, QtGui

from pyqtgraph.exporters import ImageExporter, SVGExporter

#from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import io

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

        # context menu
        self.spectrogramcanvas.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.spectrogramcanvas.customContextMenuRequested.connect(self._spec_context_menu)


    def _spec_context_menu(self, pos):
        menu = QtWidgets.QMenu(self.spectrogramcanvas)
        act_copy = menu.addAction("Copy to Clipboard")
        act_save = menu.addAction("Save Figure…")
        action = menu.exec(self.spectrogramcanvas.mapToGlobal(pos))
        if action == act_copy:
            self._spec_copy_to_clipboard()
        elif action == act_save:
            self._spec_save_figure()

    def _spec_copy_to_clipboard(self):
        buf = io.BytesIO()
        self.spectrogramcanvas.figure.savefig(buf, format="png", bbox_inches="tight")
        img = QtGui.QImage.fromData(buf.getvalue(), "PNG")
        QtWidgets.QApplication.clipboard().setImage(img)

    def _spec_save_figure(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.spectrogramcanvas,
            "Save Figure",
            "spectrogram",
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)"
        )
        if not fn:
            return
        self.spectrogramcanvas.figure.savefig(fn, bbox_inches="tight")

        
            
        
    def _update_spectrogram_list(self):
        # list all channels with sample frequencies > 32 Hz
        df = self.p.headers()

        if df is not None:
            chs = df.loc[df['SR'] >= 32, 'CH'].tolist()
        else:
            chs = [ ] 
        
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

        plot_spec( ch , ax=self.spectrogramcanvas.ax , p = self.p , gui = self.ui )

        self.spectrogramcanvas.draw_idle()

        
        

    def _calc_hjorth(self):
        ch = self.ui.combo_spectrogram.currentText()

        # check it still exists in the in-memory EDF                                          
        if ch not in self.p.edf.channels():
            return

        plot_hjorth( ch , ax=self.spectrogramcanvas.ax , p = self.p , gui = self.ui )
        self.spectrogramcanvas.draw_idle()

    
    



   
