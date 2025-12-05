class Quadtree:
    """
    A Quadtree implementation for optimizing 2D spatial queries.
    This is used by the SmartBorderManager to quickly find visible points
    without iterating through the entire dataset on every frame.
    """
    def __init__(self, boundary, capacity=4):
        """
        Initializes the Quadtree.
        :param boundary: A tuple (x, y, width, height) representing the area this node covers.
        :param capacity: The maximum number of points a node can hold before subdividing.
        """
        self.boundary = boundary
        self.capacity = capacity
        self.points = []
        self.divided = False
        self.northwest = None
        self.northeast = None
        self.southwest = None
        self.southeast = None

    def subdivide(self):
        """Divides the current node into four sub-quadrants."""
        x, y, w, h = self.boundary
        hw, hh = w / 2, h / 2

        nw_boundary = (x, y, hw, hh)
        ne_boundary = (x + hw, y, hw, hh)
        sw_boundary = (x, y + hh, hw, hh)
        se_boundary = (x + hw, y + hh, hw, hh)

        self.northwest = Quadtree(nw_boundary, self.capacity)
        self.northeast = Quadtree(ne_boundary, self.capacity)
        self.southwest = Quadtree(sw_boundary, self.capacity)
        self.southeast = Quadtree(se_boundary, self.capacity)
        self.divided = True

    def insert(self, point):
        """
        Inserts a point into the Quadtree.
        :param point: A tuple (x, y).
        """
        x, y, w, h = self.boundary
        if not (x <= point[0] < x + w and y <= point[1] < y + h):
            return False

        if len(self.points) < self.capacity:
            self.points.append(point)
            return True
        else:
            if not self.divided:
                self.subdivide()

            if self.northwest.insert(point): return True
            if self.northeast.insert(point): return True
            if self.southwest.insert(point): return True
            if self.southeast.insert(point): return True
        return False

    def query(self, range_rect, found_points):
        """
        Finds all points within a given rectangular range.
        :param range_rect: A tuple (x, y, width, height) for the query area.
        :param found_points: A list to which found points will be appended.
        """
        x, y, w, h = self.boundary
        rx, ry, rw, rh = range_rect
        if not (rx < x + w and rx + rw > x and ry < y + h and ry + rh > y):
            return

        for p in self.points:
            if rx <= p[0] < rx + rw and ry <= p[1] < ry + rh:
                found_points.append(p)

        if self.divided:
            self.northwest.query(range_rect, found_points)
            self.northeast.query(range_rect, found_points)
            self.southwest.query(range_rect, found_points)
            self.southeast.query(range_rect, found_points)