import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { GeneratorPage } from './pages/GeneratorPage.jsx';
import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<GeneratorPage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);

