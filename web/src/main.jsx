import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { ConfirmProvider } from './confirm.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <ConfirmProvider>
    <App />
  </ConfirmProvider>,
)
