#!/usr/bin/env python
# -*- coding: utf-8 -*-

# distribution.py
# definitons of spatial distribution characters

from tqdm import tqdm  # progress bar
from shapely.geometry import LineString, Point
import numpy as np
import pandas as pd
import statistics


def orientation(objects):
    """
    Calculate orientation (azimuth) of object

    Defined as an orientation of the longext axis of bounding rectangle in range 0 - 45.
    It captures the deviation of orientation from cardinal directions.

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse

    Returns
    -------
    Series
        Series containing resulting values.

    References
    ---------
    Schirmer PM and Axhausen KW (2015) A multiscale classiﬁcation of urban morphology.
    Journal of Transport and Land Use 9(1): 101–130. (adapted)

    Examples
    --------
    >>> buildings_df['orientation'] = momepy.orientation(buildings_df)
    Calculating orientations...
    100%|██████████| 144/144 [00:00<00:00, 630.54it/s]
    Orientations calculated.
    >>> buildings_df['orientation'][0]
    41.05146788287027
    """
    # define empty list for results
    results_list = []

    print('Calculating orientations...')

    def _azimuth(point1, point2):
        '''azimuth between 2 shapely points (interval 0 - 180)'''
        angle = np.arctan2(point2.x - point1.x, point2.y - point1.y)
        return np.degrees(angle)if angle > 0 else np.degrees(angle) + 180

    # iterating over rows one by one
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        bbox = list(row['geometry'].minimum_rotated_rectangle.exterior.coords)
        centroid_ab = LineString([bbox[0], bbox[1]]).centroid
        centroid_cd = LineString([bbox[2], bbox[3]]).centroid
        axis1 = centroid_ab.distance(centroid_cd)

        centroid_bc = LineString([bbox[1], bbox[2]]).centroid
        centroid_da = LineString([bbox[3], bbox[0]]).centroid
        axis2 = centroid_bc.distance(centroid_da)

        if axis1 <= axis2:
            az = _azimuth(centroid_bc, centroid_da)
            if 90 > az >= 45:
                diff = az - 45
                az = az - 2 * diff
            elif 135 > az >= 90:
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            elif 181 > az >= 135:
                diff = az - 135
                az = az - 2 * diff
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            results_list.append(az)
        else:
            az = 170
            az = _azimuth(centroid_ab, centroid_cd)
            if 90 > az >= 45:
                diff = az - 45
                az = az - 2 * diff
            elif 135 > az >= 90:
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            elif 181 > az >= 135:
                diff = az - 135
                az = az - 2 * diff
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            results_list.append(az)

    series = pd.Series(results_list)
    print('Orientations calculated.')
    return series


def shared_walls_ratio(objects, unique_id, perimeters=None):
    """
    Calculate shared walls ratio

    .. math::
        \\textit{length of shared walls} \\over perimeter

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    unique_id : str, list, np.array, pd.Series
        the name of the dataframe column, np.array, or pd.Series with unique id
    perimeters : str, list, np.array, pd.Series (default None)
        the name of the dataframe column, np.array, or pd.Series where is stored perimeter value

    Returns
    -------
    Series
        Series containing resulting values.

    References
    ---------
    Hamaina R, Leduc T and Moreau G (2012) Towards Urban Fabrics Characterization
    Based on Buildings Footprints. In: Lecture Notes in Geoinformation and Cartography,
    Berlin, Heidelberg: Springer Berlin Heidelberg, pp. 327–346. Available from:
    https://link.springer.com/chapter/10.1007/978-3-642-29063-3_18.

    Examples
    --------
    >>> buildings_df['swr'] = momepy.shared_walls_ratio(buildings_df, 'uID')
    Generating spatial index...
    Calculating shared walls ratio...
    100%|██████████| 144/144 [00:00<00:00, 648.72it/s]
    Shared walls ratio calculated.
    >>> buildings_df['swr'][10]
    0.3424804411228673
    """
    print('Generating spatial index...')
    sindex = objects.sindex  # define rtree index
    # define empty list for results
    results_list = []

    print('Calculating shared walls ratio...')

    if perimeters is None:
        objects['mm_p'] = objects.geometry.length
        perimeters = 'mm_p'
    else:
        if type(perimeters) is not str:
            objects['mm_p'] = perimeters
            perimeters = 'mm_p'
    if type(unique_id) is not str:
        objects['mm_uid'] = unique_id
        unique_id = 'mm_uid'

    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        neighbors = list(sindex.intersection(row.geometry.bounds))
        neighbors.remove(index)

        # if no neighbour exists
        length = 0
        if len(neighbors) == 0:
            results_list.append(0)
        else:
            for i in neighbors:
                subset = objects.loc[i]['geometry']
                length = length + row.geometry.intersection(subset).length
            results_list.append(length / row[perimeters])
    series = pd.Series(results_list)
    print('Shared walls ratio calculated.')
    if 'mm_p' in objects.columns:
        objects.drop(columns=['mm_p'], inplace=True)
    return series


