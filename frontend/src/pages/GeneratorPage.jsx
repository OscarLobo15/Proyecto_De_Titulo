import { ArrowLeft, ArrowRight, Clipboard, Download, Loader2, PackageCheck } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import ibmLogo from '../assets/brand/ibm-logo.png';
import { ArchitecturePreview } from '../components/ArchitecturePreview.jsx';
import { OptionCard } from '../components/OptionCard.jsx';
import { StepHeader } from '../components/StepHeader.jsx';
import { generateProject, getOptions } from '../services/api.js';

const initialConfig = {
  project_name: 'mi-proyecto-base',
  description: 'Arquitectura base generada para iniciar desarrollo rapidamente.',
  project_type: 'fullstack',
  project_profile: 'standard',
  frontend: 'react',
  backend: 'fastapi',
  auth: 'firebase',
  database: 'postgresql',
  cloud: 'local',
  containers: ['frontend', 'backend', 'database'],
  include_docker: true,
  include_dev_script: true,
  include_services: false,
  include_langgraph: false,
  target_os: 'mac',
  pages: ['home', 'login', 'dashboard', 'settings', 'not-found'],
};

const steps = ['Proyecto', 'Stack', 'Servicios', 'Entrega'];

function normalizeConfig(nextConfig) {
  if (nextConfig.project_type === 'web') {
    return {
      ...nextConfig,
      database: 'none',
      containers: nextConfig.containers.filter((item) => item === 'frontend').length ? ['frontend'] : ['frontend'],
      include_services: false,
    };
  }

  if (nextConfig.project_type === 'api') {
    const apiContainers = nextConfig.containers.filter((item) => ['backend', 'database', 'services'].includes(item));
    return {
      ...nextConfig,
      auth: 'none',
      containers: apiContainers.includes('backend') ? apiContainers : ['backend', ...apiContainers],
    };
  }

  return nextConfig;
}

