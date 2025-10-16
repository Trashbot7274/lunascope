
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

from PySide6.QtWidgets import QVBoxLayout, QHeaderView, QMessageBox
from PySide6.QtCore import Qt

from .mplcanvas import MplCanvas
from .plts import hypno

class HypnoMixin:

    def _init_hypno(self):

        self.ui.host_hypnogram.setLayout(QVBoxLayout())
        self.hypnocanvas = MplCanvas(self.ui.host_hypnogram)
        self.ui.host_hypnogram.layout().setContentsMargins(0,0,0,0)
        self.ui.host_hypnogram.layout().addWidget( self.hypnocanvas )

        # wiring
        self.ui.butt_calc_hypnostats.clicked.connect( self._calc_hypnostats )


    # ------------------------------------------------------------
    # Run hypnostats

    def _calc_hypnostats(self):

        # clear items first
        self.hypnocanvas.ax.cla()
        self.hypnocanvas.figure.canvas.draw_idle()
        
        # test if we have somebody attached        
        if not hasattr(self, "p"): return

        # who has at least some staging available
        if not self._has_staging(): return
        
        # make hypnogram
        ss = self.p.stages()
        hypno(ss.STAGE, ax=self.hypnocanvas.ax)
        self.hypnocanvas.draw_idle()
        
        # add annotations?
        cmd_str = 'EPOCH align & HYPNO'

        if self.ui.check_hypno_annots.isChecked():
            cmd_str += " annot"

        # lights
        if self.ui.check_lights_out.isChecked():
            dt = self.ui.dt_lights_out.dateTime()
            s = dt.toString("dd/MM/yy-HH:mm:ss")
            cmd_str += " lights-off="+s
            
        if self.ui.check_lights_on.isChecked():
            dt = self.ui.dt_lights_on.dateTime()
            s = dt.toString("dd/MM/yy-HH:mm:ss")
            cmd_str += " lights-on="+s

        # Luna call to get full HYPNO outputs
        try:
            res = self.p.silent_proc(cmd_str)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Problem running HYPNO:\n{cmd_str}\nCommand failed:\n{e}",
            )
            return

        # get outputs        
        df1 = self.p.table( 'HYPNO' )
        df2 = self.p.table( 'HYPNO' , 'SS' )
        df3 = self.p.table( 'HYPNO' , 'C' )

        # update annot list?
        if self.ui.check_hypno_annots.isChecked():
            self._update_metrics()
       
        # possible that df2 and df3 will be empty - i.e. if only W
        
        # populate tables
        if df1.empty: return
        df1 = df1.T.reset_index()
        df1.columns = ["Variable", "Value"]        
        df1 = df1[df1.iloc[:, 0] != "ID"]
        model = self.df_to_model( df1 )
        self.ui.tbl_hypno1.setModel( model )
        view = self.ui.tbl_hypno1
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        view.resizeColumnsToContents()
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # populate stage table
        if df2.empty: return
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
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # populate cycle table
        if df3.empty: return
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
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
