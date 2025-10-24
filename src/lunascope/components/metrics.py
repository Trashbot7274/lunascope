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

from PySide6.QtWidgets import QHeaderView, QAbstractItemView, QTableView
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
from PySide6.QtCore import Qt, QSortFilterProxyModel, QRegularExpression, QModelIndex, QSignalBlocker

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


    # ------------------------------------------------------------
    # Attach EDF

    def _update_metrics(self):

        # ------------------------------------------------------------
        # EDF header metrics --> status bar
        
        self.p.silent_proc( 'HEADERS & EPOCH align' )
        df = self.p.table( 'HEADERS' )
        edf_id = self.p.id()
        rec_dur_hms = df.iloc[0, df.columns.get_loc('REC_DUR_HMS')]
        tot_dur_hms = df.iloc[0, df.columns.get_loc('TOT_DUR_HMS')]
        edf_type = df.iloc[0, df.columns.get_loc('EDF_TYPE')]        
        edf_na = self.p.annots().size
        edf_ns = df.iloc[0, df.columns.get_loc('NS')]
        edf_starttime = df.iloc[0, df.columns.get_loc('START_TIME')]
        edf_startdate = df.iloc[0, df.columns.get_loc('START_DATE')]
        df = self.p.table( 'EPOCH' )
        edf_ne = df.iloc[0, df.columns.get_loc('NE')]

        self.sb_id.setText( f"{edf_type}: {edf_id}" )
        self.sb_start.setText( f"Start time: {edf_starttime} date: {edf_startdate}" )
        self.sb_dur.setText( f"Duration: {rec_dur_hms} / {tot_dur_hms} / {edf_ne} epochs" )
        self.sb_ns.setText( f"{edf_ns} signals, {edf_na} annotations" )

        
        # --------------------------------------------------------------------------------
        # get units (for plot labels) 

        hdr = self.p.headers()

        if hdr is not None:
            self.units = dict( zip( hdr.CH , hdr.PDIM ) )
        else:
            self.units = None
        
            
        # ------------------------------------------------------------
        # populate signal box

        df = self.p.table( 'HEADERS' , 'CH' )
        # may be empty EDF
        if len(df.index) > 0:
            df = df[ [ 'CH' , 'PDIM' , 'SR' ] ]
        else:
            df = pd.DataFrame(columns=["CH", "PDIM", "SR"])
            

        # SOURCE model from your DataFrame
        src = self.df_to_model(df)  # must return QStandardItemModel

        # Filter proxy over SOURCE
        self.signals_table_proxy = QSortFilterProxyModel(self.ui.tbl_desc_signals)
        self.signals_table_proxy.setFilterRole(Qt.DisplayRole)
        self.signals_table_proxy.setFilterKeyColumn(-1)  # all columns
        self.signals_table_proxy.setSourceModel(src)

        # Put proxy on the view
        view = self.ui.tbl_desc_signals
        view.setModel(self.signals_table_proxy)

        # View config
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

        # hook a filter box 
        self.ui.txt_signals.textChanged.connect(self.signals_table_proxy.setFilterFixedString)
        self.signals_table_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        
        # Add virtual checkbox column; channel_col_before_insert is SOURCE index of your channel column
        add_check_column(
            view,
            channel_col_before_insert=0,   # change if your "Channel" column isn't the first
            header_text="Sel",
            initial_checked=[],
            on_change=lambda _: (self._clear_pg1(), self._update_scaling(), self._update_pg1()),
        )




        # --------------------------------------------------------------------------------
        # populate annotations box


        # SOURCE model
        df = self.p.annots()
        src = self.df_to_model(df)  # must be QStandardItemModel

        # Filter proxy (works even if you don't filter yet)
        self.annots_table_proxy = QSortFilterProxyModel(self.ui.tbl_desc_annots)
        self.annots_table_proxy.setFilterRole(Qt.DisplayRole)
        self.annots_table_proxy.setFilterKeyColumn(-1)  # all columns
        self.annots_table_proxy.setSourceModel(src)

        # View + proxy
        view = self.ui.tbl_desc_annots
        view.setModel(self.annots_table_proxy)

        # View config
        view.setSortingEnabled(True)
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
        self.ui.txt_annots.textChanged.connect(self.annots_table_proxy.setFilterFixedString)
        self.annots_table_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        # Add checkbox column; index is SOURCE column before insertion
        add_check_column(
            view,
            channel_col_before_insert=0,  # adjust if your key column isn't the first
            header_text="Sel",
            initial_checked=[],
            on_change=lambda anns: (
                self._update_instances(anns),
                self._clear_pg1(),
                self._update_scaling(),
                self._update_pg1(),
            ),
        )

        


        # --------------------------------------------------------------------------------
        # redo original populatio of ssa

        # track all original annots
        self.ssa_anns = self.p.edf.annots()
        self.ssa_anns_lookup = {v: i for i, v in enumerate(self.ssa_anns)}
        
        # but initialize a separate ss for annotations only
        self.ssa = lp.segsrv( self.p )
        self.ssa.populate( chs = [ ] , anns = self.ssa_anns )
        self.ssa.set_annot_format6( False )  # pyqtgraph vs plotly
        
        # populate here, as used by plot_simple (prior to render)
        self.ss_anns = self.ui.tbl_desc_annots.checked()
        self.ss_chs = self.ui.tbl_desc_signals.checked()
        

    # --------------------------------------------------------------------------------
    # populate annotation instances (updated when annots selected)

    def _update_instances(self, anns):
        evts = pd.Series(self.ssa.get_all_annots(anns))

        # always define df
        df = pd.DataFrame(columns=["class", "start", "stop"])

        if len(evts) != 0:
            a = evts.str.rsplit("|", n=1, expand=True)
            b = a[1].str.split("-", n=1, expand=True)

            df = pd.DataFrame({
                "class": a[0].str.strip(),
                "start": pd.to_numeric(b[0], errors="coerce"),
                "stop":  pd.to_numeric(b[1], errors="coerce"),
            }).sort_values("start", ascending=True, na_position="last")
        self.events_model = self.df_to_model(df)

        self.events_table_proxy = QSortFilterProxyModel(self)
        self.events_table_proxy.setSourceModel(self.events_model)

        view = self.ui.tbl_desc_events
        view.setModel(self.events_table_proxy)

        h = view.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(QHeaderView.Interactive)
        
        self.events_table_proxy.setFilterKeyColumn(-1)
        self.events_table_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.ui.txt_events.textChanged.connect(self.events_table_proxy.setFilterFixedString)

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
        rx = QRegularExpression(QRegularExpression.escape(text))
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
        left = self.events_model.data(self.events_model.index(src_row, 1))
        right = self.events_model.data(self.events_model.index(src_row, 2))

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




