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

import lunapi as lp

import pandas as pd
import numpy as np
from collections import defaultdict

from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QMetaObject, Qt, Slot

import pyqtgraph as pg
from PySide6.QtWidgets import QProgressBar
from PySide6.QtCore import QSignalBlocker

class SignalsMixin:

    def _init_signals(self):

        # hypnogram / navigator
        h = self.ui.pgh
        h.showAxis('left', False)
        h.showAxis('bottom', False)
        h.setMenuEnabled(False)
        h.setMouseEnabled(x=False, y=False)
        
        # pg1 - main signals
        # pgh - hypnogram, controls view on pg1
        
        self.ui.butt_render.clicked.connect( self._render_signals )

        # pyqtgraph config options
        pg.setConfigOptions(useOpenGL=False, antialias=False)  
        
        # pg1 properties
        pw = self.ui.pg1   
        pw.setXRange(0, 1, padding=0)   
        pw.setYRange(0, 1, padding=0)
        pw.showAxis('left', False)
        pw.showAxis('bottom', False)
        vb = pw.getViewBox()
        vb.enableAutoRange('x', False)
        vb.enableAutoRange('y', False)

        # disable mouse pan/zoom
        vb.setMouseEnabled(x=False, y=False)   # disables drag + wheel zoom
        vb.wheelEvent = lambda ev: None        # belt-and-suspenders on some styles
        vb.mouseDragEvent = lambda ev: None
        vb.setMenuEnabled(False)               # optional: no context menu

        pi = pw.getPlotItem()
        pi.enableAutoRange('xy', False)   # or: pi.disableAutoRange()
        pi.autoBtn.hide()                 # prevents UI trigger
        pi.disableAutoRange()
        pi.hideButtons()          # use this, not pi.autoBtn.hide()
        
        # cols
        self.stgcols_hex = {
            'N1': '#20B2DA',  # rgba(32,178,218,1)
            'N2': '#0000FF',  # blue
            'N3': '#000080',  # navy
            'R':  '#FF0000',  # red
            'W':  '#008000',  # green (CSS "green")
            '?':  '#808080',  # gray
            'L':  '#FFFF00',  # yellow
        }


        self.ui.spin_spacing.valueChanged.connect( self._update_scaling )
        self.ui.spin_scale.valueChanged.connect( self._update_scaling )

        self.ui.spin_fixed_max.valueChanged.connect( self._update_scaling )
        self.ui.spin_fixed_min.valueChanged.connect( self._update_scaling )

        self.ui.radio_fixedscale.clicked.connect( self._update_scaling )
        self.ui.radio_clip.clicked.connect( self._update_scaling )
        self.ui.radio_empiric.clicked.connect( self._update_scaling )
        self.ui.check_labels.clicked.connect( self._update_labels )
        


        
    # --------------------------------------------------------------------------------
    #
    # on attach new EDF --> initiate segsrv_t for channel / annotation drawing 
    #
    # --------------------------------------------------------------------------------


    def _render_histogram(self):

        # ------------------------------------------------------------
        # initiate segsrv 
        # ------------------------------------------------------------
        
        self.ss = lp.segsrv( self.p )
                
        # view 'epoch' is fixed at 30 seconds
        scope_epoch_sec = 30 

        # last time-point (secs)
        nsecs_clk = self.ss.num_seconds_clocktime_original()

        # number of scope-epochs (i.e. fixed at 0, 30s), and seconds
        self.ne = int( nsecs_clk / scope_epoch_sec )
        self.ns = nsecs_clk
                
        # option defaults
        self.show_labels = True
        
        # ------------------------------------------------------------
        # hypnogram init
        # ------------------------------------------------------------

        h = self.ui.pgh
        pi = h.getPlotItem()
        pi.clear()

        vb = pi.getViewBox()

        h.showAxis('left', False)
        h.showAxis('bottom', False)
        h.setMenuEnabled(False)
        h.setMouseEnabled(x=False, y=False)

        pi.showAxis('left', False)
        pi.showAxis('bottom', False)
        pi.hideButtons()
        pi.setMenuEnabled(False)
        pi.layout.setContentsMargins(0, 0, 0, 0)
        pi.setContentsMargins(0, 0, 0, 0)        
        vb.setDefaultPadding(0)
        
        vb.setMouseEnabled(x=False, y=False)
        vb.wheelEvent = lambda ev: ev.accept()
        vb.doubleClickEvent = lambda ev: ev.accept()
        vb.keyPressEvent = lambda ev: ev.accept()   # swallow 'A' and everything else
        
        pi.setXRange(0, self.ns, padding=0)
        pi.setYRange(0, 1, padding=0)
        vb.setLimits(xMin=0, xMax=self.ns, yMin=0, yMax=1)  # prevent programmatic drift

        h.setXRange(0,self.ns)
        h.setYRange(0,1)

        # get full, original staging from annotations
        stgs = [ 'N1' , 'N2' , 'N3' , 'R' , 'W' , '?' , 'L' ] 
