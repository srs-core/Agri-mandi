export interface User {
  id: string;
  email: string;
  display_name: string;
  status: string;
  roles: string[];
}

export interface Location {
  id?: string;
  name: string;
  village?: string;
  taluka?: string;
  district?: string;
  state: string;
  country_code?: string;
  postal_code?: string;
  latitude?: number;
  longitude?: number;
}

export interface UserProfile {
  user_id: string;
  email: string;
  display_name: string;
  phone_number?: string;
  roles: string[];
  status: string;
  farm_name?: string;
  land_area_hectares?: number;
  legal_name?: string;
  registration_number?: string;
  organization_name?: string;
  gstin?: string;
  verification_status: 'pending' | 'verified' | 'rejected';
  primary_location?: Location;
}

export interface Commodity {
  id: string;
  name: string;
  category: 'vegetables' | 'fruits' | 'grains' | 'pulses' | 'spices' | 'other_crops';
  default_unit: string;
  is_perishable: boolean;
  storage_guidance?: string;
  is_active: boolean;
}

export interface ProduceLotContribution {
  id: string;
  farmer_profile_id?: string;
  fpo_profile_id?: string;
  contributed_quantity: number;
}

export interface ProduceLotSummary {
  id: string;
  seller_user_id: string;
  seller_name: string;
  seller_role: string;
  seller_verification_status: 'pending' | 'verified' | 'rejected';
  commodity_id: string;
  commodity_name: string;
  commodity_category: 'vegetables' | 'fruits' | 'grains' | 'pulses' | 'spices' | 'other_crops';
  title: string;
  available_quantity: number;
  unit: string;
  quality_grade?: string;
  quality_notes?: string;
  asking_price_per_unit?: number;
  price_mode?: 'FIXED_PRICE' | 'NEGOTIABLE';
  available_from: string;
  available_until?: string;
  is_aggregated: boolean;
  status: 'draft' | 'published' | 'under_offer' | 'sold' | 'cancelled' | 'expired';
  pickup_location?: Location;
  contributions_count: number;
  created_at: string;
}

export interface ProduceLotDetail extends ProduceLotSummary {
  seller_phone?: string;
  seller_email?: string;
  contributions: ProduceLotContribution[];
}

