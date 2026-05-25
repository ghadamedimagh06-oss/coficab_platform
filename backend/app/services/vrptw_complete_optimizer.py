"""Compatibility wrapper for the former complete optimizer module."""

from app.services.vrptw_optimizer import VRPTWOptimizer


class VRPTWCompleteOptimizer:
    def __init__(self, deliveries, trucks, current_routes=None):
        self.optimizer = VRPTWOptimizer(deliveries, trucks, current_routes or [])

    def run(self):
        return self.optimizer.optimize()
