"use client";

import { useEffect, useState } from 'react';
import { AlertTriangle, Clock, TrendingUp } from 'lucide-react';
import SplitDecisionModal from './SplitDecisionModal';

/**
 * OversizedDeliveryAlert
 * Dashboard widget showing pending split decisions
 * Appears in transport supervisor dashboard
 * Real-time alerts with action items
 */

export default function OversizedDeliveryAlert({ onRefresh }) {
  const [pendingSplits, setPendingSplits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedProposal, setSelectedProposal] = useState(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    fetchPendingSplits();
    // Poll every 30 seconds for new pending splits
    const interval = setInterval(fetchPendingSplits, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchPendingSplits = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/planning/oversized/pending', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch pending splits');
      }
      
      const data = await response.json();
      setPendingSplits(data.pending_splits || []);
      setError(null);
    } catch (err) {
      console.error('Error fetching pending splits:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenProposal = (split) => {
    setSelectedProposal(split);
    setShowModal(true);
  };

  const handleDecisionSubmit = async (decision) => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/planning/oversized/${decision.delivery_id}/decision`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          },
          body: JSON.stringify(decision)
        }
      );

      if (!response.ok) {
        throw new Error('Failed to submit decision');
      }

      const result = await response.json();
      console.log('Decision submitted:', result);
      
      setShowModal(false);
      setSelectedProposal(null);
      
      // Refresh pending splits
      await fetchPendingSplits();
      
      // Callback to parent component
      if (onRefresh) {
        onRefresh();
      }
    } catch (err) {
      console.error('Error submitting decision:', err);
      alert('Erreur lors de la soumission de la décision: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDecisionCancel = () => {
    setShowModal(false);
    setSelectedProposal(null);
  };

  const formatTimeAgo = (isoDate) => {
    const date = new Date(isoDate);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);
    
    if (seconds < 60) return 'il y a quelques secondes';
    if (seconds < 3600) return `il y a ${Math.floor(seconds / 60)} min`;
    if (seconds < 86400) return `il y a ${Math.floor(seconds / 3600)}h`;
    return date.toLocaleDateString('fr-FR');
  };

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
        <p className="text-red-300">Erreur: {error}</p>
      </div>
    );
  }

  if (loading && pendingSplits.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4">
        <p className="text-gray-400">Chargement des splits en attente...</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        {/* Alert Header */}
        {pendingSplits.length > 0 && (
          <div className="bg-red-900/20 border-l-4 border-red-500 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-red-300">
                  {pendingSplits.length} livraison{pendingSplits.length > 1 ? 's' : ''} en attente de décision
                </h3>
                <p className="text-sm text-red-200 mt-1">
                  Des livraisons dépassent la capacité maximale des véhicules et nécessitent une décision.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Pending Splits List */}
        {pendingSplits.length > 0 ? (
          <div className="grid gap-3">
            {pendingSplits.map((split) => (
              <div
                key={split.audit_id}
                className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4 hover:border-red-400/30 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="inline-block px-2 py-1 bg-red-500/20 text-red-300 rounded text-xs font-mono">
                        #{split.delivery_id}
                      </span>
                      <span className="text-sm text-gray-400">
                        {split.client || 'Client inconnu'}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-3 my-3 text-sm">
                      <div>
                        <span className="text-gray-500 text-xs">Quantité</span>
                        <p className="font-mono text-white">{split.quantity} unités</p>
                      </div>
                      <div>
                        <span className="text-gray-500 text-xs">Splits proposés</span>
                        <p className="font-mono text-blue-300">{split.proposal.proposed_sub_deliveries.length}</p>
                      </div>
                      <div>
                        <span className="text-gray-500 text-xs">Détecté</span>
                        <p className="text-gray-300 text-xs">{formatTimeAgo(split.detected_at)}</p>
                      </div>
                    </div>

                    {/* Constraint Checks */}
                    <div className="text-xs space-y-1 mb-3">
                      {split.proposal.constraint_check.slice(0, 2).map((check, idx) => (
                        <div key={idx} className="text-gray-400">
                          <span className="text-green-400">✓</span> {check}
                        </div>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={() => handleOpenProposal(split)}
                    className="ml-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold transition-colors"
                  >
                    Décider
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-8 text-center">
            <TrendingUp className="w-12 h-12 text-green-400 mx-auto mb-3 opacity-50" />
            <p className="text-gray-400">Aucune livraison en attente de décision</p>
            <p className="text-xs text-gray-500 mt-1">Toutes les livraisons respectent les capacités</p>
          </div>
        )}
      </div>

      {/* Split Decision Modal */}
      {showModal && selectedProposal && (
        <SplitDecisionModal
          proposal={selectedProposal.proposal}
          onConfirm={handleDecisionSubmit}
          onCancel={handleDecisionCancel}
        />
      )}
    </>
  );
}