export interface MarketplaceProduceLotsResponse {
  items: ProduceLotSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface BuyerRequirement {
  id: string;
  buyer_user_id: string;
  buyer_name: string;
  buyer_organization?: string;
  buyer_verification_status: 'pending' | 'verified' | 'rejected';
  commodity_id: string;
  commodity_name: string;
  commodity_category: 'vegetables' | 'fruits' | 'grains' | 'pulses' | 'spices' | 'other_crops';
  required_quantity: number;
  unit: string;
  minimum_quality_grade?: string;
  target_price_per_unit?: number;
  delivery_by?: string;
  delivery_location?: Location;
  status: 'active' | 'partially_fulfilled' | 'fulfilled' | 'cancelled' | 'expired';
  created_at: string;
}

export interface NegotiationProposal {
  id: string;
  proposer_user_id: string;
  proposer_name: string;
  proposer_role: string;
  price_per_unit: number;
  quantity: number;
  total_amount: number;
  notes?: string | null;
  status_at_step: string;
  created_at: string;
}

export interface Offer {
  id: string;
  produce_lot_id: string;
  produce_title: string;
  commodity_name: string;
  buyer_user_id: string;
  buyer_name: string;
  seller_user_id: string;
  seller_name: string;
  offered_quantity: number;
  unit: string;
  offered_price_per_unit: number;
  current_price_per_unit?: number;
  current_quantity?: number;
  total_amount: number;
  price_mode?: 'FIXED_PRICE' | 'NEGOTIABLE';
  current_proposer_user_id?: string;
  current_proposer_name?: string;
  current_proposer_role?: string;
  response_required_from_user_id?: string;
  response_required_from_name?: string;
  expires_at?: string;
  status: 'pending' | 'accepted' | 'declined' | 'countered' | 'expired' | 'withdrawn';
  history?: NegotiationProposal[];
  created_at: string;
}

export interface OrderItem {
  id: string;
  produce_lot_id: string;
  commodity_id: string;
  commodity_name: string;
  quantity: number;
  unit: string;
  agreed_price_per_unit: number;
  total_item_amount: number;
}

export interface Order {
  id: string;
  buyer_user_id: string;
  buyer_name: string;
  seller_user_id: string;
  seller_name: string;
  accepted_offer_id?: string;
  status: 'draft' | 'confirmed' | 'fulfilment' | 'delivered' | 'cancelled';
  total_amount: number;
  confirmed_at?: string;
  delivery_location?: Location;
  items: OrderItem[];
  created_at: string;
}

export interface PlatformMetrics {
  total_users: number;
  total_farmers: number;
  total_fpos: number;
  total_buyers: number;
  total_commodities: number;
  active_produce_lots: number;
  active_buyer_requirements: number;
  total_offers: number;
  pending_offers: number;
  confirmed_orders: number;
  total_gmv: number;
  pending_verifications: number;
}

export interface VerificationRequest {
  id: string;
  requested_by_user_id?: string;
  user_name: string;
  user_email: string;
  user_role: string;
  subject_type: string;
  subject_id: string;
  status: 'pending' | 'verified' | 'rejected';
  document_reference?: string;
  reviewer_notes?: string;
  reviewed_at?: string;
  created_at: string;
}

export interface Notification {
  id: string;
  notification_type: string;
  title: string;
  body: string;
  data_json?: Record<string, unknown>;
  read_at?: string;
  created_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  phone_number?: string;
  status: string;
  roles: string[];
  verification_status: string;
}

export interface LogisticsDeductionBreakdown {
  distance_km: number;
  vehicle_type: string;
  base_fare: number;
  distance_charge: number;
  reefer_surcharge: number;
  loading_unloading_charge: number;
  total_transport_cost: number;
  cost_per_quintal: number;
  cost_certainty: 'VERIFIED_TRANSPORTER_QUOTE' | 'MODELED_REGIONAL_ESTIMATE' | 'UNAVAILABLE';
  is_verified_quote: boolean;
  rate_source: string;
  provider_name?: string;
  disclaimer: string;
  explanation: string;
}

export interface ForecastPriceReference {
  is_forecast_available: boolean;
  forecast_horizon?: string;
  predicted_price_per_quintal?: number;
  interval_lower_bound?: number;
  interval_upper_bound?: number;
  interval_coverage_pct?: number;
  quality_gate_status: string;
  model_version: string;
  pricing_source: string;
}

export interface EconomicOptionBreakdown {
  buyer_id: string;
  business_name: string;
  buyer_type: string;
  source_type: string;
  buyer_provenance: 'REGISTERED_VERIFIED_BUYER' | 'RESEARCHED_DIRECTORY_RECORD' | 'PUBLIC_DIRECTORY_LISTING';
  is_platform_registered: boolean;
  destination_name: string;
  destination_district?: string;
  road_distance_km: number;
  expected_unit_price: number;
  pricing_source: string;
  gross_selling_value: number;
  logistics_deduction: LogisticsDeductionBreakdown;
  expected_net_realization: number;
  net_realization_per_quintal: number;
  net_realization_certainty: 'VERIFIED_QUOTE' | 'CONDITIONAL_ESTIMATE' | 'UNAVAILABLE';
  is_net_realization_estimated: boolean;
  match_score: number;
  is_eligible: boolean;
  is_economically_viable: boolean;
  verified_facts: string[];
  modeled_estimates: string[];
  uncertainties_and_cautions: string[];
  reasoning_checklist: string[];
}

export interface BuyerRecommendationRequest {
  commodity_id?: string;
  commodity_name?: string;
  quantity_quintals: number;
  quality_grade?: string;
  pickup_location_id?: string;
  pickup_location_name?: string;
  availability_date?: string;
}

export interface BuyerRecommendationResponse {
  status: 'SUCCESS' | 'NO_ELIGIBLE_BUYER_MATCH';
  commodity_name: string;
  quantity_quintals: number;
  quality_grade?: string;
  pickup_location_name: string;
  recommended_option?: EconomicOptionBreakdown;
  alternative_options: EconomicOptionBreakdown[];
  forecast_reference: ForecastPriceReference;
  fallback_reason?: string;
  data_trust_notice: string;
  explanation: string[];
}

export type GeographicPrecision = 'exact' | 'administrative_only' | 'unavailable';
export type RoutePlanningStatus = 'route_feasible' | 'route_feasibility_unknown' | 'route_infeasible' | 'route_data_incomplete';
export type WaypointType = 'pickup' | 'destination';

export interface RouteWaypoint {
  waypoint_sequence: number;
  waypoint_type: WaypointType;
  pickup_stop_id?: string;
  location_id?: string;
  location_name: string;
  district?: string;
  taluka?: string;
  state?: string;
  postal_code?: string;
  latitude?: number | null;
  longitude?: number | null;
  geographic_precision: GeographicPrecision;
  seller_user_id?: string;
  seller_name?: string;
  seller_role?: string;
  stop_cargo_quantity_quintals: number;
  stop_cargo_quantity_tonnes: number;
  cumulative_onboard_quantity_quintals: number;
  cumulative_onboard_quantity_tonnes: number;
  earliest_arrival?: string;
  latest_departure?: string;
  segment_distance_km?: number;
  notes?: string;
}

export interface RoutePlanResponse {
  shipment_plan_id: string;
  plan_code: string;
  route_status: RoutePlanningStatus;
  status_summary: string;
  overall_geographic_precision: GeographicPrecision;
  is_optimized: boolean;
  routing_strategy: string;
  routing_provider_name: string;
  waypoints_count: number;
  pickup_stops_count: number;
  total_cargo_quantity_quintals: number;
  total_cargo_quantity_tonnes: number;
  total_modeled_distance_km?: number | null;
  distance_certainty: 'VERIFIED_ROAD_DISTANCE' | 'MODELED_GEOGRAPHIC_DISTANCE' | 'UNAVAILABLE';
  estimated_transit_hours?: number | null;
  transit_time_certainty: 'VERIFIED_ROAD_TIME' | 'MODELED_TRANSIT_ESTIMATE' | 'UNAVAILABLE';
  assigned_vehicle_class?: string;
  vehicle_payload_capacity_quintals?: number;
  waypoints: RouteWaypoint[];
  feasibility_checks: string[];
  warnings: string[];
  operational_limitations: string[];
  evaluated_at: string;
}

export type RouteOptimizationStatus =
  | 'optimized_route_found'
  | 'optimization_infeasible'
  | 'route_data_incomplete'
  | 'routing_unavailable'
  | 'time_window_conflict'
  | 'capacity_constraint_failure';

export interface OptimizationComparisonMetrics {
  baseline_distance_km: number;
  optimized_distance_km: number;
  distance_reduction_km: number;
  distance_reduction_pct: number;
  baseline_duration_hours: number;
  optimized_duration_hours: number;
  duration_reduction_pct: number;
  has_improvement: boolean;
}

export interface RouteOptimizationResponse {
  shipment_plan_id: string;
  plan_code: string;
  optimization_status: RouteOptimizationStatus;
  status_summary: string;
  overall_geographic_precision: GeographicPrecision;
  routing_strategy: 'OR_TOOLS_VRP' | 'DETERMINISTIC_BASELINE_ORDERING';
  optimizer_name: string;
  routing_provider_name: string;
  optimization_type: 'MODELED_ROUTE_OPTIMIZATION' | 'VERIFIED_ROAD_ROUTE_OPTIMIZATION';
  waypoints_count: number;
  pickup_stops_count: number;
  total_cargo_quantity_quintals: number;
  total_cargo_quantity_tonnes: number;
  total_modeled_distance_km?: number | null;
  distance_certainty: 'VERIFIED_ROAD_DISTANCE' | 'MODELED_GEOGRAPHIC_DISTANCE' | 'UNAVAILABLE';
  estimated_transit_hours?: number | null;
  transit_time_certainty: 'VERIFIED_ROAD_TIME' | 'MODELED_TRANSIT_ESTIMATE' | 'UNAVAILABLE';
  assigned_vehicle_class?: string;
  vehicle_payload_capacity_quintals?: number;
  waypoints: RouteWaypoint[];
  comparison_metrics?: OptimizationComparisonMetrics | null;
  feasibility_checks: string[];
  warnings: string[];
  operational_limitations: string[];
  evaluated_at: string;
}

export interface ShipmentPlanSummary {
  id: string;
  plan_code: string;
  planning_status: 'planned' | 'ready_for_logistics' | 'cancelled';
  commodity_name: string;
  variety?: string;
  quality_grade?: string;
  total_planned_quantity_quintals: number;
  destination_location_name: string;
  destination_district?: string;
  earliest_pickup_date: string;
  delivery_deadline?: string;
  pickup_stops_count: number;
  is_geographic_distance_exact: boolean;
  created_at: string;
}

export interface ShipmentPlanListResponse {
  total: number;
  items: ShipmentPlanSummary[];
}

export interface TransporterProfile {
  id: string;
  user_id: string;
  organization_name: string;
  verification_status: 'pending' | 'verified' | 'rejected';
  operational_status: string;
  service_area_districts?: string[];
  contact_phone?: string;
  contact_email?: string;
  preferred_commodities?: string[];
  created_at: string;
  updated_at: string;
}

export interface TransporterVehicle {
  id: string;
  provider_id: string;
  registration_number?: string;
  vehicle_type: string;
  model_name?: string;
  payload_capacity_kg: number;
  payload_capacity_quintals: number;
  payload_capacity_tonnes: number;
  volumetric_capacity_cbm?: number;
  is_refrigerated: boolean;
  temp_min_celsius?: number;
  temp_max_celsius?: number;
  is_available: boolean;
  operational_status: string;
  created_at: string;
  updated_at: string;
}

export interface TransportOpportunity {
  id: string;
  shipment_plan_id?: string;
  shipment_id?: string;
  transporter_profile_id: string;
  status: 'open' | 'offered' | 'accepted' | 'declined' | 'expired' | 'withdrawn' | 'cancelled';
  required_vehicle_class: string;
  required_payload_quintals: number;
  required_payload_tonnes: number;
  requires_cold_chain: boolean;
  pickup_stops_count: number;
  origin_district: string;
  destination_district: string;
  total_distance_km: number;
  distance_certainty: string;
  estimated_cost: number;
  cost_certainty: string;
  earliest_pickup_date: string;
  delivery_deadline?: string;
  eligibility_score: number;
  matching_criteria_json?: Record<string, unknown>;
  expires_at?: string;
  responded_at?: string;
  decline_reason?: string;
  created_at: string;
  updated_at: string;
}

export interface TransporterQuote {
  id: string;
  opportunity_id: string;
  transporter_profile_id: string;
  vehicle_id?: string;
  quote_amount: number;
  quote_unit: string;
  currency: string;
  status: 'submitted' | 'accepted' | 'rejected' | 'expired' | 'withdrawn';
  valid_until?: string;
  notes?: string;
  quote_certainty: string;
  created_at: string;
  updated_at: string;
}

export interface TransportOpportunityDetail extends TransportOpportunity {
  plan_code?: string;
  commodity_name?: string;
  buyer_organization_name?: string;
  waypoints?: RouteWaypoint[];
  vehicle_options?: TransporterVehicle[];
  my_quotes?: TransporterQuote[];
  lineage_summary?: Record<string, unknown>;
}

export interface TransporterMeResponse {
  profile: TransporterProfile;
  provider_id?: string;
  provider_name?: string;
  total_vehicles_count: number;
  available_vehicles_count: number;
  open_opportunities_count: number;
  active_shipments_count: number;
  delivered_shipments_count: number;
}

export interface BroadcastOpportunitiesResponse {
  plan_id: string;
  plan_code: string;
  opportunities_created_count: number;
  matched_transporters_count: number;
  opportunities: TransportOpportunity[];
}

export interface ShipmentCheckpoint {
  id: string;
  shipment_id: string;
  checkpoint_type: 'PICKUP' | 'DESTINATION' | 'pickup' | 'destination';
  stop_sequence: number;
  pickup_stop_id?: string | null;
  location_id: string;
  location_name: string;
  seller_user_id?: string | null;
  seller_name?: string | null;
  status: 'PENDING' | 'ARRIVED' | 'LOADING' | 'COMPLETED' | 'pending' | 'arrived' | 'loading' | 'completed';
  planned_quantity_quintals: number;
  loaded_quantity_quintals?: number | null;
  variance_quintals?: number | null;
  variance_reason?: string | null;
  arrived_at?: string | null;
  loading_started_at?: string | null;
  loading_completed_at?: string | null;
  completed_at?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ShipmentEvent {
  id: string;
  shipment_id: string;
  event_type: string;
  location_name?: string | null;
  notes?: string | null;
  recorded_at: string;
}

export interface ShipmentExecutionDetail {
  id: string;
  plan_id?: string | null;
  plan_code?: string | null;
  order_id?: string | null;
  status: string;
  commodity_name?: string | null;
  total_planned_quantity_quintals: number;
  total_picked_up_quantity_quintals: number;
  delivered_quantity_quintals?: number | null;
  progress_percentage: number;
  current_checkpoint_sequence: number;
  total_checkpoints_count: number;
  completed_checkpoints_count: number;
  vehicle_id?: string | null;
  vehicle_model?: string | null;
  vehicle_reg_number?: string | null;
  transporter_name?: string | null;
  driver_name?: string | null;
  driver_phone?: string | null;
  origin_location_name?: string | null;
  destination_location_name?: string | null;
  delivery_variance_reason?: string | null;
  receiver_name?: string | null;
  delivery_notes?: string | null;
  checkpoints: ShipmentCheckpoint[];
  timeline: ShipmentEvent[];
  created_at: string;
  updated_at: string;
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000/api/v1';


class ApiClient {
  private getAccessToken(): string | null {
    return localStorage.getItem('agri_access_token');
  }

