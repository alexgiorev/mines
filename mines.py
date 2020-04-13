import itertools
import copy
import random
import pyautogui
import math
import sys
import getopt
import time
import os

from PIL import Image
from collections import namedtuple, deque, defaultdict
from types import SimpleNamespace

class Board:
    Boundary = namedtuple('Boundary', 'miny maxy minx maxx')

    ########################################
    # Apart form the integers in range(1, 9), boxes can contain one of the
    # values below.

    # Boxes which don't contain neither numbers nor mines
    EMPTY = 'EMPTY' 
    # When we know the box does not contain a mine, but not what value it
    # contains.
    SAFE = 'SAFE'
    # When we have no knowledge about the box contents.
    HIDDEN = 'HIDDEN'
    # The box is known to contain a mine, but is not opened.
    MINE = 'MINE'
    # The box contained a mine and was opened.
    HIT = 'HIT'
    
    ########################################
    # Colors
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
        # (self._to_uncover) contains the rowcols which are still to be
        # uncovered. This is for efficiency when we sync with an image, to query
        # only at coordinates of boxes whose value is still unknown. For an
        # covered box, the possible values are Board.HIDDEN and Board.SAFE
        self._to_uncover = set(itertools.product(range(nrows), range(ncols)))
        # rowcols of boxes which contain digits
        self._digit_rowcols = set()
        # rowcols of boxes which contain mines
        self._mine_rowcols = set()
        self._init_boxes(img, topleft, nrows, ncols)
        self.nrows = nrows
        self.ncols = ncols
        self.N = N
        self.hit_mine = False # Whether a mine has been hit upon

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
        row, col = rowcol
        self._matr[row][col] = value
            
    def update(self, img):
        """Updates boxes based on (img). Returns a list of the rowcols which
        have changed."""
        self._img = img
        self._pix = img.load()
        changed = [] # the list of changed rowcols
        to_uncover = list(self._to_uncover)
        for rowcol in to_uncover:
            value = self._value_at(rowcol)
            if value is self.HIT:
                self.hit_mine = True
                return None
            if value is not self.HIDDEN:
                self.reveal(rowcol, value)
                changed.append(rowcol)
        return changed

    def _value_at(self, rowcol):
        """A helper function. For the box at (rowcol), we get the value based on
        the image (self._img). ValueError is raised if the value cannot be
        extracted from the image. The possible return values are an int or one
        of {Board.HIT, Board.EMPTY, Board.HIDDEN}"""
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

    def neighbors(self, rowcol):
        row, col = rowcol
        candidates = ((row-1, col-1), (row, col-1), (row+1, col-1),
                      (row-1, col), (row+1, col),
                      (row-1, col+1), (row, col+1), (row+1, col+1))
        return (rowcol for rowcol in candidates
                if 0 <= rowcol[0] < self.nrows and 0 <= rowcol[1] < self.ncols)

    def digit_neighbors(self, rowcol):
        return (neigh for neigh in self.neighbors(rowcol)
                if type(self[neigh]) is int)

    def mine_neighbors(self, rowcol):
        return (neigh for neigh in self.neighbors(rowcol)
                if self[neigh] is Board.MINE)

    def hidden_neighbors(self, rowcol):
        return (neigh for neigh in self.neighbors(rowcol)
                if self[neigh] is Board.HIDDEN)

    @property
    def hidden_rowcols(self):
        return (rowcol for rowcol in self._to_uncover
                if self[rowcol] is not self.SAFE)

    @property
    def mine_rowcols(self):
        return iter(self._mine_rowcols)

    @property
    def covered_rowcols(self):
        return iter(self._to_uncover)

    @property
    def digit_rowcols(self):
        return iter(self._digit_rowcols)

    def getxy(self, rowcol):
        """Returns a screen coordinate which is within the box at (rowcol)."""
        b = self._rowcol_boundary[rowcol]
        return random.randint(b.minx, b.maxx), random.randint(b.miny, b.maxy)

    def reveal(self, rowcol, value):
        """The box at (rowcol) is known to be empty or to contain a digit."""
        self._check_covered(rowcol)
        if value is not Board.EMPTY and type(value) is not int:
            raise ValueError(f'Bad reveal value: {value}')
        self[rowcol] = value
        self._to_uncover.remove(rowcol)
        if type(value) is int:
            self._digit_rowcols.add(rowcol)
        
    def mark_mine(self, rowcol):
        """Marks (rowcol) as a mine."""
        # TODO: do this check better
        if self[rowcol] is self.MINE:
            return
        self._check_covered(rowcol)
        if self.N == 0:
            raise ValueError(f'Cannot mark at {rowcol}; remaining mines count is zero.')
        self._to_uncover.remove(rowcol)
        self[rowcol] = self.MINE
        self.N -= 1

    def mark_safe(self, rowcol):
        self._check_covered(rowcol)
        self[rowcol] = Board.SAFE

    def _check_covered(self, rowcol):
        if self[rowcol] not in (self.HIDDEN, self.SAFE):
            raise ValueError(f'Rowcol {rowcol} must be covered: {self[rowcol]}.')

