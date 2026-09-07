import React, { useEffect, useState } from 'react';
import { api, type RoutePlanResponse, type RouteOptimizationResponse, type RouteWaypoint, type ShipmentPlanSummary } from '../api/client';
import { ShipmentRouteMap } from '../components/ShipmentRouteMap';

interface LogisticsRouteViewProps {
  initialPlanId?: string;
  onNavigate?: (view: string, params?: Record<string, unknown>) => void;
}

// Structured test fixtures for verifiable browser demonstration
const TEST_SCENARIOS: {
  id: string;
  name: string;
  description: string;
  lifecycleStatus: 'planned' | 'ready_for_logistics' | 'scheduled' | 'in_transit' | 'delivered';
  routePlan: RoutePlanResponse;
  optimizedRoute?: RouteOptimizationResponse;
}[] = [
  {
    id: 'pune-consolidation',
    name: 'Pune Multi-Farmer Harvest Consolidation (Exact GPS)',
    description: '3 farmer pickup yards in Junnar/Manchar belt consolidating 40 quintals onion to Narayangaon Hub.',
    lifecycleStatus: 'ready_for_logistics',
    routePlan: {
      shipment_plan_id: 'test-plan-001',
      plan_code: 'PLAN-PUNE-2026-001',
      route_status: 'route_feasible',
      status_summary: 'Deterministic nearest-neighbor sequence across 3 pickup stops and 1 buyer destination terminal.',
      overall_geographic_precision: 'exact',
      is_optimized: false,
      routing_strategy: 'DETERMINISTIC_BASELINE_ORDERING',
      routing_provider_name: 'ModeledGeographicRoutingProvider',
      waypoints_count: 4,
      pickup_stops_count: 3,
      total_cargo_quantity_quintals: 40.0,
      total_cargo_quantity_tonnes: 4.0,
      total_modeled_distance_km: 52.4,
      distance_certainty: 'MODELED_GEOGRAPHIC_DISTANCE',
      estimated_transit_hours: 1.5,
      transit_time_certainty: 'MODELED_TRANSIT_ESTIMATE',
      assigned_vehicle_class: 'Medium Commercial Vehicle (8.0 MT)',
      vehicle_payload_capacity_quintals: 80.0,
      waypoints: [
        {
          waypoint_sequence: 1,
          waypoint_type: 'pickup',
          location_name: 'Manchar Harvest Yard',
          taluka: 'Ambegaon',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 18.995,
          longitude: 73.94,
          geographic_precision: 'exact',
          seller_name: 'Farmer Anand Patil',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 10.0,
          stop_cargo_quantity_tonnes: 1.0,
          cumulative_onboard_quantity_quintals: 10.0,
          cumulative_onboard_quantity_tonnes: 1.0,
          earliest_arrival: '2026-09-01',
          segment_distance_km: 0.0,
        },
        {
          waypoint_sequence: 2,
          waypoint_type: 'pickup',
          location_name: 'Junnar Agro Collection Gate',
          taluka: 'Junnar',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 19.2,
          longitude: 73.88,
          geographic_precision: 'exact',
          seller_name: 'Farmer Balasaheb Gaikwad',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 15.0,
          stop_cargo_quantity_tonnes: 1.5,
          cumulative_onboard_quantity_quintals: 25.0,
          cumulative_onboard_quantity_tonnes: 2.5,
          earliest_arrival: '2026-09-01',
          segment_distance_km: 26.2,
        },
        {
          waypoint_sequence: 3,
          waypoint_type: 'pickup',
          location_name: 'Alephata Farm Yard',
          taluka: 'Junnar',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 19.18,
          longitude: 74.1,
          geographic_precision: 'exact',
          seller_name: 'Farmer Chandrakant Shinde',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 15.0,
          stop_cargo_quantity_tonnes: 1.5,
          cumulative_onboard_quantity_quintals: 40.0,
          cumulative_onboard_quantity_tonnes: 4.0,
          earliest_arrival: '2026-09-01',
          segment_distance_km: 23.1,
        },
        {
          waypoint_sequence: 4,
          waypoint_type: 'destination',
          location_name: 'Apex Agro Processing Terminal',
          taluka: 'Junnar',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 18.5204,
          longitude: 73.8567,
          geographic_precision: 'exact',
          seller_name: 'Apex Agro Processing Ltd (Buyer Terminal)',
          stop_cargo_quantity_quintals: 0.0,
          stop_cargo_quantity_tonnes: 0.0,
          cumulative_onboard_quantity_quintals: 40.0,
          cumulative_onboard_quantity_tonnes: 4.0,
          latest_departure: '2026-09-05',
          segment_distance_km: 74.5,
        },
      ],
      feasibility_checks: [
        'Vehicle payload capacity (80.0 qtl) accommodates peak onboard cargo (40.0 qtl).',
        'Pickup dates precede delivery deadline (2026-09-05).',
      ],
      warnings: [],
      operational_limitations: [
        'Transit durations are modeled regional estimates assuming rural multi-stop road factors.',
      ],
      evaluated_at: new Date().toISOString(),
    },
    optimizedRoute: {
      shipment_plan_id: 'test-plan-001',
      plan_code: 'PLAN-PUNE-2026-001',
      optimization_status: 'optimized_route_found',
      status_summary: 'Google OR-Tools Guided Local Search metaheuristic optimized waypoint sequence, achieving 18.4% distance savings.',
      overall_geographic_precision: 'exact',
      routing_strategy: 'OR_TOOLS_VRP',
      optimizer_name: 'Google OR-Tools Guided Local Search VRP',
      routing_provider_name: 'ModeledGeographicRoutingProvider',
      optimization_type: 'MODELED_ROUTE_OPTIMIZATION',
      waypoints_count: 4,
      pickup_stops_count: 3,
      total_cargo_quantity_quintals: 40.0,
      total_cargo_quantity_tonnes: 4.0,
      total_modeled_distance_km: 42.8,
      distance_certainty: 'MODELED_GEOGRAPHIC_DISTANCE',
      estimated_transit_hours: 1.2,
      transit_time_certainty: 'MODELED_TRANSIT_ESTIMATE',
      assigned_vehicle_class: 'Medium Commercial Vehicle (8.0 MT)',
      vehicle_payload_capacity_quintals: 80.0,
      waypoints: [
        {
          waypoint_sequence: 1,
          waypoint_type: 'pickup',
          location_name: 'Manchar Harvest Yard',
          taluka: 'Ambegaon',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 18.995,
          longitude: 73.94,
          geographic_precision: 'exact',
          seller_name: 'Farmer Anand Patil',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 10.0,
          stop_cargo_quantity_tonnes: 1.0,
          cumulative_onboard_quantity_quintals: 10.0,
          cumulative_onboard_quantity_tonnes: 1.0,
          earliest_arrival: '2026-09-01',
          segment_distance_km: 0.0,
        },
        {
          waypoint_sequence: 2,
          waypoint_type: 'pickup',
          location_name: 'Alephata Farm Yard',
          taluka: 'Junnar',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 19.18,
          longitude: 74.1,
          geographic_precision: 'exact',
          seller_name: 'Farmer Chandrakant Shinde',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 15.0,
          stop_cargo_quantity_tonnes: 1.5,
          cumulative_onboard_quantity_quintals: 25.0,
          cumulative_onboard_quantity_tonnes: 2.5,
          earliest_arrival: '2026-09-01',
          segment_distance_km: 23.1,
        },
        {
          waypoint_sequence: 3,
          waypoint_type: 'pickup',
          location_name: 'Junnar Agro Collection Gate',
          taluka: 'Junnar',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 19.2,
          longitude: 73.88,
          geographic_precision: 'exact',
          seller_name: 'Farmer Balasaheb Gaikwad',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 15.0,
          stop_cargo_quantity_tonnes: 1.5,
          cumulative_onboard_quantity_quintals: 40.0,
          cumulative_onboard_quantity_tonnes: 4.0,
          earliest_arrival: '2026-09-01',
          segment_distance_km: 23.2,
        },
        {
          waypoint_sequence: 4,
          waypoint_type: 'destination',
          location_name: 'Apex Agro Processing Terminal',
          taluka: 'Junnar',
          district: 'Pune',
          state: 'Maharashtra',
          latitude: 18.5204,
          longitude: 73.8567,
          geographic_precision: 'exact',
          seller_name: 'Apex Agro Processing Ltd (Buyer Terminal)',
          stop_cargo_quantity_quintals: 0.0,
          stop_cargo_quantity_tonnes: 0.0,
          cumulative_onboard_quantity_quintals: 40.0,
          cumulative_onboard_quantity_tonnes: 4.0,
          latest_departure: '2026-09-05',
          segment_distance_km: 74.5,
        },
      ],
      comparison_metrics: {
        baseline_distance_km: 52.4,
        optimized_distance_km: 42.8,
        distance_reduction_km: 9.6,
        distance_reduction_pct: 18.32,
        baseline_duration_hours: 1.5,
        optimized_duration_hours: 1.2,
        duration_reduction_pct: 20.0,
        has_improvement: true,
      },
      feasibility_checks: ['OR-Tools solver converged with optimal tour permutation.'],
      warnings: [],
      operational_limitations: ['Estimated road distances utilize terrain-adjusted factors.'],
      evaluated_at: new Date().toISOString(),
    },
  },
  {
    id: 'administrative-only',
    name: 'Nashik Belgaum Cluster (Administrative Only — Zero Fake GPS)',
    description: 'Stops have verified district and taluka records without surveyed GPS coordinates.',
    lifecycleStatus: 'planned',
    routePlan: {
      shipment_plan_id: 'test-plan-002',
      plan_code: 'PLAN-ADMIN-2026-002',
      route_status: 'route_feasibility_unknown',
      status_summary: 'Waypoint sequence modeled on administrative boundaries. Turn-by-turn road precision is unverified.',
      overall_geographic_precision: 'administrative_only',
      is_optimized: false,
      routing_strategy: 'DETERMINISTIC_BASELINE_ORDERING',
      routing_provider_name: 'ModeledGeographicRoutingProvider',
      waypoints_count: 3,
      pickup_stops_count: 2,
      total_cargo_quantity_quintals: 25.0,
      total_cargo_quantity_tonnes: 2.5,
      total_modeled_distance_km: 65.0,
      distance_certainty: 'MODELED_GEOGRAPHIC_DISTANCE',
      estimated_transit_hours: 1.9,
      transit_time_certainty: 'MODELED_TRANSIT_ESTIMATE',
      assigned_vehicle_class: 'Pickup (3.0 MT)',
      vehicle_payload_capacity_quintals: 30.0,
      waypoints: [
        {
          waypoint_sequence: 1,
          waypoint_type: 'pickup',
          location_name: 'Dindori Farm Cluster',
          taluka: 'Dindori',
          district: 'Nashik',
          state: 'Maharashtra',
          latitude: null,
          longitude: null,
          geographic_precision: 'administrative_only',
          seller_name: 'Farmer Devidas More',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 12.0,
          stop_cargo_quantity_tonnes: 1.2,
          cumulative_onboard_quantity_quintals: 12.0,
          cumulative_onboard_quantity_tonnes: 1.2,
        },
        {
          waypoint_sequence: 2,
          waypoint_type: 'pickup',
          location_name: 'Niphad Onion Mandi Gate',
          taluka: 'Niphad',
          district: 'Nashik',
          state: 'Maharashtra',
          latitude: null,
          longitude: null,
          geographic_precision: 'administrative_only',
          seller_name: 'Farmer Eknath Sonawane',
          seller_role: 'FARMER',
          stop_cargo_quantity_quintals: 13.0,
          stop_cargo_quantity_tonnes: 1.3,
          cumulative_onboard_quantity_quintals: 25.0,
          cumulative_onboard_quantity_tonnes: 2.5,
        },
        {
          waypoint_sequence: 3,
          waypoint_type: 'destination',
          location_name: 'Nashik City Wholesale Terminal',
          taluka: 'Nashik',
          district: 'Nashik',
          state: 'Maharashtra',
          latitude: null,
          longitude: null,
          geographic_precision: 'administrative_only',
          seller_name: 'Sahyadri Wholesalers (Buyer Terminal)',
          stop_cargo_quantity_quintals: 0.0,
          stop_cargo_quantity_tonnes: 0.0,
          cumulative_onboard_quantity_quintals: 25.0,
          cumulative_onboard_quantity_tonnes: 2.5,
        },
      ],
      feasibility_checks: ['Payload capacity verified against vehicle archetype.'],
      warnings: [
        'Locations rely on administrative boundaries; turn-by-turn road navigation requires physical address confirmation.',
      ],
      operational_limitations: ['Zero fake coordinates are rendered on the map.'],
      evaluated_at: new Date().toISOString(),
    },
  },
];

