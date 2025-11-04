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

import pandas as pd
import numpy as np
import lunapi as lp

from typing import Callable, Iterable, List, Optional

from scipy.signal import butter, sosfilt

from PySide6.QtWidgets import QHeaderView, QAbstractItemView, QTableView, QMessageBox
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression, QModelIndex, QSignalBlocker
from PySide6.QtCore import QTimer
        
from ..helpers import sort_df_by_list
from .tbl_funcs import add_combo_column, add_check_column, attach_comma_filter


# drop-in: minimal changes to make combo editors persist across filtering

from PySide6.QtWidgets import QStyledItemDelegate, QComboBox, QStyleOptionViewItem, QStyle
from PySide6.QtCore import Qt

class _ComboDelegate(QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.addItems(self.items)
        def _commit_later():
            # defer commit until the editor is fully attached to the view
            QTimer.singleShot(0, lambda: (
                self.commitData.emit(cb),
                self.closeEditor.emit(cb, QStyledItemDelegate.NoHint)
            ))
        cb.currentIndexChanged.connect(_commit_later)
        return cb


    def setEditorData(self, editor, index):
        v = index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or "None"
        i = editor.findText(v)
        editor.setCurrentIndex(max(0, i))

    def setModelData(self, editor, model, index):
        t = editor.currentText()
        model.setData(index, t, Qt.EditRole)
        model.setData(index, t, Qt.DisplayRole)

    # avoid “double text” under the combo
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""  # suppress underlying text
        if option.widget:
            option.widget.style().drawControl(QStyle.CE_ItemViewItem, opt, painter, option.widget)
        else:
            super().paint(painter, opt, index)



            

class MetricsMixin:

    def _init_metrics(self):
        
        # signal table
        view = self.ui.tbl_desc_signals
        view.setSortingEnabled(True)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)  
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(50)
        h.setDefaultSectionSize(150)
        view.resizeColumnsToContents()
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        view.verticalHeader().setVisible(False)
                
        # annots table

        view = self.ui.tbl_desc_annots
        view.setSortingEnabled(True)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(50)
        h.setDefaultSectionSize(150)
        view.resizeColumnsToContents()
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        view.verticalHeader().setVisible(False)
                
        # wiring
        self.ui.butt_sig.clicked.connect( self._toggle_sigs )
        self.ui.butt_annot.clicked.connect( self._toggle_annots )

        
    def _toggle_sigs(self):
        n = len(self.ui.tbl_desc_signals.checked())
        if n == 0:
            self.ui.tbl_desc_signals.select_all_checks()
        else:
            self.ui.tbl_desc_signals.select_none_checks()        
        self._update_pg1()

    def _toggle_annots(self):
        n = len(self.ui.tbl_desc_annots.checked())
        if n == 0:
            self.ui.tbl_desc_annots.select_all_checks()
        else:
            self.ui.tbl_desc_annots.select_none_checks()
        self._update_pg1()

        
    def all_labels(self,view):
        m = view.model()
        return [m.data(m.index(r, 0)) for r in range(m.rowCount())]

        
    # ------------------------------------------------------------
    # Attach EDF

    def _update_metrics(self):

        # ------------------------------------------------------------
        # EDF header metrics --> status bar
        
        self.p.silent_proc( 'HEADERS & EPOCH align' )

        df = self.p.table( 'EPOCH' )
        try:
            edf_ne = df.iloc[0, df.columns.get_loc('NE')]
        except KeyError:
            QMessageBox.critical(self, "Problem", "Likely no unmasked epochs left\nGoing to refresh the EDF" )
            self._refresh()
            return        
        
        df = self.p.table( 'HEADERS' )
        edf_id = self.p.id()
        rec_dur_hms = df.iloc[0, df.columns.get_loc('REC_DUR_HMS')]
        tot_dur_hms = df.iloc[0, df.columns.get_loc('TOT_DUR_HMS')]
        edf_type = df.iloc[0, df.columns.get_loc('EDF_TYPE')]        
        edf_na = self.p.annots().size
        edf_ns = df.iloc[0, df.columns.get_loc('NS')]
        edf_starttime = df.iloc[0, df.columns.get_loc('START_TIME')]
        edf_startdate = df.iloc[0, df.columns.get_loc('START_DATE')]


        self.sb_id.setText( f"{edf_type}: {edf_id}" )
        self.sb_start.setText( f"Start time: {edf_starttime} date: {edf_startdate}" )
        self.sb_dur.setText( f"Duration: {rec_dur_hms} / {tot_dur_hms} / {edf_ne} epochs" )
        self.sb_ns.setText( f"{edf_ns} signals, {edf_na} annotations" )

        
        # --------------------------------------------------------------------------------
        # get units (for plot labels) and sample rates (for filters)

        hdr = self.p.headers()

        if hdr is not None:
            self.units = dict( zip( hdr.CH , hdr.PDIM ) )
            self.srs   = dict( zip( hdr.CH , hdr.SR ) )
        else:
            self.units = None
            self.srs = None
        
            
        # ------------------------------------------------------------
        # populate signal box


        df = self.p.table('HEADERS', 'CH')
        if len(df.index) > 0:
            df = df[['CH', 'PDIM', 'SR']]
        else:
            df = pd.DataFrame(columns=["CH", "PDIM", "SR"])

        if self.cmap_list:
            df = sort_df_by_list(df, 0, self.cmap_list)

        # SOURCE model from your DataFrame
        src_sig = self.df_to_model(df)  # QStandardItemModel

        # add filter proxy
        self.signals_table_proxy = attach_comma_filter(
            self.ui.tbl_desc_signals,
            self.ui.txt_signals
        )
        self.signals_table_proxy.setSourceModel(src_sig)

        # Put proxy on the view
        view = self.ui.tbl_desc_signals
        view.setModel(self.signals_table_proxy)
        
        # View config
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(50)
        h.setDefaultSectionSize(150)
        view.resizeColumnsToContents()
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        view.verticalHeader().setVisible(False)

        # Add virtual checkbox column (unchanged)
        add_check_column(
            view,
            channel_col_before_insert=0,
            header_text="Sel",
            initial_checked=[],
            on_change=lambda _: (self._clear_pg1(), self._update_scaling(), self._update_pg1()),
        )

        # --- minimal change start: make a real model column for the combo and bind a delegate ---

        # Fixed schema after checkbox insert:
        # Sel(0), CH(1), PDIM(2), SR(3)  -> insert Filter at source col 3? You used 2 originally.
        # Keep your original: insert at source col 2, which shifts PDIM->3, SR->4
        SRC_COL_FILTER = 2
        SRC_COL_CH     = 1
        SRC_COL_SR     = 4
        PROXY_COL_FILTER = 2  # columns/order fixed per your note

        # ensure Filter column exists on SOURCE with default values
        src_sig.insertColumn(SRC_COL_FILTER)
        src_sig.setHeaderData(SRC_COL_FILTER, Qt.Horizontal, "Filter")
        for r in range(src_sig.rowCount()):
            idx = src_sig.index(r, SRC_COL_FILTER)
            if not (idx.data(Qt.DisplayRole) or idx.data(Qt.EditRole)):
                src_sig.setData(idx, "None", Qt.EditRole)
                src_sig.setData(idx, "None", Qt.DisplayRole)

        # bind delegate on the PROXY column and reopen editors after proxy changes
        filt_items = ["None", "0.3-35Hz", "Slow", "Delta", "Theta", "Alpha", "Sigma", "Beta", "Gamma"]
        view.setItemDelegateForColumn(PROXY_COL_FILTER, _ComboDelegate(filt_items, view))

        def _open_all():
            proxy = self.signals_table_proxy
            for r in range(proxy.rowCount()):
                view.openPersistentEditor(proxy.index(r, PROXY_COL_FILTER))

        _open_all()
        self.signals_table_proxy.modelReset.connect(_open_all)
        self.signals_table_proxy.layoutChanged.connect(_open_all)
        self.signals_table_proxy.rowsInserted.connect(lambda *a: _open_all())

        # widths
        view.setColumnWidth(PROXY_COL_FILTER, 90)
        view.setColumnWidth(0, 10)
        view.horizontalHeader().setSectionResizeMode(PROXY_COL_FILTER, QHeaderView.Fixed)

        



        # inside your setup method
        self._signals_proxy = self.signals_table_proxy
        self._signals_view  = self.ui.tbl_desc_signals
        PROXY_COL_FILTER = 2

        def _reopen_all():
            for r in range(self._signals_proxy.rowCount()):
                idx = self._signals_proxy.index(r, PROXY_COL_FILTER)
                if idx.isValid():
                    self._signals_view.openPersistentEditor(idx)
                    
        def _reopen_all_later():
            QTimer.singleShot(0, _reopen_all)
            
        # store on self so they can be reused / disconnected cleanly later
        self._reopen_all_filters = _reopen_all
        self._reopen_all_filters_later = _reopen_all_later

        p = self._signals_proxy
        p.modelReset.connect(_reopen_all_later)
        p.layoutChanged.connect(_reopen_all_later)
        p.rowsInserted.connect(lambda *_: _reopen_all_later())
        p.rowsRemoved.connect(lambda *_: _reopen_all_later())
        p.rowsMoved.connect(lambda *_: _reopen_all_later())
        p.dataChanged.connect(lambda *_: _reopen_all_later())
        
        self.ui.txt_signals.textChanged.connect(lambda *_: _reopen_all_later())
        _reopen_all_later()

        
        # --- minimal change end ---

        proxy = view.model()
        src_sig = getattr(proxy, "sourceModel", None) and proxy.sourceModel() or proxy

        # hardcode target_src_col: we know it's the Filter column at 2; CH at 1; SR at 4
        target_src_col = SRC_COL_FILTER
        CH_SRC_COL = SRC_COL_CH

        def on_sig_changed(top_left, bottom_right, roles, *,
                           src=src_sig, target_col=target_src_col, ch_col=CH_SRC_COL):
            if not (top_left.column() <= target_col <= bottom_right.column()):
                return
            for r in range(top_left.row(), bottom_right.row() + 1):
                val = src.index(r, target_col).data(Qt.EditRole) or 'None'
                ch_label = src.index(r, ch_col).data(Qt.DisplayRole)
                sr = src.index(r, SRC_COL_SR).data(Qt.DisplayRole)

            if val == 'None':
                self.fmap.pop(ch_label, None)
                self.ss.clear_filter(ch_label)
            else:
                self.fmap[ch_label] = val
                frqs = self.fmap_frqs[val]
                sr = float(sr)
                if frqs[1] <= sr / 2:
                    order = 2
                    sos = butter(order, frqs, btype='band', fs=sr, output='sos')
                    self.ss.apply_filter(ch_label, sos.reshape(-1))

            self._clear_pg1()
            self._update_scaling()
            self._update_pg1()

        # add wiring
        src_sig.dataChanged.connect(on_sig_changed)



        # ---- OLD VERSION OF ABOVE BELOW... w/ Broken combo / proxy stuff... --- 

        # df = self.p.table( 'HEADERS' , 'CH' )
        # # may be empty EDF
        # if len(df.index) > 0:
        #     df = df[ [ 'CH' , 'PDIM' , 'SR' ] ]
        # else:
        #     df = pd.DataFrame(columns=["CH", "PDIM", "SR"])

        # # re-order channels based on a cmap?
        # if self.cmap_list:
        #     df = sort_df_by_list( df , 0 , self.cmap_list )
            
        # # SOURCE model from your DataFrame
        # src_sig = self.df_to_model(df)  # must return QStandardItemModel        
        
        # # add filter proxy
        # self.signals_table_proxy = attach_comma_filter(
        #     self.ui.tbl_desc_signals,
        #     self.ui.txt_signals          
        # )

        # self.signals_table_proxy.setSourceModel(src_sig)

        # # Put proxy on the view
        # view = self.ui.tbl_desc_signals
        # view.setModel(self.signals_table_proxy)

        # # View config
        # view.setSortingEnabled(False)
        # h = view.horizontalHeader()
        # h.setSectionResizeMode(QHeaderView.Interactive)
        # h.setStretchLastSection(False)
        # h.setMinimumSectionSize(50)
        # h.setDefaultSectionSize(150)
        # view.resizeColumnsToContents()
        # view.setSelectionBehavior(QAbstractItemView.SelectRows)
        # view.setSelectionMode(QAbstractItemView.SingleSelection)
        # view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # view.verticalHeader().setVisible(False)

        
        # # Add virtual checkbox column; channel_col_before_insert is SOURCE index of your channel column
        # add_check_column(
        #     view,
        #     channel_col_before_insert=0,   # change if your "Channel" column isn't the first
        #     header_text="Sel",
        #     initial_checked=[],
        #     on_change=lambda _: (self._clear_pg1(), self._update_scaling(), self._update_pg1()),
        # )

        # # add combo dropdown for filtering
        # proxy_col = add_combo_column(
        #     view=self.ui.tbl_desc_signals,
        #     header_text="Filter",
        #     items=["None", "0.3-35Hz", "Slow", "Delta", "Theta", "Alpha", "Sigma", "Beta" , "Gamma" ],
        #     default_value="None",
        #     insert_source_col=2,   # if None, append
        #     open_persistent=True,
        #     on_change=lambda _: (self._clear_pg1(), self._update_scaling(), self._update_pg1()),
        #     width=90,
        #     resize_mode=QHeaderView.Fixed,
        # )

        # view = self.ui.tbl_desc_signals
        # view.setColumnWidth(proxy_col, 90)
        # view.setColumnWidth(0, 10) 
        # view.horizontalHeader().setSectionResizeMode(proxy_col, QHeaderView.Fixed)

        # proxy = view.model()
        # src_sig = getattr(proxy, "sourceModel", None) and proxy.sourceModel() or proxy

        # # map proxy_col -> source column
        # if src_sig is proxy:
        #     target_src_col = proxy_col
        # else:
        #     target_src_col = proxy.mapToSource(proxy.index(0, proxy_col)).column()

        # CH_SRC_COL = 1
        
        # def on_sig_changed(top_left, bottom_right, roles, *,
        #                    src=src_sig, target_col=target_src_col, ch_col=CH_SRC_COL ):
        #     if not (top_left.column() <= target_col <= bottom_right.column()):
        #         return
        #     for r in range(top_left.row(), bottom_right.row() + 1):
        #         val = src.index(r, target_col).data(Qt.EditRole)
        #         ch_label = src.index(r, ch_col).data(Qt.DisplayRole)
        #         sr_col = 4 # currently, SR in 5th col.
        #         sr = src.index(r, sr_col).data(Qt.DisplayRole)
        #         if val == 'None':
        #             self.fmap.pop( ch_label , None )
        #             self.ss.clear_filter( ch_label )
        #         else:
        #             # for pg1_simple()
        #             self.fmap[ ch_label ] = val

        #             # for segsrv (rendered) signals
        #             frqs = self.fmap_frqs[ val ]
        #             sr = float( sr )
        #             if frqs[1] <= sr/2:
        #                 order = 2
        #                 sos = butter( order ,
        #                               frqs, 
        #                               btype='band',
        #                               fs= sr , 
        #                               output='sos' )

        #             self.ss.apply_filter( ch_label , sos.reshape(-1) )

        #         # update view
        #         self._clear_pg1()
        #         self._update_scaling()
        #         self._update_pg1()


        # # add wiring
        # src_sig.dataChanged.connect(on_sig_changed)
            
        
        
        # --------------------------------------------------------------------------------
        # populate annotations box


        # SOURCE model
        df = self.p.annots()

        # re-order channels based on a cmap?                                                                                             
        if self.cmap_list:
            df = sort_df_by_list( df , 0 , self.cmap_list )
        
        src = self.df_to_model(df)  # must be QStandardItemModel
        
        # add filter proxy
        self.annots_table_proxy = attach_comma_filter(
            self.ui.tbl_desc_annots,
            self.ui.txt_annots            
        )

        self.annots_table_proxy.setSourceModel(src)

        # View + proxy
        view = self.ui.tbl_desc_annots
        view.setModel(self.annots_table_proxy)

        # View config
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        h.setMinimumSectionSize(50)
        h.setDefaultSectionSize(150)
        view.resizeColumnsToContents()
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        view.verticalHeader().setVisible(False)

        # hook a filter box 
