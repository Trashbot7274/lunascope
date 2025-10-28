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

        
class MasksMixin:
    
    def _init_masks(self):
        
        # wiring
        self.ui.butt_mask_ifnot_N1.clicked.connect( lambda: self._apply_mask("ifnot=N1") )
        self.ui.butt_mask_ifnot_N2.clicked.connect( lambda: self._apply_mask("ifnot=N2") )
        self.ui.butt_mask_ifnot_N3.clicked.connect( lambda: self._apply_mask("ifnot=N3") )
        self.ui.butt_mask_ifnot_NR.clicked.connect( lambda: self._apply_mask("ifnot=N1,N2,N3") )
        self.ui.butt_mask_ifnot_R.clicked.connect( lambda: self._apply_mask("ifnot=R") )
        self.ui.butt_mask_ifnot_W.clicked.connect( lambda: self._apply_mask("ifnot=W") )
                
        self.ui.butt_mask_if_N1.clicked.connect( lambda: self._apply_mask("if=N1") )
        self.ui.butt_mask_if_N2.clicked.connect( lambda: self._apply_mask("if=N2") )
        self.ui.butt_mask_if_N3.clicked.connect( lambda: self._apply_mask("if=N3") )
        self.ui.butt_mask_if_NR.clicked.connect( lambda: self._apply_mask("if=N1,N2,N3") )
        self.ui.butt_mask_if_R.clicked.connect( lambda: self._apply_mask("if=R") )
        self.ui.butt_mask_if_W.clicked.connect( lambda: self._apply_mask("if=W") )

        self.ui.butt_generic_mask.clicked.connect( lambda: self._apply_mask( self.ui.txt_generic_mask.text() ) )


    # ------------------------------------------------------------
    # Apply MASK

    def _apply_mask(self, msk ):

        # nothing to do
        if msk == "": return

        # requires attached individal
        if not hasattr(self, "p"): return

        # save selections
        self.curr_chs = self.ui.tbl_desc_signals.checked()
        self.curr_anns = self.ui.tbl_desc_annots.checked()
        
        # run MASK
        self.p.eval( 'MASK ' + msk + ' & RE ' )

        # update the things that need updating
        self._set_render_status( self.rendered , False )
        self._update_metrics()
        self._update_pg1()
        
        self.ui.tbl_desc_signals.set( self.curr_chs )
        self.ui.tbl_desc_annots.set( self.curr_anns )
        self._update_instances( self.curr_anns )
