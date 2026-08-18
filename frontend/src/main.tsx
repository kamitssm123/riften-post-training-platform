import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { TooltipProvider } from './components/ui/Tooltip.tsx'

// Apply saved theme before first paint to avoid flash
const stored = localStorage.getItem('riften-theme')
if (stored === 'dark' || stored === 'light' || stored === 'system') {
  const resolved =
    stored === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : stored
  document.documentElement.setAttribute('data-theme', resolved)
} else {
  document.documentElement.setAttribute('data-theme', 'dark')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider>
      <App />
    </TooltipProvider>
  </StrictMode>,
)
