
# This file is part of BHMM (Bayesian Hidden Markov Models).
#
# Copyright (c) 2016 Frank Noe (Freie Universitaet Berlin)
# and John D. Chodera (Memorial Sloan-Kettering Cancer Center, New York)
#
# BHMM is free software: you can redistribute it and/or modify
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

import typing

import msmtools.estimation as msmest
import numpy as np

from sktime.base import Estimator, Model
from sktime.markovprocess.bhmm import HMM
from sktime.markovprocess.bhmm.estimators.maximum_likelihood import MaximumLikelihoodHMM
from . import _tmatrix_disconnected
from .. import hidden


class BayesianHMMPosterior(Model):
    r""" Bayesian Hidden Markov model with samples of posterior and prior. """

    def __init__(self,
                 prior: typing.Optional[HMM] = None,
                 samples: typing.Optional[typing.List[HMM]] = None):
        self.prior = prior
        self.samples = samples

    def __iter__(self):
        for s in self.samples:
            yield s


class BayesianHMMSampler(Estimator):
    r"""Bayesian hidden Markov model sampler.

    Parameters
    ----------
    nstates : int
        The number of states in the model.
    initial_model : HMM, optional, default=None
        If specified, the given initial model will be used to initialize the BHMM.
        Otherwise, a heuristic scheme is used to generate an initial guess.
    reversible : bool, optional, default=True
        If True, a prior that enforces reversible transition matrices (detailed balance) is used;
        otherwise, a standard  non-reversible prior is used.
    stationary : bool, optional, default=False
        If True, the stationary distribution of the transition matrix will be used as initial distribution.
        Only use True if you are confident that the observation trajectories are started from a global
        equilibrium. If False, the initial distribution will be estimated as usual from the first step
        of the hidden trajectories.
    transition_matrix_sampling_steps : int, optional, default=1000
        number of transition matrix sampling steps per BHMM cycle
    p0_prior : None, str, float or ndarray(n)
        Prior for the initial distribution of the HMM. Will only be active
        if stationary=False (stationary=True means that p0 is identical to
        the stationary distribution of the transition matrix).
        Currently implements different versions of the Dirichlet prior that
        is conjugate to the Dirichlet distribution of p0. p0 is sampled from:
        .. math:
            p0 \sim \prod_i (p0)_i^{a_i + n_i - 1}
        where :math:`n_i` are the number of times a hidden trajectory was in
        state :math:`i` at time step 0 and :math:`a_i` is the prior count.
        Following options are available:
        |  'mixed' (default),  :math:`a_i = p_{0,init}`, where :math:`p_{0,init}`
            is the initial distribution of initial_model.
        |  'uniform',  :math:`a_i = 1`
        |  ndarray(n) or float,
            the given array will be used as A.
        |  None,  :math:`a_i = 0`. This option ensures coincidence between
            sample mean an MLE. Will sooner or later lead to sampling problems,
            because as soon as zero trajectories are drawn from a given state,
            the sampler cannot recover and that state will never serve as a starting
            state subsequently. Only recommended in the large data regime and
            when the probability to sample zero trajectories from any state
            is negligible.
    transition_matrix_prior : str or ndarray(n, n)
        Prior for the HMM transition matrix.
        Currently implements Dirichlet priors if reversible=False and reversible
        transition matrix priors as described in [1]_ if reversible=True. For the
        non-reversible case the posterior of transition matrix :math:`P` is:
        .. math:
            P \sim \prod_{i,j} p_{ij}^{b_{ij} + c_{ij} - 1}
        where :math:`c_{ij}` are the number of transitions found for hidden
        trajectories and :math:`b_{ij}` are prior counts.
        |  'mixed' (default),  :math:`b_{ij} = p_{ij,init}`, where :math:`p_{ij,init}`
            is the transition matrix of initial_model. That means one prior
            count will be used per row.
        |  'uniform',  :math:`b_{ij} = 1`
        |  ndarray(n, n) or broadcastable,
            the given array will be used as B.
        |  None,  :math:`b_ij = 0`. This option ensures coincidence between
            sample mean an MLE. Will sooner or later lead to sampling problems,
            because as soon as a transition :math:`ij` will not occur in a
            sample, the sampler cannot recover and that transition will never
            be sampled again. This option is not recommended unless you have
            a small HMM and a lot of data.
    output : str, optional, default='gaussian'
        Output model type.  ['gaussian', 'discrete']

    nsamples : int
        The number of samples to generate.

    Examples
    --------

    First, create some synthetic test data.

    >>> from sktime.markovprocess import bhmm
    >>> nstates = 3
    >>> model = bhmm.testsystems.dalton_model(nstates)
    >>> observations, hidden_states = model.generate_synthetic_observation_trajectories(ntrajectories=5, length=1000)

    Initialize a new BHMM model.

    >>> from sktime.markovprocess.bhmm import BHMM
    >>> bhmm_sampler = BHMM(nstates=nstates)
    >>> bhmm_sampler.fit(observations) # +DOCTEST.ELLIPSIS
    BayesianHMMSampler...

    Sample from the posterior.

    >>> models = bhmm_sampler.fetch_model().samples

    References
    ----------
    .. [1] Trendelkamp-Schroer, B., H. Wu, F. Paul and F. Noe:
        Estimation and uncertainty of reversible Markov models.
        J. Chem. Phys. 143, 174101 (2015).

    """
    def __init__(self, nstates, initial_model=None, reversible=True, stationary=False,
                 transition_matrix_sampling_steps=1000, p0_prior='mixed', transition_matrix_prior='mixed',
                 output='gaussian', nsamples=100, ):
        super(BayesianHMMSampler, self).__init__()
        self.reversible = reversible
        self.stationary = stationary

        self.nstates = nstates

        # Use user-specified initial model, if provided.
        if initial_model is not None:
            self.initial_model = initial_model.copy()
        else:
            self.initial_model = None

        # prior initial vector
        if p0_prior is None or p0_prior == 'sparse':
            self.prior_n0 = np.zeros(self.nstates)
        elif isinstance(p0_prior, np.ndarray):
            if len(p0_prior.shape) == 1 and p0_prior.shape[0] == self.nstates:
                self.prior_n0 = np.array(p0_prior)
            else:
                raise ValueError(f'initial distribution prior must have dimension {nstates}')
        elif p0_prior == 'mixed':
            if initial_model is not None:
                self.prior_n0 = np.array(self.initial_model.initial_distribution)
            else:
                self.prior_n0 = None
        elif p0_prior == 'uniform':
            self.prior_n0 = np.ones(nstates)
        else:
            raise ValueError(f'initial distribution prior mode undefined: {p0_prior}')

        # prior count matrix
        if transition_matrix_prior is None or p0_prior == 'sparse':
            self.prior_C = np.zeros((self.nstates, self.nstates))
        elif isinstance(transition_matrix_prior, np.ndarray):
            if np.array_equal(transition_matrix_prior.shape, (self.nstates, self.nstates)):
                self.prior_C = np.array(transition_matrix_prior)
        elif transition_matrix_prior == 'mixed':
            if initial_model is not None:
                self.prior_C = np.array(self.initial_model.transition_matrix)
            else:
                self.prior_C = None
        elif p0_prior == 'uniform':
            self.prior_C = np.ones((nstates, nstates))
        else:
            raise ValueError(f'transition matrix prior mode undefined: {transition_matrix_prior}')

        # check if we work with these options
        if (reversible and self.initial_model is not None
                and not msmest.is_connected(self.initial_model.transition_matrix + self.prior_C, directed=True)):
            raise NotImplementedError('Trying to sample disconnected HMM with option reversible:\n '
                                      f'{self.initial_model.transition_matrix}\n'
                                      'Use prior to connect, select connected subset, or use reversible=False.')

        # sampling options
        self.transition_matrix_sampling_steps = transition_matrix_sampling_steps
        self.nsamples = nsamples
        self.output = output

    def _create_model(self):
        return BayesianHMMPosterior()

    def fit(self, observations, nburn=0, nthin=1, save_hidden_state_trajectory=False, call_back=None, **kwargs):
        """Sample from the BHMM posterior.

        Parameters
        ----------
        nburn : int, optional, default=0
            The number of samples to discard to burn-in, following which `nsamples` will be generated.
        nthin : int, optional, default=1
            The number of Gibbs sampling updates used to generate each returned sample.
        save_hidden_state_trajectory : bool, optional, default=False
            If True, the hidden state trajectory for each sample will be saved as well.
        call_back : function, optional, default=None
            a call back function with no arguments, which if given is being called
            after each computed sample. This is useful for implementing progress bars.

        Returns
        -------
        models : list of bhmm.HMM


        Examples
        --------

        >>> from sktime.markovprocess.bhmm import testsystems
        >>> model, observations, states, sampler = testsystems.generate_random_bhmm(ntrajectories=5, length=1000)
        >>> nburn = 5 # run the sampler a bit before recording samples
        >>> nsamples = 10 # generate 10 samples
        >>> nthin = 2 # discard one sample in between each recorded sample
        >>> sampler.nsamples = nsamples
        >>> sampler.fit(observations, nburn=nburn, nthin=nthin) # +DOCTEST.ELLIPSIS
        BayesianHMMSampler...
        >>> model = sampler.fetch_model()
        >>> model.prior # +DOCTEST.ELLIPSIS
        HMM...
        >>> len(model.samples)
        10

        """
        # Store a copy of the observations.
        # Sanity checks.
        if len(observations) == 0:
            raise ValueError("No observations were provided.")

        maxT = max(len(o) for o in observations)

        # pre-construct hidden variables
        self._alpha = np.zeros((maxT, self.nstates))
        self._pobs = np.zeros((maxT, self.nstates))

        # Generate our own initial model.
        if self.initial_model is None:
            self.initial_model = self._generateInitialModel(observations, self.output)
            if self.prior_n0 is None:
                self.prior_n0 = self.initial_model.initial_distribution
            if self.prior_C is None:
                self.prior_C = np.array(self.initial_model.transition_matrix)

        # save a copy of the initial model as the prior
        prior = self.initial_model.copy()
        sample_model = prior.copy()
        # Run burn-in.
        for _ in range(nburn):
            self._update(sample_model, observations)

        # Collect data.
        models = []
        for _ in range(self.nsamples):
            # Run a number of Gibbs sampling updates to generate each sample.
            for _ in range(nthin):
                self._update(sample_model, observations)
            # Save a copy of the current model.
            model_copy = sample_model.copy()
            # the viterbi path is discarded, but is needed to get a new transition matrix for each model.
            if not save_hidden_state_trajectory:
                model_copy.hidden_state_trajectory = None
            models.append(model_copy)
            if call_back is not None:
                call_back()

        self._model.samples = models
        self._model.prior = prior
        # free estimation variables
        del self._alpha
        del self._pobs

        return self

    def _update(self, model, observations):
        """Update the current model using one round of Gibbs sampling."""
        self._update_hidden_state_trajectories(model, observations)
        self._update_emission_probabilities(model, observations)
        self._update_transition_matrix(model)

    def _update_hidden_state_trajectories(self, model, observations):
        """Sample a new set of state trajectories from the conditional distribution P(S | T, E, O)"""
        model.hidden_state_trajectories = [
            self._sample_hidden_state_trajectory(model, obs)
            for obs in observations
        ]

    def _sample_hidden_state_trajectory(self, model, obs):
        """Sample a hidden state trajectory from the conditional distribution P(s | T, E, o)

        Parameters
        ----------
        o_t : numpy.array with dimensions (T,)
            observation[n] is the nth observation

        Returns
        -------
        s_t : numpy.array with dimensions (T,) of type `dtype`
            Hidden state trajectory, with s_t[t] the hidden state corresponding to observation o_t[t]
        """

        # Determine observation trajectory length
        T = obs.shape[0]

        # Convenience access.
        A = model.transition_matrix
        pi = model.initial_distribution

        # compute output probability matrix
        model.output_model.p_obs(obs, out=self._pobs)
        # compute forward variables
        hidden.forward(A, self._pobs, pi, T=T, alpha=self._alpha)
        # sample path
        S = hidden.sample_path(self._alpha, A, self._pobs, T=T)

        return S

    def _update_emission_probabilities(self, model, observations):
        """Sample a new set of emission probabilites from the conditional distribution P(E | S, O) """
        observations_by_state = [model.collect_observations_in_state(observations, state)
                                 for state in range(model.nstates)]
        model.output_model.sample(observations_by_state)

    def _update_transition_matrix(self, model):
        """ Updates the hidden-state transition matrix and the initial distribution """
        C = model.count_matrix() + self.prior_C  # posterior count matrix

        # check if we work with these options
        if self.reversible and not msmest.is_connected(C, directed=True):
            raise NotImplementedError('Encountered disconnected count matrix with sampling option reversible:\n '
                                      f'{C}\nUse prior to ensure connectivity or use reversible=False.')
        # ensure consistent sparsity pattern (P0 might have additional zeros because of underflows)
        # TODO: these steps work around a bug in msmtools. Should be fixed there
        P0 = msmest.transition_matrix(C, reversible=self.reversible, maxiter=10000, warn_not_converged=False)
        zeros = np.where(P0 + P0.T == 0)
        C[zeros] = 0
        # run sampler
        Tij = msmest.sample_tmatrix(C, nsample=1, nsteps=self.transition_matrix_sampling_steps,
                                    reversible=self.reversible)

        # INITIAL DISTRIBUTION
        if self.stationary:  # p0 is consistent with P
            p0 = _tmatrix_disconnected.stationary_distribution(Tij, C=C)
        else:
            n0 = model.count_init().astype(float)
            first_timestep_counts_with_prior = n0 + self.prior_n0
            positive = first_timestep_counts_with_prior > 0
            p0 = np.zeros_like(n0)
            p0[positive] = np.random.dirichlet(first_timestep_counts_with_prior[positive])  # sample p0 from posterior

        # update HMM with new sample
        model.update(p0, Tij)

    def _generateInitialModel(self, observations, output_model_type):
        """Initialize using an MLHMM."""
        mlhmm = MaximumLikelihoodHMM(self.nstates, reversible=self.reversible,
                                     output=output_model_type)
        mlhmm.fit(observations)
        model = mlhmm.fetch_model()
        return model
