import { Activity, BarChart3, Bell, Bot, Building2, ChevronDown, Cloud, Database, FolderKanban, Layers, LayoutDashboard, LogIn, Menu, Monitor, Search, Settings, ShieldCheck, Sparkles, UserPlus, Users, Workflow } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import ibmLogo from '../assets/brand/ibm-logo.png';

function toTitle(value = '') {
  return String(value)
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function slugify(value = '') {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function getRoles(config) {
  return config.user_roles?.length ? config.user_roles : [config.experience_mode === 'admin' ? 'administrador' : 'usuario'];
}

function getCustomSections(config) {
  return Array.from(new Set((config.navigation_sections || []).map(slugify).filter(Boolean))).slice(0, 8);
}

function getServiceItems(config, modules) {
  if (!config.include_services || !config.service_count || config.project_type === 'web') {
    return [];
  }

  return Array.from({ length: config.service_count }, (_, index) => {
    const module = modules[index];
    const isAgent = config.project_profile === 'ai' && index === 0;
    const key = isAgent ? 'service-agent' : `service-${index + 1}`;
    const label = isAgent
      ? 'Agent service'
      : module
        ? `${toTitle(module)} service`
        : `Service ${index + 1}`;
    return { key, label, Icon: Workflow, kind: 'service' };
  });
}

function iconForKey(key) {
  if (key === 'workspace') return LayoutDashboard;
  if (key === 'dashboard') return BarChart3;
  if (key === 'settings') return Settings;
  if (key === 'agente') return Bot;
  if (key.includes('cliente') || key.includes('user')) return Users;
  if (key.includes('notifica') || key.includes('alert')) return Bell;
  if (key.includes('reporte') || key.includes('analytics')) return BarChart3;
  return FolderKanban;
}

function getFlowLabel(flow) {
  return flow === 'admin' ? 'Admin directo' : 'Portal + admin';
}

export function LiveProjectPreview({ config, source = 'manual' }) {
  const hasFrontend = config.project_type !== 'api';
  const roles = useMemo(() => getRoles(config), [config]);
  const customSections = useMemo(() => getCustomSections(config), [config]);
  const serviceItems = useMemo(() => getServiceItems(config, customSections), [config, customSections]);
  const appEntryView = config.experience_mode === 'admin' ? 'dashboard' : 'workspace';
  const [view, setView] = useState(config.auth === 'none' ? appEntryView : 'login');
  const showAuth = hasFrontend && config.auth !== 'none';

  useEffect(() => {
    const validViews = new Set([
      ...(showAuth ? ['login', 'register'] : []),
      'workspace',
      'dashboard',
      'settings',
      ...customSections,
      ...serviceItems.map((item) => item.key),
    ]);

    if (!validViews.has(view)) {
      setView(showAuth ? 'login' : appEntryView);
    }
  }, [appEntryView, customSections, serviceItems, showAuth, view]);

  if (!hasFrontend) {
    return null;
  }

  const navItems = [
    { key: 'workspace', label: config.experience_mode === 'admin' ? 'Workspace' : 'Inicio', Icon: LayoutDashboard, kind: 'core' },
    { key: 'dashboard', label: config.experience_mode === 'admin' ? 'Panel admin' : 'Administración', Icon: BarChart3, kind: 'core' },
    ...customSections.map((section) => ({
      key: section,
      label: toTitle(section),
      Icon: iconForKey(section),
      kind: 'section',
    })),
    ...serviceItems,
    { key: 'settings', label: 'Settings', Icon: Settings, kind: 'core' },
  ];

  function enterApp() {
    setView(appEntryView);
  }

  return (
    <section className="live-preview-shell" aria-label="Vista previa visual">
      <div className="live-preview-heading">
        <div>
          <span className="eyebrow">{source === 'ai' ? 'Live review IA' : 'Live review'}</span>
          <h2>Vista previa navegable</h2>
          <p>Simulación visual basada en la configuración actual. Refleja navegación, acceso y estructura del MVP que se generará.</p>
        </div>
        <div className="live-preview-status">
          <span>{config.navigation_layout} · {getFlowLabel(config.experience_mode)}</span>
          <strong>{config.project_name}</strong>
        </div>
      </div>

      <div className="live-preview-frame">
        <div className="preview-browser-bar">
          <span />
          <span />
          <span />
          <strong>{config.project_name}.preview.local</strong>
        </div>

        <div className="preview-screen-sizer">
          {(view === 'login' || view === 'register') && showAuth ? (
            <AuthPreview
              config={config}
              mode={view}
              onContinue={enterApp}
              onSwitch={() => setView(view === 'login' ? 'register' : 'login')}
            />
          ) : (
            <AppPreview
              config={config}
              customSections={customSections}
              navItems={navItems}
              roles={roles}
              serviceItems={serviceItems}
              setView={setView}
              view={view}
            />
          )}
        </div>
      </div>
    </section>
  );
}

function AuthPreview({ config, mode, onContinue, onSwitch }) {
  const isRegister = mode === 'register';
  const variant = config.login_variant || 'ibm-classic';

  if (variant === 'digital-workers') {
    return (
      <div className="preview-auth-screen preview-auth-screen--workers">
        <section className="preview-workers-stage">
          <div className="preview-workers-logo-box">
            <img src={ibmLogo} alt="IBM" />
          </div>
          <div className="preview-workers-brand-copy">
            <h3>IBM Operations Console</h3>
            <p className="preview-workers-inline">
              <Sparkles size={14} />
              Agentes, operaciones y flujos empresariales
            </p>
          </div>
        </section>

        <form className="preview-workers-form" onSubmit={(event) => { event.preventDefault(); onContinue(); }}>
          <div className="preview-workers-heading">
            {isRegister ? <UserPlus size={18} /> : <LogIn size={18} />}
            <div>
              <strong>{isRegister ? 'Crear acceso corporativo' : 'Ingresar al workspace'}</strong>
              <span>{config.auth === 'firebase' ? 'IBM SSO / Firebase Auth' : 'IBM SSO / Supabase Auth'}</span>
            </div>
          </div>
          <label>
            <span>Email corporativo</span>
            <input readOnly value="usuario@ibm.com" />
          </label>
          <label>
            <span>Password</span>
            <input readOnly type="password" value="password123" />
          </label>
          <button type="submit">{isRegister ? 'Crear cuenta y continuar' : 'Continuar'}</button>
          <button className="preview-link-button" type="button" onClick={onSwitch}>
            {isRegister ? 'Ya tengo acceso' : 'Registrarme'}
          </button>
        </form>
      </div>
    );
  }

  if (variant === 'digital-buyers') {
    return (
      <div className="preview-auth-screen preview-auth-screen--buyers">
        <div className="preview-buyers-panel">
          <div className="preview-buyers-hero">
            <img src={ibmLogo} alt="IBM" />
            <span className="eyebrow">Client portal</span>
            <h3>{config.project_name}</h3>
            <p>Un flujo más comercial y liviano para clientes, onboarding y autoservicio.</p>
          </div>
          <form className="preview-buyers-form" onSubmit={(event) => { event.preventDefault(); onContinue(); }}>
            <div className="preview-auth-title">
              {isRegister ? <UserPlus size={20} /> : <LogIn size={20} />}
              <h4>{isRegister ? 'Crear cuenta' : 'Acceder'}</h4>
            </div>
            {isRegister && (
              <label>
                <span>Nombre</span>
                <input readOnly value="Cliente demo" />
              </label>
            )}
            <label>
              <span>Email</span>
              <input readOnly value="cliente@empresa.com" />
            </label>
            <label>
              <span>Password</span>
              <input readOnly type="password" value="password123" />
            </label>
            <button type="submit">{isRegister ? 'Crear cuenta y continuar' : 'Continuar'}</button>
            <button className="preview-link-button" type="button" onClick={onSwitch}>
              {isRegister ? 'Ya tengo cuenta' : 'Registrarme'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="preview-auth-screen preview-auth-screen--ibm">
      <div className="preview-auth-brand">
        <img className="preview-ibm-logo" src={ibmLogo} alt="IBM" />
        <span className="eyebrow">{config.project_profile}</span>
        <h3>{config.project_name}</h3>
        <p>{config.description}</p>
      </div>
      <form className="preview-auth-panel" onSubmit={(event) => { event.preventDefault(); onContinue(); }}>
        <div className="preview-auth-title">
          {isRegister ? <UserPlus size={20} /> : <LogIn size={20} />}
          <h4>{isRegister ? 'Crear cuenta' : 'Iniciar sesión'}</h4>
        </div>
        {isRegister && (
          <label>
            <span>Nombre</span>
            <input readOnly value="Usuario demo" />
          </label>
        )}
        <label>
          <span>Email</span>
          <input readOnly value="demo@example.com" />
        </label>
        <label>
          <span>Password</span>
          <input readOnly type="password" value="password123" />
        </label>
        <button type="submit">{isRegister ? 'Crear cuenta y continuar' : 'Continuar'}</button>
        <button className="preview-link-button" type="button" onClick={onSwitch}>
          {isRegister ? 'Ya tengo una cuenta' : 'Registrarme'}
        </button>
      </form>
    </div>
  );
}

function AppPreview({ config, customSections, navItems, roles, serviceItems, setView, view }) {
  const isNavbar = config.navigation_layout === 'navbar';
  const activeSection = customSections.includes(view) ? view : customSections[0];
  const activeService = serviceItems.find((item) => item.key === view);

  return (
    <div className={`preview-app-screen preview-app-screen--${config.navigation_layout} preview-app-screen--${config.experience_mode} preview-app-screen--${config.admin_style}`}>
      {isNavbar ? (
        <PreviewNavbar config={config} navItems={navItems} setView={setView} view={view} />
      ) : (
        <PreviewSidebar config={config} navItems={navItems} roles={roles} setView={setView} view={view} />
      )}

      <main className="preview-app-main">
        {!isNavbar && (
          <header className="preview-app-header">
            <div>
              <span className="eyebrow">{view === 'settings' ? 'Configuración' : config.experience_mode === 'admin' ? 'Acceso directo al panel' : 'Portal con acceso admin'}</span>
              <h3>{getViewTitle(view, activeSection, config.experience_mode)}</h3>
            </div>
            <div className="preview-user-pill">
              <Users size={16} />
              {roles[0] || 'usuario'}
            </div>
          </header>
        )}

        {view === 'settings' ? (
          <BlankSectionPreview title="Settings" eyebrow="Configuración" />
        ) : customSections.includes(view) ? (
          <BlankSectionPreview title={toTitle(view)} eyebrow="Apartado" />
        ) : activeService ? (
          <BlankSectionPreview title={activeService.label} eyebrow="Service navigation" />
        ) : (
          <WorkspacePreview
            activeSection={activeSection}
            config={config}
            customSections={customSections}
            roles={roles}
            serviceItems={serviceItems}
            setView={setView}
            view={view}
          />
        )}
      </main>
    </div>
  );
}

function PreviewSidebar({ config, navItems, roles, setView, view }) {
  return (
    <aside className="preview-app-sidebar">
      <div className="preview-sidebar-brand">
        <img src={ibmLogo} alt="IBM" />
        <div>
          <span className="eyebrow">{getFlowLabel(config.experience_mode)}</span>
          <strong>{config.project_name}</strong>
        </div>
      </div>
      <nav>
        {navItems.map(({ key, label, Icon, kind }) => (
          <button className={view === key ? 'active' : ''} key={key} type="button" onClick={() => setView(key)}>
            <Icon size={16} />
            {label}
            {kind === 'section' && <small>nuevo</small>}
            {kind === 'service' && <small>svc</small>}
          </button>
        ))}
      </nav>
      <div className="preview-sidebar-footer">
        <div className="preview-sidebar-avatar">{(roles[0] || 'u').slice(0, 2).toUpperCase()}</div>
        <div>
          <strong>{toTitle(roles[0] || 'usuario')}</strong>
          <span>ibm.com</span>
        </div>
      </div>
    </aside>
  );
}

function PreviewNavbar({ config, navItems, setView, view }) {
  const [isOpen, setIsOpen] = useState(false);
  const visibleItems = navItems.slice(0, 5);
  const hiddenItems = navItems.slice(5);

  return (
    <div className="preview-navbar-shell">
      <header className="preview-navbar">
        <div className="preview-navbar-brand">
          <img src={ibmLogo} alt="IBM" />
          <div>
            <strong>{config.project_name}</strong>
            <span>{getFlowLabel(config.experience_mode)}</span>
          </div>
        </div>
        <nav>
          {visibleItems.map(({ key, label }) => (
            <button className={view === key ? 'active' : ''} key={key} type="button" onClick={() => setView(key)}>
              {label}
            </button>
          ))}
          {hiddenItems.length > 0 && (
            <div className="preview-navbar-overflow">
              <button className={isOpen ? 'active' : ''} type="button" onClick={() => setIsOpen((current) => !current)}>
                Más
                <ChevronDown size={14} />
              </button>
              {isOpen && (
                <div className="preview-navbar-dropdown">
                  {hiddenItems.map(({ key, label }) => (
                    <button key={key} type="button" onClick={() => { setView(key); setIsOpen(false); }}>
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </nav>
        <div className="preview-navbar-tools">
          <button type="button" aria-label="Buscar"><Search size={16} /></button>
          <button type="button" aria-label="Menú"><Menu size={16} /></button>
        </div>
      </header>
      <header className="preview-app-header preview-app-header--navbar">
        <div>
          <span className="eyebrow">{config.cloud === 'local' ? 'Local preview' : `Deploy ${config.cloud}`}</span>
          <h3>{getViewTitle(view, null, config.experience_mode)}</h3>
        </div>
        <div className="preview-user-pill">
          <Users size={16} />
          {getFlowLabel(config.experience_mode)}
        </div>
      </header>
    </div>
  );
}

function getViewTitle(view, activeSection, experienceMode) {
  if (view === 'settings') return 'Settings';
  if (String(view).startsWith('service-')) return 'Service runtime';
  if (view === 'dashboard') return experienceMode === 'admin' ? 'Panel admin' : 'Administración';
  if (view === 'workspace') return 'Workspace';
  if (view === activeSection) return toTitle(activeSection);
  return toTitle(view);
}

function WorkspacePreview({ activeSection, config, customSections, roles, serviceItems, setView, view }) {
  const cards = [
    ['Estado API', config.project_type === 'web' ? 'frontend-only' : 'ready', Activity],
    ['Backend', config.project_type === 'web' ? 'no requerido' : config.backend, Monitor],
    ['Datos', config.project_type === 'web' ? 'none' : config.database, Database],
    ['Acceso', config.auth === 'none' ? 'sin autenticación' : config.auth, ShieldCheck],
  ];

  const heroTitle = view === 'dashboard'
    ? config.experience_mode === 'admin' ? 'Centro de operación y gobierno' : 'Portal principal'
    : customSections.includes(view)
      ? `Sección ${toTitle(activeSection)}`
      : 'Workspace';

  const heroText = customSections.includes(view)
    ? `Vista base preparada para el apartado ${toTitle(activeSection)}. Se generará como una ruta editable dentro del MVP.`
    : config.experience_mode === 'admin'
      ? 'Layout orientado a decisiones, métricas y accesos internos del equipo administrador.'
      : 'Layout centrado en tareas de usuario final, navegación más liviana y acciones directas.';

  return (
    <div className="preview-content-stack">
      <section className="preview-hero-panel">
        <span>{config.navigation_layout === 'navbar' ? 'Navbar layout' : 'Sidebar layout'}</span>
        <h4>{heroTitle}</h4>
        <p>{heroText}</p>
      </section>

      <div className="preview-metric-grid">
        {cards.map(([label, value, Icon]) => (
          <article key={label}>
            <Icon size={18} />
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>

      {config.experience_mode === 'admin' ? (
        <AdminSurface config={config} roles={roles} setView={setView} />
      ) : (
        <section className="preview-user-feature-row">
          {customSections.slice(0, 3).map((item) => (
            <button key={item} type="button" onClick={() => setView(item)}>
              <span>{toTitle(item)}</span>
              <strong>Entrar</strong>
            </button>
          ))}
          <button type="button" onClick={() => setView('dashboard')}>
            <span>Administración</span>
            <strong>Abrir panel</strong>
          </button>
        </section>
      )}

      {serviceItems.length > 0 && (
        <section className="preview-service-row">
          {serviceItems.map((service) => (
            <button key={service.key} type="button" onClick={() => setView(service.key)}>
              <Workflow size={16} />
              <span>Servicio</span>
              <strong>{service.label}</strong>
            </button>
          ))}
        </section>
      )}

      {customSections.length > 0 && (
        <section className="preview-module-grid">
          {customSections.map((item) => (
            <button className={item === activeSection ? 'active' : ''} key={item} type="button" onClick={() => setView(item)}>
              {item === 'agente' ? <Bot size={17} /> : <FolderKanban size={17} />}
              <span>Apartado</span>
              <strong>{toTitle(item)}</strong>
              <p>Ruta visual incluida en la navegación del proyecto.</p>
            </button>
          ))}
        </section>
      )}

      <div className="preview-role-row">
        {roles.map((role) => <span key={role}>{toTitle(role)}</span>)}
      </div>
    </div>
  );
}

function AdminSurface({ config, roles, setView }) {
  const adminSections = config.admin_style === 'operations'
    ? [
      ['overview', 'Overview', 'Estado general del runtime y del equipo.'],
      ['users', 'Usuarios', 'Accesos, permisos y gestión de cuentas.'],
      ['workers', 'Workers', 'Automatizaciones, agentes y flujos activos.'],
      ['settings', 'Configuración', 'Parámetros del entorno y del despliegue.'],
    ]
    : [
      ['overview', 'Business overview', 'Indicadores ejecutivos y seguimiento general.'],
      ['reports', 'Reportes', 'KPIs, exportables y tableros de seguimiento.'],
      ['clients', 'Accesos', 'Personas, equipos y permisos del portal.'],
      ['settings', 'Configuración', 'Políticas, catálogos y parámetros del sistema.'],
    ];

  return (
    <section className={`preview-admin-surface preview-admin-surface--${config.admin_style}`}>
      <div className="preview-admin-nav">
        {adminSections.map(([key, label]) => (
          <button key={key} type="button" onClick={() => key === 'settings' ? setView('settings') : undefined}>
            {label}
          </button>
        ))}
      </div>
      <div className="preview-admin-grid">
        <article>
          <Building2 size={18} />
          <span>Equipo</span>
          <strong>{roles.length} roles base</strong>
          <p>Accesos listos para gobierno, permisos y administración operacional.</p>
        </article>
        <article>
          <Cloud size={18} />
          <span>Despliegue</span>
          <strong>{config.cloud}</strong>
          <p>El resumen técnico se adapta a la nube y a los contenedores elegidos.</p>
        </article>
        <article>
          <Layers size={18} />
          <span>Estilo</span>
          <strong>{config.admin_style === 'operations' ? 'Operations workspace' : 'Business control'}</strong>
          <p>El panel cambia su lenguaje visual y su estructura según el estilo elegido.</p>
        </article>
      </div>
    </section>
  );
}

function BlankSectionPreview({ eyebrow = 'Apartado', title }) {
  return (
    <div className="preview-blank-surface">
      <div className="preview-blank-mark">
        <img src={ibmLogo} alt="IBM" />
      </div>
      <span className="eyebrow">{eyebrow}</span>
      <h4>{title}</h4>
    </div>
  );
}