def street_alignment(objects, streets, orientation_column, network_id_column):
    """
    Calculate the difference between street orientation and orientation of object

    Orientation of street segment is represented by the orientation of line
    connecting first and last point of the segment. Network ID linking each object
    to specific street segment is needed. Can be generated by :py:func:`momepy.elements.get_network_id`.

    .. math::
        \\left|{\\textit{building orientation} - \\textit{street orientation}}\\right|

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    streets : GeoDataFrame
        GeoDataFrame containing street network
    orientation_column : str
        name of the column where is stored object orientation value
    network_id_column : str
        name of the column with unique network id (has to be defined beforehand)
        (can be defined using unique_id())

    Returns
    -------
    Series
        Series containing resulting values.
    """
    # define empty list for results
    results_list = []

    print('Calculating street alignments...')

    def azimuth(point1, point2):
        '''azimuth between 2 shapely points (interval 0 - 180)'''
        angle = np.arctan2(point2.x - point1.x, point2.y - point1.y)
        return np.degrees(angle)if angle > 0 else np.degrees(angle) + 180

    # iterating over rows one by one
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        if pd.isnull(row[network_id_column]):
            results_list.append(0)
        else:
            network_id = row[network_id_column]
            streetssub = streets.loc[streets[network_id_column] == network_id]
            start = Point(streetssub.iloc[0]['geometry'].coords[0])
            end = Point(streetssub.iloc[0]['geometry'].coords[-1])
            az = azimuth(start, end)
            if 90 > az >= 45:
                diff = az - 45
                az = az - 2 * diff
            elif 135 > az >= 90:
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            elif 181 > az >= 135:
                diff = az - 135
                az = az - 2 * diff
                diff = az - 90
                az = az - 2 * diff
                diff = az - 45
                az = az - 2 * diff
            results_list.append(abs(row[orientation_column] - az))
    series = pd.Series(results_list)
    print('Street alignments calculated.')
    return series


def cell_alignment(objects, tessellation, orientation_column, cell_orientation_column, unique_id):
    """
    Calculate the difference between cell orientation and orientation of object

    .. math::
        \\left|{\\textit{building orientation} - \\textit{cell orientation}}\\right|

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    tessellation : GeoDataFrame
        GeoDataFrame containing street network
    orientation_column : str
        name of the column where is stored object orientation value
    cell_orientation_column : str
        name of the column where is stored cell orientation value in tessellation gdf
    unique_id : str
        name of the column with unique id

    Returns
    -------
    Series
        Series containing resulting values.
    """
    # define empty list for results
    results_list = []

    print('Calculating cell alignments...')

    # iterating over rows one by one
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):

        results_list.append(abs(row[orientation_column] - tessellation[tessellation[unique_id] == row[unique_id]][cell_orientation_column].iloc[0]))

    series = pd.Series(results_list)
    print('Cell alignments calculated.')
    return series


