import React, { useEffect, useId, useMemo, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './ShipmentRouteMap.css';
import type { GeographicPrecision, RouteWaypoint } from '../api/client';

export interface ShipmentRouteMapProps {
  waypoints?: RouteWaypoint[];
  routeStatus?: string;
  statusSummary?: string;
  overallGeographicPrecision?: GeographicPrecision | string;
  selectedSequence?: number | null;
  onSelectWaypoint?: (sequence: number) => void;
  routeGeometry?: [number, number][] | null;
  totalDistanceKm?: number | null;
  distanceCertainty?: string;
  estimatedTransitHours?: number | null;
  transitTimeCertainty?: string;
  isOptimized?: boolean;
  optimizerName?: string;
  tileLayerUrl?: string;
  tileLayerAttribution?: string;
  height?: string | number;
  className?: string;
  readOnly?: boolean;
}

const DEFAULT_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const DEFAULT_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

const DEFAULT_CENTER: [number, number] = [19.2, 74.0]; // Maharashtra agricultural hub
const DEFAULT_ZOOM = 7;

export const ShipmentRouteMap: React.FC<ShipmentRouteMapProps> = ({
  waypoints = [],
  routeStatus = 'route_feasible',
  statusSummary,
  overallGeographicPrecision = 'exact',
  selectedSequence,
  onSelectWaypoint,
  routeGeometry,
  totalDistanceKm,
  distanceCertainty,
  estimatedTransitHours,
  transitTimeCertainty,
  isOptimized = false,
  optimizerName,
  tileLayerUrl = DEFAULT_TILE_URL,
  tileLayerAttribution = DEFAULT_ATTRIBUTION,
  height = 480,
  className = '',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const polylineLayerRef = useRef<L.LayerGroup | null>(null);
  const markersBySeqRef = useRef<Map<number, { marker: L.Marker; lat: number; lng: number }>>(new Map());

  // Split waypoints into mapped (exact GPS) and unmapped (administrative only or unavailable)
  const { mappedWaypoints, administrativeWaypoints } = useMemo(() => {
    const mapped: RouteWaypoint[] = [];
    const administrative: RouteWaypoint[] = [];

    waypoints.forEach((wp) => {
      if (
        wp.latitude != null &&
        wp.longitude != null &&
        !isNaN(Number(wp.latitude)) &&
        !isNaN(Number(wp.longitude)) &&
        wp.geographic_precision === 'exact'
      ) {
        mapped.push(wp);
      } else {
        administrative.push(wp);
      }
    });

    return { mappedWaypoints: mapped, administrativeWaypoints: administrative };
  }, [waypoints]);

  // Status Badge formatting
  const statusBadge = useMemo(() => {
    if (isOptimized || routeStatus === 'optimized_route_found') {
      return { label: 'OR-Tools Optimized', class: 'optimized' };
    }
    if (routeStatus === 'route_feasible') {
      return { label: 'Route Feasible', class: 'feasible' };
    }
    if (routeStatus === 'route_feasibility_unknown' || overallGeographicPrecision === 'administrative_only') {
      return { label: 'Modeled (Admin GPS)', class: 'warning' };
    }
    if (routeStatus === 'route_infeasible' || routeStatus === 'optimization_infeasible') {
      return { label: 'Route Infeasible', class: 'infeasible' };
    }
    return { label: routeStatus.replace(/_/g, ' '), class: 'warning' };
  }, [routeStatus, isOptimized, overallGeographicPrecision]);

  // Initialize Leaflet Map Instance
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: DEFAULT_CENTER,
        zoom: DEFAULT_ZOOM,
        scrollWheelZoom: true,
        attributionControl: true,
      });

      L.tileLayer(tileLayerUrl, {
        attribution: tileLayerAttribution,
        maxZoom: 19,
      }).addTo(map);

      const markersLayer = L.layerGroup().addTo(map);
      const polylineLayer = L.layerGroup().addTo(map);

      mapInstanceRef.current = map;
      markersLayerRef.current = markersLayer;
      polylineLayerRef.current = polylineLayer;
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markersLayerRef.current = null;
        polylineLayerRef.current = null;
      }
    };
  }, [tileLayerUrl, tileLayerAttribution]);

  // Update Markers and Polyline when waypoints change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersLayer = markersLayerRef.current;
    const polylineLayer = polylineLayerRef.current;
    if (!map || !markersLayer || !polylineLayer) return;

    markersLayer.clearLayers();
    polylineLayer.clearLayers();
    markersBySeqRef.current.clear();

    const bounds = L.latLngBounds([]);
    const lineCoordinates: [number, number][] = [];

    mappedWaypoints.forEach((wp) => {
      const lat = Number(wp.latitude);
      const lng = Number(wp.longitude);
      const isPickup = wp.waypoint_type === 'pickup';
      const isSelected = selectedSequence === wp.waypoint_sequence;

      const markerClass = `custom-route-marker ${isPickup ? 'pickup' : 'destination'} ${
        isSelected ? 'selected' : ''
      }`;
      const markerText = isPickup ? `${wp.waypoint_sequence}` : '🎯';

      const customIcon = L.divIcon({
        className: markerClass,
        html: `<span>${markerText}</span>`,
        iconSize: isPickup ? [32, 32] : [36, 36],
        iconAnchor: isPickup ? [16, 16] : [18, 18],
        popupAnchor: [0, -18],
      });

      const marker = L.marker([lat, lng], { icon: customIcon }).addTo(markersLayer);

      // Construct structured popup content
      const popupHtml = `
        <div class="route-popup-card">
          <div class="route-popup-header">
            <span class="route-popup-type-tag ${isPickup ? 'pickup' : 'destination'}">
              ${isPickup ? `Pickup Stop #${wp.waypoint_sequence}` : `Destination Terminal`}
            </span>
          </div>
          <div class="route-popup-entity-name">${wp.seller_name || wp.location_name}</div>
          <div class="route-popup-location">📍 ${[wp.taluka, wp.district, wp.state].filter(Boolean).join(', ')}</div>
          
          <div class="route-popup-row">
            <span class="route-popup-label">Stop Cargo:</span>
            <span class="route-popup-value">${wp.stop_cargo_quantity_quintals} qtl (${wp.stop_cargo_quantity_tonnes} MT)</span>
          </div>
          <div class="route-popup-row">
            <span class="route-popup-label">On-board Total:</span>
            <span class="route-popup-value">${wp.cumulative_onboard_quantity_quintals} qtl</span>
          </div>
          ${
            wp.earliest_arrival
              ? `<div class="route-popup-row"><span class="route-popup-label">Pickup Window:</span><span class="route-popup-value">${wp.earliest_arrival}</span></div>`
              : ''
          }
          <div class="route-popup-precision-badge ${wp.geographic_precision}">
            ${wp.geographic_precision === 'exact' ? '✓ Verified GPS Coordinates' : '⚠ Administrative Boundary'}
          </div>
        </div>
      `;

      marker.bindPopup(popupHtml, { closeButton: false, offset: [0, -8] });

      marker.on('click', () => {
        if (onSelectWaypoint) {
          onSelectWaypoint(wp.waypoint_sequence);
        }
      });

      markersBySeqRef.current.set(wp.waypoint_sequence, { marker, lat, lng });
      bounds.extend([lat, lng]);
      lineCoordinates.push([lat, lng]);
    });

    // Render Route Polyline
    const pathCoords = routeGeometry && routeGeometry.length > 1 ? routeGeometry : lineCoordinates;

    if (pathCoords.length > 1) {
      const isModeled =
        distanceCertainty === 'MODELED_GEOGRAPHIC_DISTANCE' ||
        isOptimized ||
        overallGeographicPrecision !== 'exact';

      L.polyline(pathCoords, {
        color: isModeled ? '#4f46e5' : '#2563eb',
        weight: 4,
        opacity: 0.85,
        dashArray: isModeled ? '7, 8' : undefined,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(polylineLayer);
    }

    // Auto-fit map bounds
    if (mappedWaypoints.length > 1) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
    } else if (mappedWaypoints.length === 1) {
      map.setView([Number(mappedWaypoints[0].latitude), Number(mappedWaypoints[0].longitude)], 11);
    } else {
      map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    }
  }, [mappedWaypoints, routeGeometry, selectedSequence, onSelectWaypoint, distanceCertainty, isOptimized, overallGeographicPrecision]);

  // Handle programmatic selectedSequence pan
  useEffect(() => {
    if (selectedSequence == null || !mapInstanceRef.current) return;
    const entry = markersBySeqRef.current.get(selectedSequence);
    if (entry) {
      mapInstanceRef.current.panTo([entry.lat, entry.lng], { animate: true, duration: 0.5 });
      entry.marker.openPopup();
    }
  }, [selectedSequence]);

  const mapHeightStyle = typeof height === 'number' ? `${height}px` : height;
  const containerId = useId();

  return (
    <div className={`shipment-route-map-container ${className}`}>
      {/* Header Bar */}
      <div className="route-map-header">
        <div className="route-map-title-area">
          <h4 className="route-map-title">
            <span>🗺️</span> Planned Multi-Stop Route Itinerary
          </h4>
          <span className={`route-map-status-badge ${statusBadge.class}`}>{statusBadge.label}</span>
        </div>

        {/* Metrics Summary */}
        <div className="route-map-metrics">
          {totalDistanceKm != null && (
            <div className="route-metric-item">
              <span className="route-metric-label">Estimated Distance</span>
              <span className="route-metric-value">{Number(totalDistanceKm).toFixed(1)} km</span>
              <span className="route-metric-subtext">
                {distanceCertainty === 'VERIFIED_ROAD_DISTANCE' ? 'Verified Road Network' : 'Modeled Road Estimate'}
              </span>
            </div>
          )}

          {estimatedTransitHours != null && (
            <div className="route-metric-item">
              <span className="route-metric-label">Estimated Travel Time</span>
              <span className="route-metric-value">{Number(estimatedTransitHours).toFixed(1)} hrs</span>
              <span className="route-metric-subtext">
                {transitTimeCertainty === 'VERIFIED_ROAD_TIME' ? 'Verified Transit' : 'Modeled Transit'}
              </span>
            </div>
          )}

          {isOptimized && optimizerName && (
            <div className="route-metric-item">
              <span className="route-metric-label">Route Optimizer</span>
              <span className="route-metric-value" style={{ color: '#2563eb' }}>
                {optimizerName}
              </span>
              <span className="route-metric-subtext">Guided Local Search VRP</span>
            </div>
          )}
        </div>
      </div>

      {/* Map Canvas */}
      <div className="route-map-wrapper" style={{ height: mapHeightStyle }}>
        <div id={containerId} ref={mapContainerRef} className="route-map-canvas" />
      </div>

      {/* Administrative-only Notice (Zero Fabricated Coordinates) */}
      {administrativeWaypoints.length > 0 && (
        <div className="route-map-administrative-panel">
          <div className="route-map-administrative-title">
            <span>⚠️</span>
            <span>
              {administrativeWaypoints.length} stop{administrativeWaypoints.length > 1 ? 's rely' : ' relies'} on
              administrative boundaries (Exact GPS coordinates pending verification):
            </span>
          </div>
          <div className="route-map-administrative-list">
            {administrativeWaypoints.map((wp) => (
              <span key={wp.waypoint_sequence} className="route-map-admin-tag">
                #{wp.waypoint_sequence} {wp.seller_name || wp.location_name} (
                {[wp.taluka, wp.district].filter(Boolean).join(', ') || 'Regional'})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Modeled Transparency Disclaimer */}
      <div className="route-map-disclaimer-banner">
        <div className="route-map-disclaimer-text">
          <span>ℹ️</span>
          <span>
            {statusSummary ||
              'Modeled route representation based on deterministic waypoint sequence and road terrain factor (1.25×). Live driver GPS tracking and real-time turn-by-turn navigation are deferred to execution.'}
          </span>
        </div>
        <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>OpenStreetMap standard tiles</span>
      </div>
    </div>
  );
};