export function GeneratorPage() {
  const [options, setOptions] = useState(null);
  const [config, setConfig] = useState(initialConfig);
  const [step, setStep] = useState(0);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    getOptions()
      .then(setOptions)
      .catch(() => setError('No se pudo conectar con la API. Levanta el backend en http://localhost:8000.'));
  }, []);

  const canGoNext = useMemo(() => config.project_name.trim().length >= 3, [config.project_name]);

  function updateField(field, value) {
    setConfig((current) => normalizeConfig({ ...current, [field]: value }));
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
      setError(generateError.response?.data?.detail || 'No fue posible generar el proyecto.');
      setStatus('idle');
    }
  }

  return (
    <main className="ibm-page">
      <nav className="top-navigation" aria-label="Principal">
        <img className="ibm-logo" src={ibmLogo} alt="IBM" />
      </nav>

      <section className="hero-band">
        <div>
          <span className="eyebrow">IBM Consulting Chile</span>
          <h1>Generador de arquitecturas base</h1>
        </div>
        <p>
          Estandariza el setup inicial de proyectos fullstack. Selecciona componentes, genera un comando npm y crea una
          estructura lista para configurar credenciales, variables de entorno y conexiones reales.
        </p>
      </section>

      <section className="app-shell" id="configure">
        <div className="generator-panel">
          <div className="panel-heading">
            <span className="eyebrow">Configuracion</span>
            <h2>Define el esqueleto tecnico</h2>
            <p>El resultado es un comando reproducible para crear el proyecto base con la estructura seleccionada.</p>
          </div>

        <StepHeader currentStep={step + 1} totalSteps={steps.length} />

        <div className="step-tabs" aria-label="Pasos">
          {steps.map((label, index) => (
            <button className={index === step ? 'active' : ''} key={label} type="button" onClick={() => setStep(index)}>
              {label}
            </button>
          ))}
        </div>

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
                <span>Descripcion breve</span>
                <textarea value={config.description} onChange={(event) => updateField('description', event.target.value)} />
              </label>
              <div className="option-group span-2">
                <span>Perfil base</span>
                <div className="option-grid">
                  {options?.projectProfiles?.map((option) => (
                    <OptionCard
                      key={option.value}
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
                <SelectGroup label="Autenticacion" options={options?.auth} value={config.auth} onSelect={(value) => updateField('auth', value)} />
              )}
              {config.project_type !== 'web' && (
                <SelectGroup label="Base de datos" options={options?.database} value={config.database} onSelect={(value) => updateField('database', value)} />
              )}
              {config.project_type !== 'web' && config.project_profile === 'ai' && (
                <label className="toggle-row span-2">
                  <input
                    checked={config.include_langgraph}
                    type="checkbox"
                    onChange={(event) => updateField('include_langgraph', event.target.checked)}
                  />
                  <span>Incluir LangGraph para el backend de IA</span>
                </label>
              )}
            </div>
          )}

          {step === 2 && (
            <div className="form-grid">
              <SelectGroup label="Cloud objetivo" options={options?.cloud} value={config.cloud} onSelect={(value) => updateField('cloud', value)} />
              <div className="option-group">
                <span>Contenedores</span>
                <div className="option-grid">
                  {options?.containers
                    ?.filter((option) => {
                      if (config.project_type === 'web') return option.value === 'frontend';
                      if (config.project_type === 'api') return ['backend', 'database', 'services'].includes(option.value);
                      return true;
                    })
                    .map((option) => (
                    <OptionCard
                      key={option.value}
                      label={option.label}
                      selected={config.containers.includes(option.value)}
                      onClick={() => toggleArrayValue('containers', option.value)}
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
                <span>Incluir Dockerfile y docker-compose.yml</span>
              </label>
              <label className="toggle-row">
                <input
                  checked={config.include_dev_script}
                  type="checkbox"
                  onChange={(event) => updateField('include_dev_script', event.target.checked)}
                />
                <span>Incluir runner local de desarrollo</span>
              </label>
              <div className="option-group">
                <span>Sistema operativo del equipo</span>
                <div className="option-grid">
                  {options?.targetOs?.map((option) => (
                    <OptionCard
                      key={option.value}
                      label={option.label}
                      selected={config.target_os === option.value}
                      onClick={() => updateField('target_os', option.value)}
                    />
                  ))}
                </div>
              </div>
              {config.project_type !== 'web' && (
                <label className="toggle-row">
                  <input
                    checked={config.include_services}
                    type="checkbox"
                    onChange={(event) => updateField('include_services', event.target.checked)}
                  />
                  <span>Incluir carpeta services con microservicio base</span>
                </label>
              )}
              <button className="generate-button" disabled={status === 'loading'} type="button" onClick={handleGenerate}>
                {status === 'loading' ? <Loader2 className="spin" size={18} /> : <PackageCheck size={18} />}
                Generar proyecto
              </button>
              {result && (
                <div className="command-result">
                  <div className="command-result-header">
                    <span>macOS / Linux — ejecuta desde cualquier directorio</span>
                    <a className="download-btn" href={result.download_url} download>
                      <Download size={15} />
                      Descargar ZIP
                    </a>
                  </div>
                  <code>{result.install_command}</code>
                  <button type="button" onClick={() => navigator.clipboard?.writeText(result.install_command)}>
                    <Clipboard size={15} />
                    Copiar
                  </button>
                  {result.install_command_windows && (
                    <>
                      <span className="command-result-label">Windows PowerShell — ejecuta desde cualquier directorio</span>
                      <code>{result.install_command_windows}</code>
                      <button type="button" onClick={() => navigator.clipboard?.writeText(result.install_command_windows)}>
                        <Clipboard size={15} />
                        Copiar
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
          <button disabled={step === 0} type="button" onClick={() => setStep((current) => current - 1)}>
            <ArrowLeft size={18} />
            Anterior
          </button>
          <button disabled={!canGoNext || step === steps.length - 1} type="button" onClick={() => setStep((current) => current + 1)}>
            Siguiente
            <ArrowRight size={18} />
          </button>
        </div>
        </div>

        <ArchitecturePreview config={config} />
      </section>
    </main>
  );
}

function SelectGroup({ label, options = [], value, onSelect }) {
  return (
    <div className="option-group">
      <span>{label}</span>
      <div className="option-grid">
        {options.map((option) => (
          <OptionCard key={option.value} label={option.label} selected={value === option.value} onClick={() => onSelect(option.value)} />
        ))}
      </div>
    </div>
  );
}
