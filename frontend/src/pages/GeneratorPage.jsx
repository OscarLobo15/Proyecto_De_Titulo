import { ArrowLeft, ArrowRight, BrainCircuit, Clipboard, Globe, Loader2, MessageSquare, PackageCheck, Search, User } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ibmLogo from '../assets/brand/ibm-logo.png';
import { ArchitecturePreview } from '../components/ArchitecturePreview.jsx';
import { OptionCard } from '../components/OptionCard.jsx';
import { generateProject, generateProjectWithAI, getOptions } from '../services/api.js';

const initialConfig = {
  project_name: 'mi-proyecto-base',
  description: 'Plataforma de gestión empresarial con arquitectura estandarizada IBM Consulting.',
  project_type: 'fullstack',
  project_profile: 'standard',
  frontend: 'react',
  backend: 'fastapi',
  auth: 'firebase',
  database: 'postgresql',
  cloud: 'local',
  containers: ['frontend', 'backend'],
  include_docker: true,
  include_dev_script: true,
  include_services: false,
  include_langgraph: false,
  service_count: 0,
  target_os: 'mac',
  pages: ['login', 'workspace', 'settings', 'not-found'],
  functional_modules: ['operaciones', 'usuarios', 'reportes'],
  user_roles: [],
};

const steps = ['Proyecto', 'Stack', 'Servicios', 'Entrega'];

function normalizeConfig(nextConfig) {
  let normalized = { ...nextConfig };

  if (normalized.project_profile === 'ai' && normalized.project_type !== 'web') {
    normalized.include_langgraph = true;
  }

  if (normalized.project_type === 'web') {
    normalized = {
      ...nextConfig,
      database: 'none',
      containers: ['frontend'],
      include_services: false,
      include_langgraph: false,
      service_count: 0,
    };
  }

  if (normalized.project_type === 'api') {
    const apiContainers = normalized.containers.filter((item) => ['backend', 'services'].includes(item));
    normalized = {
      ...normalized,
      containers: apiContainers.includes('backend') ? apiContainers : ['backend', ...apiContainers],
      pages: [],
    };
  }

  if (normalized.project_type === 'fullstack') {
    normalized.containers = Array.from(new Set(['frontend', 'backend', ...normalized.containers.filter((item) => item !== 'services')]));
  }

  if (normalized.project_profile === 'microservices' && normalized.project_type !== 'web') {
    normalized.include_services = true;
    normalized.service_count = Math.max(normalized.service_count, 2);
    normalized.containers = Array.from(new Set([...normalized.containers, 'services']));
  } else if (normalized.service_count > 0 && normalized.project_type !== 'web') {
    normalized.include_services = true;
    normalized.containers = Array.from(new Set([...normalized.containers, 'services']));
  } else {
    normalized.include_services = false;
    normalized.service_count = 0;
    normalized.containers = normalized.containers.filter((item) => item !== 'services');
  }

  if (normalized.auth === 'none') {
    normalized.pages = normalized.pages.filter((page) => page !== 'login');
  } else if (normalized.project_type !== 'api' && !normalized.pages.includes('login')) {
    normalized.pages = [...normalized.pages, 'login'];
  }

  return normalized;
}

