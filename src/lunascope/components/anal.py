import lunapi as lp
import pandas as pd

from typing import List, Tuple
from PySide6.QtWidgets import QPlainTextEdit, QFileDialog, QMessageBox
import re

import sys, traceback
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QItemSelection, QSortFilterProxyModel, QRegularExpression
from PySide6.QtWidgets import QAbstractItemView, QHeaderView

class AnalMixin:

    # ------------------------------------------------------------
    # Initiate analysis tab
    # ------------------------------------------------------------

    def _init_anal(self):

        self.ui.butt_anal_exec.clicked.connect( self._exec_luna )

        self.ui.butt_anal_load.clicked.connect( self._load_luna )

        self.ui.butt_anal_save.clicked.connect( self._save_luna )

        #
        # tree 'destrat' view
        #

        m = QStandardItemModel(self)
        m.setHorizontalHeaderLabels(["Command", "Strata"])
        self._anal_model = m        
        tv = self.ui.anal_tables
        tv.setModel(m)
        tv.setUniformRowHeights(True)
        tv.header().setStretchLastSection(True)

        # store info on selecting rows of destrat
        self._tree_sel = None
        self.ui.anal_tables.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.anal_tables.setSelectionMode(QAbstractItemView.SingleSelection)

    #
    # wire filter for slists
    #
    
    def _on_flt_table_text(self, t: str):
        rx = QRegularExpression(QRegularExpression.escape(t))
        rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self._proxy.setFilterRegularExpression(rx)

        
    # ------------------------------------------------------------
    # Run a Luna command
    # ------------------------------------------------------------

    def _exec_luna(self):

        # nothing attached
        if not hasattr(self, "p"): return
        
        # get input
        inp = self.ui.txt_inp.toPlainText()

        # save currents channels/annots selections
        curr_chs = self.ui.tbl_desc_signals.checked()                   
        curr_anns = self.ui.tbl_desc_annots.checked()

        # get/set parameters
        self.proj.clear_vars()
        self.proj.reinit()
        param = self._parse_tab_pairs( self.ui.txt_param )
        for p in param:
            self.proj.var( p[0] , p[1] )
            
        # execute the command in a separate thread
        try:
            self.p.eval( inp )
        except Exception as e:
            # print("CAUGHT in slot:", repr(e), type(e))
            print("Bad input:", e)
        

        # get the output
        tbls = self.p.strata()

        # did we add any annotations? if so, updating ssa needed 
        # (as this is where events table pulls from)
        annots = [x for x in self.p.edf.annots() if x != "SleepStage" ]
        self.ssa.populate( chs = [ ] , anns = annots )

        # some commands don't return output
        if tbls is not None:
        
            # update strata list and rewire to show
            # data table on selection
            self.set_tree_from_df( tbls )

            # save, i.e. as internal results will be overwritten
            # by the HEADERS command run implicit in the updates below
            self.results = dict()        
            for row in tbls.itertuples(index=True):
                v = "_".join( [ row.Command , row.Strata ] )
                self.results[ v ] = self.p.table( row.Command, row.Strata )
        
        # update main metrics tables (i.e. if new things added)
        self._update_metrics()
        self._update_spectrogram_list()
        self._update_soap_list()

        # reset any prior selections
        self.ui.tbl_desc_signals.set( curr_chs )
        self.ui.tbl_desc_annots.set( curr_anns )
        self._update_instances( curr_anns )


        
    def _load_luna(self):
        txt_file, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Open Luna script",
            "",
            "Text (*.txt);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if txt_file:
            try:
                text = open(txt_file, "r", encoding="utf-8").read()
                self.ui.txt_inp.setPlainText(text)
            except (UnicodeDecodeError, OSError) as e:
                QMessageBox.critical(
                    None,
                    "Error opening Luna script",
                    f"Could not load {txt_file}\nException: {type(e).__name__}: {e}"
                )



    def _save_luna(self):
        new_file = self.ui.txt_inp.toPlainText()

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Luna Script To txt",
            "",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            # Ensure .txt extension if none was given
            if not filename.endswith(".txt"):
                filename += ".txt"

            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_file)



    # ------------------------------------------------------------
    # handle output table
    # ------------------------------------------------------------
                
    def _update_table(self, cmd , stratum ):
        
        tbl = self.results[ "_".join( [ cmd , stratum ] ) ]
        tbl = tbl.drop(columns=["ID"])

        model = self.df_to_model( tbl )
        # attach proxy to model
        self.anal_table_proxy = QSortFilterProxyModel(self)
        self.anal_table_proxy.setSourceModel(model)
        self.ui.anal_table.setModel(self.anal_table_proxy)

        # filter only on first N cols (strata)
        self.anal_table_proxy.setFilterKeyColumn(-1)
        self.anal_table_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.ui.flt_table.textChanged.connect(self._on_anal_filter_text)
        
        view = self.ui.anal_table
        view.setSortingEnabled(True)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)  # user-resizable                                          
        h.setStretchLastSection(False)                   # no auto-stretch fighting you                            
        view.resizeColumnsToContents()


    def _on_anal_filter_text(self, text: str):
        rx = QRegularExpression(QRegularExpression.escape(text))
        rx.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
        self.anal_table_proxy.setFilterRegularExpression(rx)
        

    # ------------------------------------------------------------
    # tree helpers
    # ------------------------------------------------------------

    def set_tree_from_df(self, df):
        m = QStandardItemModel(self)
        m.setHorizontalHeaderLabels(["Key", "Values"])
        root = m.invisibleRootItem()

        # Empty or None: just show headers
        if df is None or getattr(df, "empty", True):
            self.ui.anal_tables.setModel(m)
            self._anal_model = m
            self._wire_tree_selection()
            self.ui.anal_tables.resizeColumnToContents(0)
            self.ui.anal_tables.resizeColumnToContents(1)
            return

        # Ensure we have up to two columns
        sub = df.iloc[:, :2].copy()
        if sub.shape[1] == 1:
            sub.insert(1, "_val", "")

        # Build rows
        keys = sub.iloc[:, 0].astype(str)
        vals = sub.iloc[:, 1]

        for key, val in zip(keys, vals):
            parts = [] if pd.isna(val) else [p for p in str(val).split("_") if p]
            root.appendRow([
                QStandardItem(key),
                QStandardItem(", ".join(parts))
            ])

        self.ui.anal_tables.setModel(m)
        self._anal_model = m
        self._wire_tree_selection()
        self.ui.anal_tables.resizeColumnToContents(0)
        self.ui.anal_tables.resizeColumnToContents(1)

           
    def _wire_tree_selection(self):
        tv = self.ui.anal_tables
        # disconnect old selection model if present
        if self._tree_sel is not None:
            try: self._tree_sel.selectionChanged.disconnect(self._on_tree_sel)
            except TypeError: pass
        self._tree_sel = tv.selectionModel()
        # avoid duplicate connects if this gets called often
        try:
            self._tree_sel.selectionChanged.connect(self._on_tree_sel, Qt.UniqueConnection)
        except TypeError:
            self._tree_sel.selectionChanged.connect(self._on_tree_sel)

    def _on_tree_sel(self, selected: QItemSelection, _):
        if not selected.indexes(): return
        ix = selected.indexes()[0]
        key  = ix.sibling(ix.row(), 0).data()
        vals = ix.sibling(ix.row(), 1).data()
        self._update_table( key , vals.replace( ", ", "_" ) )



    # ------------------------------------------------------------
    # helper - parse parameter file
    # ------------------------------------------------------------
    
    def _tokenize_pair_line(self,line: str) -> list[str]:
        # split on space/tab/'=' outside quotes; support "..." and '...' with backslash escapes
        tokens, buf, q, esc = [], [], None, False
        for ch in line:
            if esc:
                buf.append(ch); esc = False; continue
            if q:
                if ch == '\\': esc = True; continue
                if ch == q: q = None; continue
                buf.append(ch); continue
            if ch in ('"', "'"): q = ch; continue
            if ch in ' \t=':
                if buf: tokens.append(''.join(buf)); buf = []
                continue
            buf.append(ch)
        if buf: tokens.append(''.join(buf))
        return tokens

    def _parse_tab_pairs(self, edit: QPlainTextEdit) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []
        for raw in edit.toPlainText().splitlines():
            line = raw.strip()
            if not line or line.startswith('%'):
                continue
            toks = self._tokenize_pair_line(line)
            if len(toks) != 2:
                continue
            a, b = toks[0].strip(), toks[1].strip()
            if a == '' and b == '':
                continue
            pairs.append((a, b))
        return pairs


    
    # ------------------------------------------------------------
    # worker thread for executing luna commands
    # ------------------------------------------------------------

    