#        stgns = { 'N1': 0.2 , 'N2': 0.1 , 'N3': 0 , 'R': 0.3  , 'W': 0.4 , '?': 0.5 , 'L': 0.6 }
        stgns = {'N1': 0.0,
                 'N2': 0.06666666666666667,
                 'N3': 0.13333333333333333,
                'R': 0.2,
                'W': 0.26666666666666666,
                '?': 0.3333333333333333,
                'L': 0.4}

        stg_evts = self.p.fetch_annots( stgs , 30 )
        
        if len( stg_evts ) != 0:
            starts = stg_evts[ 'Start' ].to_numpy()
            stops = stg_evts[ 'Stop' ].to_numpy()
            cols = [ self.stgcols_hex[c] for c in stg_evts['Class'].tolist() ]
            ys = [ stgns[c] for c in stg_evts['Class'].tolist() ]

            # ensure we'll see
            starts, stops = _ensure_min_px_width( vb, starts, stops, px=1)  # 1-px minimum

            # keep in seconds
            x = ( ( starts + stops ) / 2.0 ) 
            w = ( stops - starts ) 

            brushes = [QtGui.QColor(c) for c in cols]   # e.g. "#20B2DA"
            pens    = [None]*len(x)
            
            bins = defaultdict(list)
            for xi, wi, yi, ci in zip(x.tolist(), w.tolist(), ys, cols):
                bins[ci].append((xi, wi, yi ))

            for ci, items in bins.items():
                xi, wi, yi = zip(*items)
                bg = pg.BarGraphItem(
                    x=list(xi), width=list(wi), y0=[ x+0.25 for x in list(yi) ], height=[0.225]*len(xi), 
                    brush=QtGui.QColor(ci), pen=None )                
                bg.setZValue(-10)
                bg.setAcceptedMouseButtons(QtCore.Qt.NoButton)
                bg.setAcceptHoverEvents(False)
                pi.addItem(bg)

        # segment plotter
        pi.plot([0, self.ns], [0.01, 0.01], pen=pg.mkPen(0, 0, 0 ))
        
        # wire up range selector (first wiping existing one, if needed)

        if getattr(self, "sel", None) is not None:
            try:
                self.sel.dispose()
            except Exception:
                pass
            self.sel = None
        
        self.sel = XRangeSelector(h, bounds=(0, self.ns),
                             integer=True,
                             click_span=30.0,
                             min_span=5.0,
                             step=30, big_step=300 )
        
        self.sel.rangeSelected.connect(self.on_window_range)  
        

        # clock ticks at top
        self.tb0 = TextBatch( vb, QtGui.QFont("Arial", 12), color=(180,255,255), mode='device')
        self.tb0.setZValue(10)
        tks = self.ssa.get_hour_ticks()
        tx = list( tks.keys() )
        tv = list( tks.values() )
        tv = [v[:-6] if v.endswith(":00:00") else v for v in tv]  # reduce to | hh
        self.tb0.setData(tx, [ 0.99 ] * len( tx ) , tv )
        self.ui.pgh.addItem(self.tb0 , ignoreBounds=True)

        
    # --------------------------------------------------------------------------------
    #
    # called on first attaching, but also after Render: masked hypnogram + segment plot
    #
    # --------------------------------------------------------------------------------

    def _update_hypnogram(self):

        # writes on the same canvas as the hypnogram above, but only updates the
        # stuff that may change

        h = self.ui.pgh
        pi = h.getPlotItem()
        vb = pi.getViewBox()        
        
        # hypnogram vesion 2
        # get staging (in units no larger than 30 seconds)
        stgs = [ 'N1' , 'N2' , 'N3' , 'R' , 'W' , '?' , 'L' ] 
        stg_evts = self.p.fetch_annots( stgs , 30 )

        # get staging (in units no larger than 30 seconds)
        # use STAGES here so that we only get the unmasked datapoints
        res = self.p.silent_proc( 'EPOCH align verbose & STAGE' )

        if "EPOCH: E" in res:
            df1 = self.p.table( 'EPOCH' , 'E' )
            df1 = df1[ ['E' , 'START' , 'STOP' ] ] 
        else:
            df1 = None
            df1 = pd.DataFrame( columns = [ "E", "OSTAGE" ] )
      
        # if no valid staging, will not have any 'STAGE' output
        tbls = self.p.strata()
        has_staging = (tbls["Command"] == "STAGE").any()
        if has_staging:
            df2 = self.p.table( 'STAGE' , 'E' )
            df2 = df2[ ['E' , 'OSTAGE' ] ]
        else:
            df2 = pd.DataFrame({
                "E": df1["E"],
                "OSTAGE": "?"
            })

        # merge
        df = pd.merge(df1, df2, on="E", how="inner")

        if len( df ) != 0:
            starts = df[ 'START' ].to_numpy()
            stops = df[ 'STOP' ].to_numpy()
            cols = [ self.stgcols_hex[c] for c in df['OSTAGE'].tolist() ]

            # ensure we'll see
            starts, stops = _ensure_min_px_width( vb, starts, stops, px=1)  # 1-px minimum
            
            # keep in seconds
            x = ( ( starts + stops ) / 2.0 ) 
            w = ( stops - starts ) 

            brushes = [QtGui.QColor(c) for c in cols]   # e.g. "#20B2DA"
            pens    = [None]*len(x)
            
            bins = defaultdict(list)
            for xi, wi, ci in zip(x.tolist(), w.tolist(), cols):
                bins[ci].append((xi, wi ))

            # clear if previously added
            if getattr(self, "updated_hypno", None) is not None:
                for it in self.updated_hypno:
                    pi.removeItem(it)
                self.updated_hypno.clear()

            self.updated_hypno = [ ] 

            # staging
            for ci, items in bins.items():
                xi, wi = zip(*items)
                bg = pg.BarGraphItem(
                    x=list(xi), width=list(wi), y0=[0.1] * len(xi), height=[0.05]*len(xi), 
                    brush=QtGui.QColor(ci), pen=None )                
                bg.setZValue(-10)
                bg.setAcceptedMouseButtons(QtCore.Qt.NoButton)
                bg.setAcceptHoverEvents(False)
                pi.addItem(bg)
                self.updated_hypno.append(bg)

            # simple segment plot
            for ci, items in bins.items():
                xi, wi = zip(*items)
                bg = pg.BarGraphItem(
                    x=list(xi), width=list(wi), y0=[0.03] * len(xi), height=[0.05]*len(xi), 
                    brush= '#FFCE1B', pen=None )                
                bg.setZValue(-10)
                bg.setAcceptedMouseButtons(QtCore.Qt.NoButton)
                bg.setAcceptHoverEvents(False)
                pi.addItem(bg)
                self.updated_hypno.append(bg)


        
    # --------------------------------------------------------------------------------
    #
    # click Render --> initiate segsrv_t for channel / annotation drawing 
    #
    # --------------------------------------------------------------------------------
    
    def _populate_segsrv(self):
        # compute on separate thread
        # --> do not touch the GUI here
        
        # pre-calculate any summary stats? [ignore for now]
        #ss.calc_bands( bsigs )
        #ss.calc_hjorths( hsigs )
        throttle1_sr = 100 
        self.ss.input_throttle( throttle1_sr )
        throttle2_np = 5 * 30 * 100 
        self.ss.throttle( throttle2_np )
        summary_mins = 30 
        self.ss.summary_threshold_mins( summary_mins )
        # special version that releases the GIL
        self.ss.segsrv.populate_lunascope( chs = self.ss_chs , anns = self.ss_anns )
        self.ss.set_annot_format6( False ) # pyqtgraph, not plotly
    
    def _render_signals(self):

        # update hypnogram and segment plot
        self._update_hypnogram()
        
        # copy originally selected channels (i.e. as denominator
        # for subsequently drop in/out)
        self.ss_chs = self.ui.tbl_desc_signals.checked()
        self.ss_anns = self.ui.tbl_desc_annots.checked()

        # for a given EDF instance, take selected channels 
        if len( self.ss_chs ) + len( self.ss_anns ) == 0:
            self.rendered = False
            return

        # we're now going to have something to plot
        self.rendered = True

        # ------------------------------------------------------------
        # do rendering on a separate thread

        # ------------------------------------------------------------
        # execute command string 'cmd' in a separate thread

        # note that we're busy
        self._busy = True

        # and do not let other jobs be run
        self._buttons( False )

        # start progress bar
        self.sb_progress.setVisible(True)
        self.sb_progress.setRange(0, 0) 
        self.sb_progress.setFormat("Running…")
        
        # set up call on different thread
        fut_ss = self._exec.submit( self._populate_segsrv )  # returns nothing
                
        def done_segsrv( _f=fut_ss ):
            try:
                exc = _f.exception()
                if exc is None:
                    print( 'all good' ) 
                    # self._last_result = _f.result()  # nothing returned
                    QMetaObject.invokeMethod(self, "_segsrv_done_ok", Qt.QueuedConnection)
                else:
                    self._last_exc = exc
                    self._last_tb = f"{type(exc).__name__}: {exc}"
                    QMetaObject.invokeMethod(self, "_segsrv_done_err", Qt.QueuedConnection)
            except Exception as cb_exc:
                self._last_exc = cb_exc
                self._last_tb = f"{type(cb_exc).__name__}: {cb_exc}"
                QMetaObject.invokeMethod(self, "_segsrv_done_err", Qt.QueuedConnection)

        # add the callback
        fut_ss.add_done_callback( done_segsrv )



    @Slot()
    def _segsrv_done_ok(self):        
        try:
            self._complete_rendering()
        finally:
            self._busy = False
            self._buttons( True )
            self.sb_progress.setRange(0, 100); self.sb_progress.setValue(0)
            self.sb_progress.setVisible(False)
            
    @Slot()
    def _segsrv_done_err(self):
        try:
            # show or log the error; pick one
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error rendering sample", self._last_tb)
        finally:
            self._busy = False
            self._buttons( True )
            self.sb_progress.setRange(0, 100); self.sb_progress.setValue(0)
            self.sb_progress.setVisible(False)

     
    def _complete_rendering(self):

        # we can now touch the GUI
        print( 'done rendering' )
        
        # update segment plot
        self._initiate_curves()        
        
        # plot segments
        num_epochs = self.ss.num_epochs()
        tscale = self.ss.get_time_scale()
        tstarts = [ tscale[idx] for idx in range(0,len(tscale),2)]
        tstops = [ tscale[idx] for idx in range(1,len(tscale),2)]
        times = np.concatenate((tstarts, tstops), axis=1)

        # ready to view
        self.ss.window(0,30)        
        self._update_scaling()
        self._update_pg1()

        
    def on_window_range(self, lo: float, hi: float):

        # time in seconds now
        if lo < 0: lo = 0
        if hi > self.ns: hi = self.ns 
        if hi < lo: hi = lo
        
        # update ss window
        t1 = ""
        t2 = ""        
        if self.rendered is True:
            self.ss.window( lo  , hi )
            t1 = self.ss.get_window_left_hms()
            t2 = self.ss.get_window_right_hms()
        else: # annot only segsrv
            self.ssa.window( lo  , hi )
            t1 = self.ssa.get_window_left_hms()
            t2 = self.ssa.get_window_right_hms()

        self.ui.lbl_twin.setText( f"T: {t1} - {t2}" )
        lo = int(lo/30)+1
        hi = int(hi/30)+1
        self.ui.lbl_ewin.setText( f"E: {lo} - {hi}" )
        self._update_pg1()





    # --------------------------------------------------------------------------------
    #
    # pre-Render plot set up (called on attaching the plot) 
    #
    # --------------------------------------------------------------------------------
    
    def _render_signals_simple(self):

        # update hypnogram and segment plot
        self._update_hypnogram()

        # get all channels
        self.ss_chs = self.p.edf.channels()
        self.ss_anns = self.p.edf.annots()

        #
        # plot segments
        #

        num_epochs = self.ssa.num_epochs()
        tscale = self.ssa.get_time_scale()
        tstarts = [ tscale[idx] for idx in range(0,len(tscale),2)]
        tstops = [ tscale[idx] for idx in range(1,len(tscale),2)]
        times = np.concatenate((tstarts, tstops), axis=1)

        # initiate curves etc 

        self._initiate_curves()

        #
        # ready view
        #

        self.ssa.window(0,30)        
        self._update_scaling()
        self._update_pg1_simple()
        




    # --------------------------------------------------------------------------------
    #
    # set up traces
    #
    # --------------------------------------------------------------------------------
    
    def _initiate_curves(self):

        pi = self.ui.pg1.getPlotItem()
        pi.clear() 

        for curve in self.curves:
            pi.removeItem(curve)
        self.curves.clear()

        nchan = len( self.ss_chs )
        colors = [pg.intColor(i, hues=nchan) for i in range(nchan)]

        
        for i in range(nchan):
            pen = pg.mkPen( colors[i], width=1, cosmetic=True)
            c = pg.PlotCurveItem(pen=pen, connect='finite')
            pi.addItem(c)
            self.curves.append(c)

        #
        # initiate annotations
        #

        self.annot_mgr = TrackManager( self.ui.pg1 )

        nann = len( self.ss_anns )
        colors = [pg.intColor(i, hues=nann) for i in range(nann)]
        self.annot_curves = []

        for i in range(nann):
            col = colors[i]
            col = self.stgcols_hex.get(self.ss_anns[i] , col)
            self.annot_mgr.update_track( self.ss_anns[i] , [] , [], [], [] , color = col )
            pen = pg.mkPen( col, width=1, cosmetic=True)
            c = pg.PlotCurveItem(pen=pen, connect='finite')
            pi.addItem(c)
            self.annot_curves.append(c)

        #
        # initiate gaps
        #

        self.annot_mgr.update_track( "__#gaps__"  ,
                                     [] , [], [], [] ,
                                     color = (0,25,25) ,
                                     pen = pg.mkPen((200, 200, 200), width=1) )
        
        #
        # initiate ticks
        #

        self.tb = TextBatch(pi.vb, QtGui.QFont("Arial", 12), color=(180,255,255), mode='device')
        self.tb.setZValue(10)
        self.tb.setData([ ], [ ], [ ])
        self.ui.pg1.addItem(self.tb)# , ignoreBounds=True)

        #
        # initiate labels
        #

        self.labs = TextBatch(pi.vb,
               QtGui.QFont("Arial", 12, QtGui.QFont.Bold),
               color=(255,255,255),
               mode='device',
               bg=(0,0,0,170),    # semi-transparent black
               pad=(6,3),         # x/y padding in px
               radius=20,          # rounded corners
               outline= (255,255,255,80) )      # or (255,255,255,80)
        
        self.labs.setZValue(10)
        self.labs.setData([ ], [ ], [ ])
        self.ui.pg1.addItem(self.labs)# , ignoreBounds=True)
        

    # --------------------------------------------------------------------------------
    #
    # labels
    #
    # --------------------------------------------------------------------------------

    def _update_labels(self):

        # labels?
        if self.ui.check_labels.isChecked():
            self.show_labels = True
        else:
            self.show_labels = False
            
        # redraw
        self._update_pg1()

    # --------------------------------------------------------------------------------
    #
    # handle y-axis scaling
    #
    # --------------------------------------------------------------------------------

    def _update_scaling(self):

        self.pg1_header_height = 0.05

        self.pg1_footer_height = 0.025

        if len(self.ss_anns) == 0:
            self.pg1_annot_height = 0
        else:
            self.pg1_annot_height = min( 0.3 , 0.10 + len(self.ss_anns) * 0.015 ) 

        if len(self.ss_chs) == 0:
            self.pg1_annot_height = 0.8

        # use empirical vals (default) 
        if self.ui.radio_empiric.isChecked():
            for ch in self.ss_chs:
                self.ss.empirical_physical_scale( ch )

            # & turn off other fixed scale , if set
            if self.ui.radio_fixedscale.isChecked() :
                with QSignalBlocker(self.ui.radio_fixedscale):
                    self.ui.radio_fixedscale.setChecked(False)

        elif self.ui.radio_fixedscale.isChecked():
            lwr = self.ui.spin_fixed_min.value()
            upr = self.ui.spin_fixed_max.value()
            if lwr <= upr:
                lwr = -1
                upr = +1
            for ch in self.ss_chs:
                self.ss.fix_physical_scale( ch , self.ui.spin_fixed_min.value(), self.ui.spin_fixed_max.value() )
        else:
            for ch in self.ss_chs:
                self.ss.free_physical_scale( ch )

        self.clip_signals = self.ui.radio_clip.isChecked()
        
        ns = len( self.ui.tbl_desc_signals.checked() )

        na = len( self.ui.tbl_desc_annots.checked() )

        yscale = 2**float( self.ui.spin_scale.value() )
        yspacing = float( self.ui.spin_spacing.value() )

        # if not annotations, take up entire screen for annots
        if ns != 0:
            yannot = self.pg1_annot_height
        else:
            yannot = 1 - self.pg1_footer_height - self.pg1_header_height 

