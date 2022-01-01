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

    #════════════════════════════════════════
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
    
    #════════════════════════════════════════
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
    MINE_FLAG_COLOR = (46, 52, 54)
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
        self._set_boundaries(img, topleft, nrows, ncols)
        self.nrows = nrows
        self.ncols = ncols
        self.total = self.remaining = N
        self.hit_mine = False # Whether a mine has been hit
        self.update(img)

    def _set_boundaries(self, img, topleft, nrows, ncols):
        """This function creates (self._boundaries), which is a mapping from a
        position (row, col) to a (Board.Boundary)."""

        pix = img.load()        
        def move_to_border(x, y, dx, dy):
            while pix[x, y] != Board.BORDER_COLOR:
                x += dx; y += dy
            return x, y
        def move_outside_border(x, y, dx, dy):
            while pix[x, y] == Board.BORDER_COLOR:
                x += dx; y += dy
            return x, y
        #════════════════════════════════════════
        # Form the boxes' vertical boundaries
        ybounds = []
        x, y = move_to_border(*topleft, 0, -1)
        for _ in range(nrows):
            x, y = move_outside_border(x, y, 0, 1)
            miny = y
            x, y = move_to_border(x, y, 0, 1)
            ybounds.append((miny, y-1))
        #════════════════════════════════════════
        # Form the boxes' horizontal boundaries
        xbounds = []
        x, y = move_to_border(*topleft, -1, 0)
        for _ in range(ncols):
            x, y = move_outside_border(x, y, 1, 0)
            minx = x
            x, y = move_to_border(x, y, 1, 0)
            xbounds.append((minx, x-1))
        rowcols = itertools.product(range(nrows), range(ncols))
        boundaries = (Board.Boundary(*yb, *xb)
                      for yb, xb in itertools.product(ybounds, xbounds))
        self._boundaries = dict(zip(rowcols, boundaries))

    def __getitem__(self, rowcol):
        row, col = rowcol
        return self._matr[row][col]

    def __setitem__(self, rowcol, value):
        row, col = rowcol
        self._matr[row][col] = value
            
    def update(self, img):
        """Updates boxes based on (img). Returns a list of the rowcols which
        have changed, or None in case a mine has been hit."""
        pix = img.load()
        changed = [] # the list of changed rowcols
        for rowcol in self.unknown_rowcols:
            value = self.value_at(pix, rowcol)
            if value is self.HIT:
                self.hit_mine = True
                return None
            if value is not self.HIDDEN:
                self[rowcol] = value
                changed.append(rowcol)
        self.remaining = self.total - len(self.mine_rowcols)
        return changed

    def value_at(self, pix, rowcol):
        """A helper function. For the box at (rowcol), we get the value based on
        the pixmap (pix), which is the return value of (IMAGE.load()). ValueError
        is raised if the value cannot be extracted from the image. The possible
        return values are an int or one of {Board.HIT, Board.EMPTY,
        Board.HIDDEN}"""
        b = self._boundaries[rowcol]
        pixels = itertools.product(range(b.minx, b.maxx+1),
                                   range(b.miny, b.maxy+1))
        for xy in pixels:
            color = pix[xy]
            if color == self.BORDER_COLOR:
                # A BORDER_COLOR may appear within the boundaries of a box
                # because the boxes' vertices are rounded.
                continue
            if color == self.CURSOR_COLOR:
                # The background color of a box that has a mine that was clicked
                # is the same as the color of a hidden box on top of the cursor
                # hovers, which is why this color is a little tricky.
                for xy in pixels: # continue from the next pixel.
                    if pix[xy] == self.HIT_COLOR:
                        return self.HIT
                # The cursor was on top of a hidden box.
                return self.HIDDEN
            elif color == self.HIDDEN_COLOR:
                # The color of a hidden box is the same as the background color
                # if a box marked as having a mine. The mine flag symbol has
                # pixels with color (self.MINE_FLAG_COLOR) somewhere along the middle
                # vertical line.
                midx = (b.minx+b.maxx)//2
                for y in range(b.miny, b.maxy):
                    if pix[midx,y] == self.MINE_FLAG_COLOR:
                        return self.MINE
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
        return set(neigh for neigh in self.neighbors(rowcol)
                   if type(self[neigh]) is int)

    def mine_neighbors(self, rowcol):
        return set(neigh for neigh in self.neighbors(rowcol)
                   if self[neigh] is Board.MINE)

    def hidden_neighbors(self, rowcol):
        return set(neigh for neigh in self.neighbors(rowcol)
                   if self[neigh] is Board.HIDDEN)

    @property
    def rowcols(self):
        """Returns an iterator of the rowcols available in SELF"""
        return set(itertools.product(range(self.nrows), range(self.ncols)))
    
    @property
    def hidden_rowcols(self):
        return set(rowcol for rowcol in self.unknown_rowcols
                   if self[rowcol] is not self.SAFE)

    @property
    def mine_rowcols(self):
        return set(rowcol for rowcol in self.rowcols
                   if self[rowcol] is self.MINE)

    @property
    def unknown_rowcols(self):
        return set(filter(self.is_unknown, self.rowcols))

    @property
    def digit_rowcols(self):
        return set(rowcol for rowcol in self.rowcols
                   if type(self[rowcol]) is int)

    def getxy(self, rowcol):
        """Returns a screen coordinate which is within the box at (rowcol)."""
        b = self._boundaries[rowcol]
        return random.randint(b.minx, b.maxx), random.randint(b.miny, b.maxy)

    def mark_mine(self, rowcol):
        """Marks (rowcol) as a mine."""
        # TODO: do this check better
        if self[rowcol] is self.MINE:
            return
        self._check_unknown(rowcol)
        if self.remaining == 0:
            raise ValueError(f'Cannot mark at {rowcol}; remaining mines count is zero.')
        self[rowcol] = self.MINE
        self.remaining -= 1

    def mark_safe(self, rowcol):
        self._check_unknown(rowcol)
        self[rowcol] = Board.SAFE

    def is_unknown(self, rowcol):
        value = self[rowcol]
        return value is self.HIDDEN or value is self.SAFE
    
    def _check_unknown(self, rowcol):
        if not self.is_unknown(rowcol):
            raise ValueError(f'Rowcol {rowcol} must be unknown: {self[rowcol]}.')

    @property
    def all_hidden(self):
        return len(self.hidden_rowcols) == self.nrows * self.ncols