#        self.ui.txt_annots.textChanged.connect(self.annots_table_proxy.setFilterFixedString)
#        self.annots_table_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        # Add checkbox column; index is SOURCE column before insertion
        add_check_column(
            view,
            channel_col_before_insert=0,  
            header_text="Sel",
            initial_checked=[],
            on_change=lambda anns: (
                self._update_instances(anns),
                self._clear_pg1(),
                self._update_scaling(),
                self._update_pg1()
            ),
        )



        
        # --------------------------------------------------------------------------------
        # redo original population of ssa

        # track all original annots (to keep the same y-axes)
        self.ssa_anns = self.p.edf.annots()
        self.ssa_anns_lookup = {v: i for i, v in enumerate(self.ssa_anns)}
        
        # but initialize a separate ss for annotations only
        # for lookups (event instance listing)
        self.ssa = lp.segsrv( self.p )
        self.ssa.populate( chs = [ ] , anns = self.ssa_anns )
        self.ssa.set_annot_format6( False )  # pyqtgraph vs plotly
        self.ssa.window(self.last_x1, self.last_x2) 
        
        # populate here, as used by plot_simple (prior to render)
        self.ss_anns = self.ui.tbl_desc_annots.checked()
        self.ss_chs = self.ui.tbl_desc_signals.checked()

        # update palette
        self.set_palette()
        

    # --------------------------------------------------------------------------------
    # populate annotation instances (updated when annots selected)

    def _update_instances(self, anns):

        # request w/ hms and duration also (True)                                                                                                                                                                                           
        evts = pd.Series(self.ssa.get_all_annots(anns, True ))
	
        # always define df                                                                                                                                                                                                                  
        df = pd.DataFrame(columns=["class", "hms", "start", "dur"])

        if len(evts) != 0:
            a = evts.str.rsplit("| ", n=3, expand=True)
            b = a[1].str.split("-", n=1, expand=True)

            df = pd.DataFrame({
                "class": a[0].str.strip(),
                "hms": a[2].str.strip(),
                "start": pd.to_numeric(b[0], errors="coerce"),
                "dur": pd.to_numeric(a[3], errors="coerce")
            }).sort_values("start", ascending=True, na_position="last")
        self.events_model = self.df_to_model(df)
        
        self.events_table_proxy = QSortFilterProxyModel(self)
        self.events_table_proxy.setSourceModel(self.events_model)

        view = self.ui.tbl_desc_events
        view.setModel(self.events_table_proxy)

        self.events_table_proxy = attach_comma_filter(self.ui.tbl_desc_events, self.ui.txt_events)
        
        h = view.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Interactive)
        
        #self.events_table_proxy.setFilterKeyColumn(-1)
        #self.events_table_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        #self.ui.txt_events.textChanged.connect(self.events_table_proxy.setFilterFixedString)