#        print('ns',ns,'na',na,'yannot', yannot )

        # update scaling (either for ss or ssa in simple rendering)

        if self.rendered is True:
            self.ss.set_scaling( ns, na,  yscale , yspacing ,
                                 self.pg1_header_height,
                                 self.pg1_footer_height ,
                                 yannot ,
                                 self.clip_signals )
        else:
            self.ssa.set_scaling( ns, na,  yscale , yspacing ,
                                  self.pg1_header_height,
                                  self.pg1_footer_height ,
                                  yannot ,
                                  self.clip_signals )



        # update main plot (passes to _update_pg1_simple() as needed)
            
        self._update_pg1()



        
    # --------------------------------------------------------------------------------
    #
    # clear main curves
    #
    # --------------------------------------------------------------------------------

    def _clear_pg1(self):

        pi = self.ui.pg1.getPlotItem()
        pi.clear() 

        for curve in self.curves:
            pi.removeItem(curve)
        self.curves.clear()

        for curve in self.annot_curves:
            pi.removeItem(curve)
        self.annot_curves.clear()

        self._initiate_curves()
        
    
    # --------------------------------------------------------------------------------
    #
    # update main signal traces
    #
    # --------------------------------------------------------------------------------

    def _update_pg1(self):

        if self.rendered is not True:
            self._update_pg1_simple()
            return

        # channels
        chs = self.ui.tbl_desc_signals.checked()
        chs = [x for x in self.ss_chs if x in chs ] 

        # annots
        anns = self.ui.tbl_desc_annots.checked()
        anns = [x for x in self.ss_anns if x in anns ]
        
        # window (sec)
        x1 = self.ss.get_window_left()
        x2 = self.ss.get_window_right()

        # get canvas
        pw = self.ui.pg1
        vb = pw.getPlotItem().getViewBox()
        vb.setRange(xRange=(x1,x2), padding=0, update=False)  # no immediate paint
        
        # channels
        idx = 0        
        tv = [ '' ] * ( len(chs) + len(anns) )
        yv = [ 0.5 ] * ( len(chs) + len(anns) )
        xv = [  x1 + ( x2 - x1 ) * 0.02 ] * ( len(chs) + len(anns) )
        for ch in chs:
            # signals
            x = self.ss.get_timetrack( ch )
            y = self.ss.get_scaled_signal( ch , idx )            
            self.curves[idx].setData(x, y)            
            # labels            
            ylim = self.ss.get_window_phys_range( ch )
            if self.show_labels:
                tv[idx] = ' ' + ch + ' ' + str(round(ylim[0],3)) + ':' + str(round(ylim[1],3)) + ' (' + self.units[ ch ] +')'
            yv[idx] = self.ss.get_ylabel( idx ) 
            # next
            idx = idx + 1
        
        # annots
        aidx = 0
        self.ss.compile_windowed_annots( anns )

        for ann in anns:
            a0 = self.ss.get_annots_xaxes( ann )            
            if len(a0) == 0:
                idx = idx + 1
                aidx = aidx + 1
                continue
            a1 = self.ss.get_annots_xaxes_ends( ann )            
            y0 = self.ss.get_annots_yaxes( ann )
            y1 = self.ss.get_annots_yaxes_ends( ann )
            self.annot_curves[aidx].setData( [ x1 , x2 ] , [ ( y0[0] + y1[0] ) / 2  , ( y0[0] + y1[0] ) / 2 ] )