# Engines
#════════════════════════════════════════

class Engine:
    def run(self):
        """Finds out which rowcols contain mines and which are safe and marks
        them in the board accordingly. Returns a pair of sets (MINES, SAFE)"""
        raise NotImplementedError

class GroupsEngine(Engine):
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
        #════════════════════════════════════════
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
        #════════════════════════════════════════
        # Process pending groups
        while pending_groups:
            group = pending_groups.popleft()
            if group in collection.groups:
                # already processed
                continue
            #════════════════════════════════════════
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
            #════════════════════════════════════════
            # Add the current group
            collection.groups.add(group)
            if len(group.rowcols) == group.N:
                collection.full_groups.add(group)
            elif group.N == 0:
                collection.empty_groups.add(group)
        #════════════════════════════════════════
        return collection

class BruteForceEngine(Engine):
    def __init__(self, board):
        self.board = board

    def run(self):
        mines, safe = set(), set()
        least_probables = set()
        for equiv_class in self._equiv_classes():
            alternatives = self._equiv_class_alternatives(equiv_class)
            hidden = set(itertools.chain.from_iterable(
                self.board.hidden_neighbors(rowcol) for rowcol in equiv_class))
            counts = {rowcol:0 for rowcol in hidden}
            for alt in alternatives:
                for rowcol in alt:
                    counts[rowcol] += 1
            in_all, in_none = set(), set()
            least_counted, least_count = None, None
            for rowcol, count in counts.items():
                if least_counted is None or count < least_count:
                    least_counted, least_count = rowcol, count
                if count == 0:
                    in_none.add(rowcol)
                elif count == len(alternatives):
                    in_all.add(rowcol)
            least_probables.add(least_counted)
            mines.update(in_all)
            safe.update(in_none)
        if not (mines or safe):
            safe = least_probables
        for rowcol in mines:
            self.board.mark_mine(rowcol)
        for rowcol in safe:
            self.board.mark_safe(rowcol)
        return mines, safe

    def _equiv_class_alternatives(self, equiv_class):
        self._equiv_class = list(equiv_class)
        alternatives = set()
        first_rowcol = self._equiv_class[0]
        board_copy = copy.deepcopy(self.board)
        choices = self._choices(first_rowcol, board_copy)
        if choices is None:
            raise ValueError("No choices for first member of equivalence class")
        choice = 0
        self._stack = [[first_rowcol, board_copy, choices, choice]]
        while self._stack:
            if self._go_down():
                alternative = []
                for rowcol, board, choices, index in self._stack:
                    alternative.extend(choices[index])
                alternatives.add(frozenset(alternative))
            self._backtrack()
        return alternatives

    def _go_down(self):
        rowcol, board, choices, choice_index = self._stack[-1]
        while len(self._stack) < len(self._equiv_class):
            board = copy.deepcopy(board)
            self._apply_choice(rowcol, board, choices[choice_index])
            rowcol = self._equiv_class[len(self._stack)]
            choices = self._choices(rowcol, board)
            if choices is None:
                return False
            choice_index = 0
            self._stack.append([rowcol, board, choices, choice_index])
        return True

    def _backtrack(self):
        while self._stack:
            rowcol, board, choices, choice_index = self._stack[-1]
            if choice_index == len(choices)-1:
                self._stack.pop()
            else:
                self._stack[-1][-1] += 1
                break

    def _apply_choice(self, rowcol, board, choice):
        safe = board.hidden_neighbors(rowcol)-choice
        for rowcol in choice:
            board.mark_mine(rowcol)
        for rowcol in safe:
            board.mark_safe(rowcol)
        
    def _choices(self, rowcol, board):
        hidden = board.hidden_neighbors(rowcol)
        if not hidden:
            return [set()]
        count = board[rowcol] - len(board.mine_neighbors(rowcol))
        if count < 0 or count > len(hidden):
            return None
        return list(map(set, itertools.combinations(hidden, count)))
    
    def _graph(self):
        # the graph will be represented as an adjacency set, which is a dict that
        # maps each vertex (a digit rowcol) to a set of its adjacent vertices
        graph = {}
        for digit in self.board.digit_rowcols:
            hidden_neighbors = self.board.hidden_neighbors(digit)
            if not hidden_neighbors:
                continue
            adj_set = graph[digit] = set()
            for hidden in hidden_neighbors:
                adj_set.update(rowcol for rowcol in self.board.digit_neighbors(hidden)
                                if rowcol != digit)
        return graph

    def _equiv_classes(self):
        graph = self._graph()
        vertices = iter(graph.keys())
        equiv_classes = []
        while graph:
            root = next(iter(graph.keys()))
            equiv_class = set()
            equiv_classes.append(equiv_class)
            queue = deque([root])
            while queue:
                vertex = queue.popleft()
                if vertex in equiv_class:
                    continue
                equiv_class.add(vertex)
                queue.extend(graph.pop(vertex))
        return equiv_classes

