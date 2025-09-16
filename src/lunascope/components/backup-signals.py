
import pandas as pd
import numpy as np
from os import fspath
import lunapi as lp
import pyqtgraph as pg
from collections import defaultdict

from PySide6.QtWidgets import QApplication, QVBoxLayout, QTableView
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# pg1: main signal views
# phh: hypnogram/segment encoding: epoch-level plot 
# phs: spectrogram/Hjorth


# using lp.segsrv()
# init
#   ss = lp.segsrv( self.p )
#   ss.calc_bands( bsigs ) - can be blank for now
#   ss.calc_hjorths( hsigs )
#   ss.input_throttle( 100 ) 
#   ss.throttle( 5 * 30 * 100 )
#   ss.summary_threshold_mins( 30 ) - not used
#     height = 600
#     annot_height = 0.15
#     header_height = 0.04
#     footer_height = 0.01


# 
#   ss.populate( chs , anns )

#           stgs = [ 'N1' , 'N2' , 'N3' , 'R' , 'W' , '?' , 'L' ] ,
#           stgcols = { 'N1':'blue' , 'N2':'blue', 'N3':'navy','R':'red','W':'green','?':'gray','L':'yellow' } ,
#           stgns = { 'N1':-1 , 'N2':-2, 'N3':-3,'R':0,'W':1,'?':2,'L':2 } ,

           
# window
#  ss.window( 0 , 30 )
#  ss.get_window_left_hms()
#  ss.get_window_right_hms()

# scaling
#    ss.set_scaling( #ns, #na,
#                     2**float(yscale.value) , float(yspace.value)
#                   , header_height, footer_height , annot_height )

# signals
# ss.get_timetrack( s )
# ss.get_scaled_signal( s , idx ) [ idx = 0,1,2,... of displayed channels)

# gaps
#  ss.get_gaps()

# annots
#   ss.compile_windowed_annots( [list of anns] )
#   ss.get_annots_xaxes( a )
#   ss.get_annots_yaxes( a )  


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
        
        pg.setConfigOptions(antialias=True)

        # pg1 properties

        pw = self.ui.pg1   # pyqtgraph.PlotWidget
        pw.setXRange(0, 1, padding=0)   
        pw.setYRange(0, 1, padding=0)
        pw.showAxis('left', False)
        pw.showAxis('bottom', False)
        vb = pw.getViewBox()
        vb.enableAutoRange('x', False)
        vb.enableAutoRange('y', False)
#        vb.setMouseEnabled(x=False, y=False)


        
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
        
        # ------------------------------------------------------------
        # hypnogram init
        # ------------------------------------------------------------

        h = self.ui.pgh
        pi = h.getPlotItem()
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

        # get staging (in units no larger than 30 seconds)
        stgs = [ 'N1' , 'N2' , 'N3' , 'R' , 'W' , '?' , 'L' ] 
        stgns = { 'N1': 0.2 , 'N2': 0.1 , 'N3': 0 , 'R': 0.3  , 'W': 0.4 , '?': 0.5 , 'L': 0.6 }
        stg_evts = self.p.fetch_annots( stgs , 30 )
                
        stgcols_hex = {
            'N1': '#20B2DA',  # rgba(32,178,218,1)
            'N2': '#0000FF',  # blue
            'N3': '#000080',  # navy
            'R':  '#FF0000',  # red
            'W':  '#008000',  # green (CSS "green")
            '?':  '#808080',  # gray
            'L':  '#FFFF00',  # yellow
        }

        if len( stg_evts ) != 0:
            starts = stg_evts[ 'Start' ].to_numpy()
            stops = stg_evts[ 'Stop' ].to_numpy()
            cols = [ stgcols_hex[c] for c in stg_evts['Class'].tolist() ]
            ys = [ stgns[c] for c in stg_evts['Class'].tolist() ]

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
                    x=list(xi), width=list(wi), y0=list(yi), height=[0.4]*len(xi),
                    brush=QtGui.QColor(ci), pen=None )                
                bg.setZValue(-10)
                bg.setAcceptedMouseButtons(QtCore.Qt.NoButton)
                bg.setAcceptHoverEvents(False)
                pi.addItem(bg)

        # baseline to show full x-range
        pi.plot([0, self.ns], [0.01, 0.01], pen=pg.mkPen(0, 0, 0 ))
        
        # wire up range selector
        sel = XRangeSelector(h, bounds=(0, self.ns),
                             integer=True,
                             point_tol_px=12,
                             step=30, big_step=300,
                             line_width=8)


        
        sel.rangeSelected.connect(self.on_window_range)  
        

    # --------------------------------------------------------------------------------
    #
    # click Render --> initiate segsrv_t for channel / annotation drawing 
    #
    # --------------------------------------------------------------------------------
    
    def _render_signals(self):
        
        # selected channels:
        self.ss_chs = self.ui.tbl_desc_signals.checked_channels()