#            self.annot_mgr.toggle( ann , True )
            a0, a1 = _ensure_min_px_width( vb, a0, a1, px=1)  # 1-px minimum
            self.annot_mgr.update_track( ann , x0 = a0 , x1 = a1 , y0 = y0 , y1 = y1 )
            # labels
            yv[idx] = ( y0[0] * 2 + y1[0]  ) / 3.0
            if self.show_labels: 
                if ann and str(ann).strip():
                    tv[idx] = ann
            idx = idx + 1
            aidx = aidx + 1

        xv2, yv2, tv2 = [], [], []
        for x, y, t in zip(xv, yv, tv):
            if t and str(t).strip():  # keep only non-empty labels
                xv2.append(x)
                yv2.append(y)
                tv2.append(t)

        self.labs.setData(xv2, yv2, tv2)

        # gaps (list of (start,stop) values
        gaps = self.ss.get_gaps()
        x0 =  [ x[0] for x in gaps ]
        x1 =  [ x[1] for x in gaps ]
        y0 =  [ 0.04 for x in gaps ]
        y1 =  [ 0.96 for x in gaps ]
        gaps = self.annot_mgr.update_track( "__#gaps__" ,x0 = x0 , x1 = x1 , y0 = y0 , y1 = y1 )
            
        # clock-ticks                                                                                                          
        tks = self.ss.get_clock_ticks(6)
        tx = list( tks.keys() )
        tv = list( tks.values() )        
        self.tb.setData(tx, [ 0.99 ] * len( tx ) , tv )

        # repaint
        vb.update()  




    # --------------------------------------------------------------------------------
    #
    # simple (non-segsrv) update main signal traces - called if segsrv not populated
    # restrict to single epoch plotting here
    # --------------------------------------------------------------------------------

    def _update_pg1_simple(self):

        # get epoch 'e' for channel 'ch =' w/ time
        # p.slice( p.e2i( 1 ) ,  chs = ['C3'] , time = True ) 
        # --> tuple x[0] header; x[1] nparray
        # --> window in timepoints:  p.e2i( 1 ) 

        # use self.ssa segsrv for annotations and mapping

        # channels
        chs = self.ui.tbl_desc_signals.checked()

        # annots
        anns = self.ui.tbl_desc_annots.checked()
        
        # window (sec)
        x1 = self.ssa.get_window_left()
        x2 = self.ssa.get_window_right()

        # if 1+ signals, do not allow large windows
        if len(chs) != 0 and x2 - x1 > 30:
            self.sel.setRange(x1, x1+30)
            return
        
        # get canvas
        pw = self.ui.pg1
        vb = pw.getPlotItem().getViewBox()
        vb.setRange(xRange=(x1,x2), padding=0, update=False)  # no immediate paint

        # scaling
        h = 1 - self.pg1_header_height - self.pg1_footer_height - self.pg1_annot_height
        if len(chs) != 0:
            h = h / len(chs) 
        else:
            h = 0
      
        
        # channels
        idx = 0        
        tv = [ '' ] * ( len(chs) + len(anns) )
        yv = [ 0.5 ] * ( len(chs) + len(anns) )
        xv = [ x1 + ( x2 - x1 ) * 0.02 ] * ( len(chs) + len(anns) )
        for ch in chs:
            # signals
            d = self.p.slice( self.p.s2i( [ ( x1 , x2 ) ] ) , chs = ch , time = True )[1]
            x = d[:,0]  # time-track
            y = d[:,1]  # unscaled signal
            # need to scale manually: to 0/1
            mn, mx = min(y), max(y)
            if mx > mn: y = (y - mn) / (mx - mn)
            else: y = y - y
            # --> to grid value
            ybase = idx * h + self.pg1_footer_height
            y = ybase + y * h 
            # plot
            self.curves[idx].setData(x, y)
            # labels
            ylim = [ mn , mx ] 
            if self.show_labels:
                tv[idx] = ' ' + ch + ' ' + str(round(ylim[0],3)) + ':' + str(round(ylim[1],3)) + ' (' + self.units[ ch ] +')'
            yv[idx] = ybase + 0.5 * h
            # next
            idx = idx + 1

        # annots (from ssa)
        aidx = 0
        self.ssa.compile_windowed_annots( anns )
        anns1 = [self.ssa_anns_lookup[v] for v in anns ]

