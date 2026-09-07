import React, { useEffect, useState } from 'react';
import {
  api,
  type ShipmentCheckpoint,
  type ShipmentExecutionDetail,
  type TransporterMeResponse,
  type TransporterVehicle,
  type TransportOpportunity,
  type TransportOpportunityDetail,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { ShipmentRouteMap } from '../components/ShipmentRouteMap';

interface TransporterDashboardViewProps {
  initialOpportunityId?: string;
  initialShipmentId?: string;
  onNavigate?: (view: string, params?: Record<string, unknown>) => void;
}

export const TransporterDashboardView: React.FC<TransporterDashboardViewProps> = ({
  initialOpportunityId,
  initialShipmentId,
}) => {
  const { user } = useAuth();
  const [summary, setSummary] = useState<TransporterMeResponse | null>(null);
  const [opportunities, setOpportunities] = useState<TransportOpportunity[]>([]);
  const [vehicles, setVehicles] = useState<TransporterVehicle[]>([]);
  const [shipments, setShipments] = useState<Record<string, unknown>[]>([]);
  const [activeTab, setActiveTab] = useState<'opportunities' | 'shipments' | 'fleet' | 'profile'>(
    initialShipmentId ? 'shipments' : 'opportunities'
  );
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Modals state
  const [selectedOppDetail, setSelectedOppDetail] = useState<TransportOpportunityDetail | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);
  const [isAcceptModalOpen, setIsAcceptModalOpen] = useState<boolean>(false);
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState<boolean>(false);
  const [isAddVehicleModalOpen, setIsAddVehicleModalOpen] = useState<boolean>(false);

  // Phase 2H: Execution Tracking State
  const [executionDetail, setExecutionDetail] = useState<ShipmentExecutionDetail | null>(null);
  const [isExecutionTrackerOpen, setIsExecutionTrackerOpen] = useState<boolean>(false);
  const [isLoadingExecution, setIsLoadingExecution] = useState<boolean>(false);
  const [isPickupCompleteModalOpen, setIsPickupCompleteModalOpen] = useState<boolean>(false);
  const [activeCheckpointForComplete, setActiveCheckpointForComplete] = useState<ShipmentCheckpoint | null>(null);
  const [completeLoadedQty, setCompleteLoadedQty] = useState<string>('');
  const [completeVarianceReason, setCompleteVarianceReason] = useState<string>('');
  const [completeNotes, setCompleteNotes] = useState<string>('');
  const [isDeliveryModalOpen, setIsDeliveryModalOpen] = useState<boolean>(false);
  const [deliveryQty, setDeliveryQty] = useState<string>('');
  const [deliveryReceiver, setDeliveryReceiver] = useState<string>('');
  const [deliveryVarianceReason, setDeliveryVarianceReason] = useState<string>('');
  const [deliveryNotes, setDeliveryNotes] = useState<string>('');
  const [isExceptionModalOpen, setIsExceptionModalOpen] = useState<boolean>(false);
  const [exceptionCode, setExceptionCode] = useState<string>('LOADING_DELAY');
  const [exceptionNotes, setExceptionNotes] = useState<string>('');
  const [exceptionCheckpointId, setExceptionCheckpointId] = useState<string>('');

  // Accept Form
  const [acceptVehicleId, setAcceptVehicleId] = useState<string>('');
  const [acceptDriverName, setAcceptDriverName] = useState<string>('');
  const [acceptDriverPhone, setAcceptDriverPhone] = useState<string>('');
  const [acceptNotes, setAcceptNotes] = useState<string>('');

  // Quote Form
  const [quoteAmount, setQuoteAmount] = useState<string>('');
  const [quoteVehicleId, setQuoteVehicleId] = useState<string>('');
  const [quoteNotes, setQuoteNotes] = useState<string>('');

  // Vehicle Form
  const [newRegNumber, setNewRegNumber] = useState<string>('');
  const [newVehicleType, setNewVehicleType] = useState<string>('medium_commercial');
  const [newModelName, setNewModelName] = useState<string>('');
  const [newPayloadKg, setNewPayloadKg] = useState<string>('5000');
  const [newIsRefrigerated, setNewIsRefrigerated] = useState<boolean>(false);

  // Profile Form
  const [editOrgName, setEditOrgName] = useState<string>('');
  const [editPhone, setEditPhone] = useState<string>('');
  const [editEmail, setEditEmail] = useState<string>('');
  const [editDistricts, setEditDistricts] = useState<string>('');

  const handleOpenDetail = async (oppId: string) => {
    try {
      const detail = await api.getTransportOpportunityDetail(oppId);
      setSelectedOppDetail(detail);
      setIsDetailModalOpen(true);
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to fetch opportunity route details.' });
    }
  };

  const handleOpenExecutionTracker = async (shipmentId: string) => {
    setIsLoadingExecution(true);
    try {
      const detail = await api.getShipmentExecutionDetail(shipmentId);
      setExecutionDetail(detail);
      setIsExecutionTrackerOpen(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load shipment execution tracking.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setIsLoadingExecution(false);
    }
  };

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [meRes, oppsRes, vehRes, shipRes] = await Promise.all([
        api.getTransporterMe(),
        api.getTransportOpportunities(),
        api.getTransporterVehicles(),
        api.getTransporterShipments(),
      ]);
      setSummary(meRes);
      setOpportunities(oppsRes);
      setVehicles(vehRes);
      setShipments(shipRes);

      if (meRes.profile) {
        setEditOrgName(meRes.profile.organization_name || '');
        setEditPhone(meRes.profile.contact_phone || '');
        setEditEmail(meRes.profile.contact_email || '');
        setEditDistricts((meRes.profile.service_area_districts || []).join(', '));
      }
    } catch (err: unknown) {
      console.error('Failed to load transporter data:', err);
      setStatusMessage({ type: 'error', text: 'Could not load transporter operational records.' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      try {
        const [meRes, oppsRes, vehRes, shipRes] = await Promise.all([
          api.getTransporterMe(),
          api.getTransportOpportunities(),
          api.getTransporterVehicles(),
          api.getTransporterShipments(),
        ]);
        if (!mounted) return;
        setSummary(meRes);
        setOpportunities(oppsRes);
        setVehicles(vehRes);
        setShipments(shipRes);

        if (meRes.profile) {
          setEditOrgName(meRes.profile.organization_name || '');
          setEditPhone(meRes.profile.contact_phone || '');
          setEditEmail(meRes.profile.contact_email || '');
          setEditDistricts((meRes.profile.service_area_districts || []).join(', '));
        }
      } catch (err: unknown) {
        console.error('Failed to load transporter data:', err);
        if (mounted) setStatusMessage({ type: 'error', text: 'Could not load transporter operational records.' });
      } finally {
        if (mounted) setIsLoading(false);
      }
    };
    void init();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const loadInitialDeepLink = async () => {
      if (initialOpportunityId) {
        try {
          const detail = await api.getTransportOpportunityDetail(initialOpportunityId);
          if (!isMounted) return;
          setSelectedOppDetail(detail);
          setIsDetailModalOpen(true);
        } catch {
          if (!isMounted) return;
          setStatusMessage({ type: 'error', text: 'Failed to fetch opportunity route details.' });
        }
      } else if (initialShipmentId) {
        try {
          setIsLoadingExecution(true);
          const detail = await api.getShipmentExecutionDetail(initialShipmentId);
          if (!isMounted) return;
          setExecutionDetail(detail);
          setIsExecutionTrackerOpen(true);
        } catch (err: unknown) {
          if (!isMounted) return;
          const msg = err instanceof Error ? err.message : 'Failed to load shipment execution tracking.';
          setStatusMessage({ type: 'error', text: msg });
        } finally {
          if (isMounted) setIsLoadingExecution(false);
        }
      }
    };
    void loadInitialDeepLink();
    return () => {
      isMounted = false;
    };
  }, [initialOpportunityId, initialShipmentId]);

  const handleOpenAccept = async (oppId: string) => {
    try {
      const detail = await api.getTransportOpportunityDetail(oppId);
      setSelectedOppDetail(detail);
      const availVehicles = (detail.vehicle_options || []).filter((v) => v.is_available);
      if (availVehicles.length > 0) {
        setAcceptVehicleId(availVehicles[0].id);
      }
      setIsAcceptModalOpen(true);
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to prepare acceptance dialog.' });
    }
  };

  const handleConfirmAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOppDetail || !acceptVehicleId) return;

    try {
      await api.acceptTransportOpportunity(selectedOppDetail.id, {
        vehicle_id: acceptVehicleId,
        driver_name: acceptDriverName || undefined,
        driver_phone: acceptDriverPhone || undefined,
        notes: acceptNotes || undefined,
      });
      setStatusMessage({ type: 'success', text: `Successfully accepted transport job! Vehicle assigned.` });
      setIsAcceptModalOpen(false);
      setSelectedOppDetail(null);
      void loadDashboardData();
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : 'Job acceptance failed or was claimed by another carrier.';
      setStatusMessage({ type: 'error', text: errorMsg });
    }
  };

  const handleOpenQuote = async (oppId: string) => {
    try {
      const detail = await api.getTransportOpportunityDetail(oppId);
      setSelectedOppDetail(detail);
      setQuoteAmount(String(detail.estimated_cost || 5000));
      setIsQuoteModalOpen(true);
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to open quote dialog.' });
    }
  };

  const handleSubmitQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOppDetail || !quoteAmount) return;

    try {
      await api.submitTransporterQuote(selectedOppDetail.id, {
        vehicle_id: quoteVehicleId || undefined,
        quote_amount: parseFloat(quoteAmount),
        quote_unit: 'INR_TOTAL',
        notes: quoteNotes || undefined,
      });
      setStatusMessage({ type: 'success', text: 'Commercial freight quote submitted successfully.' });
      setIsQuoteModalOpen(false);
      void loadDashboardData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to submit freight quote.' });
    }
  };

  const handleDecline = async (oppId: string) => {
    if (!window.confirm('Are you sure you want to decline this transport opportunity?')) return;
    try {
      await api.declineTransportOpportunity(oppId, { reason: 'Declined by operator' });
      setStatusMessage({ type: 'success', text: 'Transport opportunity declined.' });
      void loadDashboardData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to decline opportunity.' });
    }
  };

  // Phase 2H: Checkpoint & Execution Handlers
  const handleArriveCheckpoint = async (checkpointId: string) => {
    if (!executionDetail) return;
    try {
      const updated = await api.recordCheckpointArrival(executionDetail.id, checkpointId);
      setExecutionDetail(updated);
      setStatusMessage({ type: 'success', text: 'Confirmed arrival at checkpoint!' });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to record arrival.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleStartLoading = async (checkpointId: string) => {
    if (!executionDetail) return;
    try {
      const updated = await api.recordCheckpointLoadingStart(executionDetail.id, checkpointId);
      setExecutionDetail(updated);
      setStatusMessage({ type: 'success', text: 'Started loading produce at farm stop.' });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start loading.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleOpenCompletePickupModal = (cp: ShipmentCheckpoint) => {
    setActiveCheckpointForComplete(cp);
    setCompleteLoadedQty(String(Number(cp.planned_quantity_quintals)));
    setCompleteVarianceReason('');
    setCompleteNotes('');
    setIsPickupCompleteModalOpen(true);
  };

  const handleSubmitCompletePickup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!executionDetail || !activeCheckpointForComplete) return;
    const loadedQty = parseFloat(completeLoadedQty);
    if (isNaN(loadedQty) || loadedQty <= 0) {
      setStatusMessage({ type: 'error', text: 'Please enter a valid positive loaded quantity.' });
      return;
    }
    const planned = Number(activeCheckpointForComplete.planned_quantity_quintals);
    if (Math.abs(loadedQty - planned) > 0.001 && !completeVarianceReason.trim()) {
      setStatusMessage({ type: 'error', text: 'An explicit variance reason is required when loaded quantity differs from planned quantity.' });
      return;
    }

    try {
      const updated = await api.recordCheckpointComplete(executionDetail.id, activeCheckpointForComplete.id, {
        loaded_quantity_quintals: loadedQty,
        variance_reason: completeVarianceReason.trim() || undefined,
        notes: completeNotes.trim() || undefined,
      });
      setExecutionDetail(updated);
      setIsPickupCompleteModalOpen(false);
      setActiveCheckpointForComplete(null);
      setStatusMessage({ type: 'success', text: `Pickup completed! Loaded ${loadedQty} QTL recorded.` });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to complete pickup stop.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleStartTransit = async () => {
    if (!executionDetail) return;
    try {
      const updated = await api.recordTransitStart(executionDetail.id);
      setExecutionDetail(updated);
      setStatusMessage({ type: 'success', text: 'Linehaul transit started! Status updated to In Transit.' });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start linehaul transit.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleDestinationArrive = async () => {
    if (!executionDetail) return;
    try {
      const updated = await api.recordDestinationArrival(executionDetail.id);
      setExecutionDetail(updated);
      setStatusMessage({ type: 'success', text: 'Arrived at destination receiving terminal!' });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to record destination arrival.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleOpenDeliveryModal = () => {
    if (!executionDetail) return;
    setDeliveryQty(String(Number(executionDetail.total_picked_up_quantity_quintals)));
    setDeliveryReceiver('');
    setDeliveryVarianceReason('');
    setDeliveryNotes('');
    setIsDeliveryModalOpen(true);
  };

  const handleSubmitDelivery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!executionDetail) return;
    const delQty = parseFloat(deliveryQty);
    if (isNaN(delQty) || delQty <= 0) {
      setStatusMessage({ type: 'error', text: 'Please enter a valid delivered quantity.' });
      return;
    }
    const pickedUp = Number(executionDetail.total_picked_up_quantity_quintals);
    if (Math.abs(delQty - pickedUp) > 0.001 && !deliveryVarianceReason.trim()) {
      setStatusMessage({ type: 'error', text: 'An explicit variance reason is required when delivered quantity differs from picked-up total.' });
      return;
    }

    try {
      const updated = await api.recordDeliveryComplete(executionDetail.id, {
        delivered_quantity_quintals: delQty,
        receiver_name: deliveryReceiver.trim() || undefined,
        variance_reason: deliveryVarianceReason.trim() || undefined,
        delivery_notes: deliveryNotes.trim() || undefined,
      });
      setExecutionDetail(updated);
      setIsDeliveryModalOpen(false);
      setStatusMessage({ type: 'success', text: 'Delivery confirmed & completed! Vehicle released back to fleet.' });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to complete delivery.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleOpenExceptionModal = (checkpointId?: string) => {
    setExceptionCheckpointId(checkpointId || '');
    setExceptionCode('LOADING_DELAY');
    setExceptionNotes('');
    setIsExceptionModalOpen(true);
  };

  const handleSubmitException = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!executionDetail || !exceptionNotes.trim()) return;
    try {
      const updated = await api.reportShipmentException(executionDetail.id, {
        checkpoint_id: exceptionCheckpointId || undefined,
        exception_code: exceptionCode,
        notes: exceptionNotes.trim(),
      });
      setExecutionDetail(updated);
      setIsExceptionModalOpen(false);
      setStatusMessage({ type: 'success', text: 'Operational exception logged in audit timeline.' });
      void loadDashboardData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to report exception.';
      setStatusMessage({ type: 'error', text: msg });
    }
  };

  const handleAddVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.registerTransporterVehicle({
        registration_number: newRegNumber || undefined,
        vehicle_type: newVehicleType,
        model_name: newModelName || undefined,
        payload_capacity_kg: parseFloat(newPayloadKg),
        is_refrigerated: newIsRefrigerated,
        is_available: true,
        operational_status: 'available',
      });
      setStatusMessage({ type: 'success', text: 'New freight vehicle registered in fleet.' });
      setIsAddVehicleModalOpen(false);
      setNewRegNumber('');
      setNewModelName('');
      void loadDashboardData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to register vehicle.' });
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const districts = editDistricts
        .split(',')
        .map((d) => d.trim())
        .filter(Boolean);
      await api.updateTransporterProfile({
        organization_name: editOrgName,
        contact_phone: editPhone,
        contact_email: editEmail,
        service_area_districts: districts,
      });
      setStatusMessage({ type: 'success', text: 'Transporter profile & service corridors updated.' });
      void loadDashboardData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to update transporter profile.' });
    }
  };

  return (
    <div className="landing-page" style={{ minHeight: '100vh', padding: '1.5rem 1rem 4rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {/* Header Bar */}
        <div
          className="glass-panel"
          style={{
            padding: '1.5rem 2rem',
            borderRadius: '1.5rem',
            marginBottom: '1.5rem',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '1rem',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
              <span style={{ fontSize: '1.75rem' }}>🚚</span>
              <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: '#1b4332' }}>
                {summary?.profile.organization_name || user?.display_name || 'Transporter Operations Hub'}
              </h1>
              <span
                className="clay-badge"
                style={{
                  background: summary?.profile.verification_status === 'verified' ? '#d8f3dc' : '#fff3cd',
                  color: summary?.profile.verification_status === 'verified' ? '#1b4332' : '#856404',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  padding: '0.2rem 0.6rem',
                  borderRadius: '999px',
                }}
              >
                {summary?.profile.verification_status === 'verified' ? '✓ Verified Transporter' : '⏳ Verification Pending'}
              </span>
            </div>
            <p style={{ margin: 0, color: '#40916c', fontSize: '0.9rem' }}>
              Two-sided rural freight aggregation, multi-stop pickup routing & transactional dispatch
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={() => setIsAddVehicleModalOpen(true)}
              className="clay-button-primary"
              style={{
                background: 'linear-gradient(135deg, #2d6a4f, #1b4332)',
                color: 'white',
                border: 'none',
                padding: '0.6rem 1.2rem',
                borderRadius: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              + Register Vehicle
            </button>
            <button
              onClick={() => void loadDashboardData()}
              style={{
                background: 'rgba(255, 255, 255, 0.8)',
                border: '1px solid #b7e4c7',
                padding: '0.6rem 1rem',
                borderRadius: '0.75rem',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              🔄 Refresh
            </button>
          </div>
        </div>

        {/* Status Alerts */}
        {statusMessage && (
          <div
            style={{
              padding: '0.85rem 1.25rem',
              borderRadius: '0.75rem',
              marginBottom: '1.25rem',
              backgroundColor: statusMessage.type === 'success' ? '#d8f3dc' : '#f8d7da',
              color: statusMessage.type === 'success' ? '#1b4332' : '#721c24',
              border: `1px solid ${statusMessage.type === 'success' ? '#b7e4c7' : '#f5c6cb'}`,
              fontWeight: 600,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>{statusMessage.text}</span>
            <button
              onClick={() => setStatusMessage(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700 }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Operational KPI Cards */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem',
            marginBottom: '1.5rem',
          }}
        >
          <div className="glass-card" style={{ padding: '1.25rem', borderRadius: '1rem', background: 'rgba(255, 255, 255, 0.85)' }}>
            <div style={{ fontSize: '0.8rem', color: '#52796f', fontWeight: 700, textTransform: 'uppercase' }}>
              Available Fleet
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#1b4332', marginTop: '0.25rem' }}>
              {summary?.available_vehicles_count ?? 0}{' '}
              <span style={{ fontSize: '0.9rem', color: '#74c69d', fontWeight: 600 }}>/ {summary?.total_vehicles_count ?? 0} Total</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#74c69d', marginTop: '0.2rem' }}>Verified operational trucks</div>
          </div>

          <div className="glass-card" style={{ padding: '1.25rem', borderRadius: '1rem', background: 'rgba(255, 255, 255, 0.85)' }}>
            <div style={{ fontSize: '0.8rem', color: '#52796f', fontWeight: 700, textTransform: 'uppercase' }}>
              Open Opportunities
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#2d6a4f', marginTop: '0.25rem' }}>
              {opportunities.filter((o) => o.status === 'open' || o.status === 'offered').length}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#74c69d', marginTop: '0.2rem' }}>Matched to fleet capacity</div>
          </div>

          <div className="glass-card" style={{ padding: '1.25rem', borderRadius: '1rem', background: 'rgba(255, 255, 255, 0.85)' }}>
            <div style={{ fontSize: '0.8rem', color: '#52796f', fontWeight: 700, textTransform: 'uppercase' }}>
              Active Scheduled Jobs
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#1b4332', marginTop: '0.25rem' }}>
              {shipments.length}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#74c69d', marginTop: '0.2rem' }}>In transit or scheduled</div>
          </div>

          <div className="glass-card" style={{ padding: '1.25rem', borderRadius: '1rem', background: 'rgba(255, 255, 255, 0.85)' }}>
            <div style={{ fontSize: '0.8rem', color: '#52796f', fontWeight: 700, textTransform: 'uppercase' }}>
              Service Corridor
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 700, color: '#1b4332', marginTop: '0.5rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {(summary?.profile.service_area_districts || ['Maharashtra Region']).slice(0, 3).join(', ')}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#74c69d', marginTop: '0.2rem' }}>Configured districts</div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            gap: '0.5rem',
            marginBottom: '1.5rem',
            borderBottom: '2px solid rgba(45, 106, 79, 0.15)',
            paddingBottom: '0.5rem',
          }}
        >
          <button
            onClick={() => setActiveTab('opportunities')}
            style={{
              padding: '0.6rem 1.25rem',
              borderRadius: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
              border: 'none',
              background: activeTab === 'opportunities' ? '#1b4332' : 'rgba(255, 255, 255, 0.6)',
              color: activeTab === 'opportunities' ? 'white' : '#2d6a4f',
            }}
          >
            📋 Transport Opportunities ({opportunities.length})
          </button>
          <button
            onClick={() => setActiveTab('shipments')}
            style={{
              padding: '0.6rem 1.25rem',
              borderRadius: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
              border: 'none',
              background: activeTab === 'shipments' ? '#1b4332' : 'rgba(255, 255, 255, 0.6)',
              color: activeTab === 'shipments' ? 'white' : '#2d6a4f',
            }}
          >
            🚛 Active Scheduled Jobs ({shipments.length})
          </button>
          <button
            onClick={() => setActiveTab('fleet')}
            style={{
              padding: '0.6rem 1.25rem',
              borderRadius: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
              border: 'none',
              background: activeTab === 'fleet' ? '#1b4332' : 'rgba(255, 255, 255, 0.6)',
              color: activeTab === 'fleet' ? 'white' : '#2d6a4f',
            }}
          >
            🚚 My Fleet ({vehicles.length})
          </button>
          <button
            onClick={() => setActiveTab('profile')}
            style={{
              padding: '0.6rem 1.25rem',
              borderRadius: '0.75rem',
              fontWeight: 700,
              cursor: 'pointer',
              border: 'none',
              background: activeTab === 'profile' ? '#1b4332' : 'rgba(255, 255, 255, 0.6)',
              color: activeTab === 'profile' ? 'white' : '#2d6a4f',
            }}
          >
            ⚙️ Service Profile
          </button>
        </div>

        {/* Tab 1: Opportunities Feed */}
        {activeTab === 'opportunities' && (
          <div>
            {isLoading ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: '#52796f' }}>Loading opportunities...</div>
            ) : opportunities.length === 0 ? (
              <div
                className="glass-panel"
                style={{ padding: '3rem', textAlign: 'center', borderRadius: '1rem', color: '#52796f' }}
              >
                <span style={{ fontSize: '2.5rem' }}>🌱</span>
                <h3 style={{ color: '#1b4332', marginTop: '0.5rem' }}>No open transport opportunities right now</h3>
                <p style={{ maxWidth: '500px', margin: '0 auto', fontSize: '0.9rem' }}>
                  When buyers aggregate harvest orders that match your fleet capacity and service districts, they will appear here.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {opportunities.map((opp) => {
                  const isOpen = opp.status === 'open' || opp.status === 'offered';
                  const isAccepted = opp.status === 'accepted';
                  return (
                    <div
                      key={opp.id}
                      className="glass-card"
                      style={{
                        padding: '1.5rem',
                        borderRadius: '1.25rem',
                        background: 'rgba(255, 255, 255, 0.9)',
                        borderLeft: `6px solid ${isAccepted ? '#2d6a4f' : isOpen ? '#52b788' : '#adb5bd'}`,
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          flexWrap: 'wrap',
                          gap: '0.75rem',
                          marginBottom: '0.75rem',
                        }}
                      >
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: 800, fontSize: '1.15rem', color: '#1b4332' }}>
                              📍 {opp.origin_district} ➔ {opp.destination_district}
                            </span>
                            <span
                              style={{
                                padding: '0.2rem 0.5rem',
                                borderRadius: '0.5rem',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                background: isAccepted ? '#d8f3dc' : isOpen ? '#e8f5e9' : '#f8f9fa',
                                color: isAccepted ? '#1b4332' : isOpen ? '#2d6a4f' : '#6c757d',
                              }}
                            >
                              {opp.status.toUpperCase()}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.85rem', color: '#52796f', marginTop: '0.25rem' }}>
                            {opp.pickup_stops_count} Pickup Stop(s) • Earliest Pickup:{' '}
                            <strong>{opp.earliest_pickup_date}</strong>
                          </div>
                        </div>

                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#1b4332' }}>
                            ₹{opp.estimated_cost.toLocaleString()}
                          </div>
                          <span
                            style={{
                              fontSize: '0.7rem',
                              padding: '0.15rem 0.4rem',
                              borderRadius: '0.3rem',
                              background: '#e9ecef',
                              color: '#495057',
                              fontWeight: 600,
                            }}
                          >
                            MODELED FREIGHT ESTIMATE
                          </span>
                        </div>
                      </div>

                      {/* Cargo details badges */}
                      <div
                        style={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: '0.5rem',
                          margin: '0.75rem 0 1rem',
                          padding: '0.75rem',
                          background: '#f8faf9',
                          borderRadius: '0.75rem',
                        }}
                      >
                        <div style={{ fontSize: '0.85rem', color: '#2d6a4f' }}>
                          📦 Required Payload: <strong>{opp.required_payload_quintals} qtl ({opp.required_payload_tonnes} MT)</strong>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: '#2d6a4f' }}>
                          🚚 Recommended: <strong>{opp.required_vehicle_class}</strong>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: '#2d6a4f' }}>
                          🛣️ Modeled Distance: <strong>{opp.total_distance_km} km</strong>
                        </div>
                        {opp.requires_cold_chain && (
                          <div style={{ fontSize: '0.85rem', color: '#0077b6', fontWeight: 700 }}>
                            ❄️ Refrigeration Required
                          </div>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                        <button
                          onClick={() => void handleOpenDetail(opp.id)}
                          style={{
                            padding: '0.5rem 1rem',
                            borderRadius: '0.6rem',
                            border: '1px solid #74c69d',
                            background: 'white',
                            color: '#1b4332',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          🗺️ View Route & Waypoints
                        </button>

                        {isOpen && (
                          <>
                            <button
                              onClick={() => void handleOpenAccept(opp.id)}
                              className="clay-button-primary"
                              style={{
                                padding: '0.5rem 1.25rem',
                                borderRadius: '0.6rem',
                                border: 'none',
                                background: 'linear-gradient(135deg, #2d6a4f, #1b4332)',
                                color: 'white',
                                fontWeight: 700,
                                cursor: 'pointer',
                              }}
                            >
                              ✓ Accept Job
                            </button>
                            <button
                              onClick={() => void handleOpenQuote(opp.id)}
                              style={{
                                padding: '0.5rem 1rem',
                                borderRadius: '0.6rem',
                                border: '1px solid #2d6a4f',
                                background: 'rgba(45, 106, 79, 0.05)',
                                color: '#1b4332',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              💬 Submit Quote / Bid
                            </button>
                            <button
                              onClick={() => void handleDecline(opp.id)}
                              style={{
                                padding: '0.5rem 0.9rem',
                                borderRadius: '0.6rem',
                                border: '1px solid #dee2e6',
                                background: 'white',
                                color: '#888',
                                cursor: 'pointer',
                              }}
                            >
                              Decline
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Shipments List */}
        {activeTab === 'shipments' && (
          <div>
            {shipments.length === 0 ? (
              <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', borderRadius: '1rem' }}>
                <span style={{ fontSize: '2.5rem' }}>🚚</span>
                <h3 style={{ color: '#1b4332' }}>No active shipments assigned</h3>
                <p style={{ color: '#52796f', fontSize: '0.9rem' }}>
                  When you accept an opportunity, it will become an active scheduled shipment.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {shipments.map((s, idx) => {
                  const shipmentId = String(s.id);
                  const statusStr = String(s.status).toUpperCase();
                  const isDelivered = statusStr === 'DELIVERED';
                  const isInTransit = statusStr === 'IN_TRANSIT';
                  const isInPickup = statusStr === 'IN_PICKUP';
                  const isAtDest = statusStr === 'AT_DESTINATION';

                  let statusBg = '#e2e8f0';
                  let statusColor = '#475569';
                  if (isDelivered) {
                    statusBg = '#d8f3dc';
                    statusColor = '#1b4332';
                  } else if (isInTransit) {
                    statusBg = '#e0e7ff';
                    statusColor = '#3730a3';
                  } else if (isInPickup) {
                    statusBg = '#fef3c7';
                    statusColor = '#92400e';
                  } else if (isAtDest) {
                    statusBg = '#ede9fe';
                    statusColor = '#5b21b6';
                  }

                  return (
                    <div
                      key={shipmentId || idx}
                      className="glass-card"
                      style={{ padding: '1.25rem', borderRadius: '1rem', background: 'rgba(255, 255, 255, 0.9)' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                        <div style={{ fontWeight: 800, fontSize: '1.1rem', color: '#1b4332' }}>
                          📦 Shipment Plan: {String(s.plan_code || s.id)}
                        </div>
                        <span
                          style={{
                            background: statusBg,
                            color: statusColor,
                            fontWeight: 700,
                            padding: '0.25rem 0.75rem',
                            borderRadius: '0.5rem',
                            fontSize: '0.8rem',
                          }}
                        >
                          {statusStr.replace(/_/g, ' ')}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', fontSize: '0.85rem', color: '#52796f', marginBottom: '1rem' }}>
                        <div>Origin: <strong>{String(s.origin_location_name || 'Farm Gate')}</strong></div>
                        <div>Destination: <strong>{String(s.destination_location_name || 'Buyer Hub')}</strong></div>
                        <div>Assigned Vehicle: <strong>{String(s.vehicle_registration || s.vehicle_model || 'Fleet Truck')}</strong></div>
                        <div>Driver: <strong>{String(s.driver_name || 'Unassigned')} ({String(s.driver_phone || 'N/A')})</strong></div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                        <button
                          onClick={() => void handleOpenExecutionTracker(shipmentId)}
                          disabled={isLoadingExecution}
                          className="clay-button-primary"
                          style={{
                            padding: '0.55rem 1.25rem',
                            borderRadius: '0.6rem',
                            border: 'none',
                            background: '#2d6a4f',
                            color: 'white',
                            fontWeight: 700,
                            fontSize: '0.85rem',
                            cursor: isLoadingExecution ? 'wait' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                          }}
                        >
                          <span>📍</span> {isLoadingExecution ? 'Loading Tracking...' : 'Live Execution & Checkpoints Tracker'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Fleet Management */}
        {activeTab === 'fleet' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, color: '#1b4332' }}>Registered Freight Fleet</h3>
              <button
                onClick={() => setIsAddVehicleModalOpen(true)}
                className="clay-button-primary"
                style={{
                  background: '#2d6a4f',
                  color: 'white',
                  border: 'none',
                  padding: '0.5rem 1rem',
                  borderRadius: '0.6rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                + Add Truck
              </button>
            </div>

            {vehicles.length === 0 ? (
              <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center', borderRadius: '1rem' }}>
                <span style={{ fontSize: '2.5rem' }}>🚚</span>
                <h3 style={{ color: '#1b4332' }}>No vehicles registered</h3>
                <p style={{ color: '#52796f' }}>Register your trucks to start receiving tailored transport opportunities.</p>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
                {vehicles.map((v) => (
                  <div
                    key={v.id}
                    className="glass-card"
                    style={{ padding: '1.25rem', borderRadius: '1rem', background: 'rgba(255, 255, 255, 0.9)' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <div style={{ fontWeight: 800, color: '#1b4332', fontSize: '1.05rem' }}>
                        {v.registration_number || v.model_name || 'Registered Freight Truck'}
                      </div>
                      <span
                        style={{
                          background: v.is_available ? '#d8f3dc' : '#f8d7da',
                          color: v.is_available ? '#1b4332' : '#721c24',
                          fontWeight: 700,
                          fontSize: '0.75rem',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '0.4rem',
                        }}
                      >
                        {v.is_available ? 'AVAILABLE' : 'BUSY / IN TRANSIT'}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: '#52796f', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <div>Type: <strong>{v.vehicle_type.replace('_', ' ').toUpperCase()}</strong></div>
                      <div>Payload Capacity: <strong>{v.payload_capacity_quintals} qtl ({v.payload_capacity_tonnes} MT)</strong></div>
                      <div>Refrigerated: <strong>{v.is_refrigerated ? 'Yes (Cold-Chain Capable)' : 'No (Ambient)'}</strong></div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Service Profile */}
        {activeTab === 'profile' && (
          <div className="glass-card" style={{ padding: '2rem', borderRadius: '1.25rem', background: 'rgba(255, 255, 255, 0.9)' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#1b4332' }}>Operating Corridors & Contact Info</h3>
            <form onSubmit={handleSaveProfile} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Business / Organization Name
                </label>
                <input
                  type="text"
                  value={editOrgName}
                  onChange={(e) => setEditOrgName(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    value={editPhone}
                    onChange={(e) => setEditPhone(e.target.value)}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                    Contact Email
                  </label>
                  <input
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Operating Districts / Corridors (comma separated)
                </label>
                <input
                  type="text"
                  value={editDistricts}
                  onChange={(e) => setEditDistricts(e.target.value)}
                  placeholder="e.g. Pune, Nashik, Ahmednagar, Satara, Solapur"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <button
                type="submit"
                className="clay-button-primary"
                style={{
                  alignSelf: 'flex-start',
                  background: '#2d6a4f',
                  color: 'white',
                  border: 'none',
                  padding: '0.6rem 1.5rem',
                  borderRadius: '0.6rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  marginTop: '0.5rem',
                }}
              >
                Save Profile
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Modal: View Route Details & Map */}
      {isDetailModalOpen && selectedOppDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            className="glass-panel"
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '900px',
              width: '100%',
              maxHeight: '92vh',
              overflowY: 'auto',
              padding: '1.75rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                  <h3 style={{ margin: 0, color: '#1b4332', fontSize: '1.35rem' }}>
                    📦 Transport Opportunity: {selectedOppDetail.commodity_name || 'Consolidated Agri Cargo'}
                  </h3>
                  <span
                    style={{
                      padding: '0.2rem 0.6rem',
                      borderRadius: '0.4rem',
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      textTransform: 'uppercase',
                      background:
                        selectedOppDetail.status === 'open'
                          ? '#dcfce7'
                          : selectedOppDetail.status === 'accepted'
                          ? '#dbeafe'
                          : selectedOppDetail.status === 'declined'
                          ? '#fee2e2'
                          : selectedOppDetail.status === 'withdrawn'
                          ? '#fef3c7'
                          : '#f1f5f9',
                      color:
                        selectedOppDetail.status === 'open'
                          ? '#15803d'
                          : selectedOppDetail.status === 'accepted'
                          ? '#1d4ed8'
                          : selectedOppDetail.status === 'declined'
                          ? '#b91c1c'
                          : selectedOppDetail.status === 'withdrawn'
                          ? '#b45309'
                          : '#64748b',
                    }}
                  >
                    {selectedOppDetail.status}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#64748b', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                  <span><strong>Opp ID:</strong> {selectedOppDetail.id.slice(0, 8)}...</span>
                  {selectedOppDetail.plan_code && <span><strong>Plan:</strong> {selectedOppDetail.plan_code}</span>}
                  {selectedOppDetail.buyer_organization_name && (
                    <span><strong>Buyer:</strong> {selectedOppDetail.buyer_organization_name}</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => setIsDetailModalOpen(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.35rem', cursor: 'pointer', color: '#64748b' }}
              >
                ✕
              </button>
            </div>

            {/* Status Notices */}
            {selectedOppDetail.status === 'accepted' && (
              <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af', padding: '0.75rem 1rem', borderRadius: '0.6rem', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
                ✅ <strong>Accepted:</strong> You have accepted this transport assignment. View active status and checkpoints in your Active Jobs tab.
              </div>
            )}
            {selectedOppDetail.status === 'declined' && (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', padding: '0.75rem 1rem', borderRadius: '0.6rem', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
                ⚠️ <strong>Declined:</strong> You declined this transport opportunity. {selectedOppDetail.decline_reason ? `Reason: ${selectedOppDetail.decline_reason}` : ''}
              </div>
            )}
            {selectedOppDetail.status === 'withdrawn' && (
              <div style={{ background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', padding: '0.75rem 1rem', borderRadius: '0.6rem', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
                🔒 <strong>Unavailable:</strong> This opportunity has been withdrawn or claimed by another logistics provider.
              </div>
            )}
            {selectedOppDetail.status === 'expired' && (
              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', color: '#64748b', padding: '0.75rem 1rem', borderRadius: '0.6rem', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
                ⏱️ <strong>Expired:</strong> This opportunity deadline has passed.
              </div>
            )}

            {/* Key Logistics Parameter Badges */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '0.75rem',
                marginBottom: '1.25rem',
                padding: '1rem',
                background: '#f8fafc',
                borderRadius: '0.75rem',
                border: '1px solid #e2e8f0',
              }}
            >
              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Total Cargo</div>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: '#1e293b' }}>
                  {selectedOppDetail.required_payload_quintals} QTL
                  <span style={{ fontSize: '0.8rem', fontWeight: 500, color: '#64748b', marginLeft: '0.3rem' }}>
                    ({selectedOppDetail.required_payload_tonnes || (Number(selectedOppDetail.required_payload_quintals) / 10).toFixed(2)} T)
                  </span>
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Vehicle Required</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 800, color: '#1e293b' }}>
                  {selectedOppDetail.required_vehicle_class.toUpperCase().replace('_', ' ')}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  Min payload: {(Number(selectedOppDetail.required_payload_quintals) * 100).toLocaleString()} kg
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Cold Chain</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 800, color: selectedOppDetail.requires_cold_chain ? '#0369a1' : '#15803d' }}>
                  {selectedOppDetail.requires_cold_chain ? '❄️ Reefer Required' : '🌾 Ambient / Standard'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Freight Estimate</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#15803d' }}>
                  ₹{Number(selectedOppDetail.estimated_cost).toLocaleString('en-IN')}
                </div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: selectedOppDetail.cost_certainty === 'VERIFIED_TRANSPORTER_RATE' ? '#15803d' : '#b45309' }}>
                  {selectedOppDetail.cost_certainty === 'VERIFIED_TRANSPORTER_RATE' ? '🟢 VERIFIED RATE CARD' : '🟡 MODELED ESTIMATE'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Corridor & Distance</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e293b' }}>
                  {selectedOppDetail.origin_district} ➔ {selectedOppDetail.destination_district}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {selectedOppDetail.total_distance_km} km ({selectedOppDetail.distance_certainty || 'Modeled'})
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 700 }}>Pickup Schedule</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e293b' }}>
                  {selectedOppDetail.earliest_pickup_date}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  Deadline: {selectedOppDetail.delivery_deadline || 'Within 48h'}
                </div>
              </div>
            </div>

            {/* Embedded Leaflet OSM Map */}
            <div style={{ marginBottom: '1.25rem', borderRadius: '0.75rem', overflow: 'hidden', border: '1px solid #e2e8f0' }}>
              <ShipmentRouteMap
                waypoints={selectedOppDetail.waypoints || []}
                totalDistanceKm={selectedOppDetail.total_distance_km}
                distanceCertainty={selectedOppDetail.distance_certainty}
                height={340}
              />
            </div>

            {/* Waypoint list */}
            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ margin: '0 0 0.6rem 0', color: '#2d6a4f', fontSize: '0.95rem' }}>
                Consolidated Route Stops ({selectedOppDetail.pickup_stops_count} Pickups + 1 Destination):
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {(selectedOppDetail.waypoints || []).map((wp) => (
                  <div
                    key={wp.waypoint_sequence}
                    style={{
                      padding: '0.65rem 0.9rem',
                      background: wp.waypoint_type === 'destination' ? '#d8f3dc' : '#f8f9fa',
                      border: wp.waypoint_type === 'destination' ? '1px solid #b7e4c7' : '1px solid #e2e8f0',
                      borderRadius: '0.5rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.85rem',
                    }}
                  >
                    <span>
                      <strong>Stop {wp.waypoint_sequence} ({wp.waypoint_type === 'destination' ? '🏁 Terminal' : '🌾 Farm Pickup'}):</strong>{' '}
                      {wp.location_name} ({wp.district || 'Maharashtra'})
                    </span>
                    <span style={{ fontWeight: 700, color: wp.waypoint_type === 'destination' ? '#1b4332' : '#2d6a4f' }}>
                      {wp.waypoint_type === 'pickup' ? `+${wp.stop_cargo_quantity_quintals} QTL` : '🏁 Final Buyer Destination'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Bar */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', flexWrap: 'wrap', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
              <button
                onClick={() => setIsDetailModalOpen(false)}
                style={{ padding: '0.55rem 1.1rem', borderRadius: '0.5rem', border: '1px solid #cbd5e1', background: '#f8fafc', color: '#475569', fontWeight: 600, cursor: 'pointer' }}
              >
                Close
              </button>

              {selectedOppDetail.status === 'open' && (
                <>
                  <button
                    onClick={() => {
                      setIsDetailModalOpen(false);
                      void handleDecline(selectedOppDetail.id);
                    }}
                    style={{
                      padding: '0.55rem 1.1rem',
                      borderRadius: '0.5rem',
                      border: '1px solid #fca5a5',
                      background: '#fff1f2',
                      color: '#b91c1c',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    ✕ Decline
                  </button>

                  <button
                    onClick={() => {
                      setIsDetailModalOpen(false);
                      void handleOpenQuote(selectedOppDetail.id);
                    }}
                    style={{
                      padding: '0.55rem 1.1rem',
                      borderRadius: '0.5rem',
                      border: '1px solid #cbd5e1',
                      background: '#ffffff',
                      color: '#1e293b',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    💬 Submit Quote / Bid
                  </button>

                  <button
                    onClick={() => {
                      setIsDetailModalOpen(false);
                      void handleOpenAccept(selectedOppDetail.id);
                    }}
                    className="clay-button-primary"
                    style={{
                      padding: '0.55rem 1.3rem',
                      borderRadius: '0.5rem',
                      border: 'none',
                      background: '#2d6a4f',
                      color: 'white',
                      fontWeight: 700,
                      cursor: 'pointer',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                    }}
                  >
                    🚚 Accept Job & Assign Vehicle
                  </button>
                </>
              )}

              {selectedOppDetail.status === 'accepted' && (
                <button
                  onClick={() => {
                    setIsDetailModalOpen(false);
                    setActiveTab('shipments');
                    if (selectedOppDetail.shipment_id) {
                      void handleOpenExecutionTracker(selectedOppDetail.shipment_id);
                    }
                  }}
                  className="clay-button-primary"
                  style={{
                    padding: '0.55rem 1.3rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#1d4ed8',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  📦 View Shipment in Active Jobs
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal: Accept Job & Assign Vehicle */}
      {isAcceptModalOpen && selectedOppDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '520px',
              width: '100%',
              padding: '1.5rem',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#1b4332' }}>Confirm Transport Job Acceptance</h3>
            <p style={{ fontSize: '0.85rem', color: '#52796f', margin: '0 0 1rem 0' }}>
              Plan Code: <strong>{selectedOppDetail.plan_code || selectedOppDetail.id}</strong> • Cargo: <strong>{selectedOppDetail.required_payload_quintals} qtl</strong>
            </p>

            <form onSubmit={handleConfirmAccept} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Select Vehicle from Fleet *
                </label>
                <select
                  value={acceptVehicleId}
                  onChange={(e) => setAcceptVehicleId(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required
                >
                  <option value="">-- Select Available Vehicle --</option>
                  {(selectedOppDetail.vehicle_options || vehicles)
                    .filter((v) => v.is_available)
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.registration_number || v.model_name} ({v.payload_capacity_quintals} qtl payload)
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Driver Name (Optional)
                </label>
                <input
                  type="text"
                  value={acceptDriverName}
                  onChange={(e) => setAcceptDriverName(e.target.value)}
                  placeholder="e.g. Ramesh Kulkarni"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Driver Contact Phone (Optional)
                </label>
                <input
                  type="text"
                  value={acceptDriverPhone}
                  onChange={(e) => setAcceptDriverPhone(e.target.value)}
                  placeholder="+919876543210"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Dispatch Notes
                </label>
                <textarea
                  value={acceptNotes}
                  onChange={(e) => setAcceptNotes(e.target.value)}
                  placeholder="Arrival time, special handling details..."
                  rows={2}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsAcceptModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #ccc', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="clay-button-primary"
                  style={{
                    padding: '0.5rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#2d6a4f',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Confirm & Lock Assignment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Submit Commercial Quote */}
      {isQuoteModalOpen && selectedOppDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '480px',
              width: '100%',
              padding: '1.5rem',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#1b4332' }}>Submit Freight Bid / Quote</h3>
            <p style={{ fontSize: '0.85rem', color: '#52796f', margin: '0 0 1rem 0' }}>
              Modeled regional estimate is <strong>₹{selectedOppDetail.estimated_cost.toLocaleString()}</strong>. You can offer custom terms.
            </p>

            <form onSubmit={handleSubmitQuote} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Total Quoted Amount (₹ INR) *
                </label>
                <input
                  type="number"
                  value={quoteAmount}
                  onChange={(e) => setQuoteAmount(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Vehicle (Optional)
                </label>
                <select
                  value={quoteVehicleId}
                  onChange={(e) => setQuoteVehicleId(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                >
                  <option value="">-- Any Suitable Fleet Truck --</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.registration_number || v.model_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Bid Terms / Notes
                </label>
                <textarea
                  value={quoteNotes}
                  onChange={(e) => setQuoteNotes(e.target.value)}
                  placeholder="Includes driver loading assistance, flexible timing..."
                  rows={2}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsQuoteModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #ccc', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="clay-button-primary"
                  style={{
                    padding: '0.5rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#2d6a4f',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Submit Quote
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Register Vehicle */}
      {isAddVehicleModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '480px',
              width: '100%',
              padding: '1.5rem',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#1b4332' }}>Register Commercial Vehicle</h3>
            <p style={{ fontSize: '0.85rem', color: '#52796f', margin: '0 0 1rem 0' }}>
              Add a commercial truck or pickup to receive relevant harvest transport jobs.
            </p>

            <form onSubmit={handleAddVehicle} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Registration Number
                </label>
                <input
                  type="text"
                  value={newRegNumber}
                  onChange={(e) => setNewRegNumber(e.target.value.toUpperCase())}
                  placeholder="e.g. MH-12-AB-1234"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                    Vehicle Type
                  </label>
                  <select
                    value={newVehicleType}
                    onChange={(e) => setNewVehicleType(e.target.value)}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  >
                    <option value="mini_truck">Mini Truck (1.5 MT)</option>
                    <option value="pickup">Pickup (3 MT)</option>
                    <option value="medium_commercial">Medium Commercial (8 MT)</option>
                    <option value="heavy_truck">Heavy Commercial / Truck (16 MT)</option>
                    <option value="reefer_van">Refrigerated Reefer Van</option>
                    <option value="container">Freight Container</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                    Payload Capacity (kg) *
                  </label>
                  <input
                    type="number"
                    value={newPayloadKg}
                    onChange={(e) => setNewPayloadKg(e.target.value)}
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                    required
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Model / Make Name
                </label>
                <input
                  type="text"
                  value={newModelName}
                  onChange={(e) => setNewModelName(e.target.value)}
                  placeholder="e.g. Tata 407 Gold / Eicher Pro"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <input
                  type="checkbox"
                  id="refrig"
                  checked={newIsRefrigerated}
                  onChange={(e) => setNewIsRefrigerated(e.target.checked)}
                />
                <label htmlFor="refrig" style={{ fontSize: '0.85rem', fontWeight: 600, color: '#2d6a4f' }}>
                  Refrigerated / Insulated (Cold-Chain Capable)
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsAddVehicleModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #ccc', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="clay-button-primary"
                  style={{
                    padding: '0.5rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#2d6a4f',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Register Vehicle
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* PHASE 2H: MODAL - LIVE EXECUTION & CHECKPOINT TRACKER   */}
      {/* ========================================================= */}
      {isExecutionTrackerOpen && executionDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '860px',
              width: '100%',
              maxHeight: '92vh',
              overflowY: 'auto',
              padding: '1.75rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #e2e8f0', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span style={{ fontSize: '1.25rem', fontWeight: 800, color: '#1b4332' }}>
                    🚚 Shipment Execution: {executionDetail.plan_code || executionDetail.id}
                  </span>
                  <span
                    style={{
                      background: executionDetail.status === 'delivered' ? '#d8f3dc' : '#e0e7ff',
                      color: executionDetail.status === 'delivered' ? '#1b4332' : '#3730a3',
                      fontWeight: 700,
                      fontSize: '0.75rem',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '0.4rem',
                      textTransform: 'uppercase',
                    }}
                  >
                    {executionDetail.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <div style={{ fontSize: '0.85rem', color: '#52796f' }}>
                  Commodity: <strong>{executionDetail.commodity_name || 'Produce'}</strong> • Vehicle: <strong>{executionDetail.vehicle_reg_number || executionDetail.vehicle_model || 'Fleet Vehicle'}</strong> • Driver: <strong>{executionDetail.driver_name || 'Assigned Driver'} ({executionDetail.driver_phone || 'N/A'})</strong>
                </div>
              </div>
              <button
                onClick={() => setIsExecutionTrackerOpen(false)}
                style={{
                  background: '#f1f5f9',
                  border: 'none',
                  borderRadius: '50%',
                  width: '32px',
                  height: '32px',
                  cursor: 'pointer',
                  fontWeight: 700,
                  color: '#64748b',
                }}
              >
                ✕
              </button>
            </div>

            {/* Cargo Progress & Volume Metrics */}
            <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                <span style={{ fontWeight: 700, color: '#1e293b' }}>
                  Cargo Reconciliation: {executionDetail.total_picked_up_quantity_quintals} QTL Picked Up / {executionDetail.total_planned_quantity_quintals} QTL Planned
                </span>
                <span style={{ fontWeight: 800, color: '#2d6a4f' }}>
                  {executionDetail.progress_percentage}% Completed
                </span>
              </div>
              <div style={{ width: '100%', height: '10px', background: '#e2e8f0', borderRadius: '5px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${Math.min(100, Math.max(0, executionDetail.progress_percentage))}%`,
                    height: '100%',
                    background: executionDetail.status === 'delivered' ? '#1b4332' : 'linear-gradient(90deg, #2d6a4f, #52b788)',
                    transition: 'width 0.4s ease',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
                <span>Milestone {executionDetail.completed_checkpoints_count} of {executionDetail.total_checkpoints_count} completed</span>
                <span>Active Stop Sequence: #{executionDetail.current_checkpoint_sequence}</span>
              </div>
            </div>

            {/* Sequential Checkpoints Stepper */}
            <div style={{ marginBottom: '1.5rem' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', color: '#1b4332', fontSize: '0.95rem', fontWeight: 800 }}>
                Sequential Checkpoint Execution
              </h4>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {executionDetail.checkpoints.map((cp) => {
                  const isCurrent = cp.stop_sequence === executionDetail.current_checkpoint_sequence;
                  const isCompleted = cp.status.toUpperCase() === 'COMPLETED';
                  const isLoadingStep = cp.status.toUpperCase() === 'LOADING';
                  const isArrived = cp.status.toUpperCase() === 'ARRIVED';
                  const isPending = cp.status.toUpperCase() === 'PENDING';
                  const isPickup = cp.checkpoint_type.toUpperCase() === 'PICKUP';

                  let cardBorder = '#e2e8f0';
                  let cardBg = '#ffffff';
                  if (isCompleted) {
                    cardBorder = '#b7e4c7';
                    cardBg = '#f0fdf4';
                  } else if (isCurrent) {
                    cardBorder = '#93c5fd';
                    cardBg = '#eff6ff';
                  }

                  return (
                    <div
                      key={cp.id}
                      style={{
                        border: `1.5px solid ${cardBorder}`,
                        background: cardBg,
                        borderRadius: '0.75rem',
                        padding: '1rem',
                        position: 'relative',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span
                            style={{
                              width: '26px',
                              height: '26px',
                              borderRadius: '50%',
                              background: isCompleted ? '#2d6a4f' : isCurrent ? '#2563eb' : '#94a3b8',
                              color: 'white',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 800,
                              fontSize: '0.75rem',
                            }}
                          >
                            {isCompleted ? '✓' : cp.stop_sequence}
                          </span>
                          <div>
                            <div style={{ fontWeight: 800, fontSize: '0.9rem', color: '#1e293b' }}>
                              {isPickup ? `Stop #${cp.stop_sequence}: ${cp.location_name}` : `Destination Terminal: ${cp.location_name}`}
                            </div>
                            {cp.seller_name && (
                              <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                                Seller / Farmer: <strong>{cp.seller_name}</strong>
                              </div>
                            )}
                          </div>
                        </div>

                        <div style={{ textAlign: 'right' }}>
                          <span
                            style={{
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              padding: '0.2rem 0.5rem',
                              borderRadius: '0.35rem',
                              background: isCompleted ? '#dcfce7' : isCurrent ? '#dbeafe' : '#f1f5f9',
                              color: isCompleted ? '#166534' : isCurrent ? '#1e40af' : '#475569',
                              textTransform: 'uppercase',
                            }}
                          >
                            {cp.status}
                          </span>
                          <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                            Planned: <strong>{cp.planned_quantity_quintals} QTL</strong>
                          </div>
                        </div>
                      </div>

                      {/* Completed Details */}
                      {isCompleted && (
                        <div style={{ fontSize: '0.8rem', color: '#166534', background: '#dcfce7', padding: '0.5rem', borderRadius: '0.4rem', marginTop: '0.5rem' }}>
                          <div>✓ Loaded Cargo: <strong>{cp.loaded_quantity_quintals} QTL</strong></div>
                          {cp.variance_quintals != null && cp.variance_quintals !== 0 && (
                            <div style={{ color: '#b45309', marginTop: '0.2rem' }}>
                              Variance: <strong>{cp.variance_quintals > 0 ? `+${cp.variance_quintals}` : cp.variance_quintals} QTL</strong> ({cp.variance_reason || 'Variance approved'})
                            </div>
                          )}
                          {cp.completed_at && (
                            <div style={{ fontSize: '0.7rem', color: '#52796f', marginTop: '0.2rem' }}>
                              Completed at: {new Date(cp.completed_at).toLocaleString()}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Active Action Controls */}
                      {isCurrent && executionDetail.status !== 'delivered' && isPickup && (
                        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                          {isPending && (
                            <button
                              onClick={() => void handleArriveCheckpoint(cp.id)}
                              className="clay-button-primary"
                              style={{
                                background: '#2563eb',
                                color: 'white',
                                border: 'none',
                                padding: '0.45rem 0.9rem',
                                borderRadius: '0.5rem',
                                fontWeight: 700,
                                fontSize: '0.8rem',
                                cursor: 'pointer',
                              }}
                            >
                              📍 Confirm Arrival at Farm Stop
                            </button>
                          )}

                          {isArrived && (
                            <button
                              onClick={() => void handleStartLoading(cp.id)}
                              className="clay-button-primary"
                              style={{
                                background: '#d97706',
                                color: 'white',
                                border: 'none',
                                padding: '0.45rem 0.9rem',
                                borderRadius: '0.5rem',
                                fontWeight: 700,
                                fontSize: '0.8rem',
                                cursor: 'pointer',
                              }}
                            >
                              📦 Start Produce Loading
                            </button>
                          )}

                          {isLoadingStep && (
                            <button
                              onClick={() => handleOpenCompletePickupModal(cp)}
                              className="clay-button-primary"
                              style={{
                                background: '#16a34a',
                                color: 'white',
                                border: 'none',
                                padding: '0.45rem 0.9rem',
                                borderRadius: '0.5rem',
                                fontWeight: 700,
                                fontSize: '0.8rem',
                                cursor: 'pointer',
                              }}
                            >
                              ✓ Complete Pickup & Verify Weight
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Linehaul & Delivery Progression Actions */}
            <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '0.75rem', border: '1px solid #e2e8f0', marginBottom: '1.5rem' }}>
              <h4 style={{ margin: '0 0 0.5rem 0', color: '#1b4332', fontSize: '0.9rem', fontWeight: 800 }}>
                Linehaul & Final Delivery Actions
              </h4>

              {/* Ready for Transit */}
              {executionDetail.completed_checkpoints_count >= executionDetail.total_checkpoints_count - 1 &&
                executionDetail.status !== 'in_transit' &&
                executionDetail.status !== 'at_destination' &&
                executionDetail.status !== 'delivered' && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#dbeafe', padding: '0.75rem', borderRadius: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', color: '#1e40af', fontWeight: 700 }}>
                      🚀 All {executionDetail.total_checkpoints_count - 1} farm pickups completed ({executionDetail.total_picked_up_quantity_quintals} QTL on-board). Ready for road transit.
                    </span>
                    <button
                      onClick={() => void handleStartTransit()}
                      className="clay-button-primary"
                      style={{
                        background: '#1d4ed8',
                        color: 'white',
                        border: 'none',
                        padding: '0.5rem 1rem',
                        borderRadius: '0.5rem',
                        fontWeight: 700,
                        fontSize: '0.85rem',
                        cursor: 'pointer',
                      }}
                    >
                      🚚 Depart Farm & Start Road Transit
                    </button>
                  </div>
                )}

              {/* In Transit -> Arrive at Buyer Hub */}
              {executionDetail.status === 'in_transit' && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#e0e7ff', padding: '0.75rem', borderRadius: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', color: '#3730a3', fontWeight: 700 }}>
                    🛣 Linehaul freight in transit to {executionDetail.destination_location_name || 'Buyer Mandi'}.
                  </span>
                  <button
                    onClick={() => void handleDestinationArrive()}
                    className="clay-button-primary"
                    style={{
                      background: '#4338ca',
                      color: 'white',
                      border: 'none',
                      padding: '0.5rem 1rem',
                      borderRadius: '0.5rem',
                      fontWeight: 700,
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                    }}
                  >
                    🎯 Confirm Arrival at Buyer Hub
                  </button>
                </div>
              )}

              {/* At Destination -> Confirm Delivery */}
              {executionDetail.status === 'at_destination' && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ede9fe', padding: '0.75rem', borderRadius: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', color: '#5b21b6', fontWeight: 700 }}>
                    🏢 Arrived at destination receiving terminal. Ready for weighbridge inspection and sign-off.
                  </span>
                  <button
                    onClick={handleOpenDeliveryModal}
                    className="clay-button-primary"
                    style={{
                      background: '#6d28d9',
                      color: 'white',
                      border: 'none',
                      padding: '0.5rem 1rem',
                      borderRadius: '0.5rem',
                      fontWeight: 700,
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                    }}
                  >
                    ✅ Confirm Final Delivery Sign-off
                  </button>
                </div>
              )}

              {/* Delivered Banner */}
              {executionDetail.status === 'delivered' && (
                <div style={{ background: '#dcfce7', padding: '0.75rem', borderRadius: '0.5rem', color: '#166534', fontSize: '0.85rem' }}>
                  <strong>🎉 Delivery Completed & Vehicle Released!</strong> Delivered Quantity: <strong>{executionDetail.delivered_quantity_quintals} QTL</strong>. Received by: <strong>{executionDetail.receiver_name || 'Authorized Buyer'}</strong>.
                  {executionDetail.delivery_notes && <div>Notes: {executionDetail.delivery_notes}</div>}
                </div>
              )}
            </div>

            {/* Operational Exception Reporting & Audit Timeline */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h4 style={{ margin: 0, color: '#1b4332', fontSize: '0.95rem', fontWeight: 800 }}>
                Audit Timeline Events ({executionDetail.timeline.length})
              </h4>
              <button
                onClick={() => handleOpenExceptionModal()}
                style={{
                  background: '#fee2e2',
                  color: '#991b1b',
                  border: '1px solid #fca5a5',
                  padding: '0.35rem 0.75rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🚨 Report Issue / Exception
              </button>
            </div>

            <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '0.5rem', padding: '0.75rem', background: '#ffffff' }}>
              {executionDetail.timeline.length === 0 ? (
                <div style={{ fontSize: '0.8rem', color: '#94a3b8', textAlign: 'center', padding: '1rem' }}>No events recorded yet.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {executionDetail.timeline.map((evt) => (
                    <div key={evt.id} style={{ fontSize: '0.8rem', borderBottom: '1px solid #f1f5f9', paddingBottom: '0.4rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, color: '#1e293b' }}>{evt.event_type}</span>
                        <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{new Date(evt.recorded_at).toLocaleTimeString()}</span>
                      </div>
                      <div style={{ color: '#64748b', fontSize: '0.75rem' }}>{evt.location_name && `📍 ${evt.location_name} • `}{evt.notes}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1.25rem' }}>
              <button
                type="button"
                onClick={() => setIsExecutionTrackerOpen(false)}
                style={{
                  padding: '0.5rem 1.25rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #cbd5e1',
                  background: '#f8fafc',
                  color: '#334155',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Close Tracker
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* PHASE 2H: MODAL - COMPLETE PICKUP & QUANTITY RECONCILIATION */}
      {/* ========================================================= */}
      {isPickupCompleteModalOpen && activeCheckpointForComplete && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '480px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#1b4332' }}>
              Confirm Pickup Completion (Stop #{activeCheckpointForComplete.stop_sequence})
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#52796f', margin: '0 0 1rem 0' }}>
              Location: <strong>{activeCheckpointForComplete.location_name}</strong> • Planned: <strong>{activeCheckpointForComplete.planned_quantity_quintals} QTL</strong>
            </p>

            <form onSubmit={handleSubmitCompletePickup} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Actual Loaded Quantity (QTL) *
                </label>
                <input
                  type="number"
                  step="0.001"
                  value={completeLoadedQty}
                  onChange={(e) => setCompleteLoadedQty(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required
                />
              </div>

              {/* Variance Notice */}
              {Math.abs(Number(completeLoadedQty || 0) - Number(activeCheckpointForComplete.planned_quantity_quintals)) > 0.001 && (
                <div style={{ background: '#fffbeb', border: '1px solid #fef3c7', padding: '0.75rem', borderRadius: '0.5rem', fontSize: '0.8rem', color: '#92400e' }}>
                  ⚠️ Quantity variance detected: <strong>{(Number(completeLoadedQty || 0) - Number(activeCheckpointForComplete.planned_quantity_quintals)).toFixed(3)} QTL</strong>. An explicit reason is required by mandi compliance.
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Variance Reason {Math.abs(Number(completeLoadedQty || 0) - Number(activeCheckpointForComplete.planned_quantity_quintals)) > 0.001 ? '*' : '(Optional)'}
                </label>
                <input
                  type="text"
                  value={completeVarianceReason}
                  onChange={(e) => setCompleteVarianceReason(e.target.value)}
                  placeholder="e.g. Higher moisture content, Farmer harvested extra sacks"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required={Math.abs(Number(completeLoadedQty || 0) - Number(activeCheckpointForComplete.planned_quantity_quintals)) > 0.001}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Notes / Bag Details (Optional)
                </label>
                <input
                  type="text"
                  value={completeNotes}
                  onChange={(e) => setCompleteNotes(e.target.value)}
                  placeholder="e.g. 40 bags of Grade A Produce"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsPickupCompleteModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #ccc', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="clay-button-primary"
                  style={{
                    padding: '0.5rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#16a34a',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Confirm & Complete Stop
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* PHASE 2H: MODAL - DELIVERY COMPLETE & SIGN-OFF            */}
      {/* ========================================================= */}
      {isDeliveryModalOpen && executionDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '480px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#1b4332' }}>Confirm Final Delivery & Receiver Sign-off</h3>
            <p style={{ fontSize: '0.85rem', color: '#52796f', margin: '0 0 1rem 0' }}>
              Destination: <strong>{executionDetail.destination_location_name || 'Buyer Mandi'}</strong> • Total Picked Up: <strong>{executionDetail.total_picked_up_quantity_quintals} QTL</strong>
            </p>

            <form onSubmit={handleSubmitDelivery} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Delivered / Unloaded Quantity (QTL) *
                </label>
                <input
                  type="number"
                  step="0.001"
                  value={deliveryQty}
                  onChange={(e) => setDeliveryQty(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Receiver Name / Supervisor
                </label>
                <input
                  type="text"
                  value={deliveryReceiver}
                  onChange={(e) => setDeliveryReceiver(e.target.value)}
                  placeholder="e.g. Ramesh Kadam (Warehouse Gate In-charge)"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              {/* Variance Notice */}
              {Math.abs(Number(deliveryQty || 0) - Number(executionDetail.total_picked_up_quantity_quintals)) > 0.001 && (
                <div>
                  <div style={{ background: '#fffbeb', border: '1px solid #fef3c7', padding: '0.75rem', borderRadius: '0.5rem', fontSize: '0.8rem', color: '#92400e', marginBottom: '0.5rem' }}>
                    ⚠️ Delivery variance: <strong>{(Number(deliveryQty || 0) - Number(executionDetail.total_picked_up_quantity_quintals)).toFixed(3)} QTL</strong>. Please document reasons.
                  </div>
                  <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                    Delivery Variance Reason *
                  </label>
                  <input
                    type="text"
                    value={deliveryVarianceReason}
                    onChange={(e) => setDeliveryVarianceReason(e.target.value)}
                    placeholder="e.g. Transit sorting loss, Mandi weighbridge calibration"
                    style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                    required
                  />
                </div>
              )}

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Delivery Notes / Weighbridge Slip # (Optional)
                </label>
                <input
                  type="text"
                  value={deliveryNotes}
                  onChange={(e) => setDeliveryNotes(e.target.value)}
                  placeholder="e.g. Weighbridge Slip #9928, unloaded bay 4"
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsDeliveryModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #ccc', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="clay-button-primary"
                  style={{
                    padding: '0.5rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#6d28d9',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Complete Delivery & Release Truck
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* PHASE 2H: MODAL - REPORT OPERATIONAL EXCEPTION            */}
      {/* ========================================================= */}
      {isExceptionModalOpen && executionDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1200,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '1.25rem',
              maxWidth: '480px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            }}
          >
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#991b1b' }}>🚨 Report Operational Exception / Delay</h3>
            <p style={{ fontSize: '0.85rem', color: '#52796f', margin: '0 0 1rem 0' }}>
              Log an operational exception without advancing the milestone. Notifies all counterparties.
            </p>

            <form onSubmit={handleSubmitException} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Exception Category *
                </label>
                <select
                  value={exceptionCode}
                  onChange={(e) => setExceptionCode(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                >
                  <option value="LOADING_DELAY">Loading Delay (Labor / Farm Gate)</option>
                  <option value="FARMER_UNAVAILABLE">Farmer Unavailable at Gate</option>
                  <option value="QUANTITY_MISMATCH">Quantity / Grade Mismatch</option>
                  <option value="ROAD_BLOCKED">Road Blocked / Traffic Congestion</option>
                  <option value="VEHICLE_BREAKDOWN">Vehicle Mechanical Breakdown</option>
                  <option value="BUYER_UNAVAILABLE">Buyer Receiving Dock Congestion</option>
                  <option value="WEATHER_DELAY">Adverse Weather / Rain</option>
                  <option value="OTHER">Other Operational Issue</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: '#2d6a4f', marginBottom: '0.25rem' }}>
                  Detailed Description *
                </label>
                <textarea
                  value={exceptionNotes}
                  onChange={(e) => setExceptionNotes(e.target.value)}
                  placeholder="Describe the issue, estimated delay time, and current vehicle status..."
                  rows={3}
                  style={{ width: '100%', padding: '0.6rem', borderRadius: '0.5rem', border: '1px solid #b7e4c7' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setIsExceptionModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', borderRadius: '0.5rem', border: '1px solid #ccc', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '0.5rem 1.25rem',
                    borderRadius: '0.5rem',
                    border: 'none',
                    background: '#dc2626',
                    color: 'white',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Log Exception Alert
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
