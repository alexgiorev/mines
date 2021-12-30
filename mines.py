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
from fractions import Fraction

class Board:
    Boundary = namedtuple('Boundary', 'miny maxy minx maxx')

    ########################################
    # Apart form the integers in range(1, 9), boxes can contain one of the
    # values below.

    # Boxes which don't contain neither numbers nor mines
    EMPTY = 'EMPTY' 
    # When we know the box does not contain a mine,
    # but not what value it contains.
    SAFE = 'SAFE'
    # When we have no knowledge about the box contents.
    HIDDEN = 'HIDDEN'
    # The box is known to contain a mine, but is not opened.
    MINE = 'MINE'
    # The box contained a mine and was opened.
    HIT = 'HIT'
    
    ########################################
    # Colors. These colors were manually discovered,
    # maybe they differ from system to system.
    HIDDEN_COLOR = (186, 189, 182)
    # When the cursor is ontop of a hidden box, the box gets highlighted and
    # changes color. This is why CURSOR_COLOR is needed.
    CURSOR_COLOR = (211, 215, 207)
    # A mine was hit, and this is the color of the mine picture in the box.
    HIT_COLOR = (204, 0, 0)
    # A mine was hit, and all of the mines are displayed. This is the color of
    # the box which shows an unhit mine.
    NOTHIT_COLOR = (136, 138, 133)
    # The color of an opened box which holds nothing.
    EMPTY_COLOR = (222, 222, 220)
    BORDER_COLOR = (242, 241, 240)
    ONE_COLOR = (221, 250, 195)
    TWO_COLOR = (236, 237, 191)
    THREE_COLOR = (237, 218, 180)
    FOUR_COLOR = (237, 195, 138)
    FIVE_COLOR = (247, 161, 162)
    SIX_COLOR = (254, 167, 133)
    SEVEN_COLOR = (255, 125, 96)
    # Maps colors to objects which belong to the box having that color.
    COLOR_MAP = {ONE_COLOR: 1, TWO_COLOR: 2, THREE_COLOR: 3,
                 FOUR_COLOR: 4, FIVE_COLOR: 5, SIX_COLOR: 6, 
                 SEVEN_COLOR: 7, HIDDEN_COLOR: HIDDEN,
                 EMPTY_COLOR: EMPTY, NOTHIT_COLOR: HIT, HIT_COLOR: HIT}

    def __init__(self, img, topleft, nrows, ncols, N):
        """(img) must be an image of a completely hidden board. (topleft) must be
        a pixel coordinate that is within the top-left box. (nrows, ncols) are the
        dimensions of the board. (N) is the number of mines within the board."""
        self._matr = [[self.HIDDEN for col in range(ncols)] for row in range(nrows)]
        self._init_boxes(img, topleft, nrows, ncols)
        self.nrows = nrows
        self.ncols = ncols
        self.N = N
        self.hit_mine = False # Whether a mine has been hit

    def _init_boxes(self, img, topleft, nrows, ncols):
        """This function creates (self._rowcol_boundary), which is a mapping from a
        position (row, col) to a (Board.Boundary)."""
        
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
        have changed, or None in case a mine has been hit."""
        self._img = img
        self._pix = img.load()
        changed = [] # the list of changed rowcols
        for rowcol in self.unknown_rowcols:
            value = self._value_at(rowcol)
            if value is self.HIT:
                self.hit_mine = True
                return None
            if value is not self.HIDDEN:
                self[rowcol] = value
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
                # is the same as the color of a hidden box on top of the cursor
                # hovers, which is why this color is a little tricky.
                for xy in pixels: # continue from the next pixel.
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
    def rowcols(self):
        """Returns an iterator of the rowcols available in SELF"""
        return itertools.product(range(self.nrows), range(self.ncols))
    
    @property
    def hidden_rowcols(self):
        return (rowcol for rowcol in self.unknown_rowcols
                if self[rowcol] is not self.SAFE)

    @property
    def mine_rowcols(self):
        for rowcol in self.rowcols:
            if self[rowcol] is self.MINE:
                yield rowcol

    @property
    def unknown_rowcols(self):
        return filter(self.is_unknown, self.rowcols)

    @property
    def digit_rowcols(self):
        for rowcol in self.rowcols:
            if type(self[rowcol]) is int:
                yield rowcol

    def getxy(self, rowcol):
        """Returns a screen coordinate which is within the box at (rowcol)."""
        b = self._rowcol_boundary[rowcol]
        return random.randint(b.minx, b.maxx), random.randint(b.miny, b.maxy)

    def mark_mine(self, rowcol):
        """Marks (rowcol) as a mine."""
        # TODO: do this check better
        if self[rowcol] is self.MINE:
            return
        self._check_unknown(rowcol)
        if self.N == 0:
            raise ValueError(f'Cannot mark at {rowcol}; remaining mines count is zero.')
        self[rowcol] = self.MINE
        self.N -= 1

    def mark_safe(self, rowcol):
        self._check_unknown(rowcol)
        self[rowcol] = Board.SAFE

    def is_unknown(self, rowcol):
        return (self[rowcol] is self.HIDDEN or self[rowcol] is self.SAFE)
    
    def _check_unknown(self, rowcol):
        if not self.is_unknown(rowcol):
            raise ValueError(f'Rowcol {rowcol} must be unknown: {self[rowcol]}.')

class GroupsEngine:
    """
    When an engine is run (via engine.run()), it marks the rowcols which it
    thinks contain mines, and also those which it believes definitely to be free
    of mines. After marking, it then returns the positions so marked so that the
    actuator can modify the real board.
    """

    Group = namedtuple('Group', 'rowcols N')
    Collection = namedtuple('Collection', 'groups full_groups empty_groups')
    
    def __init__(self, board):
        self.board = board
        self.collection = None

    def run(self):
        mines, safe = self._mark_as_mine_or_safe()
        return mines, safe

    def _mark_as_mine_or_safe(self):
        """Marks the rowcols which the engine knows for sure contain
        mines. Returns a pair (marked, safe). The former is a set of the rowcols
        which the engine marked. The latter is those it believes to not contain
        mines, these can be revealed safely."""
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
    
    def _make_safe_rowcol_guess(self):
        """Makes a guess about which rowcol is safe and returns it. The guess
        may not be correct, leading to the opening of a box which contains a
        mine."""
        safe_probabilities = {}
        for group in self.collection.groups:
            group_probability = Fraction(group.N, len(group.rowcols))
            for rowcol in group.rowcols:
                current_probability = safe_probabilities.get(rowcol, -1)
                safe_probabilities[rowcol] = max(current_probability, group_probability)
        return min(safe_probabilities.items(), key=lambda item: item[1])[0]

    def new_collection(self):
        """Creates a new collection based on (self.board) and stores it in
        (self.collection). The function also returns the collection for
        convenience."""
        pending_groups = self.pending_groups = deque()
        collection = self.collection = self.Collection(set(), set(), set())
        ########################################
        # Enqueue the digit boxes' main groups
        # TODO: this could be made more efficient by keeping track of the digit
        # boxes which don't have hidden neighbors.
        for digit_rowcol in self.board.digit_rowcols:
            # use a frozenset so that the group is hashable so that we can check
            # if it is in a set
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
            
class Agent:
    def __init__(self, board, engine_factory):
        self.engine = engine_factory(board)
        self.board = board
        # the rowcol at which the cursor is at
        self.rowcol = None

    #════════════════════════════════════════
    # The following functions implement the actions the agent can take,
    # so the group defines the "actuator"
        
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

    def msg(self, text):
        os.system(f"notify-send '{text}'")

    def mark_reveal(self, mines, safe):
        ########################################
        # Mark
        pyautogui.keyDown('ctrl')
        for rowcol in mines:
            self.moveTo(rowcol)
            pyautogui.click()
        pyautogui.keyUp('ctrl')
        ########################################
        # Reveal
        for rowcol in safe:
            self.reveal(rowcol)
        self.sync_board()

    #════════════════════════════════════════
    # main function
        
    def run(self):
        self.reveal_random()        
        while True:
            if self.board.hit_mine:
                print('Exit Reason: A mine was hit')
                break
            mines, safe = self.engine.run()
            if not (mines or safe):
                print('Exit Reason: Engine not good enough.')
                self.switch()
                break
            if self.board.N == 0:
                self.mark_reveal(mines, self.board.unknown_rowcols)
                print('Exit Reason: No more mines.')
                break
            else:
                self.mark_reveal(mines, safe)

def parse_args():
    optlist, args = getopt.getopt(sys.argv[1:], 'd:m:')
    opts = dict(optlist)
    nrows, ncols = map(int, opts['-d'].split(','))
    mines = int(opts['-m'])
    return nrows, ncols, mines

if __name__ == '__main__':
    time.sleep(2)
    rows, cols, mines = parse_args()
    topleft = pyautogui.position()
    pyautogui.move((-100,-100)) # so that the cursor is not on a box
    img = pyautogui.screenshot()
    board = Board(img, topleft, rows, cols, mines)    
    agent = Agent(board, GroupsEngine)
    agent.run()