def alignment(objects, orientation_column, tessellation, weights_matrix=None):
    """
    Calculate the mean deviation of solar orientation of objects on adjacent cells from object

    .. math::
        \\frac{1}{n}\\sum_{i=1}^n dev_i=\\frac{dev_1+dev_2+\\cdots+dev_n}{n}

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    orientation_column : str
        name of the column where is stored object orientation value
    tessellation : GeoDataFrame
        GeoDataFrame containing morphological tessellation - source of weights_matrix.
        It is crucial to use exactly same input as was used durign the calculation of weights matrix.
        If weights_matrix is None, tessellation is used to calulate it.
    weights_matrix : libpysal.weights, optional
        spatial weights matrix - If None, Queen contiguity matrix will be calculated
        based on tessellation

    Returns
    -------
    Series
        Series containing resulting values.
    """
    # define empty list for results
    results_list = []

    print('Calculating alignments...')

    if weights_matrix is None:
        print('Calculating spatial weights...')
        from libpysal.weights import Queen
        weights_matrix = Queen.from_dataframe(tessellation)
        print('Spatial weights ready...')

    # iterating over rows one by one
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        id = tessellation.loc[tessellation['uID'] == row['uID']].index[0]
        neighbours = weights_matrix.neighbors[id]
        neighbours_ids = []

        for n in neighbours:
            uniq = tessellation.iloc[n]['uID']
            neighbours_ids.append(uniq)

        orientations = []
        for i in neighbours_ids:
            ori = objects.loc[objects['uID'] == i].iloc[0][orientation_column]
            orientations.append(ori)

        deviations = []
        for o in orientations:
            dev = abs(o - row[orientation_column])
            deviations.append(dev)

        if len(deviations) > 0:
            results_list.append(statistics.mean(deviations))
        else:
            results_list.append(0)

    series = pd.Series(results_list)

    print('Alignments calculated.')
    return series


def neighbour_distance(objects, tessellation, weights_matrix=None):
    """
    Calculate the mean distance to buildings on adjacent cells

    .. math::
        \\frac{1}{n}\\sum_{i=1}^n dist_i=\\frac{dist_1+dist_2+\\cdots+dist_n}{n}

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    tessellation : GeoDataFrame
        GeoDataFrame containing morphological tessellation - source of weights_matrix.
        It is crucial to use exactly same input as was used durign the calculation of weights matrix.
        If weights_matrix is None, tessellation is used to calulate it.
    weights_matrix : libpysal.weights, optional
        spatial weights matrix - If None, Queen contiguity matrix will be calculated
        based on tessellation

    Returns
    -------
    Series
        Series containing resulting values.

    References
    ---------
    Schirmer PM and Axhausen KW (2015) A multiscale classiﬁcation of urban morphology.
    Journal of Transport and Land Use 9(1): 101–130.
    """
    # define empty list for results
    results_list = []

    print('Calculating distances...')

    if weights_matrix is None:
        print('Calculating spatial weights...')
        from libpysal.weights import Queen
        weights_matrix = Queen.from_dataframe(tessellation)
        print('Spatial weights ready...')

    # iterating over rows one by one
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        id = tessellation.loc[tessellation['uID'] == row['uID']].index[0]
        neighbours = weights_matrix.neighbors[id]

        neighbours_ids = tessellation.iloc[neighbours]['uID']
        building_neighbours = objects.loc[objects['uID'].isin(neighbours_ids)]
        if len(building_neighbours) > 0:
            results_list.append(np.mean(building_neighbours.geometry.distance(row['geometry'])))
        else:
            results_list.append(0)

    series = pd.Series(results_list)

    print('Distances calculated.')
    return series


