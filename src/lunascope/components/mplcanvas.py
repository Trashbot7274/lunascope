
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, dpi=100):
        fig = Figure(dpi=dpi, facecolor="black")         # figure background
        super().__init__(fig)
        if parent is not None:
            self.setParent(parent)
        self.ax = fig.add_axes([0,0,1,1])                # full-bleed axes
        self.ax.set_facecolor("black")                   # axes background
        self.ax.set_axis_off()                           # no ticks, spines, grid
        self.ax.grid(False)
        fig.patch.set_facecolor("black")                 # extra safety
        self.draw()