#        print( 'len(anns)' , len(anns) )
#        print( 'len(anns1)' , len(anns1) )
        
        for ann in anns:
            print('ann',ann,idx,aidx,anns1[aidx] )
            a0 = self.ssa.get_annots_xaxes( ann )            
            if len(a0) == 0:
                idx = idx + 1
                aidx = aidx + 1
                continue

            a1 = self.ssa.get_annots_xaxes_ends( ann )
            y0 = self.ssa.get_annots_yaxes( ann )
            y1 = self.ssa.get_annots_yaxes_ends( ann )
            self.annot_curves[ anns1[aidx] ].setData( [ x1 , x2 ] , [ ( y0[0] + y1[0] ) / 2  , ( y0[0] + y1[0] ) / 2 ] ) 
#            self.annot_mgr.toggle( ann , True )
            a0, a1 = _ensure_min_px_width( vb, a0, a1, px=1)  # 1-px minimum
            self.annot_mgr.update_track( ann , x0 = a0 , x1 = a1 , y0 = y0 , y1 = y1 )
            # labels
            yv[idx] = ( y0[0] * 2 + y1[0]  ) / 3.0 

            if self.show_labels: tv[idx] = ann

            idx = idx + 1
            aidx = aidx + 1

            
        # add labels
        # filter out empty/blank labels before drawing
        xv2, yv2, tv2 = [], [], []
        for x, y, t in zip(xv, yv, tv):
            if t and str(t).strip():  # keep only non-empty labels
                xv2.append(x)
                yv2.append(y)
                tv2.append(t)

        self.labs.setData(xv2, yv2, tv2)

        # gaps (list of (start,stop) values
        gaps = self.ssa.get_gaps()
        x0 =  [ x[0] for x in gaps ]
        x1 =  [ x[1] for x in gaps ]
        y0 =  [ 0.04 for x in gaps ]
        y1 =  [ 0.96 for x in gaps ]
        gaps = self.annot_mgr.update_track( "__#gaps__" ,x0 = x0 , x1 = x1 , y0 = y0 , y1 = y1 )
            
        # clock-ticks                                                                                                          
        tks = self.ssa.get_clock_ticks(6)
        tx = list( tks.keys() )
        tv = list( tks.values() )        
        self.tb.setData(tx, [ 0.99 ] * len( tx ) , tv )

        # repaint
        vb.update()  
        

        
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui
import pyqtgraph as pg