#        self.ss_annots = self.ui.tbl_desc_signals.checked_annots()


        # for a given EDF instance, take selected channels 
        if len( self.ss_chs ) == 0:
            self.rendered = False
            return

        self.rendered = True

        #ss.calc_bands( bsigs )
        #ss.calc_hjorths( hsigs )
        
        throttle1_sr = 100 
        self.ss.input_throttle( throttle1_sr )

        throttle2_np = 5 * 30 * 100 
        self.ss.throttle( throttle2_np )

        summary_mins = 30 
        self.ss.summary_threshold_mins( summary_mins )

        self.ss.populate( chs = self.ss_chs , anns = [ 'N1', 'N2', 'N3', 'R', 'W' ] )

        
        # initiate curves for each channel
        self.curves = []
        nchan = len( self.ss_chs )
        colors = [pg.intColor(i, hues=nchan) for i in range(nchan)]

        pi = self.ui.pg1.getPlotItem()
        pi.clear() 
        
        for i in range(nchan):
            pen = pg.mkPen( colors[i], width=1, cosmetic=True)
            c = pg.PlotCurveItem(pen=pen, connect='finite')
            pi.addItem(c)
            self.curves.append(c)
        

        #
        # plot segments
        #

        num_epochs = self.ss.num_epochs()
        tscale = self.ss.get_time_scale()
        tstarts = [ tscale[idx] for idx in range(0,len(tscale),2)]
        tstops = [ tscale[idx] for idx in range(1,len(tscale),2)]
        times = np.concatenate((tstarts, tstops), axis=1)
        
                   
    def on_window_range(self, lo: float, hi: float):

        # time in seconds now
        if lo < 0: lo = 0
        if hi > self.ns: hi = self.ns 
        if hi < lo: hi = lo
        
        # update ss window
        self.ss.window( lo  , hi )         
        t1 = self.ss.get_window_left_hms()
        t2 = self.ss.get_window_right_hms()        
        self.ui.lbl_twin.setText( f"T: {t1} - {t2}" )
        lo = int(lo/30)+1
        hi = int(hi/30)+1
        self.ui.lbl_ewin.setText( f"E: {lo} - {hi}" )
        self._update_pg1()

    # --------------------------------------------------------------------------------
    #
    # update main signal traces
    #
    # --------------------------------------------------------------------------------

    def _update_pg1(self):

        if self.rendered is not True: return
            
        chs = self.ui.tbl_desc_signals.checked_channels()

        # ignore any newly added channels
        chs = [x for x in self.ss_chs if x in chs ] 
        
        x1 = self.ss.get_window_left()
        x2 = self.ss.get_window_right()
        
        pw = self.ui.pg1
        vb = pw.getPlotItem().getViewBox()
        vb.setRange(xRange=(x1,x2), padding=0, update=False)  # no immediate paint
                
        idx = 0        
        for ch in chs:
            x = self.ss.get_timetrack( ch )
            y = self.ss.get_scaled_signal( ch , idx )
            self.curves[idx].setData(x, y)  
            idx = idx + 1

        vb.update()  # one repaint
        
    

        
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui
import pyqtgraph as pg


