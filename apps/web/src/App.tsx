import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { LandingView } from './views/LandingView';
import { MarketplaceView } from './views/MarketplaceView';
import { ProduceDetailView } from './views/ProduceDetailView';
import { CreateProduceLotView } from './views/CreateProduceLotView';
import { BuyerRequirementsView } from './views/BuyerRequirementsView';
import { CreateRequirementView } from './views/CreateRequirementView';
import { OffersView } from './views/OffersView';
import { OrdersView } from './views/OrdersView';
import { FarmerDashboardView } from './views/FarmerDashboardView';
import { BuyerDashboardView } from './views/BuyerDashboardView';
import { FPODashboardView } from './views/FPODashboardView';
import { AdminDashboardView } from './views/AdminDashboardView';
import { ProfileView } from './views/ProfileView';
import { LoginView } from './views/LoginView';
import { RegisterView } from './views/RegisterView';
import { RecommendationView } from './views/RecommendationView';
import { LogisticsRouteView } from './views/LogisticsRouteView';
import { TransporterDashboardView } from './views/TransporterDashboardView';
import { DesignSystemShowcaseView } from './views/DesignSystemShowcaseView';

interface RouteState {

  view: string;
  params?: Record<string, unknown>;
}

const getInitialView = (): string => {
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const viewParam = params.get('view');
    if (viewParam) return viewParam;
    if (window.location.hash) {
      return window.location.hash.replace('#', '');
    }
  }
  return 'landing';
};

const MainRouter: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [route, setRoute] = useState<RouteState>({ view: getInitialView() });

  useEffect(() => {
    const handleHashChange = () => {
      if (typeof window !== 'undefined' && window.location.hash) {
        const view = window.location.hash.replace('#', '');
        if (view) {
          setRoute((prev) => (prev.view === view ? prev : { view }));
        }
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (view: string, params?: Record<string, unknown>) => {
    setRoute({ view, params });
    if (typeof window !== 'undefined') {
      window.location.hash = view === 'landing' ? '' : `#${view}`;
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (isLoading) {
    return (
      <div className="global-loading-screen">
        <div className="loading-content">
          <div className="loading-logo">🌱</div>
          <h2>AgriMandi</h2>
          <p>Connecting agricultural markets...</p>
        </div>
      </div>
    );
  }

  const renderCurrentView = () => {
    switch (route.view) {
      case 'landing':
        return <LandingView onNavigate={navigate} />;
      case 'marketplace':
        return (
          <MarketplaceView
            initialCategory={typeof route.params?.category === 'string' ? route.params.category : undefined}
            onNavigate={navigate}
          />
        );
      case 'produce-detail':
        return (
          <ProduceDetailView
            lotId={typeof route.params?.lotId === 'string' ? route.params.lotId : ''}
            onNavigate={navigate}
          />
        );
      case 'create-lot':
        return isAuthenticated ? (
          <CreateProduceLotView onNavigate={navigate} />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'requirements':
        return <BuyerRequirementsView onNavigate={navigate} />;
      case 'create-requirement':
        return isAuthenticated ? (
          <CreateRequirementView onNavigate={navigate} />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'offers':
        return isAuthenticated ? (
          <OffersView
            initialLotId={typeof route.params?.lotId === 'string' ? route.params.lotId : undefined}
            onNavigate={navigate}
          />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'orders':
        return isAuthenticated ? <OrdersView onNavigate={navigate} /> : <LoginView onNavigate={navigate} />;
      case 'farmer-dashboard':
        return isAuthenticated ? (
          <FarmerDashboardView onNavigate={navigate} />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'recommendation':
        return isAuthenticated ? (
          <RecommendationView
            initialLotId={typeof route.params?.lotId === 'string' ? route.params.lotId : undefined}
            onNavigate={navigate}
          />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'buyer-dashboard':

        return isAuthenticated ? (
          <BuyerDashboardView onNavigate={navigate} />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'fpo-dashboard':
        return isAuthenticated ? (
          <FPODashboardView onNavigate={navigate} />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'admin':
        return isAuthenticated && user?.roles.includes('admin') ? (
          <AdminDashboardView onNavigate={navigate} />
        ) : (
          <LandingView onNavigate={navigate} />
        );
      case 'transporter-dashboard':
      case 'transporter-opportunities':
      case 'transporter-opportunity':
      case 'transporter-vehicles':
        return isAuthenticated ? (
          <TransporterDashboardView
            initialOpportunityId={typeof route.params?.opportunityId === 'string' ? route.params.opportunityId : undefined}
            initialShipmentId={typeof route.params?.shipmentId === 'string' ? route.params.shipmentId : undefined}
            onNavigate={navigate}
          />
        ) : (
          <LoginView onNavigate={navigate} />
        );
      case 'profile':
        return isAuthenticated ? <ProfileView onNavigate={navigate} /> : <LoginView onNavigate={navigate} />;
      case 'login':
        return <LoginView onNavigate={navigate} />;
      case 'logistics-route':
        return (
          <LogisticsRouteView
            initialPlanId={typeof route.params?.planId === 'string' ? route.params.planId : undefined}
            onNavigate={navigate}
          />
        );
      case 'register':
        return (
          <RegisterView
            initialRole={
              typeof route.params?.role === 'string' &&
              ['farmer', 'fpo', 'buyer', 'transporter'].includes(route.params.role)
                ? (route.params.role as 'farmer' | 'fpo' | 'buyer' | 'transporter')
                : undefined
            }
            onNavigate={navigate}
          />
        );
      case 'design-system':
        return <DesignSystemShowcaseView onNavigate={navigate} />;
      default:
        return <LandingView onNavigate={navigate} />;
    }
  };

  return (
    <div className="app-layout">
      <Navbar currentView={route.view} onNavigate={navigate} />
      <main className="app-main-content">{renderCurrentView()}</main>
      <Footer />
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <MainRouter />
    </AuthProvider>
  );
}