def mean_interbuilding_distance(objects, tessellation, weights_matrix=None, weights_matrix_higher=None, order=3):
    """
    Calculate the mean interbuilding distance within x topological steps

    Interbuilding distances are calculated between buildings on adjacent cells based on `weights_matrix`.

    .. math::


    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    tessellation : GeoDataFrame
        GeoDataFrame containing morphological tessellation - source of weights_matrix and weights_matrix_higher.
        It is crucial to use exactly same input as was used durign the calculation of weights matrix and weights_matrix_higher.
        If weights_matrix or weights_matrix_higher is None, tessellation is used to calulate it.
    weights_matrix : libpysal.weights, optional
        spatial weights matrix - If None, Queen contiguity matrix will be calculated
        based on tessellation
    weights_matrix_higher : libpysal.weights, optional
        spatial weights matrix - If None, Queen contiguity of higher order will be calculated
        based on tessellation
    order : int
        Order of Queen contiguity

    Returns
    -------
    Series
        Series containing resulting values.

    References
    ---------
    ADD, but it is adapted quite a lot.
    """

    print('Calculating mean interbuilding distances...')
    if weights_matrix is None:
        print('Generating weights matrix (Queen)...')
        from libpysal.weights import Queen
        # matrix to capture interbuilding relationship
        weights_matrix = Queen.from_dataframe(tessellation)

    if weights_matrix_higher is None:
        print('Generating weights matrix (Queen) of {} topological steps...'.format(order))
        from momepy import Queen_higher
        # matrix to define area of analysis (more steps)
        weights_matrix_higher = Queen_higher(tessellation, k=order)

    # define empty list for results
    results_list = []

    print('Generating adjacency matrix based on weights matrix...')
    # define adjacency list from lipysal
    adj_list = weights_matrix.to_adjlist()
    adj_list['distance'] = -1

    print('Computing interbuilding distances...')
    # measure each interbuilding distance of neighbours and save them to adjacency list
    for index, row in tqdm(adj_list.iterrows(), total=adj_list.shape[0]):
        inverted = adj_list[(adj_list.focal == row.neighbor)][(adj_list.neighbor == row.focal)].iloc[0]['distance']
        if inverted == -1:
            object_id = tessellation.iloc[row.focal.astype(int)]['uID']
            building_object = objects.loc[objects['uID'] == object_id]

            neighbours_id = tessellation.iloc[row.neighbor.astype(int)]['uID']
            building_neighbour = objects.loc[objects['uID'] == neighbours_id]
            adj_list.loc[index, 'distance'] = building_neighbour.iloc[0].geometry.distance(building_object.iloc[0].geometry)
        else:
            adj_list.at[index, 'distance'] = inverted

    print('Computing mean interbuilding distances...')
    # iterate over objects to get the final values
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        # id to match spatial weights
        id = tessellation.loc[tessellation['uID'] == row['uID']].index[0]
        # define neighbours based on weights matrix defining analysis area
        neighbours = weights_matrix_higher.neighbors[id]
        neighbours.append(id)
        if len(neighbours) > 0:
            selection = adj_list[adj_list.focal.isin(neighbours)][adj_list.neighbor.isin(neighbours)]
            results_list.append(np.nanmean(selection.distance))

    series = pd.Series(results_list)
    print('Mean interbuilding distances calculated.')
    return series


def neighbouring_street_orientation_deviation(objects):
    """
    Calculate the mean deviation of solar orientation of adjacent streets

    Orientation of street segment is represented by the orientation of line
    connecting first and last point of the segment.

    .. math::
        \\frac{1}{n}\\sum_{i=1}^n dev_i=\\frac{dev_1+dev_2+\\cdots+dev_n}{n}

    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing street network to analyse

    Returns
    -------
    Series
        Series containing resulting values.
    """
    # define empty list for results
    results_list = []

    print('Calculating street alignments...')

    def azimuth(point1, point2):
        '''azimuth between 2 shapely points (interval 0 - 180)'''
        angle = np.arctan2(point2.x - point1.x, point2.y - point1.y)
        return np.degrees(angle)if angle > 0 else np.degrees(angle) + 180

    # iterating over rows one by one
    print(' Preparing street orientations...')
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):

        start = Point(row['geometry'].coords[0])
        end = Point(row['geometry'].coords[-1])
        az = azimuth(start, end)
        if 90 > az >= 45:
            diff = az - 45
            az = az - 2 * diff
        elif 135 > az >= 90:
            diff = az - 90
            az = az - 2 * diff
            diff = az - 45
            az = az - 2 * diff
        elif 181 > az >= 135:
            diff = az - 135
            az = az - 2 * diff
            diff = az - 90
            az = az - 2 * diff
            diff = az - 45
            az = az - 2 * diff
        results_list.append(az)
    series = pd.Series(results_list)

    objects['tmporient'] = series

    print(' Generating spatial index...')
    sindex = objects.sindex
    results_list = []

    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        possible_neighbors_idx = list(sindex.intersection(row.geometry.bounds))
        possible_neighbours = objects.iloc[possible_neighbors_idx]
        neighbors = possible_neighbours[possible_neighbours.intersects(row.geometry)]
        neighbors.drop([index])

        orientations = []
        for idx, r in neighbors.iterrows():
            orientations.append(r.tmporient)

        deviations = []
        for o in orientations:
            dev = abs(o - row.tmporient)
            deviations.append(dev)

        if len(deviations) > 0:
            results_list.append(np.mean(deviations))
        else:
            results_list.append(0)

    series = pd.Series(results_list)
    objects.drop(['tmporient'], axis=1)
    return series


