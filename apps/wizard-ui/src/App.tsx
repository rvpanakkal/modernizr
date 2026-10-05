import React from 'react';
import { useWizardStore } from './store/wizardStore';
import { WizardLayout } from './components/WizardLayout';
import { SourceIngestScreen } from './screens/SourceIngestScreen';
import { TopologyScreen } from './screens/TopologyScreen';
import { TelemetryScreen } from './screens/TelemetryScreen';
import { HitlReviewScreen } from './screens/HitlReviewScreen';
import { SynthesisScreen } from './screens/SynthesisScreen';

export const App: React.FC = () => {
  const { currentStep } = useWizardStore();

  const renderActiveScreen = () => {
    switch (currentStep) {
      case 1:
        return <SourceIngestScreen />;
      case 2:
        return <TopologyScreen />;
      case 3:
        return <TelemetryScreen />;
      case 4:
        return <HitlReviewScreen />;
      case 5:
        return <SynthesisScreen />;
      default:
        return <SourceIngestScreen />;
    }
  };

  return <WizardLayout>{renderActiveScreen()}</WizardLayout>;
};

export default App;
