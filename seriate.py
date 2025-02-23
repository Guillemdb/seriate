"""Seriation - NP-hard ordering of elements in a set given the distance matrix."""
from typing import List

import numpy
import ortools
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from packaging.version import Version


__version__ = "1.0.1"
ortools_version = Version(ortools.__version__)
ortools6 = Version("6.0.0") <= ortools_version < Version("7")
ortools7 = Version("7.0.0") <= ortools_version < Version("8")


def seriate(dists: numpy.ndarray, approximation_multiplier=1000, timeout=2.0) -> List[int]:
    """
    Order the elements of a set so that the sum of sequential pairwise distances is minimal.

    We solve the Travelling Salesman Problem (TSP) under the hood.
    Reference: http://nicolas.kruchten.com/content/2018/02/seriation/

    :param dists: Either a condensed pdist-like or a symmetric square distance matrix.
    :param approximation_multiplier: Multiply by this number before converting distances \
                                     to integers.
    :param timeout: Maximum amount of time allowed to spend for solving the TSP, in seconds.
    :return: List with ordered element indexes, the same length as the number of elements \
             involved in calculating `dists`.
    """
    assert dists[dists < 0].size == 0, "distances must be non-negative"
    squareform = len(dists.shape) == 2 and dists.shape[1] > 1
    if squareform:
        assert dists.shape[0] == dists.shape[1]
        size = dists.shape[0]
    else:
        # dists.shape[0] = (m * (m - 1)) // 2
        assert 1 <= len(dists.shape) <= 2
        assert int(numpy.round(numpy.sqrt(1 + 8 * dists.shape[0]))) ** 2 == 1 + 8 * dists.shape[0]
        size = int(numpy.round((1 + numpy.sqrt(1 + 8 * dists.shape[0])) / 2))

    if ortools6:
        routing = pywrapcp.RoutingModel(size + 1, 1, size)
    elif ortools7:
        manager = pywrapcp.RoutingIndexManager(size + 1, 1, size)
        routing = pywrapcp.RoutingModel(manager)

    def dist_callback(x, y):
        if ortools7:
            x = manager.IndexToNode(x)
            y = manager.IndexToNode(y)
        if x == size or y == size or x == y:
            return 0
        if squareform:
            dist = dists[x][y]
        else:
            # convert to the condensed index
            if x < y:
                x, y = y, x
            dist = dists[size * y - y * (y + 1) // 2 + x - y - 1]
        # ortools wants integers, so we approximate here
        return int(dist * approximation_multiplier)

    if ortools6:
        routing.SetArcCostEvaluatorOfAllVehicles(dist_callback)
        search_parameters = pywrapcp.RoutingModel.DefaultSearchParameters()
        search_parameters.time_limit_ms = int(timeout * 1000)
    elif ortools7:
        routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(dist_callback))
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.time_limit.FromMilliseconds(int(timeout * 1000))
    search_parameters.local_search_metaheuristic = \
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    assignment = routing.SolveWithParameters(search_parameters)
    index = routing.Start(0)
    route = []
    while not routing.IsEnd(index):
        if ortools6:
            node = routing.IndexToNode(index)
        elif ortools7:
            node = manager.IndexToNode(index)
        if node < size:
            route.append(node)
        index = assignment.Value(routing.NextVar(index))
    return route
