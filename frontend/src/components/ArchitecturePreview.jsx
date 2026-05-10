import { Boxes, Brain, Cloud, Container, Database, Laptop, LayoutPanelTop, Lock, Monitor, Rows4, Server, UserSquare2 } from 'lucide-react';

const iconMap = {
  frontend: Monitor,
  backend: Server,
  database: Database,
  auth: Lock,
  cloud: Cloud,
  docker: Container,
  profile: Boxes,
  services: Boxes,
  os: Laptop,
  langgraph: Brain,
  roles: Lock,
  modules: Boxes,
  navigation: Rows4,
  login: LayoutPanelTop,
  experience: UserSquare2,
  admin_style: UserSquare2,
};

const labelMap = {
  profile: 'Perfil',
  os: 'Entorno',
  frontend: 'Frontend',
  backend: 'Backend',
  auth: 'Autenticación',
  database: 'Base de datos',
  cloud: 'Plataforma',
  docker: 'Contenedores',
  services: 'Microservicios',
  langgraph: 'IA / Agentes',
  roles: 'Roles',
  modules: 'Módulos',
  navigation: 'Navegación',
  login: 'Login',
  experience: 'Experiencia',
  admin_style: 'Panel admin',
};

function presentValue(key, value) {
  if (key === 'experience') {
    return value === 'admin' ? 'admin directo' : 'portal + admin';
  }
  if (key === 'login') {
    return {
      'ibm-classic': 'editorial',
      'digital-workers': 'operations console',
      'digital-buyers': 'client portal',
    }[value] || value;
  }
  if (key === 'admin_style') {
    return {
      operations: 'operations workspace',
      business: 'business control',
    }[value] || value;
  }
  return value;
}

export function ArchitecturePreview({ config }) {
  const items = [
    ['profile', config.project_profile],
    ['os', config.target_os === 'windows' ? 'Windows PowerShell' : 'macOS / Linux'],
    config.project_type !== 'api' && ['frontend', config.frontend],
    config.project_type !== 'web' && ['backend', config.backend],
    config.project_type !== 'api' && ['auth', config.auth],
    config.project_type !== 'web' && ['database', config.database],
    ['cloud', config.cloud],
    config.project_type !== 'api' && ['navigation', `${config.navigation_layout}${config.navigation_sections?.length ? ` · ${config.navigation_sections.length} apartados` : ''}`],
    config.project_type !== 'api' && config.auth !== 'none' && ['login', config.login_variant],
    config.project_type !== 'api' && ['experience', config.experience_mode],
    config.project_type !== 'api' && ['admin_style', config.admin_style],
    ['docker', config.include_docker ? `${config.containers.join(' + ')} en Docker` : 'sin docker'],
    ['modules', config.functional_modules?.length ? `${config.functional_modules.length} módulos` : 'módulos base'],
    ['roles', config.user_roles?.length ? config.user_roles.join(', ') : 'roles demo'],
    config.project_profile === 'ai' && [
      'langgraph',
      config.project_type === 'web' ? 'Modulo Agente frontend' : 'LangGraph + Gemini 2.5 Flash',
    ],
    config.project_type !== 'web' && ['services', config.service_count > 0 ? `${config.service_count} servicios` : 'sin servicios extra'],
  ].filter(Boolean);

  return (
    <aside className="preview-panel">
      <span className="eyebrow">Arquitectura</span>
      <h2>{config.project_name || 'nuevo-proyecto'}</h2>
      <p>{config.description}</p>
      <div className="architecture-flow">
        {items.map(([key, value]) => {
          const Icon = iconMap[key];
          return (
            <div className="architecture-node" key={key}>
              <Icon size={18} />
              <span>{labelMap[key] ?? key}</span>
              <strong>{presentValue(key, value)}</strong>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
