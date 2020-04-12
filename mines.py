import itertools
import copy
import random
import pyautogui
import math
import sys
import getopt
import time

from PIL import Image
from collections import namedtuple, deque, defaultdict
from types import SimpleNamespace

class Board:
    Boundary = namedtuple('Boundary', 'miny maxy minx maxx')
    
    EMPTY = 'EMPTY' # boxes which don't contain numbers or mines
    HIDDEN = 'HIDDEN' # rowcols whose contents are unknown
    MINE = 'MINE' # to be used at rowcols which we know are mines
    HIT = 'HIT'
    # colors
    HIDDEN_COLOR = (186, 189, 182)
    # When the cursor is ontop of a hidden box, the box gets highlighted and
    # changes color. This is why CURSOR_COLOR is needed.
    CURSOR_COLOR = (211, 215, 207)
    # A mine was hit, and this is the color of the mine picture in the box.
    HIT_COLOR = (204, 0, 0)
    # A mine was hit, and all of the mines are displayed. This is the color of
    # the box which shows an unhit mine.
    NOTHIT_COLOR = (48, 10, 36)
    EMPTY_COLOR = (222, 222, 220)
    BORDER_COLOR = (242, 241, 240)
    ONE_COLOR = (221, 250, 195)
    TWO_COLOR = (236, 237, 191)
    THREE_COLOR = (237, 218, 180)
    FOUR_COLOR = (237, 195, 138)
    FIVE_COLOR = (247, 161, 162)
    SIX_COLOR = (254, 167, 133)
    SEVEN_COLOR = (255, 125, 96)
    COLOR_MAP = {ONE_COLOR: 1, TWO_COLOR: 2, THREE_COLOR: 3,
                 FOUR_COLOR: 4, FIVE_COLOR: 5, SIX_COLOR: 6, 
                 SEVEN_COLOR: 7, HIDDEN_COLOR: HIDDEN,
                 EMPTY_COLOR: EMPTY, NOTHIT_COLOR: HIT}

    def __init__(self, img, topleft, nrows, ncols, N):
        """(img) must be an image of a completly hidden board. (topleft) must be
        a pixel coordinate that is within the top-left box. (nrows, ncols) are the
        dimensions of the box. (N) is the number of mines remaining."""
        self._matr = [[self.HIDDEN for col in range(ncols)] for row in range(nrows)]
        self._hidden = set(itertools.product(range(nrows), range(ncols)))
        self._digits = set()
        self._mines = set()
        self._init_boxes(img, topleft, nrows, ncols)
        self.nrows = nrows
        self.ncols = ncols
        self.N = N
        self.hit = False # Whether a mine is hit

    def _init_boxes(self, img, topleft, nrows, ncols):
        """This function creates (self._rowcol_boundary), which is a mapping from a
        position (row, col) to a (Boundary)."""
        
        pix = img.load()
        
        def move_to_color(x, y, dx, dy, color):
            while pix[x, y] != color:
                x += dx; y += dy
            return x, y

        ########################################
        # Form the boxes' vertical boundaries
        ybounds = []
        x, y = move_to_color(*topleft, 0, -1, Board.BORDER_COLOR)
        for _ in range(nrows):
            x, y = move_to_color(x, y, 0, 1, Board.HIDDEN_COLOR)
            miny = y
            x, y = move_to_color(x, y, 0, 1, Board.BORDER_COLOR)
            ybounds.append((miny, y-1))

        ########################################
        # Form the boxes' horizontal boundaries
        xbounds = []
        x, y = move_to_color(*topleft, -1, 0, Board.BORDER_COLOR)
        for _ in range(ncols):
            x, y = move_to_color(x, y, 1, 0, Board.HIDDEN_COLOR)
            minx = x
            x, y = move_to_color(x, y, 1, 0, Board.BORDER_COLOR)
            xbounds.append((minx, x-1))

        rowcols = itertools.product(range(nrows), range(ncols))
        boundaries = (Board.Boundary(*yb, *xb)
                      for yb, xb in itertools.product(ybounds, xbounds))
        self._rowcol_boundary = dict(zip(rowcols, boundaries))

    def __getitem__(self, rowcol):
        row, col = rowcol
        return self._matr[row][col]

    def __setitem__(self, rowcol, value):
        current_box = self[rowcol]
        if current_box is not Board.HIDDEN:
            return # already revealed
        row, col = rowcol
        self._matr[row][col] = value
        if type(value) is int:
            self._digits.add(rowcol)
        elif value is Board.MINE:
            self._mines.add(rowcol)

    def refresh(self, img):
        """Updates boxes based on (img). Returns a list of the rowcols which
        have changed."""
        self._img = img
        self._pix = img.load()
        # copy (self._hidden) so that we can modify it while iterating.
        hidden = list(self._hidden)
        changed = [] # the list of changed rowcols
        for rowcol in hidden:
            value = self._value_at(rowcol)
            if value is self.HIT:
                self.hit = True
                return None
            if value is not self.HIDDEN:
                self[rowcol] = value
                changed.append(rowcol)
        return changed

    def _value_at(self, rowcol):
        """A helper function. Returns the value of the box whose coordinates
        within the board are (rowcol). Uses information from the image to do
        this. Assumes (self._img) and (self._pix) are set properly."""
        b = self._rowcol_boundary[rowcol]
        pixels = itertools.product(range(b.minx, b.maxx+1),
                                   range(b.miny, b.maxy+1))
        for xy in pixels:
            color = self._pix[xy]
            if color == self.BORDER_COLOR:
                continue
            if color == self.CURSOR_COLOR:
                # The background color of a box that has a mine that was clicked
                # is the same as the color of a hidden box on top of which we
                # have the cursor, which is why this color is a little tricky.
                for xy in pixels:
                    if self._pix[xy] == self.HIT_COLOR:
                        return self.HIT
                # The cursor was on top of a hidden box.
                return self.HIDDEN
            else:
                value = self.COLOR_MAP.get(color)
                if value is None:
                    continue
                return value
        raise ValueError(f'Could not get the value at position {rowcol}')

    def reveal(self, rowcol):
        """Presses the box at (rowcol) and updates the state of the board."""
        raise NotImplementedError

    def neighbors(self, rowcol):
        row, col = rowcol
        candidates = ((row-1, col-1), (row, col-1), (row+1, col-1),
                      (row-1, col), (row+1, col),
                      (row-1, col+1), (row, col+1), (row+1, col+1))
        return (rowcol for rowcol in candidates
                if 0 <= rowcol[0] < self.nrows and 0 <= rowcol[1] < self.ncols)

    def digit_neighbors(self, rowcol):
        return frozenset(neigh for neigh in self.neighbors(rowcol)
                         if type(self[neigh]) is int)

    def mine_neighbors(self, rowcol):
        return frozenset(neigh for neigh in self.neighbors(rowcol)
                         if self[neigh] is Board.MINE)

    def hidden_neighbors(self, rowcol):
        return frozenset(neigh for neigh in self.neighbors(rowcol)
                         if self[neigh] is Board.HIDDEN)

    @property
    def hidden_rowcols(self):
        return set(self._hidden)

    @property
    def mine_rowcols(self):
        return set(self._mines)

    @property
    def digit_rowcols(self):
        return set(self._digits)

    def getxy(self, rowcol):
        """Returns a screen coordinate which is within the box at (rowcol)."""
        b = self._rowcol_boundary[rowcol]
        return random.randint(b.minx, b.maxx), random.randint(b.miny, b.maxy)

    def mark(self, rowcol):
        """Marks (rowcol) as a mine."""
        if self.N == 0:
            raise ValueError(f'Cannot mark at {rowcol}; mark count is zero.')
        self[rowcol] = self.MINE
        self.N -= 1

