# This file is part of scikit-time
#
# Copyright (c) 2020 AI4Science Group, Freie Universitaet Berlin (GER)
#
# scikit-time is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from typing import Optional

import numpy as np


def timeshifted_split(inputs, lagtime: int, chunksize: int = 1000, stride: int = 1, n_splits: Optional[int] = None,
                      shuffle: bool = False, random_state: Optional[np.random.RandomState] = None):
    r""" Utility function which splits input trajectories into pairs of timeshifted data :math:`(X_t, X_{t+\tau})`.
    In case multiple trajectories are provided, the timeshifted pairs are always within the same trajectory.

    Parameters
    ----------
    inputs : (T, n) ndarray or list of (T_i, n) ndarrays
        Input trajectory or trajectories. In case multiple trajectories are provided, they must have the same dimension
        in the second axis but may be of variable length.
    lagtime : int
        The lag time :math:`\tau` used to produce timeshifted blocks.
    chunksize : int, default=1000
        The chunk size, i.e., the maximal length of the blocks.
    stride: int, default=1
        Optional stride which is applied *after* creating a tau-shifted version of the dataset.
    n_splits : int, optional, default=None
        Alternative to chunksize - this determines the number of timeshifted blocks that is drawn from each provided
        trajectory. Supersedes whatever was provided as chunksize.
    shuffle : bool, default=False
        Whether to shuffle the data prior to splitting it.
    random_state : np.random.RandomState, default=None
        When shuffling this can be used to set a specific random state.

    Returns
    -------
    iterable : Generator
        A Python generator which can be iterated.

    Examples
    --------
    Using chunksize:

    >>> data = np.array([0, 1, 2, 3, 4, 5, 6])
    >>> for X, Y in timeshifted_split(data, lagtime=1, chunksize=4):
    ...     print(X, Y)
    [0 1 2 3] [1 2 3 4]
    [4 5] [5 6]

    Using n_splits:

    >>> data = np.array([0, 1, 2, 3, 4, 5, 6])
    >>> for X, Y in timeshifted_split(data, lagtime=1, n_splits=2):
    ...     print(X, Y)
    [0 1 2] [1 2 3]
    [3 4 5] [4 5 6]
    """
    if lagtime < 0:
        raise ValueError('lagtime has to be positive')
    if int(chunksize) < 0:
        raise ValueError('chunksize has to be positive')

    if shuffle and random_state is None:
        random_state = np.random.RandomState()

    if not isinstance(inputs, list):
        if isinstance(inputs, tuple):
            inputs = list(inputs)
        inputs = [inputs]

    if not all(len(data) > lagtime for data in inputs):
        too_short_inputs = [i for i, x in enumerate(inputs) if len(x) < lagtime]
        raise ValueError(f'Input contained to short (smaller than lagtime({lagtime}) at following '
                         f'indices: {too_short_inputs}')

    for data in inputs:
        data = np.asarray_chkfinite(data)
        data_lagged = data[lagtime:][::stride]
        if lagtime > 0:
            data = data[:-lagtime][::stride]
        else:
            data = data[0::stride]  # otherwise data is empty as slice over `data[:-0]`
        ix = np.arange(len(data))  # iota range over data
        if shuffle:
            random_state.shuffle(ix)

        if n_splits is not None:
            assert n_splits >= 1
            for ix_split in np.array_split(ix, n_splits):
                if len(ix_split) > 0:
                    x = data[ix_split]
                    if lagtime > 0:
                        x_lagged = data_lagged[ix_split]
                        yield x, x_lagged
                    else:
                        yield x
                else:
                    break
        else:
            t = 0
            while t < len(data):
                if t == len(data_lagged):
                    break
                x = data[ix[t:min(t + chunksize, len(data))]]
                if lagtime > 0:
                    x_lagged = data_lagged[ix[t:min(t + chunksize, len(data_lagged))]]
                    yield x, x_lagged
                else:
                    yield x
                t += chunksize
