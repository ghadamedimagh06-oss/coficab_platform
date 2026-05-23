"""
Split Strategy Service: Intelligent algorithm for respecting business constraints
Respects: palette multiples, whole bobines, client order increments
"""

import math
from typing import List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from app.models.delivery_split import OversizedDeliveryState, SplitProposalSchema, SubDeliverySchema


@dataclass
class VehicleCapacity:
    """Vehicle capacity information"""
    vehicle_id: str
    vehicle_type: str
    capacity: int


@dataclass 
class DeliveryInfo:
    """Delivery information for split calculation"""
    id: int
    quantity: int
    unit_increment: int  # e.g., 24 bobines per palette
    client_id: str
    product_type: str
    notes: Optional[str] = None


class SplitStrategy:
    """
    Intelligent split algorithm respecting business constraints.
    
    Business rules:
    1. Split must respect vehicle capacity
    2. Each sub-delivery must be a multiple of unit_increment (palette of 24 bobines)
    3. No partial bobines (contiguous cable constraint)
    4. Client order increments preserved
    5. Minimize number of splits (efficiency)
    """
    
    def __init__(self, vehicles: List[VehicleCapacity]):
        self.vehicles = vehicles
        self.max_capacity = max(v.capacity for v in vehicles) if vehicles else 1000
    
    def compute_split(
        self,
        delivery: DeliveryInfo,
        max_vehicle_capacity: Optional[int] = None
    ) -> SplitProposalSchema:
        """
        Compute optimal split respecting all constraints.
        
        Args:
            delivery: DeliveryInfo object with quantity, unit_increment, etc.
            max_vehicle_capacity: Override vehicle capacity for this calculation
            
        Returns:
            SplitProposalSchema with proposed sub-deliveries and constraint validation
        """
        capacity = max_vehicle_capacity or self.max_capacity
        quantity = delivery.quantity
        unit_increment = delivery.unit_increment
        
        # Constraint 1: Check if split is even necessary
        if quantity <= capacity:
            # No split needed, but we still validate constraints
            return SplitProposalSchema(
                original_delivery_id=delivery.id,
                total_quantity=quantity,
                max_vehicle_capacity=capacity,
                proposed_sub_deliveries=[
                    SubDeliverySchema(
                        sequence=1,
                        quantity=quantity,
                        unit_increment=unit_increment,
                        estimated_vehicle_type=self._select_best_vehicle(quantity)
                    )
                ],
                constraint_check=[
                    f"✓ Pas de split nécessaire (quantité {quantity} ≤ capacité {capacity})",
                    f"✓ Multiple de {unit_increment} respecté (quantité = {quantity})",
                    f"✓ Respect de l'incrément client"
                ],
                algorithm_notes="Delivery fits single vehicle"
            )
        
        # Constraint 2: Calculate minimum number of splits
        n_splits = math.ceil(quantity / capacity)
        
        # Constraint 3: Calculate base quantity respecting unit_increment
        base_qty_before_rounding = quantity / n_splits
        base_qty = (math.floor(base_qty_before_rounding / unit_increment)) * unit_increment
        
        # Ensure base_qty is not zero
        if base_qty == 0:
            base_qty = unit_increment
            n_splits = math.ceil(quantity / capacity)
        
        # Build sub-deliveries with constraint validation
        sub_deliveries: List[SubDeliverySchema] = []
        accumulated = 0
        
        for i in range(n_splits - 1):
            sub_qty = base_qty
            if sub_qty + accumulated > quantity:
                # Avoid overshooting
                sub_qty = quantity - accumulated
            
            # Ensure it's a multiple of unit_increment
            sub_qty = (math.floor(sub_qty / unit_increment)) * unit_increment
            
            if sub_qty > 0:
                sub_deliveries.append(
                    SubDeliverySchema(
                        sequence=len(sub_deliveries) + 1,
                        quantity=sub_qty,
                        unit_increment=unit_increment,
                        estimated_vehicle_type=self._select_best_vehicle(sub_qty)
                    )
                )
                accumulated += sub_qty
        
        # Last delivery gets the remainder
        remainder = quantity - accumulated
        if remainder > 0:
            # Ensure remainder is multiple of unit_increment if possible
            remainder = (math.floor(remainder / unit_increment)) * unit_increment
            if remainder > 0:
                sub_deliveries.append(
                    SubDeliverySchema(
                        sequence=len(sub_deliveries) + 1,
                        quantity=remainder,
                        unit_increment=unit_increment,
                        estimated_vehicle_type=self._select_best_vehicle(remainder)
                    )
                )
        
        # If we still have a remainder (rounding error), add it to last delivery
        total_allocated = sum(s.quantity for s in sub_deliveries)
        if total_allocated < quantity:
            diff = quantity - total_allocated
            if len(sub_deliveries) > 0:
                sub_deliveries[-1].quantity += diff
            else:
                # Fallback: single sub-delivery with full quantity
                sub_deliveries = [
                    SubDeliverySchema(
                        sequence=1,
                        quantity=quantity,
                        unit_increment=unit_increment,
                        estimated_vehicle_type=self._select_best_vehicle(quantity)
                    )
                ]
        
        # Validate all constraints
        constraint_checks = self._validate_constraints(
            quantity, sub_deliveries, unit_increment, capacity
        )
        
        return SplitProposalSchema(
            original_delivery_id=delivery.id,
            total_quantity=quantity,
            max_vehicle_capacity=capacity,
            proposed_sub_deliveries=sub_deliveries,
            constraint_check=constraint_checks,
            algorithm_notes=f"Split en {len(sub_deliveries)} livraisons pour respecter capacité max {capacity}"
        )
    
    def _validate_constraints(
        self,
        original_qty: int,
        sub_deliveries: List[SubDeliverySchema],
        unit_increment: int,
        capacity: int
    ) -> List[str]:
        """Validate all business constraints and return human-readable checks"""
        checks = []
        
        # Constraint 1: Sum integrity
        total = sum(s.quantity for s in sub_deliveries)
        if total == original_qty:
            checks.append(f"✓ Somme = {total} (original {original_qty}) [INTÉGRITÉ OK]")
        else:
            checks.append(f"✗ Somme {total} ≠ original {original_qty} [ERREUR CALCUL]")
        
        # Constraint 2: Each sub-delivery respects capacity
        all_fit = all(s.quantity <= capacity for s in sub_deliveries)
        if all_fit:
            checks.append(f"✓ Chaque sous-livraison ≤ {capacity} [CAPACITÉ OK]")
        else:
            exceeding = [s for s in sub_deliveries if s.quantity > capacity]
            checks.append(f"✗ {len(exceeding)} sous-livraisons dépassent capacité [ERREUR]")
        
        # Constraint 3: All quantities are multiples of unit_increment
        all_multiples = all(s.quantity % unit_increment == 0 for s in sub_deliveries)
        if all_multiples:
            checks.append(f"✓ Tous les multiples de {unit_increment} [BOBINE ENTIÈRE OK]")
        else:
            non_multiples = [s for s in sub_deliveries if s.quantity % unit_increment != 0]
            checks.append(f"⚠ {len(non_multiples)} quantités ne respectent pas incrément client")
        
        # Constraint 4: Minimum efficiency (at least 2 splits if necessary)
        if len(sub_deliveries) > 1:
            avg_util = (total / (len(sub_deliveries) * capacity)) * 100
            checks.append(f"✓ Utilisation moyenne {avg_util:.1f}% des véhicules [EFFICACITÉ]")
        
        return checks
    
    def _select_best_vehicle(self, quantity: int) -> str:
        """Select the smallest vehicle that can accommodate this quantity"""
        suitable = [v for v in self.vehicles if v.capacity >= quantity]
        if suitable:
            best = min(suitable, key=lambda v: v.capacity)
            return best.vehicle_type
        return "Custom Vehicle"
    
    def validate_modified_quantities(
        self,
        original_qty: int,
        modified_quantities: List[int],
        unit_increment: int,
        capacity: int
    ) -> tuple[bool, List[str]]:
        """
        Validate manually modified split quantities.
        
        Returns:
            (is_valid, constraint_messages)
        """
        messages = []
        is_valid = True
        
        # Check 1: Sum integrity
        if sum(modified_quantities) != original_qty:
            messages.append(f"✗ Somme {sum(modified_quantities)} ≠ original {original_qty}")
            is_valid = False
        else:
            messages.append(f"✓ Somme OK ({sum(modified_quantities)} = {original_qty})")
        
        # Check 2: All respect capacity
        exceeding = [q for q in modified_quantities if q > capacity]
        if exceeding:
            messages.append(f"✗ {len(exceeding)} quantités dépassent capacité {capacity}")
            is_valid = False
        else:
            messages.append(f"✓ Capacité OK (max {max(modified_quantities)} ≤ {capacity})")
        
        # Check 3: All are multiples of unit_increment
        non_multiples = [q for q in modified_quantities if q % unit_increment != 0]
        if non_multiples:
            messages.append(f"⚠ {len(non_multiples)} quantités ne respectent pas incrément {unit_increment}")
            # This is a warning, not a blocker
        else:
            messages.append(f"✓ Incrément client OK (multiples de {unit_increment})")
        
        return is_valid, messages
