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
from os import path
import os
from pathlib import Path
        
from PySide6.QtWidgets import QFileDialog, QHeaderView, QAbstractItemView
from PySide6.QtCore import Qt, QDir, QRegularExpression, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem

class SListMixin:

    def _init_slist(self):
        # for filtering the slist table
        self._proxy = QSortFilterProxyModel( self.ui.tbl_slist )
        self._proxy.setFilterRole(Qt.DisplayRole)
        self._proxy.setFilterKeyColumn(-1)  # all columns
        self.ui.tbl_slist.setModel(self._proxy)

        # wire buttons
        self.ui.butt_load_slist.clicked.connect(self.open_file)
        self.ui.butt_build_slist.clicked.connect(self.open_folder)
        self.ui.butt_load_edf.clicked.connect(self.open_edf)
        self.ui.butt_load_annot.clicked.connect(self.open_annot)
        self.ui.butt_refresh.clicked.connect(self._refresh)
        
        # filter SL
        self.ui.flt_slist.textChanged.connect( self._on_filter_text)

        # wire select ID from slist --> load
        self.ui.tbl_slist.selectionModel().currentRowChanged.connect( self._attach_inst )
        

    # wire filter for slists
    def _on_filter_text(self, t: str):
        rx = QRegularExpression(QRegularExpression.escape(t))
        rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self._proxy.setFilterRegularExpression(rx)
        

    # ------------------------------------------------------------
    # Load slist from a file
    # ------------------------------------------------------------
        
    def open_file(self):

        slist, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Open sample-list file",
            "",
            "slist (*.lst *.txt);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        # set the path , i.e. to handle relative sample lists

        folder_path = str(Path(slist).parent) + os.sep

        self.proj.var( 'path' , folder_path )
        
        self._read_slist_from_file( slist )


    # ------------------------------------------------------------
    # Build slist from a folder
    # ------------------------------------------------------------

    def _read_slist_from_file( self, slist : str ):
        if slist:
            # load sample list into luna
            self.proj.sample_list( slist )

            # get the SL
            df = self.proj.sample_list()

            # assgin to model
            model = self.df_to_model( df )              
            self._proxy.setSourceModel(model)

            # display options resize
            view = self.ui.tbl_slist
#            view.setSortingEnabled(True)
            h = view.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.Interactive)  # user-resizable
            h.setStretchLastSection(False)                   # no auto-stretch fighting you
            view.resizeColumnsToContents()  
            view.setSelectionBehavior(QAbstractItemView.SelectRows)
            view.setSelectionMode(QAbstractItemView.SingleSelection)
            view.verticalHeader().setVisible(True)
            # update label to show slist file
            self.ui.lbl_slist.setText( slist )

            
    # ------------------------------------------------------------
    # Build slist from a folder
    # ------------------------------------------------------------
        
    def open_folder(self):

        folder = QFileDialog.getExistingDirectory( self.ui , "Select Folder", QDir.currentPath(),
                                                   options=QFileDialog.Option.DontUseNativeDialog )

        # update
        if folder != "":

            # build SL
            self.proj.build( folder )

            # get the SL
            df = self.proj.sample_list()

            # assgin to model
            model = self.df_to_model( df )              
            self._proxy.setSourceModel(model)

            # display options resize
            view = self.ui.tbl_slist
