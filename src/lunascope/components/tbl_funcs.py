
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


from PySide6.QtCore import Qt, QSize, QObject
from PySide6.QtWidgets import (
    QApplication, QComboBox, QStyledItemDelegate, QTableView,
    QStyle, QStyleOptionViewItem, QHeaderView
)
from PySide6.QtGui import QIcon, QStandardItem


from typing import Iterable, Optional, Callable, List
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QSortFilterProxyModel


class ComboDelegate(QStyledItemDelegate):
    def __init__(self, items, parent: QObject | None = None):
        super().__init__(parent)
        self.items = list(items)

    # do not paint the cell text when using a persistent editor
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = QIcon()
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter)

    def createEditor(self, parent, option, index):
        w = QComboBox(parent)
        w.addItems(self.items)
        w.setEditable(False)
        w.setFrame(False)
        w.setStyleSheet("QComboBox{padding:0;margin:0;}QComboBox::down-arrow{image:none;}QComboBox::drop-down{width:0;border:0;}")
        # commit to model whenever selection changes
        w.currentIndexChanged.connect(lambda _=None, ed=w: self.commitData.emit(ed))
        return w

    def updateEditorGeometry(self, editor, option, index):
        # leave the right grid line visible
        r = option.rect.adjusted(0, 0, -1, 0)
        editor.setGeometry(r)
                
    def sizeHint(self, option, index):
        return QSize(80, option.rect.height())

    def setEditorData(self, editor, index):
        val = index.data(Qt.EditRole) or index.data(Qt.DisplayRole) or ""
        i = editor.findText(str(val))
        editor.setCurrentIndex(i if i >= 0 else 0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)


def add_combo_column(
    view: QTableView,
    header_text: str,
    items,
    default_value: str | None = None,
    insert_source_col: int | None = None,
    open_persistent: bool = True,
    on_change=None,
    width: int = 90,
    resize_mode: QHeaderView.ResizeMode = QHeaderView.Fixed,
) -> int:
    """
    Adds a compact combo column to a QTableView that is bound to either:
      - a QSortFilterProxyModel over a QStandardItemModel, or
      - a QStandardItemModel directly.

    Returns the proxy column index for further use.
    """
    proxy = view.model()
    if proxy is None:
        raise RuntimeError("view has no model")

    # get source model if proxy, else the model itself
    try:
        src = proxy.sourceModel()
    except AttributeError:
        src = proxy

    nrows = src.rowCount()
    ncols = src.columnCount()

    col = ncols if insert_source_col is None else int(insert_source_col)
    src.insertColumn(col)
    src.setHeaderData(col, Qt.Horizontal, header_text)

    if default_value is None:
        default_value = next(iter(items), "")

    for r in range(nrows):
        it = QStandardItem(str(default_value))
        it.setEditable(True)
        it.setSelectable(True)
        it.setEnabled(True)
        src.setItem(r, col, it)

    # map to proxy column
    if src is proxy:
        proxy_col = col
    else:
        if nrows > 0:
            proxy_col = proxy.mapFromSource(src.index(0, col)).column()
        else:
            # safe fallback when no rows exist yet
            proxy_col = col

    # install delegate and keep it alive
    delegate = ComboDelegate(items, view)
    view.setItemDelegateForColumn(proxy_col, delegate)
    if not hasattr(view, "_column_delegates"):
        view._column_delegates = {}
    view._column_delegates[proxy_col] = delegate

    # width and resize policy
    view.horizontalHeader().setSectionResizeMode(proxy_col, resize_mode)
    view.setColumnWidth(proxy_col, width)

    # open editors so the combo is always visible
    def _open_all_persistent():
        prow = proxy.rowCount()
        for r in range(prow):
            idx = proxy.index(r, proxy_col)
            view.openPersistentEditor(idx)

    if open_persistent:
        _open_all_persistent()

        # keep new rows opened too
        def _rows_inserted(*_):
            _open_all_persistent()
        src.rowsInserted.connect(_rows_inserted)

    # optional change hook
    if on_change is not None:
        def _emit_change(*_):
            on_change(None)
        src.dataChanged.connect(_emit_change)

    return proxy_col






# -----------------------------------------------------------------------------


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



# ------------------------------------------------------------
#
# filter tabels
#
# ------------------------------------------------------------
        
def attach_comma_filter(table_view, line_edit, proxy=None):
    from PySide6.QtCore import Qt, QRegularExpression, QSortFilterProxyModel

    # create new proxy only if none provided
    if proxy is None:
        proxy = QSortFilterProxyModel(table_view)
        proxy.setSourceModel(table_view.model())
        table_view.setModel(proxy)
    else:
        # already the view's model; do not setSourceModel again
        if table_view.model() is not proxy:
            proxy.setSourceModel(table_view.model())
            table_view.setModel(proxy)

    def on_text_changed(text: str):
        parts = [s.strip() for s in text.split(',') if s.strip()]
        if not parts:
            proxy.setFilterRegularExpression(QRegularExpression())
            return
        esc = [QRegularExpression.escape(p) for p in parts]
        rx = QRegularExpression("(" + "|".join(esc) + ")")
        rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        proxy.setFilterRegularExpression(rx)

    # avoid duplicate connects
    if not hasattr(proxy, "_comma_filter_connected"):
        line_edit.textChanged.connect(on_text_changed)
        proxy._comma_filter_connected = True

    proxy.setFilterKeyColumn(-1)
    proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
    return proxy
