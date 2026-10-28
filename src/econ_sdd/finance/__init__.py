"""Pure financial models. No UI, storage, network, or machine-learning dependencies."""

from .savings import SavingsScenario, SavingsProjection, calculate_savings

__all__ = ["SavingsScenario", "SavingsProjection", "calculate_savings"]
