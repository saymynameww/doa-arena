import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/Layout';
import ExperimentConfigPage from './pages/ExperimentConfig';
import ExperimentRunPage from './pages/ExperimentRun';
import HistoryPage from './pages/History';
import AlgorithmsPage from './pages/Algorithms';
import TemplatesPage from './pages/Templates';
import ComparePage from './pages/Compare';
import SettingsPage from './pages/Settings';

const App: React.FC = () => {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<ExperimentConfigPage />} />
            <Route path="runs/:id" element={<ExperimentRunPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="algorithms" element={<AlgorithmsPage />} />
            <Route path="templates" element={<TemplatesPage />} />
            <Route path="compare" element={<ComparePage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
};

export default App;
