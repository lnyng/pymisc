#!/usr/bin/env python3
import enum
import re
from functools import reduce
import curses
import curses.textpad

class Compass(enum.Enum):
    NORTH = 'N'
    WEST = 'W'
    SOUTH = 'S'
    EAST = 'E'

    def oppo(self):
        if self is Compass.NORTH:
            return Compass.SOUTH
        if self is Compass.WEST:
            return Compass.EAST
        if self is Compass.SOUTH:
            return Compass.NORTH
        if self is Compass.EAST:
            return Compass.WEST

    def cells(self, w, h):
        if self is Compass.NORTH:
            return [(col, h-1) for col in range(w)]
        if self is Compass.WEST:
            return [(0, row) for row in range(h)]
        if self is Compass.SOUTH:
            return [(col, 0) for col in range(w)]
        if self is Compass.EAST:
            return [(w-1, row) for row in range(h)]

class Orient(enum.Enum):
    VERT = 1
    HORZ = 2

class Pawn:
    def __init__(self, side, pos, num_fences=10):
        self.num_fences = num_fences
        self.side = side
        self.pos = pos
        self.win = False

class Quoridor:

    WIDTH = 9
    HEIGHT = 9

    def default_pos(self, side):
        """
        Gets the middle position (COL, ROW) of a side. (0, 0) refers to the bottom left corner on the board. If even number of cells, the one to the right is returned.

        :param side: side of the board, must be a Compass enum
        :param width: width of the board
        :param height: height of the board
        :return: default position of a pawn
        :rtype: tuple(int, int)
        """
        if side is Compass.NORTH:
            return (int((self.width-1)/2), self.height-1)
        if side is Compass.SOUTH:
            return (int(self.width/2), 0)
        if side is Compass.WEST:
            return (0, int((self.height-1)/2))
        if side is Compass.EAST:
            return (self.width-1,int(self.height/2))

    def __init__(self, height=HEIGHT, width=WIDTH, pawns=None,
            def_pos=None):
        self.height = height
        self.width = width
        if def_pos is None:
            def_pos = self.default_pos
        if pawns is None:
            pawns = [Pawn(Compass.SOUTH, def_pos(Compass.SOUTH)),
                    Pawn(Compass.NORTH, def_pos(Compass.NORTH))]
        self.pawns = pawns
        self._curr_pawn = 0
        self.cells = [[None for _ in range(height)] for _ in range(width)]
        for pawn in pawns:
            self.cells[pawn.pos[0]][pawn.pos[1]] = pawn
        self._cell_tags = None
        self.grid = [[None for _ in range(height-1)] for _ in range(width-1)]
        self.finished = False

    def do(self, cmd):
        if self.finished:
            raise ValueError('Game already finished')
        cmd = cmd.upper()
        m = re.match(r'([NSWE]+)$|([A-Z]+[1-9][0-9]*[\-|])$', cmd)
        if m is None:
            raise ValueError('Illegal command')
        if m.group(1) is not None:
            pawn = self.curr_pawn
            pos = pawn.pos
            for c in cmd:
                if c == 'N':
                    pos = pos[0], pos[1]+1
                elif c == 'S':
                    pos = pos[0], pos[1]-1
                elif c == 'W':
                    pos = pos[0]-1, pos[1]
                else:
                    pos = pos[0]+1, pos[1]
            dst = pos
            self.move(dst)
        else:
            coord = Quoridor.parse_text_coord(cmd[:-1])
            orient = Orient.VERT if cmd[-1] == '|' else Orient.HORZ
            self.put_fence(coord, orient)

    @property
    def curr_pawn(self):
        return self.pawns[self._curr_pawn]

    def next_pawn(self):
        self._curr_pawn = (self._curr_pawn+1) % len(self.pawns)
        return self.curr_pawn

    @staticmethod
    def parse_text_coord(coord):
        if len(coord) != 2:
            raise ValueError("Text coordinates must be length of 2")
        m = re.match(r'([A-Z]+)([1-9][0-9]*)', coord)
        if m is None:
            raise ValueError("Invalid text coordinate format")
        col = reduce(lambda x, y: x*26+y, [ord(c)-64 for c in m.group(1)])-1
        row = int(m.group(2))-1
        return (col, row)

    @staticmethod
    def _fill_cells(cells, grid, pos, tag):
        c, r = pos
        w, h = len(cells), len(cells[0])
        if cells[c][r] is not None:
            return
        cells[c][r] = tag
        if c > 0:
            if (r == 0 or grid[c-1][r-1] is not Orient.VERT) and \
                (r == h-1 or grid[c-1][r] is not Orient.VERT):
                    Quoridor._fill_cells(cells, grid, (c-1, r), tag)
        if c < w-1:
            if (r == 0 or grid[c][r-1] is not Orient.VERT) and \
                (r == h-1 or grid[c][r] is not Orient.VERT):
                    Quoridor._fill_cells(cells, grid, (c+1, r), tag)
        if r > 0:
            if (c == 0 or grid[c-1][r-1] is not Orient.HORZ) and \
                (c == w-1 or grid[c][r-1] is not Orient.HORZ):
                    Quoridor._fill_cells(cells, grid, (c, r-1), tag)
        if r < h-1:
            if (c == 0 or grid[c-1][r] is not Orient.HORZ) and \
                (c == w-1 or grid[c][r] is not Orient.HORZ):
                    Quoridor._fill_cells(cells, grid, (c, r+1), tag)

    def is_blocking(self, pawn):
        w, h = self.width, self.height
        if self._cell_tags is None:
            cell_tags = [[None for _ in range(w)] for _ in range(h)]
            tag = 0
            for col in range(w):
                for row in range(h):
                    if cell_tags[col][row] is not None:
                        continue
                    Quoridor._fill_cells(cell_tags, self.grid, (col, row), tag)
                    tag += 1
            self._cell_tags = cell_tags
        tag = self._cell_tags[pawn.pos[0]][pawn.pos[1]]
        return all(tag != self._cell_tags[dst[0]][dst[1]]
            for dst in pawn.side.oppo().cells(w, h))

    def can_put_fence(self, coord, orient):
        if not isinstance(orient, Orient):
            raise TypeError("Invalid type for orient")
        if not (0 <= coord[0] < self.width-1 and 0 <= coord[1] < self.height-1):
            return False
        if self.grid[coord[0]][coord[1]] is not None:
            return False
        if orient is Orient.HORZ:
            if coord[0] > 0:
                if self.grid[coord[0]-1][coord[1]] is Orient.HORZ:
                    return False
            if coord[0] < self.width-2:
                if self.grid[coord[0]+1][coord[1]] is Orient.HORZ:
                    return False
        else:
            if coord[1] > 0:
                if self.grid[coord[0]][coord[1]-1] is Orient.VERT:
                    return False
            if coord[1] < self.height-2:
                if self.grid[coord[0]][coord[1]+1] is Orient.VERT:
                    return False
        self.grid[coord[0]][coord[1]] = orient
        blocking = any(self.is_blocking(pawn) for pawn in self.pawns)
        self._cell_tags = None
        self.grid[coord[0]][coord[1]] = None
        return not blocking

    def put_fence(self, coord, orient, player=None, check=True):
        if player is None:
            player = self.curr_pawn
        if check:
            if player.num_fences <= 0:
                raise ValueError('Not enough fences to put')
            if not self.can_put_fence(coord, orient):
                raise ValueError("Illegal position and orientation to put fence")
        self.grid[coord[0]][coord[1]] = orient
        player.num_fences -= 1
        self.next_pawn()

    def move_region(self, pawn=None):
        if pawn is None:
            pawn = self.curr_pawn
        w, h = self.width, self.height
        grid = self.grid
        def _move_region(pos, region, visited):
            if pos in visited:
                return region
            c, r = pos
            if self.cells[c][r] is None:
                region.add(pos)
                return region
            visited.add(pos)
            if c > 0:
                if (r == 0 or grid[c-1][r-1] is not Orient.VERT) and \
                    (r == h-1 or grid[c-1][r] is not Orient.VERT):
                        _move_region((c-1, r), region, visited)
            if c < w-1:
                if (r == 0 or grid[c][r-1] is not Orient.VERT) and \
                    (r == h-1 or grid[c][r] is not Orient.VERT):
                        _move_region((c+1, r), region, visited)
            if r > 0:
                if (c == 0 or grid[c-1][r-1] is not Orient.HORZ) and \
                    (c == w-1 or grid[c][r-1] is not Orient.HORZ):
                        _move_region((c, r-1), region, visited)
            if r < h-1:
                if (c == 0 or grid[c-1][r] is not Orient.HORZ) and \
                    (c == w-1 or grid[c][r] is not Orient.HORZ):
                        _move_region((c, r+1), region, visited)
            return region
        return _move_region(pawn.pos, set(), set())

    def move(self, dst, pawn=None, check=True):
        if pawn is None:
            pawn = self.curr_pawn
        if check:
            region = self.move_region(pawn)
            if dst not in region:
                raise ValueError("Illegal destination for pawn")
        self.cells[pawn.pos[0]][pawn.pos[1]] = None
        pawn.pos = dst
        self.cells[dst[0]][dst[1]] = pawn
        if (pawn.side is Compass.NORTH and dst[1] == 0) or \
                (pawn.side is Compass.SOUTH and dst[1] == self.height-1) or \
                (pawn.side is Compass.WEST and dst[0] == 0) or \
                (pawn.side is Compass.EAST and dst[0] == self.width-1):
                    pawn.win = True
                    self.finished = True
                    return
        self.next_pawn()

    def __str__(self):
        w, h = self.width, self.height
        s = [[' ' for _ in range(w*4+7)] for _ in range(h*2+5)]
        s[2][3] = s[h*2+2][3] = s[h*2+2][w*4+3] = s[2][w*4+3] = '+'
        for i in range(1, w*4):
            s[2][i+3] = s[h*2+2][i+3] = '-'
        for i in range(1, h*2):
            s[i+2][3] = s[i+2][w*4+3] = '|'
        for i in range(w-1):
            s[0][i*4+7] = s[h*2+4][i*4+7] = chr(ord('A')+i)
            s[1][i*4+7] = s[h*2+3][i*4+7] = '|'
        for i in range(h-1):
            s[i*2+4][0] = s[i*2+4][w*4+6] = str(h-i-1)
            for j in (1,2,w*4+4,w*4+5):
                s[i*2+4][j] = '-'
        for col in range(w-1):
            for row in range(h-1):
                orient = self.grid[col][row]
                if orient is None:
                    s[(h-2-row)*2+4][col*4+7] = '+'
                elif orient is Orient.VERT:
                    for i in range(3):
                        s[(h-2-row)*2+3+i][col*4+7] = '|'
                else:
                    for i in range(7):
                        s[(h-2-row)*2+4][col*4+4+i] = '-'
        for pawn in self.pawns:
            c, r = pawn.pos
            s[(h-1-r)*2+3][c*4+5] = pawn.side.value
        for pos in self.move_region():
            c, r = pos
            s[(h-1-r)*2+3][c*4+5] = 'o'
        s = '\n'.join(''.join(row) for row in s) + '\n'
        for pawn in self.pawns:
            s += '\n    %s | fences=%d' % (pawn.side.value, pawn.num_fences)
            if pawn is self.curr_pawn:
                s += ' *'
        return s

