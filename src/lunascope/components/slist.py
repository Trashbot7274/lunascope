
import pandas as pd
import numpy as np
from os import fspath, path

from PySide6.QtWidgets import QApplication, QFileDialog, QTableView, QHeaderView, QLineEdit, QAbstractItemView
from PySide6.QtCore import Qt, QFile, QDir, QRegularExpression, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QModelIndex


class SListMixin:

    def _init_slist(self):
        # for filtering the slist table
        self._proxy = QSortFilterProxyModel( self.ui.tbl_slist )
        self._proxy.setFilterRole(Qt.DisplayRole)
        self._proxy.setFilterKeyColumn(-1)  # all columns
        self.ui.tbl_slist.setModel(self._proxy)

        # wire load slist dialog
        self.ui.butt_load_slist.clicked.connect(self.open_file)

        # wire build slist dialog
        self.ui.butt_build_slist.clicked.connect(self.open_folder)

        # wire EDF load dialog
        self.ui.butt_load_edf.clicked.connect(self.open_edf)

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

