

from PySide6.QtWidgets import QApplication, QVBoxLayout, QTableView
from PySide6.QtCore import Qt

from .mplcanvas import MplCanvas
from .plts import hypno_density
import pandas as pd

class SoapPopsMixin:

    def _has_staging(self):
        if not hasattr(self, "p"): return False
        self.p.eval( 'CONTAINS stages' )
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

        # wiring
        self.ui.butt_soap.clicked.connect( self._calc_soap )
        self.ui.butt_pops.clicked.connect( self._calc_pops )
        
        
    def _update_soap_list(self):
        if not hasattr(self, "p"): return
        # list all channels with sample frequencies > 32 Hz 
        df = self.p.headers()
        chs = df.loc[df['SR'] >= 32, 'CH'].tolist()
        self.ui.combo_soap.addItems( chs )
        self.ui.combo_pops.addItems( chs )

        
    # ------------------------------------------------------------
    # Run SOAP
    # ------------------------------------------------------------

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
        model = self.df_to_model( df )
        self.ui.tbl_soap1.setModel( model )

        # epoch-level outputs
#        df = self.p.table( 'SOAP' , 'CH_E' )
#        df = df[ [ 'PRIOR', 'PRED' , 'PP_N1' , 'PP_N2', 'PP_N3', 'PP_R', 'PP_W' , 'DISC' ] ] 
#        hypno_density( df , ax=self.soapcanvas.ax)
#        self.soapcanvas.draw_idle()
#       
#        model = self.df_to_model( df )
#        self.ui.tbl_soap_epochs.setModel( model )
#        view = self.ui.tbl_soap_epochs
#        view.verticalHeader().setVisible(False)
#        view.resizeColumnsToContents()

        
    # ------------------------------------------------------------
    # Run POPS
    # ------------------------------------------------------------

    def _calc_pops(self):

        if not hasattr(self, "p"): return
        
        # paraters
        pops_chs = self.ui.combo_pops.currentText()
        if type( pops_chs ) is str: pops_chs = [ pops_chs ] 
        pops_chs = ",".join( pops_chs )
        print( pops_chs ) 

        pops_path = self.ui.txt_pops_path.text()
        pops_model = self.ui.txt_pops_model.text()
        ignore_obs = self.ui.check_pops_ignore_obs.checkState() == Qt.Checked

        has_staging = self._has_staging()
        # requires staging
        if not has_staging:
            ignore_obs = True
        
        # run POPS
        cmd_str = 'EPOCH align & RUN-POPS sig=' + pops_chs + ' path=' + pops_path + ' model=' + pops_model 
        self.p.eval( cmd_str )

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
        # epoch table
        model = self.df_to_model( df )
        self.ui.tbl_pops_epochs.setModel( model )
        view = self.ui.tbl_pops_epochs
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()

        # other stats
