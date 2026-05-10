import { Boxes, Brain, Cloud, Container, Database, Laptop, Lock, Monitor, Server } from 'lucide-react';

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
};

export function ArchitecturePreview({ config }) {
  const items = [
    ['profile', config.project_profile],
    ['os', config.target_os === 'windows' ? 'Windows PowerShell' : 'macOS / Linux'],
    config.project_type !== 'api' && ['frontend', config.frontend],
    config.project_type !== 'web' && ['backend', config.backend],
    config.project_type !== 'api' && ['auth', config.auth],
    config.project_type !== 'web' && ['database', config.database],
    ['cloud', config.cloud],
    ['docker', config.include_docker ? `${config.containers.join(' + ')} en Docker` : 'sin docker'],
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
              <strong>{value}</strong>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