const LIFECYCLE_STEPS = [
  { key: 'planned', label: '1. Planned' },
  { key: 'ready_for_logistics', label: '2. Ready for Logistics' },
  { key: 'scheduled', label: '3. Scheduled' },
  { key: 'in_transit', label: '4. In Transit' },
  { key: 'delivered', label: '5. Delivered' },
];

export const LogisticsRouteView: React.FC<LogisticsRouteViewProps> = ({ initialPlanId }) => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('pune-consolidation');
  const [useOptimization, setUseOptimization] = useState<boolean>(false);
  const [selectedWaypointSeq, setSelectedWaypointSeq] = useState<number | null>(null);

  // Backend live plans list state
  const [dbPlans, setDbPlans] = useState<ShipmentPlanSummary[]>([]);
  const [selectedDbPlanId, setSelectedDbPlanId] = useState<string>(initialPlanId || '');
  const [liveRoutePlan, setLiveRoutePlan] = useState<RoutePlanResponse | null>(null);
  const [liveOptimizedPlan, setLiveOptimizedPlan] = useState<RouteOptimizationResponse | null>(null);
  const [isLoadingLive, setIsLoadingLive] = useState<boolean>(false);
  const [liveError, setLiveError] = useState<string | null>(null);

  // Fetch live plans on mount
  useEffect(() => {
    const fetchPlans = async () => {
      try {
        const res = await api.getShipmentPlans();
        if (res && res.items) {
          setDbPlans(res.items);
        }
      } catch {
        // Live backend plans optional for offline/mock demo
      }
    };
    fetchPlans();
  }, []);

  // Fetch live route data when selectedDbPlanId changes
  useEffect(() => {
    if (!selectedDbPlanId) return;

    let isMounted = true;
    const fetchLiveRoute = async () => {
      setIsLoadingLive(true);
      setLiveError(null);
      try {
        const planData = await api.getShipmentRoutePlan(selectedDbPlanId);
        if (!isMounted) return;
        setLiveRoutePlan(planData);

        try {
          const optData = await api.optimizeShipmentRoute(selectedDbPlanId);
          if (!isMounted) return;
          setLiveOptimizedPlan(optData);
        } catch {
          // Non-critical optimization failure
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        setLiveError(err instanceof Error ? err.message : 'Failed to load route data from API');
      } finally {
        if (isMounted) {
          setIsLoadingLive(false);
        }
      }
    };

    fetchLiveRoute();
    return () => {
      isMounted = false;
    };
  }, [selectedDbPlanId]);

  // Determine active route payload
  const currentScenario = TEST_SCENARIOS.find((s) => s.id === selectedScenarioId);

  const activeRouteData: RoutePlanResponse | RouteOptimizationResponse | null = selectedDbPlanId
    ? useOptimization && liveOptimizedPlan
      ? liveOptimizedPlan
      : liveRoutePlan
    : currentScenario
    ? useOptimization && currentScenario.optimizedRoute
      ? currentScenario.optimizedRoute
      : currentScenario.routePlan
    : null;

  const waypoints: RouteWaypoint[] = activeRouteData?.waypoints || [];
  const activeRouteStatus = activeRouteData
    ? 'route_status' in activeRouteData
      ? activeRouteData.route_status
      : activeRouteData.optimization_status
    : undefined;
  const activeOptimizerName =
    activeRouteData && 'optimizer_name' in activeRouteData
      ? activeRouteData.optimizer_name
      : undefined;

  const activeLifecycleStatus = currentScenario?.lifecycleStatus || 'ready_for_logistics';

  return (
    <div className="container" style={{ paddingTop: '2rem', paddingBottom: '4rem' }}>
      {/* Title & Plan Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
            <span className="role-pill">LOGISTICS DESK</span>
            <span className="trust-badge-modeled">🗺️ Leaflet OpenStreetMap Engine</span>
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 900, color: '#0f291e', margin: 0 }}>
            Logistics Operations & Route Visualization
          </h1>
        </div>

        {/* Live database vs Test Scenario selector */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {dbPlans.length > 0 && (
            <select
              className="form-select"
              value={selectedDbPlanId}
              onChange={(e) => {
                setSelectedDbPlanId(e.target.value);
                setSelectedWaypointSeq(null);
                setLiveRoutePlan(null);
                setLiveOptimizedPlan(null);
              }}
              style={{ fontSize: '0.85rem', padding: '0.5rem 0.9rem', minWidth: '220px' }}
            >
              <option value="">-- Select Live Database Plan --</option>
              {dbPlans.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.plan_code} ({p.commodity_name} - {p.total_planned_quantity_quintals} qtl)
                </option>
              ))}
            </select>
          )}

          {!selectedDbPlanId && (
            <select
              className="form-select"
              value={selectedScenarioId}
              onChange={(e) => {
                setSelectedScenarioId(e.target.value);
                setSelectedWaypointSeq(null);
                setUseOptimization(false);
              }}
              style={{ fontSize: '0.85rem', padding: '0.5rem 0.9rem' }}
            >
              {TEST_SCENARIOS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Shipment Status Progression Stepper */}
      <div className="glass-panel" style={{ padding: '1rem 1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#0f291e', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Shipment Execution Status
          </span>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {LIFECYCLE_STEPS.map((step) => {
              const isActive = step.key === activeLifecycleStatus;
              return (
                <span
                  key={step.key}
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: '9999px',
                    background: isActive ? '#dcfce7' : '#f1f5f9',
                    color: isActive ? '#15803d' : '#64748b',
                    border: isActive ? '1px solid #86efac' : '1px solid #e2e8f0',
                  }}
                >
                  {step.label}
                </span>
              );
            })}
          </div>
        </div>
      </div>

      {isLoadingLive && (
        <div style={{ padding: '1.5rem', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', marginBottom: '1rem' }}>
          <span>⏳ Loading route planning data from backend API...</span>
        </div>
      )}

      {liveError && (
        <div style={{ padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.875rem' }}>
          <strong>Error loading live route:</strong> {liveError}
        </div>
      )}

      {/* Main Grid: Left Map + Right Waypoints List */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: '1.5rem', alignItems: 'start' }}>
        {/* Dominant Map Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {activeRouteData ? (
            <ShipmentRouteMap
              waypoints={waypoints}
              routeStatus={activeRouteStatus}
              statusSummary={activeRouteData.status_summary}
              overallGeographicPrecision={activeRouteData.overall_geographic_precision}
              selectedSequence={selectedWaypointSeq}
              onSelectWaypoint={(seq) => setSelectedWaypointSeq(seq)}
              totalDistanceKm={activeRouteData.total_modeled_distance_km}
              distanceCertainty={activeRouteData.distance_certainty}
              estimatedTransitHours={activeRouteData.estimated_transit_hours}
              transitTimeCertainty={activeRouteData.transit_time_certainty}
              isOptimized={useOptimization}
              optimizerName={activeOptimizerName}
              height={520}
            />
          ) : (
            <div style={{ height: '480px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f1f5f9', borderRadius: '12px', border: '1px dashed #cbd5e1' }}>
              <p style={{ color: '#64748b' }}>No route data available for the selected plan.</p>
            </div>
          )}

          {/* Optimizer Comparison Bar (if available) */}
          {(currentScenario?.optimizedRoute || liveOptimizedPlan) && (
            <div className="glass-panel" style={{ padding: '1.25rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: '0.92rem', color: '#0f291e' }}>Google OR-Tools Route Optimizer</div>
                <div style={{ fontSize: '0.78rem', color: '#4d725d' }}>
                  Guided Local Search metaheuristic compares nearest-neighbor baseline with optimized multi-stop tour.
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                {activeRouteData && 'comparison_metrics' in activeRouteData && activeRouteData.comparison_metrics && (
                  <span style={{ fontSize: '0.8rem', fontWeight: 800, color: '#059669', background: '#ecfdf5', padding: '4px 10px', borderRadius: '6px', border: '1px solid #a7f3d0' }}>
                    ↓ {activeRouteData.comparison_metrics.distance_reduction_pct}% distance saved ({activeRouteData.comparison_metrics.distance_reduction_km} km)
                  </span>
                )}

                <button
                  className={useOptimization ? 'clay-button-primary' : 'btn-secondary'}
                  onClick={() => setUseOptimization(!useOptimization)}
                  style={{ fontSize: '0.82rem', padding: '0.5rem 1rem' }}
                >
                  {useOptimization ? '✓ Showing OR-Tools Optimized' : 'Show OR-Tools Optimized'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Waypoints & Summary Sidebar */}
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem' }}>
            <h4 style={{ margin: '0 0 0.25rem 0', fontSize: '1.05rem', fontWeight: 800, color: '#0f291e' }}>
              Waypoints ({waypoints.length})
            </h4>
            <div style={{ fontSize: '0.78rem', color: '#4d725d' }}>
              Click any stop to highlight and center it on the OpenStreetMap view.
            </div>
          </div>

          {/* Ordered Waypoints Itinerary */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '460px', overflowY: 'auto' }}>
            {waypoints.map((wp) => {
              const isSelected = selectedWaypointSeq === wp.waypoint_sequence;
              const isPickup = wp.waypoint_type === 'pickup';
              const hasGps = wp.latitude != null && wp.longitude != null;

              return (
                <div
                  key={wp.waypoint_sequence}
                  onClick={() => setSelectedWaypointSeq(wp.waypoint_sequence)}
                  role="button"
                  tabIndex={0}
                  style={{
                    padding: '1rem',
                    borderRadius: '10px',
                    border: isSelected ? '2px solid #15803d' : '1px solid #e2e8f0',
                    background: isSelected ? '#f0fdf4' : '#ffffff',
                    cursor: 'pointer',
                    boxShadow: isSelected ? '0 4px 12px rgba(21, 128, 61, 0.15)' : 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          background: isPickup ? '#15803d' : '#4f46e5',
                          color: '#ffffff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '0.75rem',
                          fontWeight: 800,
                        }}
                      >
                        {isPickup ? wp.waypoint_sequence : '🎯'}
                      </span>
                      <strong style={{ fontSize: '0.875rem', color: '#0f291e' }}>
                        {wp.seller_name || wp.location_name}
                      </strong>
                    </div>

                    <span
                      style={{
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: hasGps ? '#ecfdf5' : '#fffbeb',
                        color: hasGps ? '#047857' : '#b45309',
                        border: `1px solid ${hasGps ? '#a7f3d0' : '#fde68a'}`,
                      }}
                    >
                      {hasGps ? 'GPS' : 'Admin'}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.78rem', color: '#4d725d', marginLeft: '32px', marginBottom: '0.35rem' }}>
                    📍 {[wp.taluka, wp.district, wp.state].filter(Boolean).join(', ')}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginLeft: '32px', color: '#1e3a2b' }}>
                    <span>Stop: <strong>{wp.stop_cargo_quantity_quintals} qtl</strong></span>
                    <span>Onboard: <strong>{wp.cumulative_onboard_quantity_quintals} qtl</strong></span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Vehicle Capacity Bar */}
          {activeRouteData && (
            <div style={{ padding: '0.85rem 1rem', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '10px', fontSize: '0.78rem', color: '#14532d' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                <span>Matched Vehicle Class:</span>
                <strong>{activeRouteData.assigned_vehicle_class || 'Medium Commercial Vehicle'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Total Payload Volume:</span>
                <strong>{activeRouteData.total_cargo_quantity_quintals} qtl ({activeRouteData.total_cargo_quantity_tonnes} MT)</strong>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
