import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import AgentAnalysis from './AgentAnalysis.jsx'
import NavBar from './NavBar.jsx'
import Axis2ChatTab from './Axis2ChatTab.jsx'
import SeoTab from './SeoTab.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <NavBar />
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/agents" element={<AgentAnalysis />} />
        <Route path="/axis2-chat" element={<Axis2ChatTab />} />
        <Route path="/seo-agent" element={<SeoTab />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