  private getRefreshToken(): string | null {
    return localStorage.getItem('agri_refresh_token');
  }

  public setTokens(access: string, refresh: string) {
    localStorage.setItem('agri_access_token', access);
    localStorage.setItem('agri_refresh_token', refresh);
  }

  public clearTokens() {
    localStorage.removeItem('agri_access_token');
    localStorage.removeItem('agri_refresh_token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retryOnAuth = true
  ): Promise<T> {
    const token = this.getAccessToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401 && retryOnAuth) {
      const refreshed = await this.tryRefreshToken();
      if (refreshed) {
        return this.request<T>(endpoint, options, false);
      } else {
        this.clearTokens();
        window.dispatchEvent(new Event('agri-auth-expired'));
      }
    }

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      let errorMsg = data?.error?.message || data?.detail || `Request failed with status ${response.status}.`;
      if (data?.error?.details && Array.isArray(data.error.details)) {
        const detailMessages = data.error.details
          .map((d: { message?: string; location?: string[] }) => {
            const field = d.location ? d.location[d.location.length - 1] : '';
            return field ? `${field}: ${d.message}` : d.message;
          })
          .filter(Boolean)
          .join(', ');
        if (detailMessages) {
          errorMsg = `${errorMsg} (${detailMessages})`;
        }
      }
      throw new Error(errorMsg);
    }

