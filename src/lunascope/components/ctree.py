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

from PySide6.QtCore import QModelIndex, QItemSelection, QItemSelectionModel
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem

class CTreeMixin:

    def _init_ctree(self):

        # 5 cols
        # ------
        # <domains>
        #  <commands>
        #   Param
        #    <params>
        #   Tables
        #    <tables>
        #     <vars>
        
        # model
        view = self.ui.tree_helper
        
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Element", "Description"])  

        h = view.header()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        
        def add_root(model: QStandardItemModel, name: str, desc="") -> QStandardItem:
            n = QStandardItem(str(name)); n.setEditable(False)
            d = QStandardItem(str(desc)); d.setEditable(False)
            model.invisibleRootItem().appendRow([n, d])
            return n  # return the column-0 item; use it as parent

        def add_child(parent: QStandardItem, name: str, desc="") -> QStandardItem:
            n = QStandardItem(str(name)); n.setEditable(False)
            d = QStandardItem(str(desc)); d.setEditable(False)
            parent.appendRow([n, d])
            return n
    
        # domains
        doms = lp.fetch_doms()

        for dom in doms:
            l1 = add_root( model, dom ,  lp.fetch_desc_dom( dom ) )

            # get commands
            cmds = lp.fetch_cmds( dom )
            for cmd in cmds:
                l2 = add_child( l1 , cmd , lp.fetch_desc_cmd( cmd ) )

                l3p = add_child( l2 , "Parameters" , "" )
                l3o = add_child( l2 , "Outputs" , "" )

                # parameters
                params = lp.fetch_params( cmd )
                for param in params:
                    add_child( l3p , param , lp.fetch_desc_param( cmd , param ) )


                # tables
                tbls = lp.fetch_tbls( cmd )
                for tbl in tbls:
                    l4 = add_child( l3o , tbl , lp.fetch_desc_tbl( cmd , tbl ) )

                    vars = lp.fetch_vars( cmd , tbl )
                    for var in vars:
                        add_child( l4 , var , lp.fetch_desc_var( cmd , tbl , var ) )

        # finish wiring
        view.setModel(model)              
        view.setUniformRowHeights(True)
        view.setAlternatingRowColors(True)
        view.collapseAll()
        view.resizeColumnToContents(0)

        # set filter
        view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        # wire filter
        self.ui.flt_ctree.textChanged.connect(
            lambda txt: expand_and_show_matches(self.ui.tree_helper, txt , partial = True )
        )
            

def expand_and_show_matches(view, needle: str, partial=True, case_insensitive=True):
    m = view.model()
    if m is None or needle is None:
        return

    text = needle.strip()
    if not text:
        view.collapseAll()
        return

    needle_cmp = text.lower() if case_insensitive else text

    matches = []  # outer scope list; append is OK (no nonlocal needed)

    def is_match(s: str) -> bool:
        if s is None:
            return False
        a = s.lower() if case_insensitive else s
        return (needle_cmp in a) if partial else (a == needle_cmp)

    def walk(parent: QModelIndex):
        for r in range(m.rowCount(parent)):
            idx = m.index(r, 0, parent)          # column 0
            if is_match(m.data(idx)):
                p = idx
                while p.isValid():
                    view.expand(p)
                    p = p.parent()
                matches.append(idx)
            walk(idx)

    view.setUpdatesEnabled(False)
    view.collapseAll()
    walk(QModelIndex())
    view.setUpdatesEnabled(True)

    sm = view.selectionModel()
    if not matches or sm is None:
        return

    # allow multi-select if you want all matches highlighted
    view.setSelectionMode(QAbstractItemView.ExtendedSelection)

    sel = QItemSelection()
    for idx in matches:
        sel.merge(QItemSelection(idx, idx), QItemSelectionModel.Select)
    sm.select(sel, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
    view.scrollTo(matches[0], QAbstractItemView.PositionAtCenter)

    