from typing import Iterable, Optional, Callable, List
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QSortFilterProxyModel

def add_check_column(
    view: QTableView,
    channel_col_before_insert: int,
    header_text: str = "✔",
    initial_checked: Optional[Iterable[str]] = None,
    on_change: Optional[Callable[[List[str]], None]] = None,
    visible_only: bool = False,  # True = affect only filtered rows
) -> None:
    model = view.model()
    proxy: Optional[QSortFilterProxyModel] = None

    if isinstance(model, QSortFilterProxyModel):
        proxy = model
        src = proxy.sourceModel()
    else:
        src = model

    if not isinstance(src, QStandardItemModel):
        raise TypeError("Model must be QStandardItemModel or a QSortFilterProxyModel wrapping one.")

    _squelch = False
    prev_sort = view.isSortingEnabled()
    view.setSortingEnabled(False)

    # insert checkbox col at 0 on SOURCE
    src.insertColumn(0)
    if header_text:
        src.setHeaderData(0, Qt.Horizontal, header_text)
    view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

    checked = set(map(str, initial_checked or []))
    chan_col_after = channel_col_before_insert + 1  # after insertion on SOURCE

    # helpers to iterate rows and map indexes
    def _row_range():
        if proxy and visible_only:
            return range(proxy.rowCount())
        return range(src.rowCount())

    def _s_index(r: int, c: int):
        if proxy and visible_only:
            return proxy.mapToSource(proxy.index(r, c))
        elif proxy and not visible_only:
            # we want ALL rows in source
            return src.index(r, c)  # r already source row in this branch
        else:
            return src.index(r, c)

    # populate without per-item signals
    src.blockSignals(True)
    try:
        if proxy and not visible_only:
            # iterate ALL source rows
            for r in range(src.rowCount()):
                it = QStandardItem()
                it.setEditable(False)
                it.setCheckable(True)
                ch = str(src.data(src.index(r, chan_col_after)))
                it.setCheckState(Qt.Checked if ch in checked else Qt.Unchecked)
                it.setDragEnabled(True)
                it.setDropEnabled(True)
                src.setItem(r, 0, it)
        else:
            # iterate visible rows (proxy) or direct source when no proxy
            for r in _row_range():
                it = QStandardItem()
                it.setEditable(False)
                it.setCheckable(True)
                si = _s_index(r, chan_col_after)
                ch = str(src.data(si))
                it.setCheckState(Qt.Checked if ch in checked else Qt.Unchecked)
                it.setDragEnabled(True)
                it.setDropEnabled(True)
                src.setItem(si.row(), 0, it)
    finally:
        src.blockSignals(False)

    # repaint column 0 via SOURCE so proxy relays it
    def _repaint_col0():
        if not src.rowCount():
            return
        tl = src.index(0, 0)
        br = src.index(src.rowCount() - 1, 0)
        nonlocal _squelch
        was = _squelch
        _squelch = True
        try:
            src.dataChanged.emit(tl, br, [Qt.CheckStateRole])
        finally:
            _squelch = was

    _repaint_col0()

    def _checked() -> List[str]:
        out: List[str] = []
        if proxy and visible_only:
            for r in range(proxy.rowCount()):
                si0 = _s_index(r, 0)
                it = src.item(si0.row(), 0)
                if it and it.checkState() == Qt.Checked:
                    out.append(str(src.data(_s_index(r, chan_col_after))))
        else:
            for r in range(src.rowCount()):
                it = src.item(r, 0)
                if it and it.checkState() == Qt.Checked:
                    out.append(str(src.data(src.index(r, chan_col_after))))
        return out

    setattr(view, "checked", _checked)

    def _loop_set(state: Qt.CheckState, xs: Optional[Iterable[str]] = None):
        nonlocal _squelch
        _squelch = True
        blocker = QSignalBlocker(src)
        try:
            target_set = set(map(str, xs)) if xs is not None else None
            if proxy and visible_only:
                rng = range(proxy.rowCount())
                for r in rng:
                    srow = _s_index(r, 0).row()
                    it = src.item(srow, 0)
                    if it is None:
                        continue
                    if target_set is not None:
                        ch = str(src.data(src.index(srow, chan_col_after)))
                        tgt = Qt.Checked if ch in target_set else Qt.Unchecked
                        if it.checkState() != tgt:
                            it.setCheckState(tgt)
                    else:
                        if it.checkState() != state:
                            it.setCheckState(state)
            else:
                rng = range(src.rowCount())
                for r in rng:
                    it = src.item(r, 0)
                    if it is None:
                        continue
                    if target_set is not None:
                        ch = str(src.data(src.index(r, chan_col_after)))
                        tgt = Qt.Checked if ch in target_set else Qt.Unchecked
                        if it.checkState() != tgt:
                            it.setCheckState(tgt)
                    else:
                        if it.checkState() != state:
                            it.setCheckState(state)
        finally:
            del blocker
            _squelch = False
        _repaint_col0()
        if on_change:
            on_change(_checked())

    setattr(view, "select_all_checks", lambda: _loop_set(Qt.Checked))
    setattr(view, "select_none_checks", lambda: _loop_set(Qt.Unchecked))
    setattr(view, "set", lambda xs: _loop_set(Qt.PartiallyChecked, xs))

    def _on_item_changed(itm: QStandardItem):
        if _squelch or itm.column() != 0:
            return
        if on_change:
            on_change(_checked())

    if not getattr(src, "_checkcol_connected", False):
        src.itemChanged.connect(_on_item_changed)
        setattr(src, "_checkcol_connected", True)

    view.setSortingEnabled(prev_sort)