class XRangeSelector(QtCore.QObject):
    """
    Background left-drag: draw/resize selection.
    Single-click: fixed `click_span` centered at click.
    Drag inside region: MOVE whole region (fixed width). If wide and near edges, LRI resizes.
    Left/Right pan. Shift+Left/Right bigger pan.
    Up/Down zoom in/out. Min span = `min_span`. Max = bounds/view.
    Emits: rangeSelected(lo: float, hi: float)
    """
    rangeSelected = QtCore.Signal(float, float)

    def __init__(self, plot, bounds=None, integer=False,
                 click_span=30.0, min_span=5.0,
                 line_width=6, step=1, big_step=10, step_px=3, big_step_px=15,
                 drag_thresh_px=6, edge_tol_px=10, thin_px=16):
        super().__init__(plot)

        # resolve plot + focus widget
        self.pi  = plot.getPlotItem() if isinstance(plot, pg.PlotWidget) else plot
        self.vb  = self.pi.getViewBox()
        views = self.pi.scene().views()
        self.wid = plot if hasattr(plot, "setFocusPolicy") else (views[0] if views else None)
        if self.wid is None:
            raise RuntimeError("No focusable view for shortcuts.")
        self.wid.setFocusPolicy(QtCore.Qt.StrongFocus)

        # config
        self.integer     = bool(integer)
        self.bounds      = tuple(bounds) if bounds is not None else None
        self.click_span  = float(click_span)
        self.min_span    = max(0.0, float(min_span))
        self.step, self.big_step = float(step), float(big_step)
        self.step_px, self.big_step_px = int(step_px), int(big_step_px)
        self.drag_thresh_px = int(drag_thresh_px)
        self.edge_tol_px    = int(edge_tol_px)
        self.thin_px        = int(thin_px)   # width ≤ thin_px ⇒ move-only anywhere inside

        # state
        self._setting_region = False
        self._region_active  = False     # LRI is handling its own drag
        self._last_emitted = None
        self._pending = None
        self._dragging_bg = False
        self._dragging_move = False
        self._moved = False
        self._press_scene = None
        self._anchor_x = None
        self._move_width = None
        self._move_offset = 0.0
        self._disposed = False
        
        # coalesced emitter
        self._emit_timer = QtCore.QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.timeout.connect(self._flush_emit)

        # selection region
        self.region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Vertical)
        self.region.setMovable(True)
        if self.bounds is not None:
            self.region.setBounds(self.bounds)
        try:
            self.region.setBrush(pg.mkBrush(0,120,255,40))
            self.region.setHoverBrush(pg.mkBrush(0,120,255,80))
        except Exception:
            pass
        for ln in getattr(self.region, "lines", []):
            try:
                ln.setPen(pg.mkPen(width=line_width))
                ln.setHoverPen(pg.mkPen(width=line_width+4))
                ln.setCursor(QtCore.Qt.SizeHorCursor)
            except Exception:
                pass
        self.region.setZValue(10); self.region.hide()
        self.pi.addItem(self.region)

        # signals
        self.region.sigRegionChanged.connect(self._on_region_changed)
        if hasattr(self.region, "sigRegionChangeStarted"):
            self.region.sigRegionChangeStarted.connect(lambda: setattr(self, "_region_active", True))
        if hasattr(self.region, "sigRegionChangeFinished"):
            self.region.sigRegionChangeFinished.connect(self._on_region_finished)

        # keyboard + scene filter
        self._mk_shortcuts()
        self.pi.scene().installEventFilter(self)

    # ---------- shortcuts ----------
    def _mk_shortcuts(self):
        self._sc = []
        def sc(keyseq, fn):
            s = QtGui.QShortcut(QtGui.QKeySequence(keyseq), self.wid)
            # critical: restrict scope to this widget (not whole window)
            s.setContext(QtCore.Qt.WidgetWithChildrenShortcut)  # or QtCore.Qt.WidgetShortcut
            s.setAutoRepeat(True)
            s.activated.connect(fn)
            self._sc.append(s)

        sc(QtCore.Qt.Key_Left,  lambda: self._nudge(self._step(False)*-1))
        sc(QtCore.Qt.Key_Right, lambda: self._nudge(self._step(False)*+1))
        sc(QtCore.Qt.SHIFT | QtCore.Qt.Key_Left,  lambda: self._nudge(self._step(True)*-1))
        sc(QtCore.Qt.SHIFT | QtCore.Qt.Key_Right, lambda: self._nudge(self._step(True)*+1))
        sc(QtCore.Qt.Key_Up,    lambda: self._zoom(0.8))
        sc(QtCore.Qt.Key_Down,  lambda: self._zoom(1.25))

    def _step(self, big: bool):
        if self.integer:
            return self.big_step if big else self.step
        px = self.big_step_px if big else self.step_px
        (xmin, xmax), w = self.vb.viewRange()[0], max(1.0, float(self.vb.width() or 1))
        return (xmax - xmin) * (float(px) / w)

    # ---------- helpers ----------
    def _snap(self, x): return int(round(x)) if self.integer else float(x)

    def _in_vb(self, scene_pos): return self.vb.sceneBoundingRect().contains(scene_pos)

    def _px_to_dx(self, px):
        (xmin, xmax), w = self.vb.viewRange()[0], max(1.0, float(self.vb.width() or 1))
        return (xmax - xmin) * (float(px) / w)

    def _dx_to_px(self, dx):
        (xmin, xmax), w = self.vb.viewRange()[0], max(1.0, float(self.vb.width() or 1))
        span = max(1e-12, xmax - xmin)
        return abs(dx) * (w / span)

    def _full_bounds(self):
        # Prefer explicit bounds
        if self.bounds is not None:
            return float(self.bounds[0]), float(self.bounds[1])
        # Else use data bounds in the ViewBox
        br = self.vb.childrenBounds()  # QRectF over all child items (data coords)
        if br is not None and br.width() > 0:
            return float(br.left()), float(br.right())
        # Fallback: current view (last resort)
        xmin, xmax = self.vb.viewRange()[0]
        return float(xmin), float(xmax)

    def _inside_region_scene(self, scene_pos):
        if not self.region.isVisible():
            return False
        p = self.region.mapFromScene(scene_pos)
        return self.region.boundingRect().contains(p)
    
    def _max_span(self):
        if self.bounds is not None:
            return max(0.0, float(self.bounds[1] - self.bounds[0]))
        xmin, xmax = self.vb.viewRange()[0]
        return max(0.0, float(xmax - xmin))

    def _clamp_pair(self, lo, hi):
        if self.bounds is None:
            return lo, hi
        b0, b1 = self.bounds
        span = hi - lo
        if span <= 0:
            x = min(max(lo, b0), b1); return x, x
        lo = max(lo, b0); hi = lo + span
        if hi > b1: hi = b1; lo = hi - span
        return lo, hi

    def _enforce_span_limits(self, lo, hi):
        span = hi - lo
        max_span = self._max_span()
        eff_min = min(self.min_span, max_span) if max_span > 0 else self.min_span
        if span < eff_min:
            c = 0.5*(lo + hi); lo, hi = c - 0.5*eff_min, c + 0.5*eff_min
        if max_span > 0 and (hi - lo) > max_span:
            c = 0.5*(lo + hi); lo, hi = c - 0.5*max_span, c + 0.5*max_span
        return self._clamp_pair(lo, hi)

    def _set_region_silent(self, lo, hi):
        self._setting_region = True
        blockers = [QtCore.QSignalBlocker(self.region)]
        for ln in getattr(self.region, "lines", []):
            try: blockers.append(QtCore.QSignalBlocker(ln))
            except Exception: pass
        self.region.setRegion((lo, hi))
        del blockers
        self._setting_region = False

    def _ensure_region_visible(self, span=None):
        if self.region.isVisible():
            return
        max_span = self._max_span()
        span = min(span or self.click_span, max_span) if max_span > 0 else (span or self.click_span)
        xmin, xmax = self.vb.viewRange()[0]
        c = 0.5*(xmin + xmax)
        lo, hi = c - 0.5*span, c + 0.5*span
        lo, hi = self._enforce_span_limits(lo, hi)
        self._set_region_silent(lo, hi)
        self.region.show()
        self.wid.setFocus()
        self._schedule_emit(lo, hi)

    def _schedule_emit(self, lo, hi):
        lo, hi = self._snap(lo), self._snap(hi)
        self._pending = (lo, hi)
        if not self._emit_timer.isActive():
            self._emit_timer.start(0)

    def _flush_emit(self):
        if self._pending is None:
            return
        if self._pending != self._last_emitted:
            self._last_emitted = self._pending
            self.rangeSelected.emit(*self._pending)

    def dispose(self):
        if getattr(self, "_disposed", False):
            return
        self._disposed = True

        scene = None
        try:
            scene = self.pi.scene()
        except Exception:
            scene = None
        if scene is not None:
            try:
                scene.removeEventFilter(self)
            except Exception:
                pass

        if getattr(self, "region", None) is not None:
            try:
                self.pi.removeItem(self.region)
            except Exception:
                pass
            try:
                self.region.setParentItem(None)
            except Exception:
                pass
            try:
                self.region.deleteLater()
            except Exception:
                pass
            self.region = None

        sc_list = getattr(self, "_sc", None)
        if sc_list is not None:
            for sc in sc_list:
                try:
                    sc.activated.disconnect()
                except Exception:
                    pass
                try:
                    sc.setParent(None)
                except Exception:
                    pass
                try:
                    sc.deleteLater()
                except Exception:
                    pass
            sc_list.clear()

        if getattr(self, "_emit_timer", None) is not None:
            try:
                self._emit_timer.stop()
            except Exception:
                pass

        try:
            QtCore.QObject.deleteLater(self)
        except Exception:
            pass

            
    # ---------- mouse (event filter) ----------
    def eventFilter(self, obj, ev):
        if obj is not self.pi.scene():
            return False
        if self._region_active:
            return False  # let LRI handle its own drags/resizes

        et = ev.type()


        if et == QtCore.QEvent.GraphicsSceneMouseDoubleClick and ev.button() == QtCore.Qt.LeftButton:
            if not self._in_vb(ev.scenePos()):
                return False

            # cancel any press/drag in progress
            self._dragging_bg = False
            self._dragging_move = False

            # check if click is inside the region (in scene coords)
            inside = False
            if self.region.isVisible():
                # scene-space hit test for robustness
                r = self.region.mapRectToScene(self.region.boundingRect())
                inside = r.contains(ev.scenePos())
                print('set')
            print ('inside',inside)
            
            if inside:
                # shrink to one epoch centered at click
                x = self.vb.mapSceneToView(ev.scenePos()).x()
                half = 0.5 * self.click_span
                lo2, hi2 = self._enforce_span_limits(*self._clamp_pair(x - half, x + half))
            else:
                # expand to whole recording (bounds or data extent)
                lo2, hi2 = self._full_bounds()
                if self.bounds is not None:
                    lo2, hi2 = self._enforce_span_limits(lo2, hi2)

            self._set_region_silent(lo2, hi2)
            self.region.show()
            self._schedule_emit(lo2, hi2)
            return True

                  
        elif et == QtCore.QEvent.GraphicsSceneMousePress and ev.button() == QtCore.Qt.LeftButton:
            if not self._in_vb(ev.scenePos()):
                return False
            x = self.vb.mapSceneToView(ev.scenePos()).x()

            if self.region.isVisible():
                lo, hi = self.region.getRegion()
                w = max(hi - lo, 0.0)
                w_px = self._dx_to_px(w)
                tol_dx = self._px_to_dx(self.edge_tol_px)

                # THIN region -> move-only anywhere inside [lo, hi]
                if w_px <= self.thin_px and (lo - tol_dx) <= x <= (hi + tol_dx):
                    self._start_move_drag(x, lo, hi); return True

                # WIDE region:
                # inside core (away from edges) -> move-only
                if (lo + tol_dx) <= x <= (hi - tol_dx):
                    self._start_move_drag(x, lo, hi); return True

                # near edges -> let LRI resize
                if (lo - tol_dx) <= x <= (hi + tol_dx):
                    return False

            # outside region -> background selection drag
            self._dragging_bg = True; self._moved = False
            self._press_scene = ev.scenePos()
            self._anchor_x = self._snap(x)
            return False

        elif et == QtCore.QEvent.GraphicsSceneMouseMove:
            if self._dragging_move:
                if not self._in_vb(ev.scenePos()):
                    return True
                x = self._snap(self.vb.mapSceneToView(ev.scenePos()).x())
                c = x - self._move_offset
                half = 0.5 * self._move_width
                lo, hi = c - half, c + half
                lo, hi = self._enforce_span_limits(lo, hi)
                self._set_region_silent(lo, hi)
                self.region.show()
                self._schedule_emit(lo, hi)
                self._moved = True
                return True

            if self._dragging_bg:
                if not self._in_vb(ev.scenePos()):
                    return True
                if (ev.scenePos() - self._press_scene).manhattanLength() >= self.drag_thresh_px:
                    self._moved = True
                if self._moved:
                    x = self._snap(self.vb.mapSceneToView(ev.scenePos()).x())
                    lo, hi = sorted((self._anchor_x, x))
                    lo, hi = self._enforce_span_limits(*self._clamp_pair(lo, hi))
                    self._set_region_silent(lo, hi)
                    self.region.show()
                    self._schedule_emit(lo, hi)
                return True

        elif et == QtCore.QEvent.GraphicsSceneMouseRelease and ev.button() == QtCore.Qt.LeftButton:
            if self._dragging_move:
                self._dragging_move = False
                return True
            if self._dragging_bg:
                self._dragging_bg = False
                if not self._moved:
                    x = self._anchor_x
                    half = 0.5 * self.click_span
                    lo, hi = self._enforce_span_limits(*self._clamp_pair(x - half, x + half))
                    self._set_region_silent(lo, hi)
                    self.region.show()
                    self._schedule_emit(lo, hi)
                return True

        return False

    def _start_move_drag(self, x, lo, hi):
        self._dragging_move = True
        self._moved = False
        self._press_scene = None
        self._move_width = max(hi - lo, self.min_span)
        c = 0.5 * (lo + hi)
        self._move_offset = x - c

    # ---------- region + keys ----------
    def _on_region_changed(self):
        if self._setting_region:
            return
        lo, hi = self.region.getRegion()
        lo, hi = self._enforce_span_limits(self._snap(lo), self._snap(hi))
        self._set_region_silent(lo, hi)
        self._schedule_emit(lo, hi)

    def _on_region_finished(self):
        self._region_active = False
        lo, hi = self.region.getRegion()
        self._schedule_emit(*self._enforce_span_limits(lo, hi))

    def _nudge(self, dx):
        self._ensure_region_visible()
        lo, hi = self.region.getRegion()
        lo, hi = self._clamp_pair(self._snap(lo)+dx, self._snap(hi)+dx)
        self._set_region_silent(lo, hi)
        self._schedule_emit(lo, hi)

    def _zoom(self, factor):
        self._ensure_region_visible()
        lo, hi = self.region.getRegion()
        c = 0.5*(lo + hi)
        w = max(hi - lo, 0.0)
        max_w = self._max_span()
        min_w = min(self.min_span, max_w) if max_w > 0 else self.min_span
        if w <= 0:
            w = min(max_w if max_w > 0 else self.click_span, self.click_span)
        new_w = w * float(factor)
        if max_w > 0:
            new_w = min(max(new_w, min_w), max_w)
        else:
            new_w = max(new_w, min_w)
        lo2, hi2 = c - 0.5*new_w, c + 0.5*new_w
        lo2, hi2 = self._enforce_span_limits(lo2, hi2)
        self._set_region_silent(lo2, hi2)
        self._schedule_emit(lo2, hi2)

    # ---------- lifecycle ----------
    def detach(self):
        try: self.pi.scene().removeEventFilter(self)
        except Exception: pass
        for sig, slot in [
            (self.region.sigRegionChanged, self._on_region_changed),
        ]:
            try: sig.disconnect(slot)
            except TypeError: pass
        try: self.pi.removeItem(self.region)
        except Exception: pass
        for s in getattr(self, "_sc", []):
            try: s.setParent(None)
            except Exception: pass
            
    # programmatically set range
    def setRange(self, lo: float, hi: float, emit: bool = True):
        lo, hi = self._enforce_span_limits(lo, hi)
        self._set_region_silent(lo, hi)
        self.region.show()
        self.wid.setFocus()
        if emit:
            self._schedule_emit(lo, hi)



