import { ArrowRight, Boxes, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button.jsx';

export function Home() {
  return (
    <main className="home-screen">
      <section className="home-content">
        <span className="eyebrow">Local Docker</span>
        <h1>Test Proj2</h1>
        <p>Proyecto generado desde arquitectura base.</p>
        <div className="home-actions">
          <Link to="/login">
            <Button>
              Ingresar
              <ArrowRight size={18} />
            </Button>
          </Link>
          <a className="text-link" href="http://localhost:8000/docs">
            Ver API
          </a>
        </div>
      </section>
      <section className="capability-grid" aria-label="Capacidades">
        <article>
          <Boxes size={22} />
          <h2>Arquitectura modular</h2>
          <p>Frontend, backend, servicios y configuracion separados desde el primer commit.</p>
        </article>
        <article>
          <ShieldCheck size={22} />
          <h2>Rutas protegidas</h2>
          <p>Base lista para autenticacion y crecimiento de permisos por rol.</p>
        </article>
      </section>
    </main>
  );
}