class SequenceEngine(Engine):
    def __init__(self, engines):
        self.engines = engines
    def run(self):
        for engine in self.engines:
            mines, safe = engine.run()
            if mines or safe:
                return mines, safe
        return set(), set()
#════════════════════════════════════════
# Agent

class Agent:
    def __init__(self, board, engine):
        self.engine = engine
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
        #════════════════════════════════════════
        # Mark
        pyautogui.keyDown('ctrl')
        for rowcol in mines:
            self.moveTo(rowcol)
            pyautogui.click()
        pyautogui.keyUp('ctrl')
        #════════════════════════════════════════
        # Reveal
        for rowcol in safe:
            self.reveal(rowcol)
        self.sync_board()

    #════════════════════════════════════════
    # main function
        
    def run(self):
        if self.board.all_hidden:
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
            if self.board.remaining == 0:
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

def get_board(nrows, ncols, mines):
    time.sleep(2)
    topleft = pyautogui.position()
    pyautogui.move((-100,-100)) # so that the cursor is not on a box
    img = pyautogui.screenshot()
    return Board(img, topleft, nrows, ncols, mines)

def take_screenshot():
    time.sleep(2)
    return pyautogui.screenshot()

def update_board(board):
    time.sleep(2)
    img = pyautogui.screenshot()
    board.update(img)

#════════════════════════════════════════

def main():
    time.sleep(2)
    rows, cols, mines = parse_args()
    topleft = pyautogui.position()
    pyautogui.move((-100,-100)) # so that the cursor is not on a box
    img = pyautogui.screenshot()
    board = Board(img, topleft, rows, cols, mines)
    engine = SequenceEngine([GroupsEngine(board), BruteForceEngine(board)])
    agent = Agent(board, engine)
    agent.run()

if __name__ == "__main__":
    main()