# --------------------------------------------------------------------------------
#
# text updater
#
# --------------------------------------------------------------------------------


class TextBatch(pg.GraphicsObject):
    def __init__(self, viewbox: pg.ViewBox, font: QtGui.QFont=None,
                 color=(255,255,255), mode='device',
                 bg=(0,0,0,170), pad=(6,3), radius=3, outline=None):
        super().__init__()
        self.vb = viewbox
        self.mode = mode
        self.font = font or QtGui.QFont("Sans Serif", 10)
        self.color = pg.mkColor(color)
        self.bg_brush = None if bg is None else pg.mkBrush(bg)
        self.bg_pen = QtGui.QPen(QtCore.Qt.NoPen) if not outline else pg.mkPen(outline)
        self.pad_x, self.pad_y = pad
        self.radius = radius
        self._x = np.empty(0); self._y = np.empty(0)
        self._labels = []
        self._stat = {}
        self._bbox = QtCore.QRectF()

                
    def setData(self, x, y, labels):
        x = np.asarray(x, float); y = np.asarray(y, float)
        assert len(x) == len(y) == len(labels)
        self._x, self._y = x, y
        self._labels = list(map(str, labels))
        self._stat.clear()
        self._rebuild_bbox()
        self.update()

    def setMode(self, mode):
        self.mode = mode
        self.update()

    def _rebuild_bbox(self):
        if self._x.size == 0:
            self.prepareGeometryChange()
            self._bbox = QtCore.QRectF()
            return
        xmin, xmax = np.min(self._x), np.max(self._x)
        ymin, ymax = np.min(self._y), np.max(self._y)
        self.prepareGeometryChange()
        self._bbox = QtCore.QRectF(xmin, ymin, xmax-xmin, ymax-ymin)

    def boundingRect(self):
        return self._bbox

    def _qstatic(self, s: str) -> QtGui.QStaticText:
        st = self._stat.get(s)
        if st is None:
            st = QtGui.QStaticText(s)
            st.setTextFormat(QtCore.Qt.PlainText)
            st.prepare(font=self.font)
            self._stat[s] = st
        return st

    def _draw_with_bg(self, p: QtGui.QPainter, top_left: QtCore.QPointF, st: QtGui.QStaticText):
        if self.bg_brush is not None:
            sz = st.size()  # QSizeF in current painter coord system
            r = QtCore.QRectF(top_left.x() - self.pad_x,
                              top_left.y() - self.pad_y,
                              sz.width() + 2*self.pad_x,
                              sz.height() + 2*self.pad_y)
            p.setPen(self.bg_pen)
            p.setBrush(self.bg_brush)
            if self.radius:
                p.drawRoundedRect(r, self.radius, self.radius)
            else:
                p.drawRect(r)
        # text color
        p.setPen(pg.mkPen(self.color))
        p.drawStaticText(top_left, st)

    def paint(self, p: QtGui.QPainter, opt, widget=None):
        if self._x.size == 0:
            return
        (xmin, xmax), (ymin, ymax) = self.vb.viewRange()
        m = (self._x >= xmin) & (self._x <= xmax) & (self._y >= ymin) & (self._y <= ymax)
        if not np.any(m):
            return

        p.setFont(self.font)

        if self.mode == 'data':
            # text and bg scale with view (data coords)
            for xi, yi, lab in zip(self._x[m], self._y[m], np.asarray(self._labels, object)[m]):
                st = self._qstatic(lab)
                self._draw_with_bg(p, QtCore.QPointF(xi, yi), st)
            return

        # device mode: constant pixel size (screen coords)
        p.save()
        p.resetTransform()
        mv = self.vb.mapViewToDevice
        for xi, yi, lab in zip(self._x[m], self._y[m], np.asarray(self._labels, object)[m]):
            dp = mv(QtCore.QPointF(float(xi), float(yi)))
            if dp is None:
                continue
            st = self._qstatic(lab)
            self._draw_with_bg(p, dp, st)
        p.restore()


