"""
Objectives that place some value on a set on input points

Author: Jeff Mahler
"""
from abc import ABCMeta, abstractmethod

import numbers
import numpy as np

class Objective:
    __metaclass__ = ABCMeta

    def __call__(self, x):
        """ Evaluate the objective at a point x """
        return self.evaluate(x)

    @abstractmethod
    def evaluate(self, x):
        """ Evaluates a function to be maximized at some point x """
        pass

    @abstractmethod
    def check_valid_input(self):
        """ Return whether or not a point is valid for the objective """
        pass

class DifferentiableObjective(Objective):
    __metaclass__ = ABCMeta

    @abstractmethod
    def gradient(self, x):
        """ Evaluate the gradient at x """
        pass

    @abstractmethod
    def hessian(self, x):
        """ Evaluate the hessian at x """
        pass

class MaximizationObjective(DifferentiableObjective):
    """
    Maximization on some supplied objective function. Actually not super important, here for symmetry
    """
    def __init__(self, obj):
        """ obj is the objective to call """
        if not isinstance(obj, Objective):
            raise ValueError("Function must be a single argument objective")
        self.obj_ = obj

    def check_valid_input(self, x):
        self.obj_.check_valid_input(x)

    def evaluate(self, x):
        return self.obj_(x)

    def gradient(self, x):
        if not isinstance(self.obj_, DifferentiableObjective):
            raise ValueError("Objective is non-differentiable")
        return self.obj_.gradient(x)

    def hessian(self, x):
        if not isinstance(self.obj_, DifferentiableObjective):
            raise ValueError("Objective is non-differentiable")
        return self.obj_.hessian(x)

class MinimizationObjective(DifferentiableObjective):
    """
    Maximization on some supplied objective function. Actually not super important, here for symmetry
    """
    def __init__(self, obj):
        """ obj is the objective to call """
        if not isinstance(obj, Objective):
            raise ValueError("Function must be a single argument objective")
        self.obj_ = obj

    def check_valid_input(self, x):
        self.obj_.check_valid_input(x)

    def evaluate(self, x):
        """ Return negative, as all solvers will be assuming a maximization """
        return -self.obj_(x)

    def gradient(self, x):
        if not isinstance(self.obj_, DifferentiableObjective):
            raise ValueError("Objective is non-differentiable")
        return -self.obj_.gradient(x)

    def hessian(self, x):
        if not isinstance(self.obj_, DifferentiableObjective):
            raise ValueError("Objective is non-differentiable")
        return -self.obj_.hessian(x)

class NonDeterministicObjective(Objective):

    def __init__(self, det_objective):
        """ Wraps around a deterministic objective """
        self.det_objective_ = det_objective

    def evaluate(self, x):
        """ Sample the input space, then evaluate """
        if not hasattr(x, "sample_success"):
            raise ValueError("Data points must have a sampling function returning a 0 or 1")

        x_val = x.sample_success()
        return self.det_objective_.evaluate(x_val)

class ZeroOneObjective(Objective):
    """ Zero One Loss based on thresholding """
    def __init__(self, b = 0):
        self.b_ = b

    def check_valid_input(self, x):
        """ Check whether or not input is valid for the objective """
        if not isinstance(x, numbers.Number):
            raise ValueError("Zero-One objective can only be evaluated on numbers")

    def evaluate(self, x):
        self.check_valid_input(x)
        return x >= self.b_

class RandomBinaryObjective(NonDeterministicObjective):
    """
    Returns a 0 or 1 based on some underlying random probability of success for the data points
    Evaluated data points must have a sample_success method that returns 0 or 1
    """
    def __init__(self):
        NonDeterministicObjective.__init__(self, ZeroOneObjective(0.5))

    def check_valid_input(self, x):
        """ Check whether or not input is valid for the objective """
        if not isinstance(x, numbers.Number):
            raise ValueError("Random binary objective can only be evaluated on numbers")

class LeastSquaresObjective(DifferentiableObjective):
    """ Classic least-squares loss 0.5 * |Ax - b|**2 """
    def __init__(self, A, b):
        self.A_ = A
        self.b_ = b

        self.x_dim_ = A.shape[1]
        self.b_dim_ = A.shape[0]
        if self.b_dim_ != b.shape[0]:
            raise ValueError('A and b must have same dimensions')

    def check_valid_input(self, x):
        if not isinstance(x, np.ndarray):
            raise ValueError('Least squares objective only works with numpy ndarrays!')
        if x.shape[0] != self.x_dim_:
            raise ValueError('x values must have same dimensions as number of columns of A')

    def evaluate(self, x):
        self.check_valid_input(x)
        return 0.5 * (x.T.dot(self.A_.T).dot(self.A_).dot(x) - 2 * self.b_.T.dot(self.A_).dot(x) + self.b_.T.dot(self.b_))

    def gradient(self, x):
        self.check_valid_input(x)
        return self.A_.T.dot(self.A_).dot(x) - self.A_.T.dot(self.b_)

    def hessian(self, x):
        self.check_valid_input(x)
        return self.A_.T.dot(self.A_)