class XRangeSelector(QtCore.QObject):
    """Click -> (x,x) line. Second click far enough -> (lo,hi) region.
       ←/→ move (Shift = bigger). Live updates. Emits once per update.
    """
    rangeSelected = QtCore.Signal(float, float)

    def __init__(self, plot, bounds=None, integer=False,
                 point_tol_px=12, line_width=6,
                 step=1, big_step=10, step_px=3, big_step_px=15):
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
        self.integer = bool(integer)
        self.point_tol_px = int(point_tol_px)
        self.bounds = tuple(bounds) if bounds is not None else None
        self.step, self.big_step = float(step), float(big_step)
        self.step_px, self.big_step_px = int(step_px), int(big_step_px)

        self._anchor = None
        self._setting_region = False
        self._pending = None
        self._last_emitted = None

        # coalesced emitter
        self._emit_timer = QtCore.QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.timeout.connect(self._flush_emit)

        # point: line
        self.line = pg.InfiniteLine(angle=90, movable=True)
        try:
            self.line.setPen(pg.mkPen(width=line_width))
            self.line.setHoverPen(pg.mkPen(width=line_width+4))
        except Exception:
            pass
        if self.bounds is not None:
            try: self.line.setBounds(self.bounds)
            except Exception: pass
        self.line.setZValue(10); self.line.hide()
        self.pi.addItem(self.line)

        # region: LinearRegionItem
        self.region = pg.LinearRegionItem(orientation=pg.LinearRegionItem.Vertical)
        if self.bounds is not None:
            self.region.setBounds(self.bounds)
        for attr, arg in (("setBrush", pg.mkBrush(0,120,255,40)),
                          ("setHoverBrush", pg.mkBrush(0,120,255,80))):
            try: getattr(self.region, attr)(arg)
            except Exception: pass
        for ln in getattr(self.region, "lines", []):
            try: ln.setPen(pg.mkPen(width=line_width))
            except Exception: pass
            try: ln.setHoverPen(pg.mkPen(width=line_width+4))
            except Exception: pass
            try: ln.setCursor(QtCore.Qt.SizeHorCursor)
            except Exception: pass
        self.region.setZValue(10); self.region.hide()
        self.pi.addItem(self.region)

        # live signals
        self.pi.scene().sigMouseClicked.connect(self._on_click)
        self.line.sigPositionChanged.connect(self._on_point_changed)
        self.region.sigRegionChanged.connect(self._on_region_changed)

        # shortcuts
        self._mk_shortcuts()

    # ---------- shortcuts ----------
    def _mk_shortcuts(self):
        self._sc = []
        def sc(keyseq, fn):
            s = QtGui.QShortcut(QtGui.QKeySequence(keyseq), self.wid)
            s.setAutoRepeat(True); s.activated.connect(fn); self._sc.append(s)
        sc(QtCore.Qt.Key_Left,  lambda: self._nudge(self._step(False)*-1))
        sc(QtCore.Qt.Key_Right, lambda: self._nudge(self._step(False)*+1))
        sc(QtCore.Qt.SHIFT | QtCore.Qt.Key_Left,  lambda: self._nudge(self._step(True)*-1))
        sc(QtCore.Qt.SHIFT | QtCore.Qt.Key_Right, lambda: self._nudge(self._step(True)*+1))

    def _step(self, big: bool):
        if self.integer: return self.big_step if big else self.step
        px = self.big_step_px if big else self.step_px
        return self._px_to_dx(px)

    # ---------- helpers ----------
    def _snap(self, x): return int(round(x)) if self.integer else float(x)

    def _px_to_dx(self, px):
        (xmin, xmax), w = self.vb.viewRange()[0], max(1.0, float(self.vb.width() or 1))
        return (xmax - xmin) * (float(px) / w)

    def _tol_dx(self): return self._px_to_dx(self.point_tol_px)

    def _clamp_pair(self, lo, hi):
        if self.bounds is None: return lo, hi
        b0, b1 = self.bounds; span = hi - lo
        if span <= 0:
            x = min(max(lo, b0), b1); return x, x
        lo = max(lo, b0); hi = lo + span
        if hi > b1: hi = b1; lo = hi - span
        return lo, hi

    def _set_line_silent(self, x):
        blk = QtCore.QSignalBlocker(self.line)
        self.line.setPos(x)
        del blk

    def _set_region_silent(self, lo, hi):
        self._setting_region = True
        blockers = [QtCore.QSignalBlocker(self.region)]
        for ln in getattr(self.region, "lines", []):
            try: blockers.append(QtCore.QSignalBlocker(ln))
            except Exception: pass
        self.region.setRegion((lo, hi))
        del blockers
        self._setting_region = False

    def _enter_point(self, x):
        self.region.hide()
        self._set_line_silent(x)
        self.line.show()
        self.wid.setFocus()

    def _enter_region(self, lo, hi):
        self.line.hide()
        self._set_region_silent(lo, hi)
        self.region.show()
        self.wid.setFocus()

    def _schedule_emit(self, lo, hi):
        lo, hi = self._snap(lo), self._snap(hi)
        self._pending = (lo, hi)
        # coalesce within the same event turn
        if not self._emit_timer.isActive():
            self._emit_timer.start(0)

    def _flush_emit(self):
        if self._pending is None: return
        if self._pending != self._last_emitted:
            self._last_emitted = self._pending
            self.rangeSelected.emit(*self._pending)

    # ---------- events ----------
    def _on_click(self, ev):
        if ev.button() != QtCore.Qt.LeftButton: return
        x = self._snap(self.vb.mapSceneToView(ev.scenePos()).x())
        if self._anchor is None:
            self._anchor = x
            x, _ = self._clamp_pair(x, x)
            self._enter_point(x)
            self._schedule_emit(x, x)
        else:
            lo, hi = sorted((self._anchor, x)); self._anchor = None
            if (hi - lo) >= self._tol_dx():
                lo, hi = self._clamp_pair(lo, hi)
                self._enter_region(lo, hi)
                self._schedule_emit(lo, hi)
            else:
                x, _ = self._clamp_pair(x, x)
                self._enter_point(x)
                self._schedule_emit(x, x)

    def _on_point_changed(self):
        x = self._snap(self.line.value())
        x, _ = self._clamp_pair(x, x)
        # keep snapped/clamped without re-trigger storm
        if self.line.value() != x:
            self._set_line_silent(x)
        self._schedule_emit(x, x)

    def _on_region_changed(self):
        if self._setting_region:
            return
        lo, hi = self.region.getRegion()
        lo, hi = self._snap(lo), self._snap(hi)
        if (hi - lo) < self._tol_dx():
            c = self._snap(0.5*(lo+hi))
            c, _ = self._clamp_pair(c, c)
            self._enter_point(c)
            self._schedule_emit(c, c)
        else:
            lo, hi = self._clamp_pair(lo, hi)
            # normalize visuals silently
            self._set_region_silent(lo, hi)
            self._schedule_emit(lo, hi)

    def _nudge(self, dx):
        if self.line.isVisible():
            x = self._snap(self.line.value()) + dx
            self._set_line_silent(x)
            self._schedule_emit(x, x)
        elif self.region.isVisible():
            lo, hi = self.region.getRegion()
            lo, hi = self._snap(lo)+dx, self._snap(hi)+dx
            lo, hi = self._clamp_pair(lo, hi)
            self._set_region_silent(lo, hi)
            self._schedule_emit(lo, hi)

    # ---------- lifecycle ----------
    def detach(self):
        for sig, slot in [
            (self.pi.scene().sigMouseClicked, self._on_click),
            (self.line.sigPositionChanged, self._on_point_changed),
            (self.region.sigRegionChanged, self._on_region_changed),
        ]:
            try: sig.disconnect(slot)
            except TypeError: pass
        for item in (self.line, self.region):
            try: self.pi.removeItem(item)
            except Exception: pass
        for s in getattr(self, "_sc", []):
            try: s.setParent(None)
            except Exception: pass