class Engine:
    """
    * Public interface.
    An Engine is used to mark mine rowcols and to make predictions which rowcols
    do not have mines. This information is communicated via engine.run().
    """

    Group = namedtuple('Group', 'rowcols N')
    Collection = namedtuple('Collection', 'groups full_groups empty_groups')
    
    def __init__(self, board):
        self.board = board
        self.collection = None

    def run(self):
        """Marks the rowcols which the engine knows contain mines. Returns a
        pair (marked, safe). The former is a set of the rowcols which the engine
        marked. The latter is those it predicts do not contain mines. These can
        be revealed safely. At that point, you can run the engine again."""
        mines, safe = set(), set()
        while True:
            col = self.new_collection()
            if not (col.full_groups or col.empty_groups):
                break
            for group in col.full_groups:
                for rowcol in group.rowcols:
                    self.board.mark_mine(rowcol)
                    mines.add(rowcol)
            for group in col.empty_groups:
                for rowcol in group.rowcols:
                    self.board.mark_safe(rowcol)
                    safe.add(rowcol)
        return mines, safe

    def new_collection(self):
        """Creates a new collection based on (self.board) and stores it in
        (self.collection). The function returns the collection for
        convenience."""
        pending_groups = self.pending_groups = deque()
        collection = self.collection = self.Collection(set(), set(), set())
        ########################################
        # Enqueue the digit boxes' main groups
        # TODO: this could be made more efficient by keeping track of the digit
        # boxes which don't have hidden neighbors.
        for digit_rowcol in self.board.digit_rowcols:
            rowcols = frozenset(self.board.hidden_neighbors(digit_rowcol))
            if not rowcols:
                continue
            N = self.board[digit_rowcol] - len(list(self.board.mine_neighbors(digit_rowcol)))
            self.pending_groups.append(self.Group(rowcols, N))
        ########################################
        # Process pending groups
        while pending_groups:
            group = pending_groups.popleft()
            if group in collection.groups:
                # already processed
                continue
            ########################################
            # Enqueue the complements
            for other_group in collection.groups:
                if group.rowcols < other_group.rowcols:
                    subgroup, supergroup = group, other_group
                elif other_group.rowcols < group.rowcols:
                    subgroup, supergroup = other_group, group
                else:
                    continue
                rowcols = supergroup.rowcols - subgroup.rowcols
                N = supergroup.N - subgroup.N
                pending_groups.append(self.Group(rowcols, N))
            ########################################
            # Add the current group
            collection.groups.add(group)
            if len(group.rowcols) == group.N:
                collection.full_groups.add(group)
            elif group.N == 0:
                collection.empty_groups.add(group)
        ########################################
        return collection
            
    def update_collection(self, *args):
        """TODO. Rather than creating a new collection, this function updates
        the existing one in (self.collection). This may be more efficient."""
        raise NotImplementedError

class Main:
    def __init__(self, engine_factory):
        self.engine_factory = engine_factory
        
    def reveal(self, rowcol):
        self.moveTo(rowcol)
        pyautogui.click()
        
    def mark(self, rowcol):
        self.moveTo(rowcol)
        pyautogui.keyDown('ctrl')
        pyautogui.click()
        pyautogui.keyUp('ctrl')

    def moveTo(self, rowcol):
        to_xy = self.board.getxy(rowcol)
        pyautogui.moveTo(to_xy)
        self.rowcol = rowcol
        
    def sync_board(self):
        """Synchronizes the state of (board) to that in the game. Returns the
        rowcols which have new values."""
        return self.board.update(pyautogui.screenshot())

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

    def perform(self, marked, safe):
        pyautogui.keyDown('ctrl')
        for rowcol in marked:
            self.moveTo(rowcol)
            pyautogui.click()
        pyautogui.keyUp('ctrl')
        for rowcol in safe:
            self.reveal(rowcol)
        self.sync_board()

    def msg(self, text):
        os.system(f"notify-send '{text}'")
    
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
        while True:
            if self.board.hit_mine:
                print('Hit mine.')
                break
            marked, safe = self.engine.run()
            if not (marked or safe):
                self.msg('Engine not good enough.')
                print('Not good enough.')
                break
            if self.board.N == 0:
                self.perform(marked, self.board.covered_rowcols)
                print('final performance')
                break
            else:
                self.perform(marked, safe)

if __name__ == '__main__':
    m = Main(Engine)
    m.main()