def building_adjacency(objects, tessellation, weights_matrix=None, weights_matrix_higher=None, order=3, unique_id='uID'):
    """
    Calculate the level of building adjacency

    Building adjacency reflects how much buildings tend to join together into larger structures.
    It is calculated as a ratio of buildings within k topological steps and joined built-up structures.

    .. math::


    Parameters
    ----------
    objects : GeoDataFrame
        GeoDataFrame containing objects to analyse
    tessellation : GeoDataFrame
        GeoDataFrame containing morphological tessellation - source of weights_matrix and weights_matrix_higher.
        It is crucial to use exactly same input as was used durign the calculation of weights matrix and weights_matrix_higher.
        If weights_matrix or weights_matrix_higher is None, tessellation is used to calulate it.
    weights_matrix : libpysal.weights, optional
        spatial weights matrix - If None, Queen contiguity matrix will be calculated
        based on tessellation
    weights_matrix_higher : libpysal.weights, optional
        spatial weights matrix - If None, Queen contiguity of higher order will be calculated
        based on tessellation
    order : int
        Order of Queen contiguity

    Returns
    -------
    Series
        Series containing resulting values.

    References
    ---------
    Vanderhaegen S and Canters F (2017) Mapping urban form and function at city
    block level using spatial metrics. Landscape and Urban Planning 167: 399–409.
    """
    # define empty list for results
    results_list = []

    print('Calculating adjacency...')

    # if weights matrix is not passed, generate it from objects
    if weights_matrix is None:
        print('Calculating spatial weights...')
        from libpysal.weights import Queen
        weights_matrix = Queen.from_dataframe(objects, silence_warnings=True)
        print('Spatial weights ready...')

    if weights_matrix_higher is None:
        print('Generating weights matrix (Queen) of {} topological steps...'.format(order))
        from momepy import Queen_higher
        # matrix to define area of analysis (more steps)
        weights_matrix_higher = Queen_higher(tessellation, k=order)

    print('Generating dictionary of built-up patches...')
    # dict to store nr of courtyards for each uID
    patches = {}
    jID = 1
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):

        # if the id is already present in courtyards, continue (avoid repetition)
        if index in patches:
            continue
        else:
            to_join = [index]  # list of indices which should be joined together
            neighbours = []  # list of neighbours
            weights = weights_matrix.neighbors[index]  # neighbours from spatial weights
            for w in weights:
                neighbours.append(w)  # make a list from weigths

            for n in neighbours:
                while n not in to_join:  # until there is some neighbour which is not in to_join
                    to_join.append(n)
                    weights = weights_matrix.neighbors[n]
                    for w in weights:
                        neighbours.append(w)  # extend neighbours by neighbours of neighbours :)
            for b in to_join:
                patches[b] = jID  # fill dict with values
            jID = jID + 1

    print('Calculating adjacency within k steps...')
    for index, row in tqdm(objects.iterrows(), total=objects.shape[0]):
        id = tessellation.loc[tessellation[unique_id] == row[unique_id]].index[0]
        neighbours = weights_matrix_higher.neighbors[id]

        neighbours_ids = tessellation.iloc[neighbours][unique_id]
        neighbours_ids = neighbours_ids.append(pd.Series(row[unique_id], index=[index]))
        building_neighbours = objects.loc[objects[unique_id].isin(neighbours_ids)]
        indices = list(building_neighbours.index)
        patches_sub = [patches[x] for x in indices]
        patches_nr = len(set(patches_sub))

        results_list.append(len(building_neighbours) / patches_nr)

    series = pd.Series(results_list)

    print('Adjacency calculated.')
    return series
# to be deleted, keep at the end
#
# path = "/Users/martin/Strathcloud/Personal Folders/Test data/Royston/buildings.shp"
# objects = gpd.read_file(path)
#
# orientation(objects, 'ptbOri')
# objects.to_file(path)