class LogisticCrossEntropyObjective(DifferentiableObjective):
    def __init__(self, X, y):
        self.X_ = X
        self.y_ = y

    def check_valid_input(self, beta):
        if not isinstance(beta, np.ndarray):
            raise ValueError('Logistic cross-entropy objective only works with np.ndarrays!')
        if self.X_.shape[1] != beta.shape[0]:
            raise ValueError('beta dimension mismatch')

    def _mu(self, X, beta):
        return 1.0 / (1.0 + np.exp(-np.dot(X, beta)))

    def evaluate(self, beta):
        self.check_valid_input(beta)
        mu = self._mu(self.X_, beta)
        return -np.sum(self.y_ * np.log(mu) + (1 - self.y_) * np.log(1 - mu))

    def gradient(self, beta):
        self.check_valid_input(beta)
        mu = self._mu(self.X_, beta)
        return 2 * beta - np.dot(self.X_.T, self.y_ - mu)

    def hessian(self, beta):
        self.check_valid_input(beta)
        mu = self._mu(self.X_, beta)
        return 2 - np.dot(np.dot(self.X_.T, np.diag(mu * (1 - mu))), self.X_)

class StochasticLogisticCrossEntropyObjective(LogisticCrossEntropyObjective):
    def __init__(self, X, y, batch_size=1):
        LogisticCrossEntropyObjective.__init__(self, X, y)
        self.batch_size = batch_size

    def get_random_datum(self):
        num_data = self.y_.shape[0]
        indices = range(num_data) * (self.batch_size // num_data)
        if self.batch_size % num_data != 0:
            indices += list(np.random.randint(num_data, size=self.batch_size % num_data))
        x = self.X_[indices, :]
        y = self.y_[indices]
        return x, y

    def gradient(self, beta):
        self.check_valid_input(beta)
        x, y = self.get_random_datum()
        mu = self._mu(x, beta)
        return (2 * beta - np.dot(x.T, y - mu)).squeeze()

    def hessian(self, beta):
        self.check_valid_input(beta)
        x, y = self.get_random_datum()
        mu = self._mu(x, beta)
        return 2 - np.dot(np.dot(x.T, np.diag(mu * (1 - mu))), x)

class StochasticGraspWeightObjective(DifferentiableObjective):
    def __init__(self, X, S, F):
        self.X_ = X     # design matrix
        self.S_ = S     # num successes
        self.F_ = F     # num failures
        self.N_ = S + F # num trials

        self.mu_ = S / F
        self.batch_size = 1 # hard-coded for now
        self.num_grasps_ = S.shape[0]
        self.num_features_ = X.shape[1]

        if not (X.shape[0] == S.shape[0] == F.shape[0]):
            raise ValueError('Dimension mismatch')

    def check_valid_input(self, w):
        if not isinstance(w, np.ndarray):
            raise ValueError('Grasp weight objective only works with np.ndarrays')
        if w.shape[0] == self.num_features_:
            raise ValueError('weight vector dimension mismatch')

    def kernel(self, w):
        def phi(row):
            return w * row
        return kernels.SquaredExponentialKernel(
            sigma=config['kernel_sigma'], l=config['kernel_l'], phi=phi)

    def evaluate(self, w):
        self.check_valid_input(w)
        kernel = self.kernel(w)

        total = 0
        for i in range(self.num_grasps_):
            xi = self.X_[i, :]
            kernels = [kernel(xi, xj) for xj in self.X_]
            alphas = kernels * self.S_
            betas = kernels * self.F_
            alpha_i = 1 + sum(alpha for j, alpha in enumerate(alphas) if i != j)
            beta_i = 1 + sum(beta for j, beta in enumerate(betas) if i != j)
            total += self.mu_[i] * np.log(alpha_i) + (1 - self.mu_[i]) * np.log(beta_i) - np.log(alpha_i + beta_i)
        return total

    def get_random_datum(self):
        i = np.random.randint(self.num_grasps_, size=self.batch_size)
        x = self.X_[i, :]
        without_x = np.delete(self.X_, i, 0)
        return x, without_x

    def gradient(self, w):
        self.check_valid_input(w)
        kernel = self.kernel(w)
        x, without_x, i = self.get_random_datum()

        kernels = [kernel(x, xj) for xj in self.X_]
        alphas = kernels * self.S_
        betas = kernels * self.F_

        kernels = np.delete(kernels, i)
        alpha_i = 1 + sum(alpha for j, alpha in enumerate(alphas) if i != j)
        beta_i = 1 + sum(beta for j, beta in enumerate(betas) if i != j)

        total = 0
        norm = np.delete(np.linalg.norm(self.X_ - x), i, 0)
        v = w * norm * norm

        return kernels * v * \
            ((self.S_ * self.S_ / alpha_i / self.N_) + \
             (self.F_ * self.F_ / beta_i / self.N_) + \
             self.N_ / (alpha_i + beta_i))

    def hessian(self, w):
        raise NotImplementedError