#        self.ui.txt_events.textChanged.connect( self._on_events_filter_text )

        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSelectionBehavior(QAbstractItemView.SelectRows)
        view.setSelectionMode(QAbstractItemView.SingleSelection)
        view.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        sel = view.selectionModel()
        sel.currentRowChanged.connect(self._on_row_changed)


    # ------------------------------------------------------------    
    # events table: allow filtering of events

    def _on_events_filter_text(self, text: str):
        # split on commas and trim
        parts = [s.strip() for s in text.split(',') if s.strip()]
        if not parts:
            self.events_table_proxy.setFilterRegularExpression(QRegularExpression())  # clear filter
            return

        # build an OR regex safely escaped
        escaped = [QRegularExpression.escape(p) for p in parts]
        pattern = "(" + "|".join(escaped) + ")"
        rx = QRegularExpression(pattern)
        rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self.events_table_proxy.setFilterRegularExpression(rx)

    

    # ------------------------------------------------------------    
    # events table: row-change callback

    def _on_row_changed(self, curr: QModelIndex, _prev: QModelIndex):
        if not curr.isValid():
            return
        proxy_row = curr.row()
        src_idx   = self.events_table_proxy.mapToSource(curr)
        src_row   = src_idx.row()

        # get interval            
        left = float(self.events_model.data(self.events_model.index(src_row, 2)))
        right = left + float(self.events_model.data(self.events_model.index(src_row, 3)))

        # expand?
        left , right = expand_interval( left, right )

        # set range and this should(?) update the plot
        self.sel.setRange( left , right )
        
        # update plot
        if self.rendered: self.on_window_range( left , right )
        


        
#------------------------------------------------------------------
# helper functions


def expand_interval(left, right, *, factor=2.0, point_width=10.0, min_left=0.0):
    """
    Expand [left, right] to a wider interval centered on it.
    - factor: final_width = factor * original_width (>=1 recommended)
    - if left == right: use `point_width`
    - clamp so left >= min_left by shifting right without changing width
    """
    a, b = sorted((float(left), float(right)))

    if a == b:
        half = point_width / 2.0
        L = max(min_left, a - half)
        R = L + point_width
        return L, R

    if factor <= 0:
        raise ValueError("factor must be > 0")

    w = b - a
    new_w = w * factor
    pad = 0.5 * (new_w - w)

    L = a - pad
    R = b + pad

    if L < min_left:
        shift = min_left - L
        L += shift
        R += shift
    return L, R