# --------------------------------------------------------------------------------
# rect track mgr

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

class TrackManager:
    def __init__(self, plot):
        self.plot = plot
        self.tracks = {}  # name -> dict(item, color, pen, visible)

        # --- adaptive border controls (added) ---
        self._vb = getattr(self.plot, "getViewBox", lambda: None)()
        self._pen_thresh = 1.0  # data units per screen pixel; tune to taste
        self._pen_on = pg.mkPen((0, 0, 0, 120), width=1, cosmetic=True)  # thin, translucent
        self._pen_off = pg.mkPen(None)
        self._borders_on = None  # unknown until first check

        self._border_timer = QtCore.QTimer()
        self._border_timer.setSingleShot(True)
        self._border_timer.setInterval(50)
        self._border_timer.timeout.connect(self._update_all_pens)

        if self._vb is not None:
            self._vb.sigRangeChanged.connect(lambda *_: self._border_timer.start())
        # ----------------------------------------

    def _want_borders(self):
        if self._vb is None:
            return True
        sx, sy = self._vb.viewPixelSize()
        return max(sx, sy) < self._pen_thresh

    def _effective_pen(self, orig_pen):
        """Return the pen to apply now given zoom level."""
        want = self._want_borders()
        return (self._pen_on if orig_pen is None else pg.mkPen(orig_pen)) if want else self._pen_off

    def _update_all_pens(self):
        want = self._want_borders()
        if want == self._borders_on:
            return
        self._borders_on = want
        for t in self.tracks.values():
            # Respect original pen when borders are on; hide borders when off
            eff = self._effective_pen(t["pen"])
            t["item"].setOpts(pen=eff)

    def update_track(self, name, x0, x1, y0, y1, color=None, pen=None):
        """
        Replace the given track with new rectangles spanning [x0,x1] × [y0,y1].
        Arrays must be equal length.
        """
        x0 = np.asarray(x0)
        x1 = np.asarray(x1)
        y0 = np.asarray(y0)
        y1 = np.asarray(y1)
        assert x0.shape == x1.shape == y0.shape == y1.shape

        if color is None and name in self.tracks:
            color = self.tracks[name]["color"]
        if color is None:
            color = (200, 250, 240)

        if pen is None and name in self.tracks:
            pen = self.tracks[name]["pen"]  # store original user pen (may be tuple/QPen/None)
        # default black edge if never set before
        if pen is None and name not in self.tracks:
            pen = (0, 0, 0)

        # remove old
        if name in self.tracks:
            self.plot.removeItem(self.tracks[name]["item"])

        # Create item with adaptive pen
        eff_pen = self._effective_pen(pen)
        item = pg.BarGraphItem(x0=x0, x1=x1, y0=y0, y1=y1, brush=color, pen=eff_pen, name=name)
        self.plot.addItem(item)
        self.tracks[name] = {"item": item, "color": color, "pen": pen, "visible": True}

        # Initialize border state if first time
        if self._borders_on is None:
            self._borders_on = self._want_borders()

    def toggle(self, name, on=True):
        if name in self.tracks:
            self.tracks[name]["visible"] = on
            self.tracks[name]["item"].setVisible(on)

    def clear(self, name=None):
        if name is None:
            for t in self.tracks.values():
                self.plot.removeItem(t["item"])
            self.tracks.clear()
        else:
            if name in self.tracks:
                self.plot.removeItem(self.tracks[name]["item"])
                self.tracks.pop(name)


# legacy version that did not handle overlapping black borders so well
# on low DPI screens
class OldTrackManager:
    def __init__(self, plot):
        self.plot = plot
        self.tracks = {}  # name -> dict(item, color, visible)

    def update_track(self, name, x0, x1, y0, y1, color=None, pen=None):
        """
        Replace the given track with new rectangles spanning [x0,x1] × [y0,y1].
        Arrays must be equal length.
        """
        x0 = np.asarray(x0)
        x1 = np.asarray(x1)
        y0 = np.asarray(y0)
        y1 = np.asarray(y1)
        assert x0.shape == x1.shape == y0.shape == y1.shape

        if color is None and name in self.tracks:
            color = self.tracks[name]["color"]
        if color is None:
            color = (200, 250, 240)

        if pen is None and name in self.tracks:
            pen = self.tracks[name]["pen"]
        if pen is None:
            pen = (0, 0, 0)

        # remove old
        if name in self.tracks:
            self.plot.removeItem(self.tracks[name]["item"])
        '''
        valid = (np.abs(x1 - x0) > 1e-6) & (np.abs(y1 - y0) > 1e-6)
        if not np.any(valid):
            return
        x0, x1, y0, y1 = x0[valid], x1[valid], y0[valid], y1[valid]
        '''
        item = pg.BarGraphItem(
            x0=x0, x1=x1, y0=y0, y1=y1,
            brush=color, pen=pen, name=name
        )
        self.plot.addItem(item)
        self.tracks[name] = {"item": item, "color": color, "pen": pen, "visible": True}

    def toggle(self, name, on=True):
        if name in self.tracks:
            self.tracks[name]["visible"] = on
            self.tracks[name]["item"].setVisible(on)

    def clear(self, name=None):
        if name is None:
            for t in self.tracks.values():
                self.plot.removeItem(t["item"])
            self.tracks.clear()
        else:
            if name in self.tracks:
                self.plot.removeItem(self.tracks[name]["item"])
                self.tracks.pop(name)

@staticmethod
def _ensure_min_px_width(vb, x0, x1, px=1):
    x0 = np.asarray(x0, dtype=float)
    x1 = np.asarray(x1, dtype=float)

    dx, _ = vb.viewPixelSize()
    wmin = px * dx
    w = x1 - x0
    too_narrow = w < wmin
    xc = 0.5 * (x0 + x1)
    x0a = np.where(too_narrow, xc - 0.5*wmin, x0)
    x1a = np.where(too_narrow, xc + 0.5*wmin, x1)
    return x0a, x1a
