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