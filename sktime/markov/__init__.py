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


r"""
.. currentmodule: sktime.markov

===============================================================================
Transition counting and analysis tools
===============================================================================

.. autosummary::
    :toctree: generated/
    :template: class_nomodule.rst

    pcca
    PCCAModel

    TransitionCountEstimator
    TransitionCountModel

    ReactiveFlux

    score_cv
"""

import pint

ureg = pint.UnitRegistry()
ureg.define('step = []')  # dimensionless unit for unspecified lag time unit.
Q_ = ureg.Quantity

# TODO: we need to do this for unpickling, but it will overwrite other apps default registry!
pint.set_application_registry(ureg)

del pint

from ._base import BayesianPosterior, _MSMBaseEstimator
from .pcca import pcca, PCCAModel
from .transition_counting import TransitionCountEstimator, TransitionCountModel

from .reactive_flux import ReactiveFlux

from ._base import score_cv
from . import msm
from . import hmm
