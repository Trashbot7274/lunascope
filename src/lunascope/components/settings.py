
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

from PySide6.QtWidgets import QPlainTextEdit, QFileDialog
from PySide6.QtWidgets import QVBoxLayout, QHeaderView
import pandas as pd

class SettingsMixin:

    def _init_settings(self):

        # tableview formats

        
        
        # wiring

        self.ui.butt_load_param.clicked.connect( self._load_param )
        self.ui.butt_save_param.clicked.connect( self._save_param )
        self.ui.butt_reset_param.clicked.connect( self._reset_param )

    

    # ------------------------------------------------------------
    # load/save functions

    def _load_param(self):
        txt_file, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Open a parameter file",
            "",
            "Text (*.txt);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if txt_file:
            try:
                text = open(txt_file, "r", encoding="utf-8").read()
                self.ui.txt_param.setPlainText(text)
            except (UnicodeDecodeError, OSError) as e:
                QMessageBox.critical(
                    None,
                    "Error opening parameter file",
                    f"Could not load {txt_file}\nException: {type(e).__name__}: {e}"
                )


    def _save_param(self):

        new_file = self.ui.txt_param.toPlainText()

        filename, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save parameter file to .txt",
            "",
            "Text Files (*.txt);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )

        if filename:
            # Ensure .txt extension if none was given
            if selected_filter.startswith("Text") and not filename.lower().endswith(".txt"):
                filename += ".txt"
                
            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_file)



    # ------------------------------------------------------------
    # reset all parameters

    def _reset_param(self):
        self.ui.txt_param.clear()
        self.proj.clear_vars()
        self.proj.reinit()
        self._update_params()
        
    # ------------------------------------------------------------
    # reset all parameters: called when attaching a new EDF

    def _update_params(self):
        
        # get aliases
        aliases = self.proj.eng.aliases()
        df = pd.DataFrame(aliases, columns=["Type", "Primary", "Secondary"])
        model = self.df_to_model( df )
        self.ui.tbl_aliases.setModel( model )
        view = self.ui.tbl_aliases
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        view.resizeColumnsToContents()
    
        # get special variables
        vars = self.proj.vars()
        df = pd.DataFrame(list(vars.items()), columns=["Variable", "Value"])        
        model = self.df_to_model( df )
        self.ui.tbl_param.setModel( model )
        view = self.ui.tbl_param
        view.verticalHeader().setVisible(False)
        view.resizeColumnsToContents()
        view.setSortingEnabled(False)
        h = view.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setStretchLastSection(True)
        view.resizeColumnsToContents()