def main(stdscr):
    q = Quoridor()

    stdscr.clear()
    curses.noecho()
    h, w = q.height*2+8, 80
    boardwin = curses.newwin(h, w, 0, 0)
    statuswin = curses.newwin(2, w, h+1, 0)
    promptwin = curses.newwin(1, 3, h+3, 0)
    promptwin.addstr('> ')
    promptwin.refresh()
    textwin = curses.newwin(1, w-2, h+3, 2)
    textbox = curses.textpad.Textbox(textwin, insert_mode=True)
    boardwin.addstr(0, 0, str(q))
    boardwin.refresh()
    while not q.finished:
        try:
            cmd = textbox.edit().strip()
            textwin.clear()
            statuswin.clear()
            statuswin.addstr(0, 0, 'Last command: %s' % cmd)
            q.do(cmd)
            boardwin.clear()
            boardwin.addstr(0, 0, str(q))
        except KeyboardInterrupt:
            statuswin.clear()
            statuswin.addstr('Game aborted')
            statuswin.refresh()
            curses.delay_output(1000)
            return
        except Exception as e:
            statuswin.clear()
            statuswin.addstr(str(e) + ': {%s}' % cmd)
        finally:
            boardwin.refresh()
            statuswin.refresh()
            textwin.refresh()
    statuswin.clear()
    statuswin.addstr('Game finished! Winner is player %s\n' % q.curr_pawn.side.value)
    statuswin.addstr('type anykey to exit...')
    statuswin.getch()    

if __name__ == '__main__':
    curses.wrapper(main)
