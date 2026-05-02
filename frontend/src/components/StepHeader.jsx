export function StepHeader({ currentStep, totalSteps }) {
  return (
    <div className="step-header">
      <span className="eyebrow">Paso {currentStep} de {totalSteps}</span>
      <div className="progress-track">
        <span style={{ width: `${(currentStep / totalSteps) * 100}%` }} />
      </div>
    </div>
  );
}