class Engine:
    """
    * Public interface.

    An Engine makes makes predictions which boxes have mines and which
    don't. You create it, and then .notify() it each time you modify the
    board. You tell it which boxes you revealed, and which you marked as
    containing mines. It uses this information and then tells you further boxes
    to reveal, and further boxes to mark. It is important to notify the Engine
    of all modifications made and all new information revealed."""

    Group = namedtuple('Group', 'rowcols, N')
    
    def __init__(self, board):
        self.board = board
        # contains the rowcols of digits which have no mines around them, so
        # that we don't consider them.
        self.finished = set()

    def get(self):
        """Returns a pair (mines, no_mines) of sets. The former says which
        rowcols the engine believes contain mines. The latter which it believes
        to not.

        TODO: when you are left with little, try different configurations and
        see if there are contradictions. Then choose based on lack of
        contradiction."""
        
        self.mines, self.no_mines = set(), set()
        self.groups = set()
        self.compute()
        if not (self.mines or self.no_mines):
            safest = min(self.groups,
                         key=lambda group: group.N/len(group.rowcols))
            self.no_mines.add(random.choice(tuple(safest.rowcols)))
        return self.mines, self.no_mines

    def compute(self):
        self.groups = set()
        self.pending = deque()
        for digit_rowcol in self.board.digit_rowcols - self.finished:
            rowcols = self.board.hidden_neighbors(digit_rowcol)
            if not rowcols:
                self.finished.add(digit_rowcol)
                continue
            N = self.board[digit_rowcol]
            N -= len(self.board.mine_neighbors(digit_rowcol))
            self.pending.append(self.Group(rowcols=rowcols, N=N))
        while self.pending:
            group = self.pending.popleft()
            self.groups.add(group)
            self.process_group(group)
    
    def process_group(self, group):
        if group.N == len(group.rowcols):
            self.mines.update(group.rowcols)
        elif group.N == 0:
            self.no_mines.update(group.rowcols)
        else:
            for other_group in self.groups:
                if other_group.rowcols < group.rowcols:
                    self.add_complement(other_group, group)
                elif other_group.rowcols > group.rowcols:
                    self.add_complement(group, other_group)

    def add_complement(self, subgroup, group):
        complement = self.Group(rowcols = group.rowcols - subgroup.rowcols,
                                N = group.N - subgroup.N)
        self.post_group(complement)

    def post_group(self, group):
        if group not in self.groups:
            self.pending.append(group)
        