# --------------------------------------------------------------------------------


def OLD_add_check_column(
    view: QTableView,
    channel_col_before_insert: int,
    header_text: str = "✔",
    initial_checked: Optional[Iterable[str]] = None,
    on_change: Optional[Callable[[List[str]], None]] = None,
) -> None:
    model = view.model()
    if not isinstance(model, QStandardItemModel):
        raise TypeError("Model must be QStandardItemModel.")

    _squelch = False  # guards the slot

    prev_sort = view.isSortingEnabled()
    view.setSortingEnabled(False)

    # insert checkbox column at 0
    model.insertColumn(0)
    if header_text:
        model.setHeaderData(0, Qt.Horizontal, header_text)
    view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

    checked = set(map(str, initial_checked or []))
    chan_col_after = channel_col_before_insert + 1

    # populate check items without emitting per-item signals
    model.blockSignals(True)
    try:
        for r in range(model.rowCount()):
            it = QStandardItem()
            it.setEditable(False)
            it.setCheckable(True)
            ch = str(model.data(model.index(r, chan_col_after)))
            it.setCheckState(Qt.Checked if ch in checked else Qt.Unchecked)
            it.setDragEnabled(True)
            it.setDropEnabled(True)
            model.setItem(r, 0, it)
    finally:
        model.blockSignals(False)

    # single repaint helper
    def _repaint_col0():
        if not model.rowCount():
            return
        tl = model.index(0, 0)
        br = model.index(model.rowCount() - 1, 0)
        # keep squelch during emit to avoid any delegate feedback loops
        nonlocal _squelch
        was = _squelch
        _squelch = True
        try:
            model.dataChanged.emit(tl, br, [Qt.CheckStateRole])
        finally:
            _squelch = was

    # initial repaint so checkmarks show immediately
    _repaint_col0()

    def _checked() -> List[str]:
        out: List[str] = []
        for r in range(model.rowCount()):
            chk = model.item(r, 0)
            if chk and chk.checkState() == Qt.Checked:
                out.append(str(model.data(model.index(r, chan_col_after))))
        return out
    setattr(view, "checked", _checked)

    def _set_all(state: Qt.CheckState):
        nonlocal _squelch
        _squelch = True
        blocker = QSignalBlocker(model)  # suppress itemChanged during loop
        try:
            for r in range(model.rowCount()):
                it = model.item(r, 0)
                if it and it.checkState() != state:
                    it.setCheckState(state)
        finally:
            del blocker
            _squelch = False
        _repaint_col0()
        if on_change:
            on_change(_checked())  # single callback

    setattr(view, "select_all_checks", lambda: _set_all(Qt.Checked))
    setattr(view, "select_none_checks", lambda: _set_all(Qt.Unchecked))

    def _set(xs: Iterable[str]):
        nonlocal _squelch
        xs = set(map(str, xs))
        _squelch = True
        blocker = QSignalBlocker(model)
        try:
            for r in range(model.rowCount()):
                it = model.item(r, 0)
                ch = str(model.data(model.index(r, chan_col_after)))
                target = Qt.Checked if ch in xs else Qt.Unchecked
                if it and it.checkState() != target:
                    it.setCheckState(target)
        finally:
            del blocker
            _squelch = False
        _repaint_col0()
        if on_change:
            on_change(_checked())  # single callback

    setattr(view, "set", _set)

    def _on_item_changed(itm: QStandardItem):
        if _squelch or itm.column() != 0:
            return
        if on_change:
            on_change(_checked())  # per-click

    if not getattr(model, "_checkcol_connected", False):
        model.itemChanged.connect(_on_item_changed)
        setattr(model, "_checkcol_connected", True)

    view.setSortingEnabled(prev_sort)
