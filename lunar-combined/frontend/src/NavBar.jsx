import { NavLink } from 'react-router-dom'
import './NavBar.css'

export default function NavBar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="brand-icon">📡</span>
        <span className="brand-text">Sa3ed</span>
      </div>
      <div className="navbar-links">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          📊 Dashboard
        </NavLink>
        <NavLink to="/agents" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          🤖 Agents IA
        </NavLink>
        <NavLink to="/axis2-chat" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          💬 Axis 2 Chat
        </NavLink>
        <NavLink to="/pillar3-test" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          🧪 Pillar 3 Test
        </NavLink>
        <NavLink to="/seo-agent" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          🔍 SEO Agent
        </NavLink>
      </div>
    </nav>
  )
}
