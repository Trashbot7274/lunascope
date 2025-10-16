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

from PySide6.QtWidgets import QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt
import os
from pathlib import Path
import pandas as pd

from .mplcanvas import MplCanvas
from .plts import hypno_density, hypno
        
class SoapPopsMixin:

    def _has_staging(self):
        if not hasattr(self, "p"): return False
        res = self.p.silent_proc( 'CONTAINS stages' )
        df = self.p.table( 'CONTAINS' )
        has_staging = df.at[df.index[0], "STAGES"] == 1
        return has_staging
    
    def _init_soap_pops(self):

        # SOAP hypnodensity plot
        self.ui.host_soap.setLayout(QVBoxLayout())
        self.soapcanvas = MplCanvas(self.ui.host_soap)
        self.ui.host_soap.layout().setContentsMargins(0,0,0,0)
        self.ui.host_soap.layout().addWidget( self.soapcanvas )
        
        # POPS hypnodensity plot
        self.ui.host_pops.setLayout(QVBoxLayout())
        self.popscanvas = MplCanvas(self.ui.host_pops)
        self.ui.host_pops.layout().setContentsMargins(0,0,0,0)
        self.ui.host_pops.layout().addWidget( self.popscanvas )

        # POPS hypnogram
        self.ui.host_pops_hypno.setLayout(QVBoxLayout())
        self.popshypnocanvas = MplCanvas(self.ui.host_pops)
        self.ui.host_pops_hypno.layout().setContentsMargins(0,0,0,0)
        self.ui.host_pops_hypno.layout().addWidget( self.popshypnocanvas )
        
        # wiring
        self.ui.butt_soap.clicked.connect( self._calc_soap )
        self.ui.butt_pops.clicked.connect( self._calc_pops )
        
        
    def _update_soap_list(self):
        if not hasattr(self, "p"): return
        # list all channels with sample frequencies > 32 Hz 
        df = self.p.headers()

        if df is not None:
            chs = df.loc[df['SR'] >= 32, 'CH'].tolist()
        else:
            chs = [ ]
            
        self.ui.combo_soap.addItems( chs )
        self.ui.combo_pops.addItems( chs )

        
    # ------------------------------------------------------------
    # Run SOAP

    def _calc_soap(self):

        # requires attached individal
        if not hasattr(self, "p"): return
        
        # requires staging
        if not self._has_staging():
            return

        # paraters
        soap_ch = self.ui.combo_soap.currentText()
        soap_pc = self.ui.spin_soap_pc.value()

        # run SOAP
        cmd_str = 'EPOCH align & SOAP sig=' + soap_ch + ' epoch pc=' + str(soap_pc)
        self.p.eval( cmd_str )

        # channel details
        df = self.p.table( 'SOAP' , 'CH' )        
        df = df[ [ 'K' , 'K3' , 'ACC', 'ACC3' ] ]
        for c in df.columns:
            try:
                df[c] = pd.to_numeric(df[c])
            except Exception:
                pass
        for c in df.select_dtypes(include=['float', 'float64', 'float32']).columns:
            df[c] = df[c].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
        model = self.df_to_model( df )
        self.ui.tbl_soap1.setModel( model )

        view = self.ui.tbl_soap1
        h = view.horizontalHeader()
        #h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(50)
        h.setDefaultSectionSize(100)
        view.resizeColumnsToContents()
        #view.setSelectionBehavior(QAbstractItemView.SelectRows)
        #view.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # hypnodensities
        df = self.p.table( 'SOAP' , 'CH_E' )
        df = df[ [ 'PRIOR', 'PRED' , 'PP_N1' , 'PP_N2', 'PP_N3', 'PP_R', 'PP_W' , 'DISC' ] ]                                                     
        hypno_density( df , ax=self.soapcanvas.ax)                                                                                               
        self.soapcanvas.draw_idle()                                                                                                              
               
    # ------------------------------------------------------------
    # Run POPS

    def _calc_pops(self):
      
        if not hasattr(self, "p"): return
        
        # paraters
        pops_chs = self.ui.combo_pops.currentText()
        if type( pops_chs ) is str: pops_chs = [ pops_chs ] 
        pops_chs = ",".join( pops_chs )

        pops_path = self.ui.txt_pops_path.text()
        pops_model = self.ui.txt_pops_model.text()
        ignore_obs = self.ui.check_pops_ignore_obs.checkState() == Qt.Checked

        has_staging = self._has_staging()
        # requires staging
        if not has_staging:
            ignore_obs = True
        
        # run POPS

        #test if file exists
        # pops_mod = os.path.join( pops_path, pops_model+ ".mod")
        # make more robust - and expand ~ --> user dir
        base = Path(pops_path).expanduser()
        base = Path(os.path.expandvars(str(base))).resolve()   # absolute
        pops_mod = base / f"{str(pops_model).strip()}.mod"

        if not pops_mod.is_file():
            QMessageBox.critical(
                None,
                "Error",
                "Could not open POPS files; double check file path"
            )
            return None


        try:
            cmd_str = 'EPOCH align & RUN-POPS sig=' + pops_chs + ' path=' + pops_path + ' model=' + pops_model
            self.p.eval( cmd_str )
        except (RuntimeError) as e:
            QMessageBox.critical(
                None,
                "Error running POPS",
                f"Exception: {type(e).__name__}: {e}"
            )


        # outputs

        df1 = self.p.table( 'RUN_POPS' )
        df2 = self.p.table( 'RUN_POPS' , 'SS' )
        
        # main output table (tbl_pops1)
        df = pd.DataFrame(columns=["Variable", "Value"])

        # concordance w/ any existing staging
        if has_staging:
            row = df1.index[0]
            df.loc[len(df)] = ['ACC3', df1.at[row,"ACC3"] ]
            df.loc[len(df)] = ['K3', df1.at[row,"K3"] ]
            df.loc[len(df)] = ['ACC', df1.at[row,"ACC"] ]
            df.loc[len(df)] = ['K', df1.at[row,"K"] ]

        v = df2.loc[df2['SS'].eq('W'), 'PR1']
        df.loc[len(df)] = ['TWT (mins)', (float(v.iloc[0]) if not v.empty else np.nan)]

        v = df2.loc[df2['SS'].eq('N1'), 'PR1']
        df.loc[len(df)] = ['N1 (mins)', (float(v.iloc[0]) if not v.empty else np.nan)]

        v = df2.loc[df2['SS'].eq('N2'), 'PR1']
        df.loc[len(df)] = ['N2 (mins)', (float(v.iloc[0]) if not v.empty else np.nan)]

        v = df2.loc[df2['SS'].eq('N3'), 'PR1']
        df.loc[len(df)] = ['N3 (mins)', (float(v.iloc[0]) if not v.empty else np.nan)]

        v = df2.loc[df2['SS'].eq('R'), 'PR1']
        df.loc[len(df)] = ['R (mins)', (float(v.iloc[0]) if not v.empty else np.nan)]

        model = self.df_to_model( df )
        self.ui.tbl_pops1.setModel( model )        
            
        # epoch-level outputs
        df = self.p.table( 'RUN_POPS' , 'E' )
        if has_staging:
            df = df[ [ 'E', 'START', 'PRIOR', 'PRED' , 'PP_N1' , 'PP_N2', 'PP_N3', 'PP_R', 'PP_W'  ] ]
        else:
            df = df[ [ 'E', 'START', 'PRED' , 'PP_N1' , 'PP_N2', 'PP_N3', 'PP_R', 'PP_W'  ] ]
        hypno_density( df , ax=self.popscanvas.ax)
        # plot
        self.popscanvas.draw_idle()        

        # hypnogram
        hypno( df.PRED , ax=self.popshypnocanvas.ax)
        self.popshypnocanvas.draw_idle()