export function GeneratorPage() {
  const [options, setOptions] = useState(null);
  const [config, setConfig] = useState(initialConfig);
  const [mode, setMode] = useState('ai');
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [aiMessage, setAiMessage] = useState('');
  const [aiProjectName, setAiProjectName] = useState(initialConfig.project_name);
  const [aiStatus, setAiStatus] = useState('idle');
  const [aiError, setAiError] = useState('');
  const [aiResult, setAiResult] = useState(null);
  const modeBarRef = useRef(null);
  const manualScrollPendingRef = useRef(false);

  useEffect(() => {
    getOptions()
      .then(setOptions)
      .catch(() => setError('No fue posible establecer conexión con el servidor. Verifique que el servicio esté disponible en el entorno de desarrollo.'));
  }, []);

  useEffect(() => {
    if (mode !== 'manual' || !manualScrollPendingRef.current) return;
    manualScrollPendingRef.current = false;
    scrollToManualStart();
  }, [mode, step]);

  const canGoNext = useMemo(() => config.project_name.trim().length >= 3, [config.project_name]);

  function updateField(field, value) {
    setConfig((current) => normalizeConfig({ ...current, [field]: value }));
    if (field === 'project_name') {
      setAiProjectName(value);
    }
  }

  function toggleArrayValue(field, value) {
    setConfig((current) => {
      const exists = current[field].includes(value);
      return normalizeConfig({
        ...current,
        [field]: exists ? current[field].filter((item) => item !== value) : [...current[field], value],
      });
    });
  }

  async function handleGenerate() {
    setStatus('loading');
    setError('');
    setResult(null);

    try {
      const response = await generateProject(normalizeConfig(config));
      setResult(response);
      setStatus('success');
    } catch (generateError) {
      setError(generateError.response?.data?.detail || 'El proceso de generación no pudo completarse. Inténtelo nuevamente.');
      setStatus('idle');
    }
  }

  async function handleGenerateProjectWithAI() {
    const message = aiMessage.trim();
    const projectName = aiProjectName.trim();
    if (!message) {
      setAiError('Ingrese una descripción de requerimientos antes de continuar.');
      return;
    }
    if (projectName.length < 3) {
      setAiError('El identificador del proyecto debe tener al menos 3 caracteres.');
      return;
    }

    setAiStatus('loading');
    setAiError('');
    setAiResult(null);

    try {
      const response = await generateProjectWithAI({ prompt: message, project_name: projectName });
      setAiResult(response);
      if (response.project_config) {
        setConfig(normalizeConfig(response.project_config));
        setStep(0);
      }
      setAiStatus('success');
    } catch (generationError) {
      setAiError(generationError.response?.data?.detail || 'El servicio de análisis no pudo procesar la solicitud. Inténtelo nuevamente.');
      setAiStatus('idle');
    }
  }

  function handleEditAIConfig() {
    if (aiResult?.project_config) {
      setConfig(normalizeConfig(aiResult.project_config));
      setStep(0);
    }
    setMode('manual');
  }

  function scrollToManualStart() {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!modeBarRef.current) return;
        const stickyNavHeight = 48;
        const top = modeBarRef.current.getBoundingClientRect().top + window.scrollY - stickyNavHeight;
        window.scrollTo({ top, behavior: 'auto' });
      });
    });
  }

  function goToManualStep(nextStep, event) {
    event?.currentTarget?.blur();
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    manualScrollPendingRef.current = true;
    setStep(nextStep);
  }

  return (
    <main className="ibm-page">
      <nav className="top-navigation" aria-label="Principal">
        <img className="ibm-logo" src={ibmLogo} alt="IBM" />
        <div className="top-nav-icons">
          <button className="nav-icon-btn" type="button" aria-label="Buscar"><Search size={20} /></button>
          <button className="nav-icon-btn" type="button" aria-label="Chat"><MessageSquare size={20} /></button>
          <button className="nav-icon-btn" type="button" aria-label="Idioma"><Globe size={20} /></button>
          <button className="nav-icon-btn" type="button" aria-label="Cuenta"><User size={20} /></button>
        </div>
      </nav>

      <section className="hero-band">
        <span className="eyebrow">IBM Consulting Chile</span>
        <h1>Plataforma de estandarización de arquitecturas</h1>
        <p>
          Defina la arquitectura técnica de sus proyectos fullstack a partir de un conjunto de componentes
          validados. Obtenga un comando de instalación reproducible, listo para integrarse con credenciales,
          variables de entorno y servicios de producción.
        </p>
      </section>

      <div className="mode-bar" ref={modeBarRef} role="tablist" aria-label="Modo de generacion">
        <button className={mode === 'ai' ? 'active' : ''} type="button" onClick={() => setMode('ai')}>
          <BrainCircuit size={16} />
          Asistido por IA
        </button>
        <button className={mode === 'manual' ? 'active' : ''} type="button" onClick={() => setMode('manual')}>
          <PackageCheck size={16} />
          Configuración manual
        </button>
      </div>

      {mode === 'ai' ? (
        <section className="ai-workspace" aria-labelledby="ai-generation-title">
          <div className="ai-prompt-panel">
            <div className="panel-heading compact">
              <span className="eyebrow">Análisis de requerimientos</span>
              <h2 id="ai-generation-title">Descripción del proyecto</h2>
              <p>Describa los requerimientos funcionales del proyecto. El sistema interpretará las necesidades y configurará automáticamente los parámetros técnicos.</p>
            </div>
            <div className="ai-analysis-panel">
              <label className="field">
                <span>Nombre del proyecto</span>
                <input
                  value={aiProjectName}
                  onChange={(event) => setAiProjectName(event.target.value)}
                  placeholder="mi-proyecto-base"
                />
              </label>
              <label className="field ai-input">
                <span>Requerimientos del proyecto</span>
                <textarea
                  value={aiMessage}
                  onChange={(event) => setAiMessage(event.target.value)}
                  placeholder="Plataforma web para gestión de reservas. Roles: paciente, profesional, administrador. Autenticación con SSO, dashboard analítico, base de datos relacional, despliegue en contenedores sobre GCP."
                />
              </label>
              <button className="ai-analyze-button" disabled={aiStatus === 'loading'} type="button" onClick={handleGenerateProjectWithAI}>
                {aiStatus === 'loading' ? <Loader2 className="spin" size={18} /> : <BrainCircuit size={18} />}
                Analizar y configurar
              </button>
              {aiError && <p className="notice error">{aiError}</p>}
            </div>
          </div>

          <div className="ai-review-panel">
            {aiResult ? (
              <AIGenerationResult result={aiResult} onEditConfig={handleEditAIConfig} />
            ) : (
              <div className="ai-empty-state">
                <span className="eyebrow">Resultado del análisis</span>
                <h2>Configuración generada</h2>
                <p>El sistema determinará automáticamente el tipo de proyecto, stack tecnológico, autenticación, base de datos y plantillas aplicables según los requerimientos ingresados.</p>
              </div>
            )}
          </div>
        </section>
      ) : (
      <section className="manual-workspace" id="configure">
        <div className="generator-panel">
          <div className="panel-heading manual-heading">
            <span className="eyebrow">Parámetros del proyecto</span>
            <h2>Configuración de arquitectura</h2>
            <p>Defina los componentes técnicos del proyecto. Al finalizar obtendrá un comando de instalación reproducible adaptado al entorno seleccionado.</p>
          </div>

        <nav className="progress-indicator" aria-label="Pasos del proceso">
          {steps.map((label, index) => (
            <div
              key={label}
              className={`progress-step${index === step ? ' active' : ''}${index < step ? ' done' : ''}`}
            >
              <button type="button" onClick={(event) => goToManualStep(index, event)}>
                <span className="progress-dot">{index < step ? '✓' : index + 1}</span>
                <span className="progress-label">{label}</span>
              </button>
            </div>
          ))}
        </nav>

        <form className="form-surface">
          {step === 0 && (
            <div className="form-grid">
              <label className="field span-2">
                <span>Nombre del proyecto</span>
                <input
                  value={config.project_name}
                  onChange={(event) => updateField('project_name', event.target.value)}
                  placeholder="mi-proyecto"
                />
              </label>
              <label className="field span-2">
                <span>Descripción del proyecto</span>
                <textarea value={config.description} onChange={(event) => updateField('description', event.target.value)} />
              </label>
              <div className="option-group span-2">
                <span>Perfil de arquitectura</span>
                <div className="option-grid">
                  {options?.projectProfiles?.map((option) => (
                    <OptionCard
                      key={option.value}
                      description={option.description}
                      label={option.label}
                      selected={config.project_profile === option.value}
                      onClick={() => updateField('project_profile', option.value)}
                    />
                  ))}
                </div>
              </div>
              <div className="option-group span-2">
                <span>Tipo de proyecto</span>
                <div className="option-grid">
                  {options?.projectTypes?.map((option) => (
                    <OptionCard
                      key={option.value}
                      description={option.description}
                      label={option.label}
                      selected={config.project_type === option.value}
                      onClick={() => updateField('project_type', option.value)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="form-grid">
              {config.project_type !== 'api' && (
                <SelectGroup label="Frontend" options={options?.frontend} value={config.frontend} onSelect={(value) => updateField('frontend', value)} />
              )}
              {config.project_type !== 'web' && (
                <SelectGroup label="Backend" options={options?.backend} value={config.backend} onSelect={(value) => updateField('backend', value)} />
              )}
              {config.project_type !== 'api' && (
                <SelectGroup label="Autenticación" options={options?.auth} value={config.auth} onSelect={(value) => updateField('auth', value)} />
              )}
              {config.project_type !== 'web' && (
                <SelectGroup label="Base de datos" options={options?.database} value={config.database} onSelect={(value) => updateField('database', value)} />
              )}
              {config.project_profile === 'ai' && (
                <div className="info-row span-2">
                  {config.project_type === 'web'
                    ? 'Se incorporará un módulo de agente conversacional en el frontend con soporte de historial de interacciones, sin dependencia de backend.'
                    : 'LangGraph se incorpora automáticamente. La arquitectura incluye un módulo de agente conversacional con historial persistente y grafos de razonamiento configurables.'}
                </div>
              )}
            </div>
          )}

          {step === 2 && (
            <div className="form-grid">
                <SelectGroup label="Plataforma de despliegue" options={options?.cloud} value={config.cloud} onSelect={(value) => updateField('cloud', value)} />
              {config.project_type !== 'web' && (
              <div className="option-group span-2">
                <span>Microservicios adicionales</span>
                <div className="option-grid">
                  {options?.serviceCounts?.map((option) => (
                    <OptionCard
                      key={option.value}
                      description={option.description}
                      label={option.label}
                      selected={config.service_count === option.value}
                      onClick={() => updateField('service_count', option.value)}
                    />
                  ))}
                </div>
                <p className="field-help">
                  Los servicios se despliegan como contenedores independientes. La base de datos se gestiona como servicio administrado externo al clúster.
                </p>
              </div>
              )}
              <div className="option-group span-2">
                <span>Contenedores del proyecto</span>
                <div className="option-grid">
                  {options?.containers
                    ?.filter((option) => config.containers.includes(option.value))
                    .map((option) => (
                      <OptionCard
                        key={option.value}
                        description={option.description}
                        label={option.label}
                        selected
                        onClick={() => {}}
                      />
                    ))}
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="delivery-grid">
              <label className="toggle-row">
                <input
                  checked={config.include_docker}
                  type="checkbox"
                  onChange={(event) => updateField('include_docker', event.target.checked)}
                />
                <span>Incluir configuración Docker (Dockerfile y docker-compose)</span>
              </label>
              <label className="toggle-row">
                <input
                  checked={config.include_dev_script}
                  type="checkbox"
                  onChange={(event) => updateField('include_dev_script', event.target.checked)}
                />
                <span>Incluir script de ejecución local (dev.sh)</span>
              </label>
              <div className="option-group span-2">
                <span>Entorno de desarrollo</span>
                <div className="option-grid">
                  {options?.targetOs?.map((option) => (
                    <OptionCard
                      key={option.value}
                      description={option.description}
                      label={option.label}
                      selected={config.target_os === option.value}
                      onClick={() => updateField('target_os', option.value)}
                    />
                  ))}
                </div>
              </div>
              <button className="generate-button" disabled={status === 'loading'} type="button" onClick={handleGenerate}>
                {status === 'loading' ? <Loader2 className="spin" size={18} /> : <PackageCheck size={18} />}
                Generar estructura del proyecto
              </button>
              {result && (
                <div className="command-result">
                  <div className="command-result-header">
                    <span>Comando de instalación — macOS / Linux</span>
                  </div>
                  <code>{result.install_command}</code>
                  <button type="button" onClick={() => navigator.clipboard?.writeText(result.install_command)}>
                    <Clipboard size={15} />
                    Copiar comando
                  </button>
                  {result.install_command_windows && (
                    <>
                      <span className="command-result-label">Comando de instalación — Windows (PowerShell)</span>
                      <code>{result.install_command_windows}</code>
                      <button type="button" onClick={() => navigator.clipboard?.writeText(result.install_command_windows)}>
                        <Clipboard size={15} />
                        Copiar comando
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </form>

        {error && <p className="notice error">{error}</p>}

        <div className="navigation-row">
          <button disabled={step === 0} type="button" onClick={(event) => goToManualStep(step - 1, event)}>
            <ArrowLeft size={18} />
            Anterior
          </button>
          <button disabled={!canGoNext || step === steps.length - 1} className="nav-primary" type="button" onClick={(event) => goToManualStep(step + 1, event)}>
            Siguiente
            <ArrowRight size={18} />
          </button>
        </div>
        </div>

        <ArchitecturePreview config={config} />
      </section>
      )}
      <footer className="ibm-footer">
        <div className="ibm-footer-grid">
          <div className="ibm-footer-col">
            <h3>Discover</h3>
            <ul>
              <li><a href="https://www.ibm.com/products">Products</a></li>
              <li><a href="https://www.ibm.com/consulting">Consulting services</a></li>
              <li><a href="https://www.ibm.com/industries">Industries</a></li>
              <li><a href="https://www.ibm.com/case-studies">Case studies</a></li>
              <li><a href="https://www.ibm.com/financing">Financing</a></li>
              <li><a href="https://research.ibm.com">Research</a></li>
            </ul>
          </div>
          <div className="ibm-footer-col">
            <h3>Connect</h3>
            <ul>
              <li><a href="https://www.ibm.com/partnerplus/directory/companies">Business partners</a></li>
              <li><a href="https://www.ibm.com/docs/en">Documentation</a></li>
              <li><a href="https://www.ibm.com/events">Events</a></li>
              <li><a href="https://www.ibm.com/subscribe">Newsletters</a></li>
              <li><a href="https://www.ibm.com/mysupport">Support</a></li>
              <li><a href="https://community.ibm.com/community/user/home">TechXchange community</a></li>
            </ul>
          </div>
          <div className="ibm-footer-col">
            <h3>Follow</h3>
            <ul>
              <li><a href="https://www.linkedin.com/company/ibm">LinkedIn</a></li>
              <li><a href="https://www.twitter.com/ibm">X</a></li>
              <li><a href="https://www.instagram.com/ibm">Instagram</a></li>
              <li><a href="https://www.youtube.com/@IBM">YouTube</a></li>
              <li><a href="https://www.ibm.com/think/podcasts">Podcasts</a></li>
            </ul>
          </div>
          <div className="ibm-footer-col">
            <h3>About</h3>
            <ul>
              <li><a href="https://www.ibm.com/about">Overview</a></li>
              <li><a href="https://www.ibm.com/careers">Careers</a></li>
              <li><a href="https://www.ibm.com/investor">Investor relations</a></li>
              <li><a href="https://newsroom.ibm.com/executive-bios">Leadership</a></li>
              <li><a href="https://newsroom.ibm.com">Newsroom</a></li>
              <li><a href="https://www.ibm.com/trust">Security, privacy and trust</a></li>
            </ul>
          </div>
        </div>
        <div className="ibm-footer-bottom">
          <img className="ibm-footer-logo" src={ibmLogo} alt="IBM" />
          <div className="ibm-footer-legal">
            <a href="https://www.ibm.com/contact/global">Contact IBM</a>
            <a href="https://www.ibm.com/us-en/privacy">Privacy</a>
            <a href="https://www.ibm.com/legal">Terms of use</a>
            <a href="https://www.ibm.com/able">Accessibility</a>
            <button type="button">Cookie Preferences</button>
          </div>
        </div>
      </footer>
    </main>
  );
}

function AIGenerationResult({ result, onEditConfig }) {
  const architecture = result.selected_architecture || {};
  const rows = [
    ['Proyecto', result.project_name],
    ['Tipo', architecture.project_type],
    ['Frontend', architecture.frontend],
    ['Backend', architecture.backend],
    ['Base de datos', architecture.database],
    ['Autenticacion', architecture.auth],
    ['Cloud', architecture.cloud],
  ];

  return (
    <div className="ai-result-panel">
      <div className="ai-download-row">
        <div>
          <span>Arquitectura configurada</span>
          <strong>{result.project_name}</strong>
        </div>
      </div>
      <div className="ai-result-grid">
        {rows.map(([label, value]) => (
          <div className="ai-result-item" key={label}>
            <span>{label}</span>
            <strong>{value || 'No definido'}</strong>
          </div>
        ))}
      </div>

      <ResultList title="Módulos identificados" items={architecture.modules} />
      <ResultList title="Roles identificados" items={architecture.roles} />
      <ResultList title="Plantillas aplicadas" items={result.selected_templates} />

      <div className="ai-actions-row">
        <button type="button" onClick={onEditConfig}>
          <ArrowRight size={16} />
          Revisar en configuración manual
        </button>
      </div>

      {result.install_command && (
        <div className="command-result ai-command-result">
          <span>Comando de instalación</span>
          <code>{result.install_command}</code>
          <button type="button" onClick={() => navigator.clipboard?.writeText(result.install_command)}>
            <Clipboard size={15} />
            Copiar comando
          </button>
        </div>
      )}
    </div>
  );
}

function ResultList({ title, items = [] }) {
  return (
    <div className="ai-list-block">
      <span>{title}</span>
      {items.length > 0 ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>No definido</p>
      )}
    </div>
  );
}

function SelectGroup({ label, options = [], value, onSelect }) {
  return (
    <div className="option-group">
      <span>{label}</span>
      <div className="option-grid">
        {options.map((option) => (
          <OptionCard
            key={option.value}
            description={option.description}
            label={option.label}
            selected={value === option.value}
            onClick={() => onSelect(option.value)}
          />
        ))}
      </div>
    </div>
  );
}
