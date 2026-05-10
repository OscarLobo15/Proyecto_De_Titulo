import { ArrowLeft, ArrowRight, BarChart3, BrainCircuit, Clipboard, Cog, Globe, LayoutDashboard, LayoutPanelTop, Loader2, MessageSquare, PackageCheck, Plug, Rows4, Search, Settings, ShieldCheck, User, Users, Workflow, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ibmLogo from '../assets/brand/ibm-logo.png';
import { ArchitecturePreview } from '../components/ArchitecturePreview.jsx';
import { LiveProjectPreview } from '../components/LiveProjectPreview.jsx';
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
  navigation_layout: 'sidebar',
  login_variant: 'ibm-classic',
  experience_mode: 'admin',
  admin_style: 'operations',
  pages: ['login', 'workspace', 'settings', 'not-found'],
  navigation_sections: [],
  functional_modules: ['operaciones', 'usuarios', 'reportes'],
  user_roles: [],
};

const baseSteps = ['Proyecto', 'Stack', 'Servicios'];

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
      navigation_sections: [],
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
  const [aiPreviewConfig, setAiPreviewConfig] = useState(null);
  const [aiRefreshStatus, setAiRefreshStatus] = useState('idle');
  const [aiStep, setAiStep] = useState(0);
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
  const hasFrontend = config.project_type !== 'api';
  const steps = useMemo(() => (hasFrontend ? [...baseSteps, 'Vista previa', 'Entrega'] : [...baseSteps, 'Entrega']), [hasFrontend]);
  const aiHasFrontend = aiPreviewConfig ? aiPreviewConfig.project_type !== 'api' : true;
  const aiSteps = useMemo(() => (aiHasFrontend ? ['Generación', 'Review', 'Vista previa', 'Entrega'] : ['Generación', 'Review', 'Entrega']), [aiHasFrontend]);

  useEffect(() => {
    if (step > steps.length - 1) {
      setStep(steps.length - 1);
    }
  }, [step, steps.length]);

  useEffect(() => {
    if (aiStep > aiSteps.length - 1) {
      setAiStep(aiSteps.length - 1);
    }
  }, [aiStep, aiSteps.length]);

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
    setAiRefreshStatus('idle');

    try {
      const response = await generateProjectWithAI({ prompt: message, project_name: projectName });
      const nextPreviewConfig = response.project_config ? normalizeConfig(response.project_config) : null;
      setAiResult(response);
      setAiPreviewConfig(nextPreviewConfig);
      if (response.project_config) {
        setConfig(normalizeConfig(response.project_config));
        setStep(0);
      }
      setAiStep(1);
      setAiStatus('success');
    } catch (generationError) {
      setAiError(generationError.response?.data?.detail || 'El servicio de análisis no pudo procesar la solicitud. Inténtelo nuevamente.');
      setAiStatus('idle');
    }
  }

  function handleEditAIConfig() {
    if (aiPreviewConfig) {
      setConfig(normalizeConfig(aiPreviewConfig));
      setStep(0);
    }
    setMode('manual');
  }

  function updateAiPreviewConfig(field, value) {
    setAiPreviewConfig((current) => normalizeConfig({ ...(current || initialConfig), [field]: value }));
  }

  function goToAIStep(nextStep) {
    setAiStep(nextStep);
  }

  function addNavigationSection(field, value, target = 'manual') {
    const normalizedValue = value.trim().toLowerCase().replace(/\s+/g, '-');
    if (!normalizedValue) return;

    if (target === 'ai') {
      setAiPreviewConfig((current) => {
        const base = current || initialConfig;
        const nextItems = base[field].includes(normalizedValue)
          ? base[field]
          : [...base[field], normalizedValue];
        return normalizeConfig({ ...base, [field]: nextItems });
      });
      return;
    }

    setConfig((current) => {
      const nextItems = current[field].includes(normalizedValue)
        ? current[field]
        : [...current[field], normalizedValue];
      return normalizeConfig({ ...current, [field]: nextItems });
    });
  }

  function removeNavigationSection(field, value, target = 'manual') {
    if (target === 'ai') {
      setAiPreviewConfig((current) => normalizeConfig({ ...(current || initialConfig), [field]: (current?.[field] || []).filter((item) => item !== value) }));
      return;
    }
    setConfig((current) => normalizeConfig({ ...current, [field]: current[field].filter((item) => item !== value) }));
  }

  async function refreshAIPackage() {
    if (!aiPreviewConfig) return;
    setAiRefreshStatus('loading');
    setAiError('');

    try {
      const response = await generateProject(aiPreviewConfig);
      setAiResult((current) => ({
        ...current,
        ...response,
        project_config: aiPreviewConfig,
      }));
      setAiRefreshStatus('success');
    } catch (refreshError) {
      setAiError(refreshError.response?.data?.detail || 'No fue posible regenerar el paquete con las opciones visuales seleccionadas.');
      setAiRefreshStatus('idle');
    }
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
        <section className="manual-workspace ai-flow-workspace" aria-labelledby="ai-generation-title">
          <div className="generator-panel">
            <div className="panel-heading manual-heading">
              <span className="eyebrow">Asistencia IA</span>
              <h2 id="ai-generation-title">Generación guiada por requerimientos</h2>
              <p>Describe el proyecto en lenguaje natural. La IA propondrá la arquitectura, poblará el MVP con módulos y roles detectados, y luego podrás revisar, previsualizar y entregar el paquete final.</p>
            </div>

            <nav className="progress-indicator" aria-label="Pasos del flujo IA">
              {aiSteps.map((label, index) => (
                <div
                  key={label}
                  className={`progress-step${index === aiStep ? ' active' : ''}${index < aiStep ? ' done' : ''}`}
                >
                  <button type="button" onClick={() => goToAIStep(index)}>
                    <span className="progress-dot">{index < aiStep ? '✓' : index + 1}</span>
                    <span className="progress-label">{label}</span>
                  </button>
                </div>
              ))}
            </nav>

            <div className="form-surface">
              {aiStep === 0 && (
                <div className="form-grid ai-step-grid">
                  <label className="field span-2">
                    <span>Nombre del proyecto</span>
                    <input
                      value={aiProjectName}
                      onChange={(event) => setAiProjectName(event.target.value)}
                      placeholder="mi-proyecto-base"
                    />
                  </label>
                  <label className="field span-2 ai-input">
                    <span>Requerimientos del proyecto</span>
                    <textarea
                      value={aiMessage}
                      onChange={(event) => setAiMessage(event.target.value)}
                      placeholder="Plataforma web para gestión de reservas. Roles: paciente, profesional, administrador. Autenticación con SSO, dashboard analítico, base de datos relacional, despliegue en contenedores sobre GCP."
                    />
                  </label>
                  <div className="info-row span-2">
                    La IA convertirá los requerimientos en stack técnico, roles, módulos funcionales, navegación base y estructura del MVP generado.
                  </div>
                  <button className="generate-button span-2" disabled={aiStatus === 'loading'} type="button" onClick={handleGenerateProjectWithAI}>
                    {aiStatus === 'loading' ? <Loader2 className="spin" size={18} /> : <BrainCircuit size={18} />}
                    Analizar y configurar
                  </button>
                  {aiError && <p className="notice error span-2">{aiError}</p>}
                </div>
              )}

              {aiStep === 1 && (
                aiResult && aiPreviewConfig ? (
                  <AIReviewStep
                    previewConfig={aiPreviewConfig}
                    result={aiResult}
                    onEditConfig={handleEditAIConfig}
                  />
                ) : (
                  <div className="ai-empty-state">
                    <span className="eyebrow">Review</span>
                    <h2>Aún no hay una arquitectura generada</h2>
                    <p>Completa el paso de generación para revisar la propuesta estructurada de la IA.</p>
                  </div>
                )
              )}

              {aiStep === 2 && aiHasFrontend && (
                aiPreviewConfig ? (
                  <>
                    <LiveProjectPreview config={aiPreviewConfig} source="ai" />
                    <DesignCustomizationPanel
                      config={aiPreviewConfig}
                      options={options}
                      onAddNavigationSection={(value) => addNavigationSection('navigation_sections', value, 'ai')}
                      onRemoveNavigationSection={(value) => removeNavigationSection('navigation_sections', value, 'ai')}
                      onUpdateField={updateAiPreviewConfig}
                    />
                  </>
                ) : (
                  <div className="ai-empty-state">
                    <span className="eyebrow">Vista previa</span>
                    <h2>La vista previa se habilita después del análisis</h2>
                    <p>Cuando la IA genere una configuración con frontend, aquí verás el MVP navegable antes de la entrega.</p>
                  </div>
                )
              )}

              {aiStep === (aiHasFrontend ? 3 : 2) && (
                aiPreviewConfig ? (
                  <AIDeliveryStep
                    aiRefreshStatus={aiRefreshStatus}
                    previewConfig={aiPreviewConfig}
                    result={aiResult}
                    options={options}
                    onRefreshPackage={refreshAIPackage}
                    onUpdatePreviewConfig={updateAiPreviewConfig}
                  />
                ) : (
                  <div className="ai-empty-state">
                    <span className="eyebrow">Entrega</span>
                    <h2>Primero necesitamos una configuración generada</h2>
                    <p>Después del análisis podrás regenerar el paquete final con los ajustes elegidos y copiar el comando de instalación.</p>
                  </div>
                )
              )}
            </div>

            <div className="navigation-row">
              <button type="button" disabled={aiStep === 0} onClick={() => goToAIStep(Math.max(0, aiStep - 1))}>
                <ArrowLeft size={16} />
                Anterior
              </button>
              <button
                type="button"
                className="nav-primary"
                disabled={aiStep >= aiSteps.length - 1 || (aiStep === 0 && !aiResult)}
                onClick={() => goToAIStep(Math.min(aiSteps.length - 1, aiStep + 1))}
              >
                Siguiente
                <ArrowRight size={16} />
              </button>
            </div>
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

        <div className="form-surface">
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

          {step === 3 && hasFrontend && (
            <>
              <LiveProjectPreview config={config} />
              <DesignCustomizationPanel
                config={config}
                options={options}
                onAddNavigationSection={(value) => addNavigationSection('navigation_sections', value)}
                onRemoveNavigationSection={(value) => removeNavigationSection('navigation_sections', value)}
                onUpdateField={updateField}
              />
            </>
          )}

          {step === (hasFrontend ? 4 : 3) && (
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

        </div>

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

function AIReviewStep({ onEditConfig, previewConfig, result }) {
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
    <div className="ai-result-panel ai-step-panel">
      <div className="panel-heading compact ai-step-heading">
        <span className="eyebrow">Review</span>
        <h2>Arquitectura propuesta por la IA</h2>
        <p>Este review traduce los requerimientos detectados a una base real de proyecto. Los módulos, roles y la navegación inferior alimentan tanto el preview como el MVP final.</p>
      </div>

      <div className="ai-result-grid ai-review-grid">
        {rows.map(([label, value]) => (
          <div className="ai-result-item" key={label}>
            <span>{label}</span>
            <strong>{value || 'No definido'}</strong>
          </div>
        ))}
      </div>

      <ResultTagSection title="Módulos que se incorporarán al MVP" items={previewConfig.functional_modules} emptyLabel="No se detectaron módulos específicos." />
      <ResultTagSection title="Roles que se incorporarán al MVP" items={previewConfig.user_roles} emptyLabel="No se detectaron roles específicos." />
      <ResultTagSection title="Apartados de navegación derivados" items={previewConfig.navigation_sections} emptyLabel="La base usará solo workspace, administración y settings." />
      <ResultTagSection title="Plantillas aplicadas" items={result.selected_templates} emptyLabel="No definido" />

      <div className="ai-actions-row">
        <button type="button" onClick={onEditConfig}>
          <ArrowRight size={16} />
          Revisar en configuración manual
        </button>
      </div>
    </div>
  );
}

function AIDeliveryStep({ aiRefreshStatus, onRefreshPackage, onUpdatePreviewConfig, options, previewConfig, result }) {
  return (
    <div className="delivery-grid">
      <label className="toggle-row">
        <input
          checked={previewConfig.include_docker}
          type="checkbox"
          onChange={(event) => onUpdatePreviewConfig('include_docker', event.target.checked)}
        />
        <span>Incluir configuración Docker (Dockerfile y docker-compose)</span>
      </label>
      <label className="toggle-row">
        <input
          checked={previewConfig.include_dev_script}
          type="checkbox"
          onChange={(event) => onUpdatePreviewConfig('include_dev_script', event.target.checked)}
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
              selected={previewConfig.target_os === option.value}
              onClick={() => onUpdatePreviewConfig('target_os', option.value)}
            />
          ))}
        </div>
      </div>
      <button className="generate-button" disabled={aiRefreshStatus === 'loading'} type="button" onClick={onRefreshPackage}>
        {aiRefreshStatus === 'loading' ? <Loader2 className="spin" size={18} /> : <PackageCheck size={18} />}
        Generar paquete final
      </button>

      {result?.install_command && (
        <div className="command-result ai-command-result">
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
                Copiar comando Windows
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function DesignCustomizationPanel({ config, options, onAddNavigationSection, onRemoveNavigationSection, onUpdateField }) {
  const [sectionDraft, setSectionDraft] = useState('');
  const [activeEditor, setActiveEditor] = useState(config?.auth !== 'none' ? 'login' : 'navigation');
  const hasFrontend = config?.project_type !== 'api';
  const editorTabs = [
    { key: 'login', label: 'Login', visible: config?.auth !== 'none' },
    { key: 'navigation', label: 'Navegación', visible: true },
    { key: 'sections', label: 'Apartados', visible: true },
    { key: 'admin-flow', label: 'Panel admin', visible: true },
  ].filter((tab) => tab.visible);
  const componentLibrary = [
    { value: 'dashboard-ejecutivo', label: 'Dashboard ejecutivo', description: 'KPIs, estado general y resumen de negocio.', Icon: BarChart3 },
    { value: 'centro-operaciones', label: 'Centro de operaciones', description: 'Vista de seguimiento operativo y actividad diaria.', Icon: Workflow },
    { value: 'gestion-usuarios', label: 'Gestión de usuarios', description: 'Administración de usuarios, permisos y cuentas.', Icon: Users },
    { value: 'reportes', label: 'Centro de reportes', description: 'Vistas analíticas, exportables y seguimiento histórico.', Icon: LayoutDashboard },
    { value: 'integraciones', label: 'Integraciones', description: 'Conectores, APIs externas y estado de servicios.', Icon: Plug },
    { value: 'configuracion-avanzada', label: 'Configuración avanzada', description: 'Reglas, parámetros y ajustes de plataforma.', Icon: Settings },
    ...(config?.project_profile === 'ai' ? [{ value: 'agente', label: 'Agente', description: 'Entrada dedicada al flujo conversacional o asistente.', Icon: BrainCircuit }] : []),
  ];

  if (!hasFrontend || !config) {
    return null;
  }

  useEffect(() => {
    if (!editorTabs.some((tab) => tab.key === activeEditor)) {
      setActiveEditor(editorTabs[0]?.key || 'navigation');
    }
  }, [activeEditor, editorTabs]);

  function handleAddSection() {
    const cleaned = sectionDraft.trim();
    if (!cleaned) return;
    onAddNavigationSection(cleaned);
    setSectionDraft('');
  }

  return (
    <section className="design-customization-panel" aria-label="Opciones de diseño visual">
      <div className="design-minimal-header">
        <span className="eyebrow">Sistema visual</span>
        <div className="design-minimal-copy">
          <h3>Diseño base del proyecto</h3>
          <p>Define cómo se verá la navegación, el acceso y el panel administrativo en la versión final del proyecto.</p>
        </div>
      </div>

      <div className="design-editor-tabs" role="tablist" aria-label="Editar diseño">
        {editorTabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeEditor === tab.key ? 'active' : ''}
            onClick={() => setActiveEditor(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="design-editor-surface">
        {activeEditor === 'navigation' && (
          <div className="option-group">
            <span>Estructura de navegación</span>
            <CompactChoiceGrid options={options?.navigationLayouts} value={config.navigation_layout} onSelect={(value) => onUpdateField('navigation_layout', value)} />
          </div>
        )}

        {activeEditor === 'login' && config.auth !== 'none' && (
          <div className="option-group">
            <span>Diseño de login</span>
            <CompactChoiceGrid options={options?.loginVariants} value={config.login_variant} onSelect={(value) => onUpdateField('login_variant', value)} />
          </div>
        )}

        {activeEditor === 'admin-flow' && (
          <div className="design-admin-panel">
            <div className="option-group">
              <span>Cómo se entra al panel admin</span>
              <AdminFlowSelector options={options?.experienceModes} value={config.experience_mode} onSelect={(value) => onUpdateField('experience_mode', value)} />
            </div>
            <div className="option-group">
              <span>Estilo del panel admin</span>
              <CompactChoiceGrid options={options?.adminStyles} value={config.admin_style} onSelect={(value) => onUpdateField('admin_style', value)} />
            </div>
          </div>
        )}

        {activeEditor === 'sections' && (
          <div className="design-sections-panel">
            <div className="design-sections-header">
              <div>
                <span className="eyebrow">Navegación</span>
                <h3>Componentes de navegación</h3>
                <p>Agrega apartados reales del producto. Se mostrarán en el {config.navigation_layout === 'sidebar' ? 'sidebar' : 'navbar'} y abrirán vistas base en el MVP.</p>
              </div>
              <div className="design-section-icons" aria-hidden="true">
                {config.navigation_layout === 'sidebar' ? <Rows4 size={18} /> : <LayoutPanelTop size={18} />}
                <Cog size={18} />
              </div>
            </div>

            <div className="navigation-library-grid">
              {componentLibrary
                .filter((item) => !config.navigation_sections?.includes(item.value))
                .map(({ value, label, description, Icon }) => (
                  <button key={value} type="button" className="navigation-library-card" onClick={() => onAddNavigationSection(value)}>
                    <Icon size={18} />
                    <strong>{label}</strong>
                    <span>{description}</span>
                  </button>
                ))}
            </div>

            {config.include_services && config.service_count > 0 && (
              <div className="services-preview-note">
                <span className="eyebrow">Servicios</span>
                <p>El preview también mostrará navegación entre {config.service_count} servicio{config.service_count > 1 ? 's' : ''} adicional{config.service_count > 1 ? 'es' : ''}.</p>
              </div>
            )}

            <div className="design-sections-form">
              <label className="field">
                <span>Nuevo apartado personalizado</span>
                <input
                  value={sectionDraft}
                  onChange={(event) => setSectionDraft(event.target.value)}
                  placeholder="Ej: auditoría, aprobaciones, mesa de control"
                />
              </label>
              <button type="button" className="section-add-button" onClick={handleAddSection}>
                Agregar
              </button>
            </div>

            <div className="design-chip-row">
              {config.navigation_sections?.length ? (
                config.navigation_sections.map((section) => (
                  <button key={section} type="button" className="design-chip" onClick={() => onRemoveNavigationSection(section)}>
                    {section.replace(/-/g, ' ')}
                    <X size={14} />
                  </button>
                ))
              ) : (
                <p className="field-help">Aún no agregas componentes extra. La base seguirá usando workspace, dashboard, módulos y settings.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function CompactChoiceGrid({ onSelect, options = [], value }) {
  return (
    <div className="compact-choice-grid">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`compact-choice${value === option.value ? ' active' : ''}`}
          onClick={() => onSelect(option.value)}
        >
          <strong>{option.label}</strong>
          <span>{option.description}</span>
        </button>
      ))}
    </div>
  );
}

function AdminFlowSelector({ onSelect, options = [], value }) {
  return (
    <div className="admin-flow-grid">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`admin-flow-card${value === option.value ? ' active' : ''}`}
          onClick={() => onSelect(option.value)}
        >
          <div className="admin-flow-card-top">
            {option.value === 'admin' ? <ShieldCheck size={18} /> : <LayoutDashboard size={18} />}
            <strong>{option.label}</strong>
          </div>
          <span>{option.description}</span>
          <div className="admin-flow-route" aria-hidden="true">
            <span>Login</span>
            <span />
            <span>{option.value === 'admin' ? 'Panel admin' : 'Portal'}</span>
            {option.value !== 'admin' && (
              <>
                <span />
                <span>Administración</span>
              </>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

function ResultTagSection({ emptyLabel, items = [], title }) {
  return (
    <div className="ai-tag-block">
      <span>{title}</span>
      {items.length > 0 ? (
        <ul className="ai-tag-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p>{emptyLabel}</p>
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
