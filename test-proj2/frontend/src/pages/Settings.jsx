import { Card } from '../components/ui/Card.jsx';

export function Settings() {
  return (
    <div className="page-stack">
      <div>
        <span className="eyebrow">Configuracion</span>
        <h2>Settings</h2>
      </div>
      <Card>
        <dl className="settings-list">
          <div>
            <dt>Cloud</dt>
            <dd>Local Docker</dd>
          </div>
          <div>
            <dt>Autenticacion</dt>
            <dd>firebase</dd>
          </div>
          <div>
            <dt>Contenedores</dt>
            <dd>frontend, backend, database</dd>
          </div>
        </dl>
      </Card>
    </div>
  );
}

