"use client";

import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, XCircle, Edit2 } from 'lucide-react';

/**
 * SplitDecisionModal
 * Human-in-the-loop workflow for approving/rejecting/modifying delivery splits
 * Component used by transport managers to make decisions on oversized deliveries
 */

export default function SplitDecisionModal({ proposal, onConfirm, onCancel }) {
  const [decision, setDecision] = useState('VALIDATE'); // VALIDATE, MODIFY, REJECT
  const [modifiedQuantities, setModifiedQuantities] = useState([]);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (proposal && proposal.proposed_sub_deliveries) {
      // Initialize modified quantities with proposed values
      setModifiedQuantities(
        proposal.proposed_sub_deliveries.map(sub => ({
          sequence: sub.sequence,
          quantity: sub.quantity,
          unit_increment: sub.unit_increment
        }))
      );
    }
  }, [proposal]);

  const handleDecisionChange = (action) => {
    setDecision(action);
    setReason('');
  };

  const handleQuantityChange = (sequence, newQuantity) => {
    const updated = modifiedQuantities.map(q =>
      q.sequence === sequence ? { ...q, quantity: parseInt(newQuantity) || 0 } : q
    );
    setModifiedQuantities(updated);
  };

  const handleSubmit = () => {
    if (!reason.trim()) {
      alert('Please provide a reason for your decision');
      return;
    }

    const payload = {
      delivery_id: proposal.original_delivery_id,
      action: decision,
      reason: reason.trim(),
      modified_quantities: decision === 'MODIFY' 
        ? modifiedQuantities.map(q => q.quantity)
        : undefined
    };

    setLoading(true);
    onConfirm(payload);
  };

  if (!proposal) {
    return null;
  }

  const totalProposed = proposal.proposed_sub_deliveries
    .reduce((sum, sub) => sum + sub.quantity, 0);
  const totalModified = modifiedQuantities
    .reduce((sum, q) => sum + q.quantity, 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4">
      <div className="w-full max-w-4xl rounded-2xl border border-red-400/30 bg-slate-950 shadow-2xl shadow-black/50">
        {/* Header */}
        <div className="rounded-t-2xl bg-red-500/10 px-8 py-6 border-b border-red-400/20">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6 text-red-400" />
            <div>
              <h2 className="text-xl font-bold text-white">Décision sur Split de Livraison</h2>
              <p className="text-sm text-gray-300 mt-1">
                Livraison #{proposal.original_delivery_id}: 
                <span className="font-mono text-red-300 ml-2">{proposal.total_quantity} unités</span>
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="px-8 py-6 space-y-6">
          {/* Proposal Summary */}
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Proposition de l'algorithme</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-xs text-gray-400">Capacité max véhicule</span>
                <p className="text-lg font-mono text-blue-300">{proposal.max_vehicle_capacity}</p>
              </div>
              <div>
                <span className="text-xs text-gray-400">Nombre de splits proposés</span>
                <p className="text-lg font-mono text-blue-300">{proposal.proposed_sub_deliveries.length}</p>
              </div>
            </div>
            
            {/* Constraint Checks */}
            <div className="mt-4 space-y-2">
              {proposal.constraint_check.map((check, idx) => (
                <div key={idx} className="text-xs text-gray-300 flex items-start gap-2">
                  <span className="text-green-400 mt-0.5">✓</span>
                  <span>{check}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Decision Buttons */}
          <div className="border-b border-slate-700/50 pb-6">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Votre décision</h3>
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => handleDecisionChange('VALIDATE')}
                className={`p-3 rounded-lg border-2 transition-all ${
                  decision === 'VALIDATE'
                    ? 'border-green-400/50 bg-green-400/10'
                    : 'border-slate-600/50 bg-slate-900/50 hover:border-green-400/30'
                }`}
              >
                <CheckCircle2 className="w-5 h-5 mx-auto mb-2 text-green-400" />
                <span className="text-xs font-medium block text-white">VALIDER</span>
                <span className="text-xs text-gray-400">Accepter la proposition</span>
              </button>

              <button
                onClick={() => handleDecisionChange('MODIFY')}
                className={`p-3 rounded-lg border-2 transition-all ${
                  decision === 'MODIFY'
                    ? 'border-amber-400/50 bg-amber-400/10'
                    : 'border-slate-600/50 bg-slate-900/50 hover:border-amber-400/30'
                }`}
              >
                <Edit2 className="w-5 h-5 mx-auto mb-2 text-amber-400" />
                <span className="text-xs font-medium block text-white">MODIFIER</span>
                <span className="text-xs text-gray-400">Ajuster les quantités</span>
              </button>

              <button
                onClick={() => handleDecisionChange('REJECT')}
                className={`p-3 rounded-lg border-2 transition-all ${
                  decision === 'REJECT'
                    ? 'border-red-400/50 bg-red-400/10'
                    : 'border-slate-600/50 bg-slate-900/50 hover:border-red-400/30'
                }`}
              >
                <XCircle className="w-5 h-5 mx-auto mb-2 text-red-400" />
                <span className="text-xs font-medium block text-white">REJETER</span>
                <span className="text-xs text-gray-400">Transport exceptionnel</span>
              </button>
            </div>
          </div>

          {/* Modify Quantities (if MODIFY selected) */}
          {decision === 'MODIFY' && (
            <div className="bg-amber-400/5 border border-amber-400/20 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-amber-300 mb-3">Ajuster les quantités</h3>
              <div className="space-y-2">
                {modifiedQuantities.map((q) => (
                  <div key={q.sequence} className="flex items-center gap-3">
                    <span className="text-sm text-gray-400 w-16">Split {q.sequence}:</span>
                    <input
                      type="number"
                      value={q.quantity}
                      onChange={(e) => handleQuantityChange(q.sequence, e.target.value)}
                      className="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-white text-sm"
                    />
                    <span className="text-xs text-gray-400">/ {q.unit_increment}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 p-2 bg-slate-900/50 rounded text-xs text-gray-300">
                <strong>Total:</strong> {totalModified} / {proposal.total_quantity}
                {totalModified !== proposal.total_quantity && (
                  <span className="text-red-300 ml-2">⚠ Somme invalide</span>
                )}
              </div>
            </div>
          )}

          {/* Reason */}
          <div>
            <label className="block text-sm font-semibold text-gray-300 mb-2">
              Justification
              {decision === 'REJECT' && ' (raison du rejet)'}
              {decision === 'MODIFY' && ' (modifications apportées)'}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={
                decision === 'REJECT'
                  ? 'Ex: Capacité insuffisante, localisation spéciale, équipement non disponible...'
                  : decision === 'MODIFY'
                  ? 'Ex: Ajustement selon disponibilité véhicules, regroupement client...'
                  : 'Justification de l\'approbation'
              }
              className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-gray-500 focus:border-slate-500 focus:outline-none"
              rows="3"
            />
          </div>

          {/* Info Box */}
          <div className="bg-blue-400/5 border border-blue-400/20 rounded-lg p-3 text-xs text-blue-200">
            <p>
              💡 Cette décision sera enregistrée dans la traçabilité IATF avec votre identifiant,
              l'horodatage et la justification fournie.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 justify-end bg-slate-900/50 border-t border-slate-700/50 px-8 py-4 rounded-b-2xl">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-6 py-2 rounded-lg border border-slate-600 text-white hover:bg-slate-900/50 transition-colors disabled:opacity-50"
          >
            Annuler
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || !reason.trim() || (decision === 'MODIFY' && totalModified !== proposal.total_quantity)}
            className={`px-6 py-2 rounded-lg font-semibold transition-all ${
              decision === 'VALIDATE'
                ? 'bg-green-600 hover:bg-green-700 text-white disabled:opacity-50'
                : decision === 'MODIFY'
                ? 'bg-amber-600 hover:bg-amber-700 text-white disabled:opacity-50'
                : 'bg-red-600 hover:bg-red-700 text-white disabled:opacity-50'
            }`}
          >
            {loading ? 'Traitement...' : 'Confirmer la décision'}
          </button>
        </div>
      </div>
    </div>
  );
}