#            view.setSortingEnabled(True)
            h = view.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.Interactive)  # user-resizable
            h.setStretchLastSection(False)                   # no auto-stretch fighting you
            view.resizeColumnsToContents()  
            view.setSelectionBehavior(QAbstractItemView.SelectRows)
            view.setSelectionMode(QAbstractItemView.SingleSelection)
            view.verticalHeader().setVisible(True)
            # update label to show slist file
            self.ui.lbl_slist.setText( folder )

            
    # ------------------------------------------------------------
    # Load EDF from a file
    # ------------------------------------------------------------
        
    def open_edf(self):

        edf_file , _ = QFileDialog.getOpenFileName(
            self.ui,
            "Open EDF file",
            "",
            "EDF (*.edf *.rec);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        # update
        if edf_file != "":

            base = path.splitext(path.basename(edf_file))[0]

            row = [ base , edf_file , "." ] 
            
            # specify SL directly
            self.proj.clear()
            self.proj.eng.set_sample_list( [ row ] )

            # get the SL
            df = self.proj.sample_list()

            # assgin to model
            model = self.df_to_model( df )              
            self._proxy.setSourceModel(model)

            # display options resize
            view = self.ui.tbl_slist
#            view.setSortingEnabled(True)
            h = view.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.Interactive)  # user-resizable
            h.setStretchLastSection(False)                   # no auto-stretch fighting you
            view.resizeColumnsToContents()  
            view.setSelectionBehavior(QAbstractItemView.SelectRows)
            view.setSelectionMode(QAbstractItemView.SingleSelection)
            view.verticalHeader().setVisible(True)
            # update label to show slist file
            self.ui.lbl_slist.setText( '<internal>' )

            # and prgrammatically select this first row
            model = self.ui.tbl_slist.model()
            if model and model.rowCount() > 0:
                self.ui.tbl_slist.selectRow(0)
                idx = model.index(0, 0)
                self._attach_inst(idx, None)
            

    # ------------------------------------------------------------
    # Reload same EDF, i.e. refresh

    def _refresh(self):

        view = self.ui.tbl_slist
        model = view.model()
        if not model: return

        sel = view.selectionModel()
        row = 0
        if sel and sel.currentIndex().isValid():
            row = sel.currentIndex().row()

        # if the model changed, clamp to bounds
        row = max(0, min(row, model.rowCount() - 1)) if model.rowCount() else -1
        if row < 0: return

        view.selectRow(row)
        idx = model.index(row, 0)
        self._attach_inst(idx, None)
                        

    # ------------------------------------------------------------
    # Load .annot from a file
        
    def open_annot(self):

        annot_file , _ = QFileDialog.getOpenFileName(
            self.ui,
            "Open annotation file",
            "",
            "EDF (*.annot *.eannot *.xml *.tsv *.txt);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        # update
        if annot_file != "":

            base = path.splitext(path.basename(annot_file))[0]

            row = [ base ,".", annot_file ] 
            
            # specify SL directly
            self.proj.clear()
            self.proj.eng.set_sample_list( [ row ] )

            # get the SL
            df = self.proj.sample_list()

            # assgin to model
            model = self.df_to_model( df )              
            self._proxy.setSourceModel(model)

            # display options resize
            view = self.ui.tbl_slist
#            view.setSortingEnabled(True)
            h = view.horizontalHeader()
            h.setSectionResizeMode(QHeaderView.Interactive)  # user-resizable
            h.setStretchLastSection(False)                   # no auto-stretch fighting you
            view.resizeColumnsToContents()  
            view.setSelectionBehavior(QAbstractItemView.SelectRows)
            view.setSelectionMode(QAbstractItemView.SingleSelection)
            view.verticalHeader().setVisible(True)
            # update label to show slist file
            self.ui.lbl_slist.setText( '<internal>' )

            # and prgrammatically select this first row
            model = self.ui.tbl_slist.model()
            if model and model.rowCount() > 0:
                self.ui.tbl_slist.selectRow(0)
                idx = model.index(0, 0)
                self._attach_inst(idx, None)

                
    # ------------------------------------------------------------
    # Populate sample-list table
    # ------------------------------------------------------------

    @staticmethod
    def df_to_model(df) -> QStandardItemModel:
        m = QStandardItemModel(df.shape[0], df.shape[1])
        m.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(df.shape[0]):
            for c in range(df.shape[1]):
                v = df.iat[r, c]
                # stringify lists/sets for display
                s = ", ".join(map(str, v)) if isinstance(v, (list, tuple, set)) else ("" if pd.isna(v) else str(v))
                m.setItem(r, c, QStandardItem(s))
        #m.setVerticalHeaderLabels([str(i) for i in df.index])
        return m