class Main:    
    def __init__(self, engine_factory):
        self.engine_factory = engine_factory
        
    def reveal(self, rowcol):
        self.moveTo(rowcol)
        pyautogui.click()
        
    def mark(self, rowcol):
        self.board.mark(rowcol)
        self.moveTo(rowcol)
        pyautogui.keyDown('ctrl')
        pyautogui.click()
        pyautogui.keyUp('ctrl')

    def moveTo_old(self, rowcol):
        SPEED = 750 # pixels per second
        to_xy = self.board.getxy(rowcol)
        from_xy = pyautogui.position()
        distance = math.sqrt(sum([(a - b) ** 2 for a, b in zip(to_xy, from_xy)]))
        pyautogui.moveTo(*to_xy, distance/SPEED)
        self.rowcol = rowcol

    def moveTo(self, rowcol):
        to_xy = self.board.getxy(rowcol)
        pyautogui.moveTo(to_xy)
        self.rowcol = rowcol
        
    def sync_board(self):
        """Synchronizes the state of (board) to that in the game. Returns the
        rowcols which have new values."""
        return self.board.refresh(pyautogui.screenshot())

    def parse_args(self):
        optlist, args = getopt.getopt(sys.argv[1:], 'd:m:')
        opts = dict(optlist)
        rows, cols = map(int, opts['-d'].split(','))
        mines = int(opts['-m'])
        return rows, cols, mines

    def switch(self):
        pyautogui.keyDown('alt')
        pyautogui.keyDown('tab')
        pyautogui.keyUp('alt')
        pyautogui.keyUp('tab')        
            
    def reveal_random(self):
        random_row = random.randint(0, self.board.nrows-1)
        random_col = random.randint(0, self.board.ncols-1)
        self.reveal((random_row, random_col))
        self.sync_board()

    def sort(self, mines, no_mines):
        requests = set()
        requests.update(('mark', rowcol) for rowcol in mines)
        requests.update(('reveal', rowcol) for rowcol in no_mines)
        def distance(request):
            other_rowcol = request[1]
            return math.sqrt(sum((a - b) ** 2 for a, b in zip(rowcol, other_rowcol)))
        result = []
        rowcol = self.rowcol
        while requests:
            closest = min(requests, key=distance)
            result.append(closest)
            rowcol = closest[1]
            requests.remove(closest)
        return result

    def perform(self, mines, no_mines):
        requests = self.sort(mines, no_mines)
        for request in requests:
            type, rowcol = request
            if type == 'mark':
                self.mark(rowcol)
            else:
                if self.board[rowcol] is Board.HIDDEN:
                    self.reveal(rowcol)
                    self.sync_board()
                    if self.board.hit:
                        return

    def main(self):
        time.sleep(2)
        rows, cols, mines = self.parse_args()
        topleft = pyautogui.position()
        pyautogui.move((-100,-100))
        img = pyautogui.screenshot()
        self.board = Board(img, topleft, rows, cols, mines)
        self.rowcol = None # the rowcol at which the cursor is at
        self.engine = self.engine_factory(self.board)
        self.reveal_random()
        
        # main loop
        while not self.board.hit:
            mines, no_mines = self.engine.get()
            if self.board.N == len(mines):
                self.perform(mines=set(), no_mines=self.board.hidden_rowcols)
                break
            else:
                self.perform(mines, no_mines)

if __name__ == '__main__':
    m = Main(Engine)
    m.main()