    return data as T;
  }

  private async tryRefreshToken(): Promise<boolean> {
    const refresh = this.getRefreshToken();
    if (!refresh) return false;

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return false;
      const json = await res.json();
      this.setTokens(json.access_token, json.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  // Health
  async getHealth() {
    return this.request<{ status: string; service: string; database: string }>('/health');
  }

  // Auth
  async login(payload: { email: string; password: string }) {
    const res = await this.request<{
      access_token: string;
      refresh_token: string;
      access_token_expires_at: string;
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    this.setTokens(res.access_token, res.refresh_token);
    return res;
  }

  async register(payload: { email: string; password: string; display_name: string; role: string; phone_number?: string }) {
    return this.request<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getMe() {
    return this.request<User>('/auth/me');
  }

  // Profiles
  async getProfile() {
    return this.request<UserProfile>('/profiles/me');
  }

  async updateProfile(payload: {
    display_name?: string;
    phone_number?: string;
    farm_name?: string;
    land_area_hectares?: number;
    legal_name?: string;
    registration_number?: string;
    organization_name?: string;
    gstin?: string;
    primary_location?: Location;
  }) {
    return this.request<UserProfile>('/profiles/me', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async submitVerificationRequest(payload: { document_reference?: string }) {
    return this.request<VerificationRequest>('/profiles/verification-request', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // Commodities
  async getCommodities(params?: { category?: string; search?: string }) {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.search) q.set('search', params.search);
    const queryStr = q.toString() ? `?${q.toString()}` : '';
    return this.request<Commodity[]>(`/commodities${queryStr}`);
  }

  // Produce Lots
  async createProduceLot(payload: {
    commodity_id: string;
    title: string;
    available_quantity: number;
    unit: string;
    quality_grade?: string;
    quality_notes?: string;
    asking_price_per_unit?: number;
    available_from: string;
    available_until?: string;
    pickup_location?: Location;
    is_aggregated?: boolean;
    contributions?: Array<{ farmer_profile_id?: string; contributed_quantity: number }>;
  }) {
    return this.request<ProduceLotDetail>('/produce-lots', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getMyProduceLots() {
    return this.request<ProduceLotSummary[]>('/produce-lots/my');
  }

  async getProduceLot(id: string) {
    return this.request<ProduceLotDetail>(`/produce-lots/${id}`);
  }

  async updateProduceLot(id: string, payload: {
    title?: string;
    available_quantity?: number;
    asking_price_per_unit?: number;
    available_from?: string;
    available_until?: string;
    quality_grade?: string;
    quality_notes?: string;
    status?: string;
  }) {
    return this.request<ProduceLotDetail>(`/produce-lots/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async browseMarketplace(params?: {
    commodity_id?: string;
    category?: string;
    state?: string;
    district?: string;
    min_price?: number;
    max_price?: number;
    min_quantity?: number;
    quality_grade?: string;
    search?: string;
    seller_role?: string;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }) {
    const q = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          q.set(k, String(v));
        }
      });
    }
    const queryStr = q.toString() ? `?${q.toString()}` : '';
    return this.request<MarketplaceProduceLotsResponse>(`/marketplace/produce-lots${queryStr}`);
  }

  // Buyer Requirements
  async createBuyerRequirement(payload: {
    commodity_id: string;
    required_quantity: number;
    unit: string;
    minimum_quality_grade?: string;
    target_price_per_unit?: number;
    delivery_by?: string;
    delivery_location?: Location;
  }) {
    return this.request<BuyerRequirement>('/buyer-requirements', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getMyBuyerRequirements() {
    return this.request<BuyerRequirement[]>('/buyer-requirements/my');
  }

  async browseBuyerRequirements(params?: { commodity_id?: string; category?: string }) {
    const q = new URLSearchParams();
    if (params?.commodity_id) q.set('commodity_id', params.commodity_id);
    if (params?.category) q.set('category', params.category);
    const queryStr = q.toString() ? `?${q.toString()}` : '';
    return this.request<BuyerRequirement[]>(`/buyer-requirements${queryStr}`);
  }

  // Offers
  async createOffer(payload: {
    produce_lot_id: string;
    buyer_requirement_id?: string;
    offered_quantity: number;
    offered_price_per_unit: number;
    notes?: string;
    expires_at?: string;
  }) {
    return this.request<Offer>('/offers', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async counterOffer(
    offerId: string,
    payload: {
      price_per_unit: number;
      quantity?: number;
      notes?: string;
    }
  ) {
    return this.request<Offer>(`/offers/${offerId}/counter`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getOffers(params?: { role_perspective?: 'sent' | 'received'; status?: string; lot_id?: string }) {
    const q = new URLSearchParams();
    if (params?.role_perspective) q.set('role_perspective', params.role_perspective);
    if (params?.status) q.set('status', params.status);
    if (params?.lot_id) q.set('lot_id', params.lot_id);
    const queryStr = q.toString() ? `?${q.toString()}` : '';
    return this.request<Offer[]>(`/offers${queryStr}`);
  }

  async acceptOffer(offerId: string) {
    return this.request<Order>(`/offers/${offerId}/accept`, {
      method: 'POST',
    });
  }

  async rejectOffer(offerId: string) {
    return this.request<Offer>(`/offers/${offerId}/reject`, {
      method: 'POST',
    });
  }

  async withdrawOffer(offerId: string) {
    return this.request<Offer>(`/offers/${offerId}/withdraw`, {
      method: 'POST',
    });
  }

  // Orders
  async getOrders() {
    return this.request<Order[]>('/orders');
  }

  async getOrder(orderId: string) {
    return this.request<Order>(`/orders/${orderId}`);
  }

  async updateOrderStatus(orderId: string, status: 'confirmed' | 'fulfilment' | 'delivered' | 'cancelled') {
    return this.request<Order>(`/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  // Admin
  async getAdminMetrics() {
    return this.request<PlatformMetrics>('/admin/metrics');
  }

  async getAdminUsers() {
    return this.request<AdminUser[]>('/admin/users');
  }

  async getAdminVerifications(status?: string) {
    const queryStr = status ? `?status=${status}` : '';
    return this.request<VerificationRequest[]>(`/admin/verifications${queryStr}`);
  }

  async reviewVerification(requestId: string, payload: { status: 'verified' | 'rejected'; reviewer_notes?: string }) {
    return this.request<VerificationRequest>(`/admin/verifications/${requestId}/review`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // Notifications
  async getNotifications() {
    return this.request<Notification[]>('/notifications');
  }

  async markNotificationRead(id: string) {
    return this.request<Notification>(`/notifications/${id}/read`, {
      method: 'PATCH',
    });
  }

  // Intelligence & Decision Support
  async getBuyerRecommendation(payload: BuyerRecommendationRequest) {
    return this.request<BuyerRecommendationResponse>('/intelligence/recommendation', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // Logistics & Route Planning
  async getShipmentPlans() {
    return this.request<ShipmentPlanListResponse>('/logistics/shipments/plans');
  }

  async getShipmentPlan(planId: string) {
    return this.request<ShipmentPlanSummary>(`/logistics/shipments/plans/${planId}`);
  }

  async getShipmentRoutePlan(shipmentPlanId: string) {
    return this.request<RoutePlanResponse>(`/logistics/shipments/${shipmentPlanId}/route-plan`);
  }

  async optimizeShipmentRoute(shipmentPlanId: string) {
    return this.request<RouteOptimizationResponse>(`/logistics/shipments/${shipmentPlanId}/route-optimize`, {
      method: 'POST',
    });
  }

  // Transporter Marketplace & Dispatch
  async getTransporterMe() {
    return this.request<TransporterMeResponse>('/logistics/transporter/me');
  }

  async updateTransporterProfile(payload: Partial<TransporterProfile>) {
    return this.request<TransporterProfile>('/logistics/transporter/profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async getTransporterVehicles() {
    return this.request<TransporterVehicle[]>('/logistics/transporter/vehicles');
  }

  async registerTransporterVehicle(payload: {
    registration_number?: string;
    vehicle_type?: string;
    model_name?: string;
    payload_capacity_kg: number;
    volumetric_capacity_cbm?: number;
    is_refrigerated?: boolean;
    temp_min_celsius?: number;
    temp_max_celsius?: number;
    is_available?: boolean;
    operational_status?: string;
  }) {
    return this.request<TransporterVehicle>('/logistics/transporter/vehicles', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateTransporterVehicle(vehicleId: string, payload: Partial<TransporterVehicle>) {
    return this.request<TransporterVehicle>(`/logistics/transporter/vehicles/${vehicleId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  async getTransportOpportunities(status?: string) {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return this.request<TransportOpportunity[]>(`/logistics/transporter/opportunities${query}`);
  }

  async getTransportOpportunityDetail(opportunityId: string) {
    return this.request<TransportOpportunityDetail>(`/logistics/transporter/opportunities/${opportunityId}`);
  }

  async acceptTransportOpportunity(opportunityId: string, payload: {
    vehicle_id: string;
    driver_name?: string;
    driver_phone?: string;
    notes?: string;
  }) {
    return this.request<TransportOpportunityDetail>(`/logistics/transporter/opportunities/${opportunityId}/accept`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async declineTransportOpportunity(opportunityId: string, payload?: { reason?: string }) {
    return this.request<TransportOpportunity>(`/logistics/transporter/opportunities/${opportunityId}/decline`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  }

  async submitTransporterQuote(opportunityId: string, payload: {
    vehicle_id?: string;
    quote_amount: number;
    quote_unit?: string;
    currency?: string;
    valid_until?: string;
    notes?: string;
  }) {
    return this.request<TransporterQuote>(`/logistics/transporter/opportunities/${opportunityId}/quotes`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getTransporterShipments() {
    return this.request<Record<string, unknown>[]>('/logistics/transporter/shipments');
  }

  async broadcastPlanOpportunities(planId: string, forceRebroadcast = false) {
    return this.request<BroadcastOpportunitiesResponse>(`/logistics/shipments/plans/${planId}/broadcast-opportunities?force_rebroadcast=${forceRebroadcast}`, {
      method: 'POST',
    });
  }

  // Phase 2H: Shipment Execution & Checkpoint Tracking
  async getShipmentExecutionDetail(shipmentId: string) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}`);
  }

  async getShipmentEvents(shipmentId: string) {
    return this.request<ShipmentEvent[]>(`/logistics/shipments/${shipmentId}/events`);
  }

  async recordCheckpointArrival(shipmentId: string, checkpointId: string, payload?: { notes?: string }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/checkpoints/${checkpointId}/arrive`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  }

  async recordCheckpointLoadingStart(shipmentId: string, checkpointId: string, payload?: { notes?: string }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/checkpoints/${checkpointId}/start-loading`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  }

  async recordCheckpointComplete(shipmentId: string, checkpointId: string, payload: {
    loaded_quantity_quintals: number;
    variance_reason?: string;
    notes?: string;
  }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/checkpoints/${checkpointId}/complete`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async recordTransitStart(shipmentId: string, payload?: { notes?: string }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/transit/start`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  }

  async recordDestinationArrival(shipmentId: string, payload?: { notes?: string }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/destination/arrive`, {
      method: 'POST',
      body: JSON.stringify(payload || {}),
    });
  }

  async recordDeliveryComplete(shipmentId: string, payload: {
    delivered_quantity_quintals: number;
    receiver_name?: string;
    variance_reason?: string;
    delivery_notes?: string;
  }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/delivery/complete`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async reportShipmentException(shipmentId: string, payload: {
    checkpoint_id?: string;
    exception_code: string;
    notes: string;
  }) {
    return this.request<ShipmentExecutionDetail>(`/logistics/shipments/${shipmentId}/exceptions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}


export const api = new ApiClient();
